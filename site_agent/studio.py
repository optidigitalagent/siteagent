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
            self._invoke_codex(self._concept_prompt(run_dir, missing))
        self._require_concepts(studio)
        checkpoints(*(f"{name}_completed" for name in CONCEPTS))

        self._capture_concept_screenshots(studio)
        checkpoints("concept_screenshots_completed")
        comparison = self._compare_concepts(studio)
        self._write_json(studio / "concept_reviews" / "comparison.json", comparison)
        if not comparison["materially_different"]:
            raise StudioError("Concept similarity gate blocked selection: " + "; ".join(comparison["reasons"]))
        checkpoints("concept_comparison_completed")

        selected_path = studio / "concept_reviews" / "selected_concept.json"
        selected_source = studio / "selected" / "source" / "index.html"
        if not selected_path.is_file():
            self._invoke_codex(
                self._selection_prompt(run_dir),
                images=[studio / "concept_reviews" / name / viewport for name in CONCEPTS for viewport in ("desktop.png", "mobile.png")],
            )
        selected = self._read_json(selected_path)
        chosen = selected.get("selected_concept") if isinstance(selected, dict) else None
        if chosen not in CONCEPTS:
            raise StudioError("Creative Director did not record a valid selected_concept.")
        if not isinstance(selected.get("reasons"), list) or not selected.get("screenshot_evidence"):
            raise StudioError("Creative Director selection lacks screenshot evidence or reasons.")
        if not selected_source.is_file():
            self._invoke_codex(self._full_build_prompt(run_dir, chosen))
        self._require_static_site(selected_source.parent)
        checkpoints("concept_selected", "selected_concept_improvements_recorded", "full_creative_build_completed")

        final_dir = studio / "full_build_visuals"
        if not (final_dir / "desktop.png").is_file():
            gate, observations = self.inspector.inspect(selected_source, final_dir)
            self._write_json(final_dir / "technical_gate.json", gate)
            self._write_json(final_dir / "observations.json", observations)
        self._require_screenshots(final_dir, tablet=True)
        art_report = studio / "art_director_report.json"
        if not art_report.is_file():
            self._invoke_codex(
                self._art_director_prompt(run_dir),
                images=[final_dir / name for name in ("desktop.png", "tablet.png", "mobile.png")],
            )
        art = self._read_json(art_report)
        if not isinstance(art.get("findings"), list) or "approved" not in art:
            raise StudioError("Art Director report lacks findings or approval decision.")
        checkpoints("full_build_visuals_completed")
        checkpoints("art_director_review_completed")
        self._write_provenance(studio, chosen)
        self._atomic_promote(selected_source.parent, site_dir)
        return StudioResult(index_path=site_dir / "index.html", selected_concept=chosen, studio_dir=studio)

    def revise(
        self, *, run_dir: Path, site_dir: Path, critique_path: Path, checkpoints: Callable[..., None], iteration: int
    ) -> None:
        studio = run_dir / "studio"
        self._invoke_codex(
            "Use $siteagent-web-studio to materially improve the selected full build after the "
            f"screenshot-led report at {critique_path.relative_to(self.project_root)}. Preserve facts, "
            "but change composition, typography, media, copy or interaction when needed; do not make a "
            "palette-only patch. Update studio/selected/source/ and write studio/fixer_history/"
            f"iteration_{iteration}.json with before/after evidence."
        )
        self._require_static_site(studio / "selected" / "source")
        self.inspector.inspect(studio / "selected" / "source" / "index.html", studio / "full_build_visuals")
        self._atomic_promote(studio / "selected" / "source", site_dir)
        checkpoints(f"creative_fixer_iteration_{iteration}_completed")

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
            "Select only after visual comparison. Write selected_concept.json with selected_concept, reasons, "
            "rejected_concepts, screenshot_evidence, mandatory_improvements and risks. Do not edit the selected "
            "build in this selection step."
        )

    def _full_build_prompt(self, run_dir: Path, chosen: str) -> str:
        return (
            "Use $siteagent-web-studio to expand the selected concept without changing its central creative idea. "
            f"Read {self._relative(run_dir / 'studio' / 'concept_reviews' / 'selected_concept.json')} and the selected "
            f"prototype at {self._relative(run_dir / 'studio' / 'concepts' / chosen)}. Write a complete static responsive "
            f"HTML/CSS/JS site to {self._relative(run_dir / 'studio' / 'selected' / 'source')}. Preserve its signature "
            "element and composition language. Use verified facts only; do not invoke Jinja, Cloudflare or Telegram."
        )

    def _art_director_prompt(self, run_dir: Path) -> str:
        return (
            "Use $siteagent-web-studio and act as an independent Art Director. Inspect the desktop, tablet and "
            f"mobile screenshots in {self._relative(run_dir / 'studio' / 'full_build_visuals')} against the bounded "
            "business input and selected concept. Write studio/art_director_report.json with approved (boolean), "
            "summary and findings. Every finding needs screenshot_region, selector, reason, severity and desired_outcome. "
            "Do not invent a score or change the build in this review."
        )

    def _invoke_codex(self, prompt: str, *, images: list[Path] | None = None) -> None:
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
            completed = self.command_runner(command, input=prompt, text=True, encoding="utf-8", capture_output=True, check=False, timeout=900)
        except (OSError, subprocess.SubprocessError) as exc:
            raise StudioError(f"Codex Studio invocation failed before generation: {exc}") from exc
        if completed.returncode != 0:
            output = (completed.stderr or completed.stdout or "").strip()
            raise StudioError(f"Codex Studio generation failed: {output[:2000]}")

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
