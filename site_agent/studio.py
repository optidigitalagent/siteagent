"""Codex-owned creative build plane for SiteAgent.

The control plane prepares bounded facts and validates outputs.  It never selects
a page composition for this path; Codex writes runnable static concepts and the
selected full build inside a job-local studio workspace.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable

from site_agent.critic import TechnicalInspector
from site_agent.config import settings
from site_agent.models import ResearchBrief, SiteSpec, StrategyBrief
from site_agent.skill_lock import directory_checksum


STUDIO_SKILLS = (
    "siteagent-web-studio",
    "creative-director",
    "concept-prototyping",
    "storytelling",
    "conversion-copy",
    "responsive-review",
    "design-critic",
    "anti-template-review",
    "accessibility-review",
    "frontend-design",
    "ui-ux-pro-max",
)
CONCEPTS = ("concept_a", "concept_b", "concept_c")


class StudioError(RuntimeError):
    """A retryable creative-plane failure; callers must never silently use Jinja."""


@dataclass(frozen=True)
class StudioResult:
    index_path: Path
    selected_concept: str
    studio_dir: Path


class CodexStudioRunner:
    def __init__(
        self,
        *,
        project_root: Path | None = None,
        command_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        inspector: TechnicalInspector | None = None,
    ) -> None:
        self.project_root = (project_root or Path.cwd()).resolve()
        self.command_runner = command_runner
        self.inspector = inspector or TechnicalInspector()
        self.task_timeouts = {
            "concept_generation": settings.codex_concept_generation_timeout_seconds,
            "concept_selection": settings.codex_concept_selection_timeout_seconds,
            "full_creative_build": settings.codex_full_creative_build_timeout_seconds,
            "art_director": settings.codex_art_director_timeout_seconds,
            "creative_fixer": settings.codex_creative_fixer_timeout_seconds,
        }

    def build(
        self,
        *,
        run_dir: Path,
        site_dir: Path,
        job_id: str,
        research: ResearchBrief,
        strategy: StrategyBrief,
        spec: SiteSpec,
        evidence: Any,
        checkpoints: Callable[..., None],
    ) -> StudioResult:
        studio = run_dir / "studio"
        self._prepare_input(studio, job_id, research, strategy, spec, evidence)
        checkpoints("studio_input_prepared")

        missing = [name for name in CONCEPTS if not (studio / "concepts" / name / "index.html").is_file()]
        if missing:
            self._run_task(studio, "concept_generation", self._concept_prompt(run_dir, missing))
        self._require_concepts(studio)
        checkpoints(*(f"{name}_completed" for name in CONCEPTS))

        self._capture_concept_screenshots(studio)
        checkpoints("concept_screenshots_completed")
        comparison_path = studio / "concept_reviews" / "comparison.json"
        comparison = self._read_json(comparison_path) if comparison_path.is_file() else self._compare_concepts(studio)
        if not comparison_path.is_file():
            self._write_json(comparison_path, comparison)
        if not comparison["materially_different"]:
            raise StudioError("Concept similarity gate blocked selection: " + "; ".join(comparison["reasons"]))
        checkpoints("concept_comparison_completed")

        selected_path = studio / "concept_reviews" / "selected_concept.json"
        selected_source = studio / "selected" / "source" / "index.html"
        staging_source = studio / "selected" / "staging"
        if not self._selection_is_valid(studio):
            self._run_task(
                studio,
                "concept_selection",
                self._selection_prompt(run_dir),
                images=[studio / "concept_reviews" / name / viewport for name in CONCEPTS for viewport in ("desktop.png", "tablet.png", "mobile.png")],
            )
        selected = self._read_json(selected_path)
        chosen = self._selected_id(selected)
        if not self._selection_is_valid(studio):
            self._mark_task(studio, "concept_selection", "retryable", "selection artifacts did not satisfy the evidence contract")
            raise StudioError("Creative Director selection is incomplete or lacks required screenshot evidence.")
        self._mark_task(studio, "concept_selection", "completed")
        checkpoints("concept_selected", "selected_concept_improvements_recorded")
        if not self._task_completed(studio, "full_creative_build") or not self._static_site_is_valid(staging_source):
            self._run_task(studio, "full_creative_build", self._full_build_prompt(run_dir, chosen))
        source_workspace = selected_source.parent
        use_fixed_source = self._task_completed(studio, "creative_fixer") and self._static_site_is_valid(source_workspace)
        promotion_source = source_workspace if use_fixed_source else staging_source
        self._require_static_site(promotion_source)
        self._validate_static_site(promotion_source)
        initial_dir = studio / "selected" / "initial_validation"
        gate, _ = self.inspector.inspect(promotion_source / "index.html", initial_dir)
        if not gate.passed:
            self._mark_task(studio, "full_creative_build", "retryable", "initial technical validation failed")
            raise StudioError("Full creative build failed initial technical validation; preserved staging is retryable.")
        if not use_fixed_source:
            self._atomic_promote(staging_source, selected_source.parent)
        self._mark_task(studio, "full_creative_build", "completed")
        checkpoints("full_creative_build_completed")

        final_dir = studio / "final_reviews"
        if not (final_dir / "desktop.png").is_file():
            self.inspector.inspect(selected_source, final_dir)
        self._require_screenshots(final_dir, tablet=True)
        art_report = studio / "art_director_report.json"
        if not self._art_director_is_valid(art_report):
            self._run_task(
                studio,
                "art_director",
                self._art_director_prompt(run_dir),
                images=[final_dir / name for name in ("desktop.png", "tablet.png", "mobile.png")],
            )
        art = self._read_json(art_report)
        if not self._art_director_is_valid(art_report):
            raise StudioError("Art Director report lacks findings or approval decision.")
        self._mark_task(studio, "art_director", "completed")
        checkpoints("full_build_visuals_completed")
        checkpoints("art_director_review_completed")
        self._write_provenance(studio, chosen)
        self._atomic_promote(selected_source.parent, site_dir)
        return StudioResult(index_path=site_dir / "index.html", selected_concept=chosen, studio_dir=studio)

    def revise(
        self, *, run_dir: Path, site_dir: Path, critique_path: Path, checkpoints: Callable[..., None], iteration: int
    ) -> None:
        studio = run_dir / "studio"
        source_index = studio / "selected" / "source" / "index.html"
        before_hash = hashlib.sha256(source_index.read_bytes()).hexdigest() if source_index.is_file() else ""
        self._run_task(
            studio,
            "creative_fixer",
            "Use $siteagent-web-studio to materially improve the selected full build after the "
            f"screenshot-led report at {self._relative(critique_path)}. Preserve facts, "
            "but change composition, typography, media, copy or interaction when needed; do not make a "
            "palette-only patch. You must write actual changed files under studio/selected/source/: remove any customer-facing "
            "internal validation language and resolve every critical/high screenshot finding. Update studio/fixer_history/"
            f"iteration_{iteration}.json with before/after evidence."
        )
        self._require_static_site(studio / "selected" / "source")
        after_hash = hashlib.sha256(source_index.read_bytes()).hexdigest()
        if before_hash and before_hash == after_hash:
            self._mark_task(studio, "creative_fixer", "retryable", "fixer returned without changing selected source")
            raise StudioError("Creative fixer returned without changing the selected source; preserved state is retryable.")
        self.inspector.inspect(studio / "selected" / "source" / "index.html", studio / "final_reviews")
        self._atomic_promote(studio / "selected" / "source", site_dir)
        self._mark_task(studio, "creative_fixer", "completed")
        checkpoints(f"creative_fixer_iteration_{iteration}_completed")

    def review_art_director(self, *, run_dir: Path, checkpoints: Callable[..., None]) -> dict[str, Any]:
        """Re-render and independently review a fixer result without rerunning concepts/build."""
        studio = run_dir / "studio"
        final_dir = studio / "final_reviews"
        self.inspector.inspect(studio / "selected" / "source" / "index.html", final_dir)
        self._run_task(
            studio,
            "art_director",
            self._art_director_prompt(run_dir),
            images=[final_dir / name for name in ("desktop.png", "tablet.png", "mobile.png")],
        )
        report_path = studio / "art_director_report.json"
        if not self._art_director_is_valid(report_path):
            raise StudioError("Art Director report lacks required screenshot evidence after fixer.")
        self._mark_task(studio, "art_director", "completed")
        checkpoints("full_build_visuals_completed", "art_director_review_completed")
        return self._read_json(report_path)

    def _prepare_input(
        self, studio: Path, job_id: str, research: ResearchBrief, strategy: StrategyBrief, spec: SiteSpec, evidence: Any
    ) -> None:
        input_dir = studio / "input"
        for folder in (input_dir, studio / "concepts", studio / "concept_reviews", studio / "selected"):
            folder.mkdir(parents=True, exist_ok=True)
        prohibited = list(dict.fromkeys(research.forbidden_claims + ["Do not invent prices, reviews, staff, guarantees, results, addresses, or contact details."]))
        media = [item.model_dump() for item in (spec.gallery_assets or research.best_media)]
        evidence_payload = evidence.model_dump() if hasattr(evidence, "model_dump") else dict(evidence or {})
        self._write_json(input_dir / "evidence.json", {"assessment": evidence_payload, "verified_facts": [item.model_dump() for item in research.verified_facts]})
        self._write_json(input_dir / "business_brief.json", {"job_id": job_id, "instagram_url": research.instagram_url, "research": research.model_dump(), "strategy": strategy.model_dump(), "site_spec": spec.model_dump()})
        self._write_json(input_dir / "media_manifest.json", {"media": media, "note": "Only verified supplied media may be used; classify missing dimensions/quality as unknown."})
        self._write_json(input_dir / "prohibited_claims.json", {"prohibited_claims": prohibited, "missing_information": research.unknowns})
        self._write_json(input_dir / "previous_site_constraints.json", {"recent_fingerprints": [], "avoid": ["category templates", "generic narrow-column landing page", "palette-only concept variants"]})
        self._write_json(input_dir / "skill_guidance.json", {"source": ".agents/skills", "skills": self._skill_snapshot()})

    def _skill_snapshot(self) -> list[dict[str, str]]:
        root = self.project_root / ".agents" / "skills"
        result: list[dict[str, str]] = []
        for name in STUDIO_SKILLS:
            path = root / name
            skill = path / "SKILL.md"
            if not skill.is_file():
                raise StudioError(f"Missing repository-owned studio skill: {name}")
            result.append({"name": name, "path": str(skill.relative_to(self.project_root)), "checksum": directory_checksum(path)})
        return result

    def _concept_prompt(self, run_dir: Path, missing: list[str]) -> str:
        return (
            "Use $siteagent-web-studio. This is a SiteAgent creative production task. Read only the "
            f"bounded input package in {self._relative(run_dir / 'studio' / 'input')}. Create the missing "
            f"runnable HTML concepts {', '.join(missing)} under {self._relative(run_dir / 'studio' / 'concepts')}. "
            "Use the project-local guidance referenced by skill_guidance.json. Do not use a category template, "
            "Jinja, secrets, Telegram, Cloudflare or external publishing. Each concept must have a distinct "
            "central idea, composition, hero, density, media strategy, typography, CTA and signature element. "
            "Write a concise concept.md beside each index.html."
        )

    def _selection_prompt(self, run_dir: Path) -> str:
        return (
            "Use $siteagent-web-studio and act as Creative Director. Read the bounded studio input, all three "
            f"prototype directories and screenshot artifacts in {self._relative(run_dir / 'studio' / 'concept_reviews')}. "
            "Select only after visual comparison. Update comparison.json with a separate review for every concept: "
            "strengths, weaknesses, technical_risks, visual_risks, business_risks, desktop_observations, "
            "mobile_observations and anti_template_observations, while retaining the structural comparison. Write "
            "selected_concept.json with selected concept, reasons, rejected concepts, concrete selected weaknesses, "
            "mandatory improvements, elements_to_preserve, desktop/mobile screenshot references and the SHA-256 of "
            "the selected concept index.html as source_concept_checksum. Do not edit a full build in this selection step."
        )

    def _full_build_prompt(self, run_dir: Path, chosen: str) -> str:
        return (
            "Use $siteagent-web-studio to expand the selected concept without changing its central creative idea. "
            f"Read {self._relative(run_dir / 'studio' / 'concept_reviews' / 'selected_concept.json')} and the selected "
            f"prototype at {self._relative(run_dir / 'studio' / 'concepts' / chosen)}. Write a complete static responsive "
            f"HTML/CSS/JS site to the staging workspace {self._relative(run_dir / 'studio' / 'selected' / 'staging')}. Preserve its signature "
            "element and composition language. Use verified facts only; do not invoke Jinja, Cloudflare or Telegram."
        )

    def _art_director_prompt(self, run_dir: Path) -> str:
        return (
            "Use $siteagent-web-studio and act as an independent Art Director. Inspect the desktop, tablet and "
            f"mobile screenshots in {self._relative(run_dir / 'studio' / 'final_reviews')} against the bounded "
            "business input and selected concept. Write studio/art_director_report.json with approved (boolean), score, "
            "summary, unresolved_issues and findings. Every finding needs severity, screenshot, screenshot_region, selector, "
            "description, reason and desired_outcome. Score and approval must cite screenshot evidence. Do not change the build."
        )

    def _run_task(self, studio: Path, task: str, prompt: str, *, images: list[Path] | None = None) -> None:
        self._mark_task(studio, task, "running")
        try:
            self._invoke_codex(prompt, task=task, images=images)
        except StudioError as exc:
            self._mark_task(studio, task, "retryable", str(exc))
            raise

    def _invoke_codex(self, prompt: str, *, task: str, images: list[Path] | None = None) -> None:
        codex_command = shutil.which(os.getenv("CODEX_COMMAND", "codex"))
        if not codex_command:
            raise StudioError("Codex CLI command not found. Install Codex or set CODEX_COMMAND.")
        command = [codex_command, "exec", "-C", str(self.project_root), "--sandbox", "workspace-write", "-"]
        for image in images or []:
            if image.is_file():
                command[2:2] = ["--image", str(image)]
        model = os.getenv("CODEX_MODEL", "").strip()
        if model:
            command[2:2] = ["-m", model]
        try:
            completed = self.command_runner(command, input=prompt, text=True, encoding="utf-8", capture_output=True, check=False, timeout=self.task_timeouts[task])
        except subprocess.TimeoutExpired as exc:
            raise StudioError(f"Codex Studio {task} timed out after {self.task_timeouts[task]} seconds; preserved state is retryable.") from exc
        except (OSError, subprocess.SubprocessError) as exc:
            raise StudioError(f"Codex Studio invocation failed before generation: {exc}") from exc
        if completed.returncode != 0:
            output = (completed.stderr or completed.stdout or "").strip()
            raise StudioError(f"Codex Studio generation failed: {output[:2000]}")

    def _task_state(self, studio: Path) -> dict[str, Any]:
        path = studio / "task_state.json"
        return self._read_json(path) if path.is_file() else {}

    def _task_completed(self, studio: Path, task: str) -> bool:
        return self._task_state(studio).get(task, {}).get("status") == "completed"

    def _mark_task(self, studio: Path, task: str, status: str, error: str | None = None) -> None:
        state = self._task_state(studio)
        record: dict[str, str] = {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
        if error:
            record["error"] = error
        state[task] = record
        self._write_json(studio / "task_state.json", state)

    def _capture_concept_screenshots(self, studio: Path) -> None:
        for name in CONCEPTS:
            artifacts = studio / "concept_reviews" / name
            if not (artifacts / "desktop.png").is_file() or not (artifacts / "mobile.png").is_file():
                self.inspector.inspect(studio / "concepts" / name / "index.html", artifacts)
            self._require_screenshots(artifacts, tablet=False)

    def _compare_concepts(self, studio: Path) -> dict[str, Any]:
        fingerprints = {name: self._concept_fingerprint(studio / "concepts" / name / "index.html") for name in CONCEPTS}
        pairs: dict[str, dict[str, Any]] = {}
        reasons: list[str] = []
        for index, left in enumerate(CONCEPTS):
            for right in CONCEPTS[index + 1:]:
                same = fingerprints[left] == fingerprints[right]
                pairs[f"{left}:{right}"] = {"same_structure": same, "left": fingerprints[left], "right": fingerprints[right]}
                if same:
                    reasons.append(f"{left} and {right} share the same structural fingerprint; palette/text-only variants are insufficient.")
        return {"fingerprints": fingerprints, "pairs": pairs, "materially_different": not reasons, "reasons": reasons}

    def _concept_fingerprint(self, path: Path) -> str:
        class Structure(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.parts: list[str] = []

            def handle_starttag(self, tag: str, attrs) -> None:
                # Attribute names are structural; values contain text, palette and
                # arbitrary class tokens, none of which can prove a new concept.
                self.parts.append(tag + "[" + ",".join(sorted(name for name, _ in attrs)) + "]")

            def handle_endtag(self, tag: str) -> None:
                self.parts.append("/" + tag)

        parser = Structure()
        parser.feed(path.read_text(encoding="utf-8"))
        return hashlib.sha256("|".join(parser.parts).encode("utf-8")).hexdigest()

    def _atomic_promote(self, source: Path, destination: Path) -> None:
        self._require_static_site(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="siteagent-studio-promotion-", dir=destination.parent) as temp:
            staged = Path(temp) / "site"
            shutil.copytree(source, staged)
            if destination.exists():
                backup = destination.with_name(destination.name + ".last-valid")
                if backup.exists():
                    shutil.rmtree(backup)
                destination.replace(backup)
                try:
                    shutil.move(str(staged), str(destination))
                except Exception:
                    backup.replace(destination)
                    raise
                shutil.rmtree(backup)
            else:
                shutil.move(str(staged), str(destination))

    def _write_provenance(self, studio: Path, selected: str) -> None:
        self._write_json(studio / "build_provenance.json", {"schema_version": 1, "selected_concept": selected, "skill_versions": self._skill_snapshot(), "codex_command": "codex exec", "created_at": datetime.now(timezone.utc).isoformat()})

    @staticmethod
    def _require_static_site(folder: Path) -> None:
        index = folder / "index.html"
        if not index.is_file() or index.stat().st_size < 128:
            raise StudioError(f"Expected complete static site at {index}")

    def _static_site_is_valid(self, folder: Path) -> bool:
        try:
            self._require_static_site(folder)
            self._validate_static_site(folder)
            return True
        except StudioError:
            return False

    @staticmethod
    def _validate_static_site(folder: Path) -> None:
        """Reject local-preview leakage and missing local HTML assets before promotion."""
        index = folder / "index.html"
        content = index.read_text(encoding="utf-8")
        lowered = content.lower()
        if "file://" in lowered or "localhost" in lowered or "127.0.0.1" in lowered:
            raise StudioError("Static studio output contains a local preview URL.")
        if any(token in content for token in ("C:\\\\", "C:/Users/", "\\\\Users\\\\")):
            raise StudioError("Static studio output contains an absolute Windows path.")
        import re

        for raw in re.findall(r"(?:src|href)=[\"']([^\"']+)[\"']", content, flags=re.IGNORECASE):
            value = raw.strip()
            if not value or value.startswith(("#", "mailto:", "tel:", "https://", "http://", "data:")):
                continue
            target = (folder / value.split("?", 1)[0].split("#", 1)[0]).resolve()
            try:
                target.relative_to(folder.resolve())
            except ValueError as exc:
                raise StudioError(f"Static studio output escapes its asset root: {value}") from exc
            if not target.exists():
                raise StudioError(f"Static studio output references a missing local asset: {value}")

    @staticmethod
    def _selected_id(selected: dict[str, Any]) -> str:
        value = selected.get("selected_concept")
        if isinstance(value, dict):
            value = value.get("id")
        return value if value in CONCEPTS else ""

    def _selection_is_valid(self, studio: Path) -> bool:
        path = studio / "concept_reviews" / "selected_concept.json"
        comparison_path = studio / "concept_reviews" / "comparison.json"
        if not path.is_file() or not comparison_path.is_file():
            return False
        try:
            selected = self._read_json(path)
            comparison = self._read_json(comparison_path)
        except StudioError:
            return False
        chosen = self._selected_id(selected)
        screenshot_evidence = selected.get("screenshot_evidence") or selected.get("screenshot_references")
        if not chosen or not isinstance(selected.get("reasons"), list) or not screenshot_evidence:
            return False
        selected_weaknesses = selected.get("selected_weaknesses") or selected.get("concrete_selected_weaknesses")
        required = ("mandatory_improvements", "elements_to_preserve", "source_concept_checksum")
        if not selected_weaknesses or any(not selected.get(field) for field in required):
            return False
        source = studio / "concepts" / chosen / "index.html"
        checksum = hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else ""
        if selected.get("source_concept_checksum") != checksum:
            return False
        reviews = comparison.get("concept_reviews") or comparison.get("reviews")
        if not isinstance(reviews, dict) or any(name not in reviews for name in CONCEPTS):
            return False
        required_review = ("strengths", "weaknesses", "technical_risks", "visual_risks", "business_risks", "desktop_observations", "mobile_observations", "anti_template_observations")
        return all(isinstance(reviews[name], dict) and all(field in reviews[name] for field in required_review) for name in CONCEPTS)

    @staticmethod
    def _art_director_is_valid(path: Path) -> bool:
        if not path.is_file():
            return False
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if not isinstance(report, dict) or not isinstance(report.get("approved"), bool) or not isinstance(report.get("score"), int) or not isinstance(report.get("findings"), list):
            return False
        fields = {"severity", "screenshot", "screenshot_region", "selector", "description", "reason", "desired_outcome"}
        return all(isinstance(item, dict) and fields <= set(item) for item in report["findings"])

    @staticmethod
    def _require_concepts(studio: Path) -> None:
        for name in CONCEPTS:
            CodexStudioRunner._require_static_site(studio / "concepts" / name)
            if not (studio / "concepts" / name / "concept.md").is_file():
                raise StudioError(f"Concept rationale is missing for {name}")

    @staticmethod
    def _require_screenshots(folder: Path, *, tablet: bool) -> None:
        names = ["desktop.png", "mobile.png"] + (["tablet.png"] if tablet else [])
        absent = [name for name in names if not (folder / name).is_file()]
        if absent:
            raise StudioError("Required screenshots missing: " + ", ".join(absent))

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise StudioError(f"Missing or invalid required studio artifact: {path}") from exc
        if not isinstance(value, dict):
            raise StudioError(f"Studio artifact must be an object: {path}")
        return value

    def _relative(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.project_root)).replace("\\", "/")
        except ValueError:
            return str(path)
