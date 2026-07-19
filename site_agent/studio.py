"""Codex-owned creative build plane for SiteAgent.

The control plane prepares bounded facts and validates outputs.  It never selects
a page composition for this path; Codex writes runnable static concepts and the
selected full build inside a job-local studio workspace.
"""
from __future__ import annotations

import hashlib
import json
import os
import signal
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
import re
from pathlib import Path
from typing import Any, Callable

from site_agent.commercial_usefulness import (
    commercial_usefulness_report,
    language_fit_report,
    semantic_repetition_report,
)
from site_agent.critic import TechnicalInspector
from site_agent.config import settings
from site_agent.design_quality import EvidenceAssessment, PageScope, assess_studio_readiness
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


CALIBRATION_ONLY_TEXT = (
    "human calibration required",
    "fixture-only",
    "fixture/stock",
    "controlled fixture stock",
    "calibration-only",
)
UNVERIFIED_PRODUCTION_MEDIA_KINDS = frozenset({"fixture_stock", "stock", "unknown"})


class _RenderedMediaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(); self.urls: list[str] = []
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        for name in ("src", "poster", "data-src"):
            if values.get(name): self.urls.append(values[name] or "")
        for value in (values.get("srcset"), values.get("style")):
            if value:
                self.urls.extend(re.findall(r"https?://[^\s,'\")]+", value))


def _rendered_media_urls(html: str) -> set[str]:
    parser = _RenderedMediaParser(); parser.feed(html)
    parser.urls.extend(re.findall(r"url\(\s*['\"]?(https?://[^\s'\")]+)", html))
    return {url for url in parser.urls if url.startswith("http")}


def _media_provenance_report(*, studio_dir: Path, site_dir: Path) -> dict[str, Any]:
    """Describe media actually rendered by one exact static-site revision.

    The report deliberately follows final HTML usage rather than trusting a
    concept's broader media manifest: unused stock cannot block a build, while
    a rendered fixture can never be hidden by removing its visible disclaimer.
    """
    source = site_dir / "index.html"
    manifest_path = studio_dir / "input" / "media_manifest.json"
    if not source.is_file() or not manifest_path.is_file():
        raise StudioError("Media provenance requires final HTML and media_manifest.json.")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise StudioError("Media provenance manifest is unreadable.") from exc

    rendered_html = unescape(source.read_text(encoding="utf-8"))
    assets: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    rendered_urls = _rendered_media_urls(rendered_html)
    manifest_urls = {str(item.get("url", "")) for item in manifest.get("media", [])}
    for item in manifest.get("media", []):
        record = dict(item)
        url = str(record.get("url", ""))
        record["rendered_uses"] = rendered_html.count(url) if url else 0
        record["status"] = "used" if record["rendered_uses"] else "not_used"
        record["portfolio_safe"] = (
            record.get("source_kind") == "business"
            and record.get("user_authorized") is True
            and record.get("allowed_for_public_site") is True
            and str(record.get("url", "")).startswith("https://res.cloudinary.com/")
        )
        if record["rendered_uses"] and not record["portfolio_safe"]:
            blocked.append({
                "asset_id": record.get("asset_id") or url,
                "source_kind": record.get("source_kind", "unknown"),
                "rendered_uses": record["rendered_uses"],
            })
        assets.append(record)
    for url in sorted(rendered_urls - manifest_urls):
        blocked.append({"asset_id": url, "source_kind": "unlisted_external", "rendered_uses": 1})
    return {
        "schema_version": 2,
        "final_html_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "final_html": str(source),
        "fixture_only": bool(assets) and all(item.get("source_kind") == "fixture_stock" for item in assets),
        "production_media_blocked": bool(blocked),
        "production_promotion_allowed": not blocked,
        "blocked_selected_media": blocked,
        "used_asset_count": sum(item["rendered_uses"] for item in assets),
        "rendered_media_urls": sorted(rendered_urls),
        "assets": assets,
        "rationale": "Only authorised business media delivered from Cloudinary may be promoted; fixture, stock, scraped, or unverified media is never production-safe.",
    }


def assert_production_promotion_allowed(*, studio_dir: Path, site_dir: Path) -> None:
    """Fail closed before a Studio artifact may be promoted to production."""
    report_path = studio_dir / "media_provenance_report.json"
    if not report_path.is_file():
        raise StudioError("Production promotion blocked: media provenance report is missing.")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise StudioError("Production promotion blocked: media provenance report is unreadable.") from exc

    current = _media_provenance_report(studio_dir=studio_dir, site_dir=site_dir)
    if report.get("final_html_sha256") != current["final_html_sha256"]:
        raise StudioError("Production promotion blocked: media provenance does not match final HTML.")
    if current["production_media_blocked"]:
        labels = ", ".join(
            f"{item['asset_id']} ({item['source_kind']})" for item in current["blocked_selected_media"]
        )
        raise StudioError("Production promotion blocked: selected fixture/stock/unverified media: " + labels)

    content = (site_dir / "index.html").read_text(encoding="utf-8").lower()
    leaked = [text for text in CALIBRATION_ONLY_TEXT if text in content]
    if leaked:
        raise StudioError(
            "Production promotion blocked: calibration-only disclosure leaked into static site: "
            + ", ".join(leaked)
        )


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
        implementation_package: dict[str, Any] | None = None,
        checkpoints: Callable[..., None],
    ) -> StudioResult:
        studio = run_dir / "studio"
        # The control plane may deliberately choose the more restrictive scope
        # from the strategist.  Never recompute that decision from media count.
        readiness = evidence if isinstance(evidence, EvidenceAssessment) else assess_studio_readiness(research)
        if readiness.page_scope is PageScope.BLOCKED:
            raise StudioError("Studio readiness blocked generation: " + "; ".join(readiness.reasons))
        self._prepare_input(studio, job_id, research, strategy, spec, readiness, implementation_package)
        checkpoints("studio_input_prepared")

        concept_names = CONCEPTS if readiness.page_scope is PageScope.FULL else ("concept_a",)
        self._write_json(studio / "input" / "concept_contract.json", {
            "required_concepts": list(concept_names),
            "scope": readiness.page_scope.value,
            "reason": "Full sites require comparison; an intentional micro-site must not be padded into three variants.",
        })
        missing = [name for name in concept_names if not (studio / "concepts" / name / "index.html").is_file()]
        if missing:
            self._run_task(studio, "concept_generation", self._concept_prompt(run_dir, missing))
        self._require_concepts(studio)
        self._mark_task(studio, "concept_generation", "completed")
        checkpoints(*(f"{name}_completed" for name in concept_names))

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
                images=[studio / "concept_reviews" / name / viewport for name in concept_names for viewport in ("desktop.png", "tablet.png", "mobile.png")],
            )
        selected = self._read_json(selected_path)
        chosen = self._selected_id(selected, studio)
        if not self._selection_is_valid(studio):
            self._mark_task(studio, "concept_selection", "retryable", "selection artifacts did not satisfy the evidence contract")
            raise StudioError("Creative Director selection is incomplete or lacks required screenshot evidence.")
        self._mark_task(studio, "concept_selection", "completed")
        checkpoints("concept_selected", "selected_concept_improvements_recorded")
        # A browser or validator failure after Codex has written a complete
        # staging build is recoverable. Revalidate that exact source first;
        # do not discard it or spend another full-generation budget unless it
        # is missing or structurally invalid.
        # A technically rejected staging build is not reusable as-is. Its
        # files remain as evidence, but the retryable task must receive a
        # material full-build revision rather than looping on the same DOM.
        build_state = self._task_state(studio).get("full_creative_build", {})
        retryable_staging_can_revalidate = self._retryable_staging_can_revalidate(
            studio, staging_source, build_state
        )
        source_workspace = selected_source.parent
        canonical_source_is_valid = self._static_site_is_valid(source_workspace)
        if not canonical_source_is_valid and (
            not self._static_site_is_valid(staging_source) or
            (build_state.get("status") == "retryable" and not retryable_staging_can_revalidate)
        ):
            self._run_task(studio, "full_creative_build", self._full_build_prompt(run_dir, chosen, readiness))
        # A source workspace is the last atomically promoted, reviewable build.
        # Preserve it during retry recovery instead of replacing it with stale
        # staging merely because a prior fixer command returned no-op.
        use_fixed_source = self._static_site_is_valid(source_workspace)
        promotion_source = source_workspace if use_fixed_source else staging_source
        self._require_static_site(promotion_source)
        self._validate_static_site(promotion_source)
        self._validate_authorised_media_rendering(studio, promotion_source)
        self._validate_scope_compliance(studio, promotion_source, readiness)
        initial_dir = studio / "selected" / "initial_validation"
        gate, _ = self.inspector.inspect(promotion_source / "index.html", initial_dir)
        rejected_report = studio / "art_director_report.json"
        reviewed_rejection_can_reenter_fixer = (
            use_fixed_source
            and self._art_director_is_valid(rejected_report)
            and self._read_json(rejected_report).get("approved") is False
        )
        if not gate.passed and not reviewed_rejection_can_reenter_fixer:
            self._mark_task(
                studio,
                "full_creative_build",
                "retryable",
                "initial technical validation failed",
                failed_source_checksum=directory_checksum(promotion_source),
                validator_checksum=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            )
            raise StudioError("Full creative build failed initial technical validation; preserved staging is retryable.")
        if not use_fixed_source:
            self._atomic_promote(staging_source, selected_source.parent)
        self._mark_task(studio, "full_creative_build", "completed")
        checkpoints("full_creative_build_completed")

        final_dir = studio / "final_reviews"
        # A recovered fixer may change the selected source after an earlier
        # review. Always bind canonical screenshots and observations to the
        # exact bytes now under review; file existence is not freshness.
        self.inspector.inspect(selected_source, final_dir)
        self._require_screenshots(final_dir, tablet=True)
        self._write_commercial_reports(studio, research, spec, selected_source)
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
        art = self._apply_art_director_calibration(studio, art)
        self._mark_task(studio, "art_director", "completed")
        checkpoints("full_build_visuals_completed")
        checkpoints("art_director_review_completed")
        self._write_provenance(studio, chosen, selected_source.parent)
        self._atomic_promote(selected_source.parent, site_dir)
        return StudioResult(index_path=site_dir / "index.html", selected_concept=chosen, studio_dir=studio)

    def revise(
        self, *, run_dir: Path, site_dir: Path, critique_path: Path, checkpoints: Callable[..., None], iteration: int
    ) -> None:
        studio = run_dir / "studio"
        source_index = studio / "selected" / "source" / "index.html"
        before_hash = hashlib.sha256(source_index.read_bytes()).hexdigest() if source_index.is_file() else ""
        state = self._task_state(studio).get("creative_fixer", {})
        # A retryable source is retained precisely so a recovered material
        # revision can be inspected instead of triggering an endless second
        # Codex invocation. It still must clear technical, commercial and
        # independent visual review below before it can be promoted.
        recovered_manual_revision = state.get("status") == "retryable" and source_index.is_file()
        if not recovered_manual_revision:
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
        if before_hash and before_hash == after_hash and not recovered_manual_revision:
            self._mark_task(studio, "creative_fixer", "retryable", "fixer returned without changing selected source")
            raise StudioError("Creative fixer returned without changing the selected source; preserved state is retryable.")
        business = self._read_json(studio / "input" / "business_brief.json")
        research = ResearchBrief.model_validate(business["research"])
        readiness = self._stored_readiness(studio)
        self._validate_static_site(studio / "selected" / "source")
        self._validate_authorised_media_rendering(studio, studio / "selected" / "source")
        self._validate_scope_compliance(studio, studio / "selected" / "source", readiness)
        self.inspector.inspect(studio / "selected" / "source" / "index.html", studio / "final_reviews")
        selected = self._selected_id(self._read_json(studio / "concept_reviews" / "selected_concept.json"))
        self._write_provenance(studio, selected, studio / "selected" / "source")
        self._atomic_promote(studio / "selected" / "source", site_dir)
        self._mark_task(studio, "creative_fixer", "completed")
        checkpoints(f"creative_fixer_iteration_{iteration}_completed")
        self.review_art_director(run_dir=run_dir, checkpoints=checkpoints)

    def review_art_director(self, *, run_dir: Path, checkpoints: Callable[..., None]) -> dict[str, Any]:
        """Re-render and independently review a fixer result without rerunning concepts/build."""
        studio = run_dir / "studio"
        final_dir = studio / "final_reviews"
        self.inspector.inspect(studio / "selected" / "source" / "index.html", final_dir)
        business = self._read_json(studio / "input" / "business_brief.json")
        research = ResearchBrief.model_validate(business["research"])
        spec = SiteSpec.model_validate(business["site_spec"])
        self._write_commercial_reports(studio, research, spec, studio / "selected" / "source" / "index.html")
        self._run_task(
            studio,
            "art_director",
            self._art_director_prompt(run_dir),
            images=[final_dir / name for name in ("desktop.png", "tablet.png", "mobile.png")],
        )
        report_path = studio / "art_director_report.json"
        if not self._art_director_is_valid(report_path) or self._read_json(report_path).get("approved") is not True:
            raise StudioError("Art Director report lacks required screenshot evidence after fixer.")
        self._apply_art_director_calibration(studio, self._read_json(report_path))
        self._mark_task(studio, "art_director", "completed")
        checkpoints("full_build_visuals_completed", "art_director_review_completed")
        return self._read_json(report_path)

    def _prepare_input(
        self, studio: Path, job_id: str, research: ResearchBrief, strategy: StrategyBrief,
        spec: SiteSpec, evidence: Any, implementation_package: dict[str, Any] | None = None,
    ) -> None:
        evidence_payload = evidence.model_dump() if hasattr(evidence, "model_dump") else dict(evidence or {})
        scope_value = evidence_payload.get("page_scope", "blocked")
        incoming_scope = scope_value.value if isinstance(scope_value, PageScope) else str(scope_value)
        self._archive_scope_bound_workspace(studio, incoming_scope)
        input_dir = studio / "input"
        for folder in (input_dir, studio / "concepts", studio / "concept_reviews", studio / "selected"):
            folder.mkdir(parents=True, exist_ok=True)
        prohibited = list(dict.fromkeys(research.forbidden_claims + ["Do not invent prices, reviews, staff, guarantees, results, addresses, or contact details."]))
        media = [item.model_dump() for item in (spec.gallery_assets or research.best_media)]
        if implementation_package is not None:
            media = list(implementation_package.get("authorised_media_manifest", {}).get("media", []))
        self._write_json(input_dir / "evidence.json", {"assessment": evidence_payload, "verified_facts": [item.model_dump() for item in research.verified_facts]})
        self._write_json(input_dir / "scope_decision.json", {
            "scope": evidence_payload.get("page_scope", "blocked"),
            "requested_product_type": evidence_payload.get("requested_product_type", research.requested_product_type),
            "exact_product": evidence_payload.get("exact_product", ""),
            "confirmed_language": research.primary_language,
            "content_theme_count": evidence_payload.get("content_theme_count", 0),
            "usable_media_count": evidence_payload.get("usable_media_count", 0),
            "required_concepts": evidence_payload.get("required_concepts", 0),
            "rules": {
                "full_site": "Three materially different concepts and a full commercial build are required. It needs at least seven meaningful decision sections covering identity, services, proof, brand, process/trust, commercial decision, objections and final conversion; repeated CTAs do not count.",
                "micro_site": "One concise concept only; no more than three semantic sections and no padded gallery or repeated caveat.",
                "blocked": "No creative output may be produced.",
            },
        })
        self._write_json(input_dir / "business_brief.json", {"job_id": job_id, "instagram_url": research.instagram_url, "research": research.model_dump(), "strategy": strategy.model_dump(), "site_spec": spec.model_dump()})
        self._write_json(input_dir / "media_manifest.json", {"media": media, "note": "Only authorised business media with Cloudinary secure URLs may be rendered."})
        self._write_json(input_dir / "prohibited_claims.json", {"prohibited_claims": prohibited, "missing_information": research.unknowns})
        self._write_json(input_dir / "previous_site_constraints.json", {"recent_fingerprints": [], "avoid": ["category templates", "generic narrow-column landing page", "palette-only concept variants"]})
        self._write_json(input_dir / "skill_guidance.json", {"source": ".agents/skills", "skills": self._skill_snapshot()})
        if implementation_package is not None:
            package = dict(implementation_package)
            brand_identity = package.get("brand_identity", {})
            brand_assets = package.get("brand_assets_manifest", {})
            self._write_json(input_dir / "brand_identity.json", brand_identity)
            self._write_json(input_dir / "brand_assets_manifest.json", brand_assets)
            if (brand_identity or brand_assets) and brand_assets.get("logo", {}).get("available") is True:
                logo = brand_assets.get("logo", {})
                source_value = str(logo.get("processed_path", ""))
                source_path = (studio.parent / source_value).resolve() if source_value else None
                run_root = studio.parent.resolve()
                if (
                    source_path is None
                    or not source_path.is_file()
                    or not source_path.is_relative_to(run_root)
                    or hashlib.sha256(source_path.read_bytes()).hexdigest() != logo.get("processed_checksum")
                ):
                    raise StudioError("Verified checksum-bound processed logo is missing from the brand package.")
                brand_asset_dir = input_dir / "brand_assets"
                brand_asset_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, brand_asset_dir / "logo_processed.png")
            # Preserve the orchestrator's canonical package checksum. The
            # Studio-specific field covers the additional local contract text.
            serialized = json.dumps(package, ensure_ascii=False, sort_keys=True).encode("utf-8")
            package["studio_input_sha256"] = hashlib.sha256(serialized).hexdigest()
            package["contract"] = "Codex must implement this package directly; legacy SiteSpec/PageComposition are validation-only."
            self._write_json(input_dir / "implementation_package.json", package)

    @staticmethod
    def _archive_scope_bound_workspace(studio: Path, incoming_scope: str) -> None:
        """Preserve stale concepts when an approved recovery scope changes.

        Concept/output artifacts are valid only under the input contract that
        created them.  Moving rather than deleting keeps crash evidence while
        forcing the replacement contract to generate its own bounded work.
        """
        contract = studio / "input" / "concept_contract.json"
        if not contract.is_file():
            return
        try:
            previous_scope = str(json.loads(contract.read_text(encoding="utf-8")).get("scope", ""))
        except (OSError, ValueError):
            previous_scope = "invalid"
        if previous_scope == incoming_scope:
            return
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive = studio / "recovery_archives" / f"scope-{previous_scope or 'unknown'}-to-{incoming_scope or 'unknown'}-{stamp}"
        archive.mkdir(parents=True, exist_ok=False)
        for name in ("input", "concepts", "concept_reviews", "selected", "initial_validation", "final_reviews", "task_state.json"):
            source = studio / name
            if source.exists():
                shutil.move(str(source), str(archive / name))
        CodexStudioRunner._write_json(archive / "scope_recovery.json", {
            "previous_scope": previous_scope,
            "incoming_scope": incoming_scope,
            "reason": "approved scope changed; prior concepts and reviews are not reusable",
        })

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
            f"bounded input package in {self._relative(run_dir / 'studio' / 'input')}, especially implementation_package.json and scope_decision.json. Create the missing "
            f"runnable HTML concepts {', '.join(missing)} under {self._relative(run_dir / 'studio' / 'concepts')}. "
            "The implementation package is the creative source of truth; legacy business_brief/site_spec files are validation-only. Use the project-local guidance referenced by skill_guidance.json. Do not use a category template, "
            "Jinja, secrets, Telegram, Cloudflare or external publishing. Obey the selected scope exactly; a micro-site must never be expanded into a long page. Each concept must have a distinct "
            "central idea, composition, hero, density, media strategy, typography, CTA and signature element. "
            "Each runnable concept must also show a persistent navigation solution on scrollable pages, a purposeful footer with verified routes, and unclipped primary CTA text; these are functional requirements, not a shared visual shell. "
            "When brand_assets_manifest.json says logo.available=true, the exact checksum-bound official logo is mandatory; otherwise use a plain text business name and invent no mark. The verified palette is mandatory in every concept; references must not override it. "
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

    def _full_build_prompt(self, run_dir: Path, chosen: str, readiness: EvidenceAssessment) -> str:
        scope_rule = (
            "This is an intentional micro-site: render no more than three semantic <section> elements and no more than two <img> treatments total. "
            "Use the strongest authorised hero image and at most one supporting image; do not turn the manifest into a gallery. "
            if readiness.page_scope is PageScope.MICRO else
            "This is a full commercial site: implement at least seven meaningful sections with explicit data-decision-role values covering identity_value, offer_services, proof, brand_about, trust_process, commercial_decision, objection_handling and final_conversion. The final conversion must be a real form or verified direct contact path. Repeated CTAs, decorative panels, a footer, or a redirect do not count as coverage. Use approved themes and media deliberately without repeating one visual treatment. "
        )
        logo_rule = (
            "Copy the exact official logo from studio/input/brand_assets/logo_processed.png into the final site assets and render it without redraw, recolour, distortion or generative replacement. "
            if (run_dir / "studio" / "input" / "brand_assets" / "logo_processed.png").is_file()
            else "No official logo was proven: use a plain text business name and do not invent, redraw or generate a mark. "
        )
        return (
            "Use $siteagent-web-studio to expand the selected concept without changing its central creative idea. "
            f"Read {self._relative(run_dir / 'studio' / 'concept_reviews' / 'selected_concept.json')} and the selected "
            f"prototype at {self._relative(run_dir / 'studio' / 'concepts' / chosen)}, implementation package at {self._relative(run_dir / 'studio' / 'input' / 'implementation_package.json')} and scope contract at {self._relative(run_dir / 'studio' / 'input' / 'scope_decision.json')}. Write a complete static responsive "
            f"HTML/CSS/JS site to the staging workspace {self._relative(run_dir / 'studio' / 'selected' / 'staging')}. Preserve its signature "
            "element and composition language. " + scope_rule +
            "Render business imagery only with the exact authorised Cloudinary URLs from studio/input/media_manifest.json; "
            "do not copy, download, proxy, transform, or reference local business-photo files. " + logo_rule + "Use the verified primary/secondary palette exactly in authored CSS. "
            "Keep primary navigation available while scrollable pages move, offset sticky controls below it, and include a semantic footer with declared-IA navigation, a primary conversion action and verified social/contact routes only. Mark primary CTA anchors with data-site-cta='primary' and ensure translated text is not clipped in default, hover, focus or active states. Do not reuse one visual header/footer composition across businesses. "
            "Use verified facts only; do not invoke Jinja, Cloudflare or Telegram."
        )

    def _art_director_prompt(self, run_dir: Path) -> str:
        return (
            "Use $siteagent-web-studio and act as an independent Art Director. Inspect the desktop, tablet and "
            f"mobile screenshots in {self._relative(run_dir / 'studio' / 'final_reviews')} against the bounded "
            "business input, selected concept, and the mandatory studio/commercial_usefulness_report.json, "
            "studio/input/brand_identity.json, studio/input/brand_assets_manifest.json, "
            "studio/language_fit_report.json, and studio/semantic_repetition_report.json. Write studio/art_director_report.json with approved (boolean), score, "
            "summary, unresolved_issues and findings. Every finding needs severity, screenshot, screenshot_region, selector, "
            "description, reason and desired_outcome. Read studio/input/scope_decision.json before judging completeness: a micro_site is a finished compact product, not a deficient full site. It needs a clear offer and CTA, real proof/process, and a conversion close; do not demand a gallery, FAQ, team, reviews, certificates, prices, or extra sections unless the evidence and approved scope require them. A full_site must demonstrate its longer commercial path. Scroll-test navigation, inspect the complete footer, and reject clipped or broken primary CTA states on every declared page without prescribing a common visual shell. Score and approval must cite screenshot evidence. You must not approve if the scope-aware commercial usefulness is below 85, business clarity is below 85, copy quality below 80, UX below 85, a high issue remains, or the result reads as an editorial exercise rather than a business site. Do not change the build."
        )

    @staticmethod
    def _write_commercial_reports(studio: Path, research: ResearchBrief, spec: SiteSpec, index_path: Path) -> None:
        """Persist deterministic commercial gates before visual approval."""
        from site_agent.design_quality import build_context

        context = build_context(research, StrategyBrief.model_validate(json.loads((studio / "input" / "business_brief.json").read_text(encoding="utf-8"))["strategy"]), spec)
        html_text = index_path.read_text(encoding="utf-8")
        readiness = CodexStudioRunner._stored_readiness(studio)
        declared_scope = CodexStudioRunner._read_json(studio / "input" / "scope_decision.json").get("scope", "")
        if declared_scope != readiness.page_scope.value:
            raise StudioError(
                f"Scope contract mismatch: declared {declared_scope!r}, effective decision is {readiness.page_scope.value!r}. "
                "A reviewer may not change the persisted approved scope."
            )
        semantic = semantic_repetition_report(spec, context, html_text=html_text, page_scope=declared_scope)
        commercial = commercial_usefulness_report(spec, context, semantic=semantic, html_text=html_text, page_scope=declared_scope)
        language = language_fit_report(spec, research)
        CodexStudioRunner._write_json(studio / "commercial_usefulness_report.json", commercial.model_dump())
        CodexStudioRunner._write_json(studio / "language_fit_report.json", language.model_dump())
        CodexStudioRunner._write_json(studio / "semantic_repetition_report.json", semantic.model_dump())

    @staticmethod
    def _apply_art_director_calibration(studio: Path, report: dict[str, Any]) -> dict[str, Any]:
        """Hard-stop an aesthetic approval that fails commercial calibration."""
        commercial = CodexStudioRunner._read_json(studio / "commercial_usefulness_report.json")
        language = CodexStudioRunner._read_json(studio / "language_fit_report.json")
        semantic = CodexStudioRunner._read_json(studio / "semantic_repetition_report.json")
        checks = commercial.get("checks", {})
        category_scores = {
            "commercial_usefulness": int(commercial.get("score", 0)),
            "business_clarity": 100 if checks.get("offer_clear_within_five_seconds") else 60,
            "copy_quality": 55 if not semantic.get("approved", False) else 85,
            "ux": 100 if checks.get("primary_cta_in_first_meaningful_viewport") else 60,
            "brand_fit": 100 if language.get("approved") and checks.get("reads_as_commercial_site") else 60,
        }
        scope = commercial.get("page_scope", "unspecified")
        scope_check = "micro_site_has_offer_proof_conversion_path" if scope == "micro_site" else "full_site_has_complete_commercial_path"
        if scope in {"micro_site", "full_site"} and not checks.get(scope_check, False):
            category_scores["commercial_usefulness"] = min(category_scores["commercial_usefulness"], 60)
        blocked = (
            category_scores["commercial_usefulness"] < 85
            or category_scores["business_clarity"] < 85
            or category_scores["copy_quality"] < 80
            or category_scores["ux"] < 85
            or not commercial.get("approved", False)
            or any(item.get("severity") in {"critical", "high"} for item in report.get("findings", []))
        )
        report["calibration"] = {
            "commercial_usefulness": commercial,
            "language_fit": language,
            "semantic_repetition": semantic,
            "category_scores": category_scores,
            "hard_gate_passed": not blocked,
        }
        if blocked:
            report["approved"] = False
            report["score"] = min(int(report.get("score", 0)), category_scores["commercial_usefulness"])
            report["unresolved_issues"] = list(report.get("unresolved_issues", [])) + [{
                "severity": "high", "description": "Commercial calibration gate failed.",
                "reason": "Commercial, clarity, copy, or UX thresholds were not met.",
            }]
            report["findings"] = list(report.get("findings", [])) + [{
                "severity": "high", "screenshot": "desktop.png, mobile.png", "screenshot_region": "first meaningful viewport and repeated narrative sections",
                "selector": "main", "description": "Commercial calibration gate failed.",
                "reason": "The build cannot receive visual approval until the required commercial thresholds pass.",
                "desired_outcome": "Make the offer and CTA clear early, remove semantic duplication, and rerun review.",
            }]
        CodexStudioRunner._write_json(studio / "art_director_report.json", report)
        return report

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
        # The app-level Code Mode host can retain an stdin-driven PowerShell
        # wrapper after a command runner exits on Windows. Studio needs the
        # regular bounded shell tool instead; otherwise the outer 900-second
        # phase timeout sees a live descendant even though no concept bytes
        # were produced. Keep the workspace sandbox and disable only that host.
        command = [
            codex_command,
            "exec",
            "--disable",
            "code_mode_host",
            "-C",
            str(self.project_root),
            "--sandbox",
            "workspace-write",
            "-",
        ]
        for image in images or []:
            if image.is_file():
                command[2:2] = ["--image", str(image)]
        model = os.getenv("CODEX_MODEL", "").strip()
        if model:
            command[2:2] = ["-m", model]
        try:
            if self.command_runner is subprocess.run:
                completed = self._run_subprocess_tree(command, prompt, timeout=self.task_timeouts[task])
            else:
                completed = self.command_runner(command, input=prompt, text=True, encoding="utf-8", capture_output=True, check=False, timeout=self.task_timeouts[task])
        except subprocess.TimeoutExpired as exc:
            raise StudioError(f"Codex Studio {task} timed out after {self.task_timeouts[task]} seconds; preserved state is retryable.") from exc
        except (OSError, subprocess.SubprocessError) as exc:
            raise StudioError(f"Codex Studio invocation failed before generation: {exc}") from exc
        if completed.returncode != 0:
            output = (completed.stderr or completed.stdout or "").strip()
            raise StudioError(f"Codex Studio generation failed: {output[:2000]}")

    @staticmethod
    def _run_subprocess_tree(command: list[str], prompt: str, *, timeout: int) -> subprocess.CompletedProcess[str]:
        """Bound Codex and all descendants, including Windows wrapper processes."""
        # Temporary files preserve diagnostic output without inheritable PIPE
        # readers that can keep communicate() alive after the direct child exits.
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stdout_file, tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stderr_file:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=stdout_file,
                stderr=stderr_file,
                text=True,
                encoding="utf-8",
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                start_new_session=os.name != "nt",
            )
            try:
                process.communicate(input=prompt, timeout=timeout)
            except subprocess.TimeoutExpired:
                CodexStudioRunner._terminate_process_tree(process)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                raise
            stdout_file.seek(0)
            stderr_file.seek(0)
            return subprocess.CompletedProcess(command, process.returncode, stdout_file.read(), stderr_file.read())

    @staticmethod
    def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def _task_state(self, studio: Path) -> dict[str, Any]:
        path = studio / "task_state.json"
        return self._read_json(path) if path.is_file() else {}

    def _task_completed(self, studio: Path, task: str) -> bool:
        return self._task_state(studio).get(task, {}).get("status") == "completed"

    def _mark_task(
        self,
        studio: Path,
        task: str,
        status: str,
        error: str | None = None,
        **metadata: str,
    ) -> None:
        state = self._task_state(studio)
        record: dict[str, str] = {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
        if error:
            record["error"] = error
        record.update(metadata)
        state[task] = record
        self._write_json(studio / "task_state.json", state)

    def _capture_concept_screenshots(self, studio: Path) -> None:
        for name in self._concept_names(studio):
            artifacts = studio / "concept_reviews" / name
            if not (artifacts / "desktop.png").is_file() or not (artifacts / "mobile.png").is_file():
                self.inspector.inspect(studio / "concepts" / name / "index.html", artifacts)
            self._require_screenshots(artifacts, tablet=False)

    def _compare_concepts(self, studio: Path) -> dict[str, Any]:
        names = self._concept_names(studio)
        fingerprints = {name: self._concept_fingerprint(studio / "concepts" / name / "index.html") for name in names}
        pairs: dict[str, dict[str, Any]] = {}
        reasons: list[str] = []
        for index, left in enumerate(names):
            for right in names[index + 1:]:
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
            # Builder recovery provenance can contain private run paths. Keep
            # it beside staging evidence, never in the customer-facing bundle.
            shutil.copytree(source, staged, ignore=shutil.ignore_patterns("provenance.json"))
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

    def _write_provenance(self, studio: Path, selected: str, final_source: Path) -> None:
        self._write_json(studio / "build_provenance.json", {"schema_version": 1, "selected_concept": selected, "skill_versions": self._skill_snapshot(), "codex_command": "codex exec", "created_at": datetime.now(timezone.utc).isoformat()})
        self._write_json(
            studio / "media_provenance_report.json",
            _media_provenance_report(studio_dir=studio, site_dir=final_source),
        )

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

    def _staging_provenance_is_valid(self, studio: Path, folder: Path) -> bool:
        """Accept a timed-out child output only when its bounded inputs verify.

        Codex can finish writing a complete staging workspace just after the
        supervising timeout fires. Reusing that output prevents a duplicate
        45-minute material build, but an ordinary technically rejected staging
        build still remains retryable and must be revised.
        """
        provenance_path = folder / "provenance.json"
        selected_path = studio / "concept_reviews" / "selected_concept.json"
        if not provenance_path.is_file() or not selected_path.is_file():
            return False
        try:
            provenance = self._read_json(provenance_path)
            selected = self._read_json(selected_path)
            if provenance.get("selected_concept") != self._selected_id(selected, studio):
                return False
            inputs = provenance.get("source_inputs")
            if not isinstance(inputs, dict) or not inputs:
                return False
            for record in inputs.values():
                if not isinstance(record, dict):
                    return False
                raw_path = str(record.get("path", ""))
                expected = str(record.get("sha256", "")).lower()
                if not __import__("re").fullmatch(r"[0-9a-f]{64}", expected):
                    return False
                source = (self.project_root / raw_path).resolve()
                try:
                    source.relative_to(self.project_root.resolve())
                except ValueError:
                    return False
                if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
                    return False
            files = provenance.get("site_files")
            if not isinstance(files, list) or "index.html" not in files:
                return False
            if any(not (folder / str(name)).is_file() for name in files):
                return False
        except (OSError, ValueError, TypeError, StudioError):
            return False
        return True

    def _retryable_staging_can_revalidate(
        self, studio: Path, folder: Path, state: dict[str, Any]
    ) -> bool:
        if state.get("status") != "retryable" or not self._staging_provenance_is_valid(studio, folder):
            return False
        error = str(state.get("error", "")).lower()
        if "timed out" in error:
            return True
        failed_checksum = str(state.get("failed_source_checksum", ""))
        failed_validator = str(state.get("validator_checksum", ""))
        validator_changed = bool(failed_validator) and (
            hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != failed_validator
        )
        return (
            "initial technical validation failed" in error
            and (
                (bool(failed_checksum) and directory_checksum(folder) != failed_checksum)
                or validator_changed
            )
        )

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
    def _validate_authorised_media_rendering(studio: Path, folder: Path) -> None:
        """Require final customer imagery to be traceable to the approved manifest.

        A local copy of an otherwise authorised photo breaks the required
        Cloudinary provenance and prevents exact rendered-use reporting.
        """
        source = folder / "index.html"
        manifest_path = studio / "input" / "media_manifest.json"
        if not source.is_file() or not manifest_path.is_file():
            raise StudioError("Authorised media validation requires final HTML and media manifest.")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise StudioError("Authorised media validation could not read media manifest.") from exc
        allowed = {str(item.get("url", "")) for item in manifest.get("media", [])}
        html = source.read_text(encoding="utf-8")
        rendered = re.findall(r"<(?:img|source|video)\b[^>]*\bsrc=[\"']([^\"']+)", html, flags=re.I)
        forbidden = [url for url in rendered if not url.startswith("data:") and url not in allowed]
        if forbidden:
            raise StudioError("Static studio output renders media outside the authorised Cloudinary manifest: " + ", ".join(forbidden[:5]))

    def _validate_scope_compliance(self, studio: Path, folder: Path, readiness: EvidenceAssessment) -> None:
        """Persist a checkable scope decision before any final screenshot approval."""
        declared = self._read_json(studio / "input" / "scope_decision.json").get("scope", "")
        stored = self._stored_readiness(studio)
        if declared != stored.page_scope.value or readiness.page_scope is not stored.page_scope:
            raise StudioError(
                f"Scope contract mismatch: declared {declared!r}, effective decision is {stored.page_scope.value!r}. "
                "Scope may not be changed to influence review or promotion."
            )
        html_text = (folder / "index.html").read_text(encoding="utf-8")
        section_count = len(__import__("re").findall(r"<section\b", html_text, flags=__import__("re").I))
        image_urls = __import__("re").findall(r"<img\b[^>]*\bsrc=[\"']([^\"']+)", html_text, flags=__import__("re").I)
        reasons: list[str] = []
        if stored.page_scope is PageScope.MICRO and section_count > 3:
            reasons.append(f"micro-site has {section_count} sections; maximum is 3")
        if stored.page_scope is PageScope.MICRO and len(image_urls) > 2:
            reasons.append(f"micro-site has {len(image_urls)} image treatments; maximum is 2")
        role_values = {
            value.lower().replace("-", "_")
            for value in __import__("re").findall(r"data-decision-role=[\"']([^\"']+)", html_text, flags=__import__("re").I)
        }
        if stored.page_scope is PageScope.FULL and section_count < 7:
            reasons.append("full commercial site has fewer than seven meaningful sections")
        if stored.page_scope is PageScope.FULL:
            required_roles = {"identity_value", "offer_services", "proof", "brand_about", "trust_process", "commercial_decision", "objection_handling", "final_conversion"}
            aliases = {
                "identity": "identity_value", "hero": "identity_value", "offer": "offer_services", "services": "offer_services",
                "portfolio": "proof", "gallery": "proof", "about": "brand_about", "brand": "brand_about",
                "process": "trust_process", "trust": "trust_process", "pricing": "commercial_decision",
                "consultation": "commercial_decision", "faq": "objection_handling", "objections": "objection_handling",
                "contact": "final_conversion", "conversion": "final_conversion",
            }
            normalized_roles = {aliases.get(role, role) for role in role_values}
            absent = sorted(required_roles - normalized_roles)
            if absent:
                reasons.append("full commercial coverage is missing: " + ", ".join(absent))
        report = {
            "scope": stored.page_scope.value,
            "exact_product": stored.exact_product,
            "section_count": section_count,
            "image_treatments": len(image_urls),
            "coverage_roles": sorted(role_values),
            "approved": not reasons,
            "reasons": reasons,
        }
        self._write_json(studio / "scope_compliance_report.json", report)
        if reasons:
            raise StudioError("Page scope compliance failed: " + "; ".join(reasons))

    @staticmethod
    def _stored_readiness(studio: Path) -> EvidenceAssessment:
        payload = CodexStudioRunner._read_json(studio / "input" / "evidence.json")
        assessment = payload.get("assessment") if isinstance(payload, dict) else None
        if not isinstance(assessment, dict):
            raise StudioError("Studio input is missing its immutable evidence assessment.")
        try:
            return EvidenceAssessment.model_validate(assessment)
        except ValueError as exc:
            raise StudioError("Studio input has an invalid immutable evidence assessment.") from exc

    def _selected_id(self, selected: dict[str, Any], studio: Path | None = None) -> str:
        value = selected.get("selected_concept")
        if isinstance(value, dict):
            value = value.get("id")
        return value if value in self._concept_names(studio) else ""

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
        chosen = self._selected_id(selected, studio)
        screenshot_evidence = (
            selected.get("screenshot_evidence")
            or selected.get("screenshot_references")
            or [selected.get(key) for key in ("desktop_screenshot_reference", "tablet_screenshot_reference", "mobile_screenshot_reference") if selected.get(key)]
        )
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
        names = self._concept_names(studio)
        if not isinstance(reviews, dict) or any(name not in reviews for name in names):
            return False
        required_review = ("strengths", "weaknesses", "technical_risks", "visual_risks", "business_risks", "desktop_observations", "mobile_observations", "anti_template_observations")
        return all(isinstance(reviews[name], dict) and all(field in reviews[name] for field in required_review) for name in names)

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

    def _require_concepts(self, studio: Path) -> None:
        for name in self._concept_names(studio):
            self._require_static_site(studio / "concepts" / name)
            if not (studio / "concepts" / name / "concept.md").is_file():
                raise StudioError(f"Concept rationale is missing for {name}")

    @staticmethod
    def _concept_names(studio: Path | None) -> tuple[str, ...]:
        if studio is None:
            return CONCEPTS
        contract = studio / "input" / "concept_contract.json"
        if not contract.is_file():
            return CONCEPTS
        try:
            names = json.loads(contract.read_text(encoding="utf-8")).get("required_concepts", [])
        except (OSError, ValueError):
            return CONCEPTS
        if isinstance(names, list) and names and all(name in CONCEPTS for name in names):
            return tuple(names)
        return CONCEPTS

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
