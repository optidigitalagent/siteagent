from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from site_agent.acceptance import AcceptanceAuditor
from site_agent.agents import DesignDirector, FixerAgent, ResearchAgent, ResearchStrategist, SiteSpecAgent, StrategyAgent
from site_agent.builder import SiteBuilder
from site_agent.config import settings
from site_agent.critic import CriticAgent
from site_agent.design_quality import (
    BuilderContext,
    EvidenceAssessment,
    EvidenceLevel,
    PageScope,
    PIPELINE_SCHEMA_VERSION,
    QualityReport,
    assess_evidence,
    audit_quality,
    build_context,
    load_fingerprint_history,
    record_fingerprint,
)
from site_agent.external_skills import LocalSkillRuntime
from site_agent.json_io import write_json
from site_agent.llm import LLMClient
from site_agent.media import MediaInputBlocked, MediaPreparer, PreviewMediaIngestor, authorised_media_assets
from site_agent.models import (
    AcceptanceAuditResult,
    CritiqueReport,
    PublishResult,
    ResearchBrief,
    SiteSpec,
    StrategyBrief,
)
from site_agent.models import SectionSpec
from site_agent.publisher import LiveVerificationError, Publisher, SiteValidationError
from site_agent.preview import PreviewLiveVerifier, PreviewPublisher
from site_agent.identifiers import stable_business_id
from site_agent.research import bootstrap_one_link_intake, normalize_business_source
from site_agent.product_director import ProductDirectorAuditor
from site_agent.studio import CodexStudioRunner, StudioError, assert_production_promotion_allowed
from site_agent.workflow import WorkflowConfigurationError, checksum, implementation_package, role_provenance, selected_references, validate_role_providers, write_markdown


class GenerationBlocked(RuntimeError):
    pass


RESEARCH_PIPELINE_VERSION = "one-link-preview-v1"


@dataclass
class JobResult:
    job_id: str
    run_dir: Path
    publish: PublishResult
    final_score: int


@dataclass
class CalibrationResult:
    """A completed local creative acceptance with no publish/delivery side effect."""
    job_id: str
    run_dir: Path
    final_score: int


class SiteAgentOrchestrator:
    def __init__(
        self,
        *,
        publisher: Publisher | None = None,
        preview_publisher: PreviewPublisher | None = None,
        acceptance_auditor: AcceptanceAuditor | None = None,
    ) -> None:
        llm = LLMClient()
        self.research_agent = ResearchAgent(llm)
        self.strategy_agent = StrategyAgent(llm)
        self.site_spec_agent = SiteSpecAgent(llm)
        self.critic_agent = CriticAgent(llm)
        self.fixer_agent = FixerAgent(llm)
        self.builder = SiteBuilder()
        self.acceptance_auditor = acceptance_auditor or AcceptanceAuditor()
        self.publisher = publisher or Publisher()
        self.preview_publisher = preview_publisher or PreviewPublisher()
        self.skill_runtime = LocalSkillRuntime() if settings.external_skills_enabled else None
        self.studio_runner = CodexStudioRunner() if settings.site_builder == "codex_studio" else None
        self.research_strategist: ResearchStrategist | None = None
        self.design_director: DesignDirector | None = None
        self.media_preparer = MediaPreparer()

    def run(
        self,
        instagram_url: str,
        *,
        production: bool = False,
        run_id: str | None = None,
        run_path: Path | None = None,
        calibration_only: bool = False,
        preview: bool = False,
    ) -> JobResult | CalibrationResult:
        """Run or resume one job without replacing valid prior checkpoints."""
        if production and preview:
            raise GenerationBlocked("A run cannot target production and isolated preview at the same time.")
        job_id = run_id or self._job_id(instagram_url)
        run_dir = run_path or settings.runs_dir / job_id
        reports_dir = run_dir / "generation_reports"
        critiques_dir = run_dir / "critique_reports"
        site_dir = run_dir / "site"
        reports_dir.mkdir(parents=True, exist_ok=True)
        critiques_dir.mkdir(parents=True, exist_ok=True)

        if not calibration_only:
            recovered = self._resume_delivery_if_ready(
                instagram_url=instagram_url,
                job_id=job_id,
                run_dir=run_dir,
                reports_dir=reports_dir,
                site_dir=site_dir,
                production=production,
                preview=preview,
            )
            if recovered is not None:
                return recovered

        builder_mode = settings.site_builder.strip().lower()
        if builder_mode not in {"codex_studio", "legacy_template"}:
            raise GenerationBlocked("Unsupported SITE_BUILDER. Use codex_studio or legacy_template explicitly.")
        package: dict | None = None
        if builder_mode == "codex_studio":
            try:
                validate_role_providers()
                normalized_url, _ = normalize_business_source(instagram_url)
                intake = self._read_json(reports_dir / "00_one_link_intake.json") if preview else None
                if preview and (
                    intake is None
                    or intake.get("pipeline_version") != RESEARCH_PIPELINE_VERSION
                    or intake.get("research", {}).get("normalized_url") != normalized_url
                    or not all(str(item.get("url", "")).startswith("https://res.cloudinary.com/") for item in intake.get("media_manifest", {}).get("media", []))
                ):
                    intake = bootstrap_one_link_intake(
                        normalized_url,
                        run_dir,
                        media_ingestor=PreviewMediaIngestor(upload_to_cloudinary=True),
                    )
                    intake["pipeline_version"] = RESEARCH_PIPELINE_VERSION
                    write_json(reports_dir / "00_one_link_intake.json", intake)
                    self._checkpoint(reports_dir, "one_link_intake_completed", "media_input_created")
                business = self._read_json(reports_dir / "01_business_research.json")
                research_provenance = self._read_json(reports_dir / "01_business_research.provenance.json")
                cached_source = ""
                if business is not None:
                    try:
                        cached_source, _ = normalize_business_source(business.get("research", {}).get("instagram_url", ""))
                    except ValueError:
                        cached_source = ""
                if business is None or cached_source != normalized_url or research_provenance is None or (preview and research_provenance.get("pipeline_version") != RESEARCH_PIPELINE_VERSION):
                    if self.research_strategist is None:
                        self.research_strategist = ResearchStrategist(LLMClient(provider=settings.research_strategist_provider))
                    public_context = __import__("json").dumps((intake or {}).get("research", {}), ensure_ascii=False, indent=2)
                    result = self.research_strategist.run(normalized_url, public_context=public_context)
                    business = result.model_dump()
                    if preview:
                        business = self._apply_provisional_preview_contract(business, (intake or {}).get("research", {}), normalized_url)
                    write_json(reports_dir / "01_business_research.json", business)
                    write_markdown(reports_dir / "business_research.md", "Business research", business)
                    provenance = role_provenance(role="Research Strategist", provider=self.research_strategist.llm.provider, model=self.research_strategist.llm.model, prompt_version="research-strategist-v2-one-link", prompt={"role": "research_strategist"}, inputs={"source_url": normalized_url, "source_ledger": (intake or {}).get("research", {}).get("source_ledger", [])}, output=business)
                    provenance["pipeline_version"] = RESEARCH_PIPELINE_VERSION
                    write_json(reports_dir / "01_business_research.provenance.json", provenance)
                research = ResearchBrief.model_validate(business["research"])
                write_json(reports_dir / "01_research.json", research)
                self._checkpoint(reports_dir, "research_strategist_completed", "research_completed")
                media_path = run_dir / settings.media_input_dir / "manifest.json"
                media_manifest = self._read_json(reports_dir / "02_authorised_media_manifest.json")
                if preview:
                    media_manifest = (intake or {}).get("media_manifest") or self._read_json(media_path)
                    if not media_manifest:
                        raise MediaInputBlocked("media-input checkpoint blocked: automatic preview manifest is missing")
                    if not all(str(item.get("url", "")).startswith("https://res.cloudinary.com/") for item in media_manifest.get("media", [])):
                        raise MediaInputBlocked("media-input checkpoint blocked: preview media was not prepared for Studio delivery")
                    write_json(reports_dir / "02_authorised_media_manifest.json", media_manifest)
                elif media_manifest is None:
                    candidates = self.media_preparer.load_candidates(media_path)
                    media_manifest = self.media_preparer.prepare(candidates, run_dir / "prepared_media")
                    write_json(reports_dir / "02_authorised_media_manifest.json", media_manifest)
                if not preview:
                    self.media_preparer.validate_manifest(media_manifest)
                # Readiness is based on the actual authorised Cloudinary assets,
                # never the scraped public URL list returned by research.
                research.best_media = authorised_media_assets(media_manifest, preview=preview)
                write_json(reports_dir / "01_research.json", research)
                self._checkpoint(reports_dir, "media_prepared", "media_input_completed")
                evidence = self._effective_evidence(reports_dir, research, business, force=preview)
                write_json(reports_dir / "01_evidence_assessment.json", evidence)
                write_json(reports_dir / "01_studio_readiness.json", evidence)
                if not evidence.build_allowed:
                    manifest = "; ".join(evidence.missing_content_manifest or evidence.reasons)
                    raise GenerationBlocked("BLOCKED_INSUFFICIENT_BUSINESS_CONTENT: " + manifest)
                references = selected_references(business_research=business)
                write_json(reports_dir / "02_selected_references.json", {"references": references, "selection_input_checksum": checksum(business), "selection_checksum": checksum(references)})
                self._checkpoint(reports_dir, "references_selected")
                design = self._read_json(reports_dir / "03_design_implementation_brief.json")
                design_provenance = self._read_json(reports_dir / "03_design_implementation_brief.provenance.json")
                if design is None or design_provenance is None or design_provenance.get("scope") != evidence.page_scope.value:
                    if self.design_director is None:
                        self.design_director = DesignDirector(LLMClient(provider=settings.design_director_provider))
                    design = self.design_director.run(
                        __import__("site_agent.models", fromlist=["BusinessResearch"]).BusinessResearch.model_validate(business),
                        media_manifest, references, scope=evidence.page_scope.value,
                    ).model_dump()
                    write_json(reports_dir / "03_design_implementation_brief.json", design)
                    write_markdown(reports_dir / "design_implementation_brief.md", "Design implementation brief", design)
                    provenance = role_provenance(role="Design Director", provider=self.design_director.llm.provider, model=self.design_director.llm.model, prompt_version="design-director-v1", prompt={"role": "design_director", "scope": evidence.page_scope.value}, inputs={"business": business, "media_manifest": media_manifest, "references": references}, output=design)
                    provenance["scope"] = evidence.page_scope.value
                    write_json(reports_dir / "03_design_implementation_brief.provenance.json", provenance)
                strategy = StrategyBrief.model_validate(design["strategy"])
                spec = SiteSpec.model_validate(design["site_spec"])
                package = implementation_package(
                    business_research=business,
                    media_manifest=media_manifest,
                    design_brief=design,
                    references=references,
                    target="isolated_preview" if preview else "production",
                )
                write_json(reports_dir / "04_implementation_package.json", package)
                write_json(reports_dir / "04_implementation_package.provenance.json", {"role": "Implementation Package", "input_checksum": checksum(package["input_checksums"]), "output_checksum": package["sha256"], "used": True})
                self._checkpoint(reports_dir, "design_director_completed", "implementation_package_prepared", "generation_completed")
            except (WorkflowConfigurationError, MediaInputBlocked, KeyError, ValueError) as exc:
                self._checkpoint(reports_dir, "media_input_blocked")
                raise GenerationBlocked(str(exc)) from exc
        else:
            research = self._read_model(reports_dir / "01_research.json", ResearchBrief)
            if research is None or not self._same_business_source(
                research.instagram_url, instagram_url
            ):
                research = self.research_agent.run(instagram_url)
                write_json(reports_dir / "01_research.json", research)
            self._checkpoint(reports_dir, "research_completed")

        if builder_mode != "codex_studio":
            evidence = self._read_model(reports_dir / "01_evidence_assessment.json", EvidenceAssessment)
            if evidence is None or evidence.pipeline_schema_version != PIPELINE_SCHEMA_VERSION:
                evidence = assess_evidence(research)
        # The explicit readiness artifact prevents a cached optimistic score from
        # silently authorising Studio work after a contract upgrade.
        write_json(reports_dir / "01_studio_readiness.json", evidence)
        self._checkpoint(reports_dir, "evidence_completed", "media_analysis_completed")
        if settings.design_quality_pipeline_enabled and not evidence.build_allowed:
            raise GenerationBlocked("insufficient_evidence: " + "; ".join(evidence.reasons))

        if builder_mode == "legacy_template":
            strategy = self._read_model(reports_dir / "02_strategy.json", StrategyBrief)
            if strategy is None:
                strategy = self.strategy_agent.run(research)
                write_json(reports_dir / "02_strategy.json", strategy)
            self._checkpoint(reports_dir, "strategy_completed")

        skill_executions = self._read_json(reports_dir / "03_external_skill_executions.json")
        if skill_executions is None:
            skill_executions = []
            if builder_mode == "legacy_template" and self.skill_runtime is not None:
                frontend = self.skill_runtime.frontend_design_brief(
                    category=research.niche, audience=strategy.target_customer,
                    goal=strategy.business_logic, atmosphere=research.brand_atmosphere,
                )
                system = self.skill_runtime.design_system(
                    category=research.niche, audience=strategy.target_customer,
                    offer=" ".join(research.sells or research.services_or_products),
                    atmosphere=research.brand_atmosphere, project_name=research.business_name,
                )
                skill_executions = [frontend.as_dict(), system.as_dict()]
            write_json(reports_dir / "03_external_skill_executions.json", {"executions": skill_executions})
        elif isinstance(skill_executions, dict):
            skill_executions = skill_executions.get("executions", [])
        self._checkpoint(reports_dir, "external_skills_completed")

        if builder_mode == "legacy_template":
            spec = self._read_model(reports_dir / "03_site_spec_initial.json", SiteSpec)
        if builder_mode == "legacy_template" and spec is None:
            spec = self._normalize_sparse_instagram_spec(
                research,
                self.site_spec_agent.run(
                    research, strategy,
                    next((entry.get("output", {}).get("prompt_guidance", "") for entry in skill_executions if entry.get("name") == "frontend-design"), ""),
                ),
            )
            write_json(reports_dir / "03_site_spec_initial.json", spec)
        self._checkpoint(reports_dir, "generation_completed")

        studio_dir: Path | None = None
        if builder_mode == "codex_studio":
            assert self.studio_runner is not None
            try:
                studio_result = self.studio_runner.build(
                    run_dir=run_dir,
                    site_dir=site_dir,
                    job_id=job_id,
                    research=research,
                    strategy=strategy,
                    spec=spec,
                    evidence=evidence,
                    implementation_package=package,
                    checkpoints=lambda *names: self._checkpoint(reports_dir, *names),
                )
            except StudioError as exc:
                raise GenerationBlocked(f"codex_studio_failed_retryable: {exc}") from exc
            studio_dir = studio_result.studio_dir

        # This compatibility context is extracted for audit artifacts only after a Studio build.
        # It is never passed to a Studio renderer or allowed to choose its composition.
        context = self._read_model(reports_dir / "04_builder_context.json", BuilderContext) if builder_mode == "legacy_template" else None
        if builder_mode == "legacy_template" and context is None:
            context = build_context(research, strategy, spec, skill_executions)
            write_json(reports_dir / "04_builder_context.json", context)
            write_json(reports_dir / "04_business_brief.json", context.business_brief)
            write_json(reports_dir / "04_ux_architecture.json", context.ux_architecture)
            write_json(reports_dir / "04_narrative_strategy.json", context.narrative)
            write_json(reports_dir / "04_visual_directions.json", {"directions": [direction.model_dump() for direction in context.visual_directions], "selected": context.selected_visual_direction.name})
            write_json(reports_dir / "04_design_system.json", context.design_system)
            write_json(reports_dir / "04_media_manifest.json", {"media": [item.model_dump() for item in context.media_manifest]})
            design_dir = run_dir / "design"
            design_dir.mkdir(parents=True, exist_ok=True)
            write_json(design_dir / "page_composition.json", context.page_composition)
        if builder_mode == "legacy_template":
            self._checkpoint(reports_dir, "strategy_artifacts_completed", "builder_context_completed")

        final_critique: CritiqueReport | None = None
        for iteration in range(1, settings.max_fix_iterations + 1):
            index_path = site_dir / "index.html"
            critique_path = critiques_dir / f"critique_iteration_{iteration}.json"
            critique_provenance_path = critiques_dir / f"critique_iteration_{iteration}.provenance.json"
            critique = self._read_model(
                critique_path, CritiqueReport
            )
            if critique is not None and not self._critique_matches_site(critique_provenance_path, index_path):
                # Preserve the historical decision, but never let it trigger a
                # fixer against different bytes after crash recovery.
                write_json(
                    critiques_dir / f"critique_iteration_{iteration}.stale.json",
                    critique,
                )
                critique = None
            if critique is None:
                if iteration != 1 or not index_path.is_file() or index_path.stat().st_size == 0:
                    if builder_mode == "codex_studio":
                        assert self.studio_runner is not None
                        try:
                            self.studio_runner.revise(
                                run_dir=run_dir,
                                site_dir=site_dir,
                                critique_path=critiques_dir / f"critique_iteration_{iteration - 1}.json",
                                checkpoints=lambda *names: self._checkpoint(reports_dir, *names),
                                iteration=iteration,
                            )
                        except StudioError as exc:
                            raise GenerationBlocked(f"codex_studio_fixer_failed_retryable: {exc}") from exc
                    else:
                        index_path = self.builder.build(
                            site_dir=site_dir,
                            research=research,
                            strategy=strategy,
                            spec=spec,
                            design_context=context,
                        )
                write_json(reports_dir / f"site_spec_iteration_{iteration}.json", spec)
                critique = self.critic_agent.run(
                    index_path=index_path,
                    artifacts_dir=critiques_dir / f"iteration_{iteration}",
                    research=research,
                    strategy=strategy,
                    site_spec=spec,
                    evidence=evidence,
                )
                write_json(critique_path, critique)
                write_json(critique_provenance_path, {
                    "site_sha256": self._site_checksum(site_dir),
                    "hash_scope": "html_css_js_tree",
                    "critique_sha256": self._file_checksum(critique_path),
                    "site_path": str(site_dir),
                    "iteration": iteration,
                })
            final_critique = critique
            self._checkpoint(reports_dir, "technical_gate_completed", "critics_completed")
            if builder_mode == "codex_studio":
                self._checkpoint(reports_dir, "art_director_review_completed")
            quality = self._read_model(reports_dir / f"quality_report_iteration_{iteration}.json", QualityReport) if builder_mode == "legacy_template" else None
            if builder_mode == "legacy_template" and quality is None:
                history = load_fingerprint_history(settings.runs_dir / "design_fingerprint_history.json", limit=settings.quality_history_limit) if settings.anti_template_enabled else []
                guideline = self.skill_runtime.web_guidelines(site_dir / "index.html") if self.skill_runtime is not None else None
                if guideline is not None:
                    write_json(reports_dir / f"web_guidelines_iteration_{iteration}.json", guideline.as_dict())
                html_text = (site_dir / "index.html").read_text(encoding="utf-8")
                quality = audit_quality(spec, context, technical_passed=critique.technical_gate.passed, historical_fingerprints=history, guideline_findings=(guideline.output["findings"] if guideline else []), html_text=html_text)
                write_json(reports_dir / f"quality_report_iteration_{iteration}.json", quality)
            if critique.approved_for_delivery and (quality is None or quality.approved):
                if not self._exact_duration_contract_passes(research, index_path):
                    raise GenerationBlocked(
                        "Exact-duration evidence violation: final customer copy upgrades "
                        "a verified exact duration to a plus/over claim."
                    )
                if builder_mode == "codex_studio" and studio_dir is not None:
                    product_report = ProductDirectorAuditor().audit(
                        requested_product_type=research.requested_product_type,
                        site_dir=site_dir,
                        screenshots_dir=studio_dir / "final_reviews",
                        business_research=business,
                        media_manifest=media_manifest,
                    )
                    write_json(studio_dir / "product_director_report.json", product_report)
                acceptance = self.acceptance_auditor.audit(
                    critique=critique,
                    site_dir=site_dir,
                    quality_report=quality,
                    studio_dir=studio_dir,
                    preview=preview,
                )
                write_json(reports_dir / "acceptance_audit.json", acceptance)
                write_json(
                    reports_dir / "acceptance_audit.provenance.json",
                    self._acceptance_provenance(
                        acceptance_path=reports_dir / "acceptance_audit.json",
                        site_dir=site_dir,
                        studio_dir=studio_dir,
                    ),
                )
                if not acceptance.approved:
                    raise GenerationBlocked(
                        "Acceptance audit blocked deployment: " + "; ".join(acceptance.reasons)
                    )
                self._checkpoint(reports_dir, "acceptance_completed")
                if builder_mode == "codex_studio":
                    self._checkpoint(reports_dir, "creative_acceptance_completed")
                    if production:
                        try:
                            assert_production_promotion_allowed(studio_dir=studio_dir, site_dir=site_dir)
                        except StudioError as exc:
                            raise GenerationBlocked(str(exc)) from exc
                    if production and settings.creative_studio_human_calibration_required:
                        raise GenerationBlocked(
                            "creative_studio_human_calibration_required: fixture evidence must be approved before production rollout."
                        )
                if calibration_only:
                    result = {
                        "status": "completed_human_calibration_required",
                        "job_id": job_id,
                        "final_score": critique.score,
                        "site_dir": str(site_dir),
                        "studio_dir": str(studio_dir) if studio_dir else "",
                        "acceptance_audit": "generation_reports/acceptance_audit.json",
                        "external_actions": {"publisher": False, "cloudflare": False, "telegram": False, "queue": False},
                    }
                    write_json(reports_dir / "calibration_result.json", result)
                    self._checkpoint(reports_dir, "calibration_completed")
                    return CalibrationResult(job_id=job_id, run_dir=run_dir, final_score=critique.score)
                if preview:
                    publish = self.preview_publisher.publish(
                        run_dir=run_dir,
                        site_dir=site_dir,
                        source_url=instagram_url,
                        run_id=job_id,
                    )
                else:
                    publish = self.publisher.publish(
                        run_dir=run_dir,
                        site_dir=site_dir,
                        instagram_url=instagram_url,
                        production=production,
                    )
                write_json(reports_dir / "publish_result.json", publish)
                if quality is not None:
                    record_fingerprint(settings.runs_dir / "design_fingerprint_history.json", quality.fingerprint, limit=settings.quality_history_limit)
                self._checkpoint(reports_dir, "preview_deployment_completed" if preview else "deployment_completed")
                return JobResult(
                    job_id=job_id,
                    run_dir=run_dir,
                    publish=publish,
                    final_score=critique.score,
                )
            next_spec = self._read_model(
                reports_dir / f"site_spec_iteration_{iteration + 1}.json", SiteSpec
            )
            if builder_mode == "legacy_template":
                spec = next_spec or self._fix(research, strategy, spec, critique)
                context = build_context(research, strategy, spec, skill_executions)
                write_json(reports_dir / "04_builder_context.json", context)
                design_dir = run_dir / "design"
                design_dir.mkdir(parents=True, exist_ok=True)
                write_json(design_dir / "page_composition.json", context.page_composition)
            self._checkpoint(reports_dir, "fixer_completed")

        assert final_critique is not None
        raise GenerationBlocked(
            "Final site did not pass quality gate: "
            f"score={final_critique.score}, "
            f"technical_gate={final_critique.technical_gate.passed}, "
            f"blocking_issues={final_critique.has_blocking_issues}"
        )

    def _resume_delivery_if_ready(
        self,
        *,
        instagram_url: str,
        job_id: str,
        run_dir: Path,
        reports_dir: Path,
        site_dir: Path,
        production: bool,
        preview: bool = False,
    ) -> JobResult | None:
        """Reuse a delivered-quality build; only publish when deployment is absent."""
        research = self._read_model(reports_dir / "01_research.json", ResearchBrief)
        critique = self._read_model(
            run_dir / "critique_reports" / "critique_iteration_1.json", CritiqueReport
        )
        index_path = site_dir / "index.html"
        critique_provenance_path = (
            run_dir / "critique_reports" / "critique_iteration_1.provenance.json"
        )
        if (
            research is None
            or not self._same_business_source(research.instagram_url, instagram_url)
            or critique is None
            or not critique.approved_for_delivery
            or not index_path.is_file()
            or index_path.stat().st_size == 0
            or not self._critique_matches_site(critique_provenance_path, index_path)
            or not self._exact_duration_contract_passes(research, index_path)
        ):
            return None

        acceptance_path = reports_dir / "acceptance_audit.json"
        acceptance = self._read_model(
            acceptance_path, AcceptanceAuditResult
        )
        studio_dir = run_dir / "studio" if settings.site_builder == "codex_studio" else None
        if (
            acceptance is None
            or not acceptance.approved
            or not self._acceptance_matches_site(
                reports_dir / "acceptance_audit.provenance.json",
                acceptance_path=acceptance_path,
                site_dir=site_dir,
                studio_dir=studio_dir,
            )
        ):
            return None

        if production and settings.site_builder == "codex_studio":
            try:
                assert_production_promotion_allowed(
                    studio_dir=run_dir / "studio", site_dir=site_dir
                )
            except StudioError as exc:
                raise GenerationBlocked(str(exc)) from exc
            if settings.creative_studio_human_calibration_required:
                raise GenerationBlocked(
                    "creative_studio_human_calibration_required: fixture evidence must be approved before production rollout."
                )

        if preview:
            from site_agent.preview import PreviewDeploymentResult
            deployment = self._read_model(run_dir / "preview_deployment.json", PreviewDeploymentResult)
            deployment_ready = deployment is not None and deployment.verification_status == "verified"
            if deployment_ready:
                try:
                    PreviewLiveVerifier(
                        http_get=self.preview_publisher.http_get,
                        sleep=self.preview_publisher.sleep,
                        retries=settings.cloudflare_live_retries,
                        backoff_seconds=settings.cloudflare_live_backoff_seconds,
                        timeout_seconds=settings.cloudflare_live_timeout_seconds,
                    ).verify(
                        deployment.preview_url,
                        site_dir=run_dir / "preview_publish",
                        expected_marker=stable_business_id(instagram_url),
                    )
                except (LiveVerificationError, SiteValidationError, OSError, ValueError):
                    deployment_ready = False
        else:
            deployment = self._read_model(run_dir / "deployment.json", PublishResult)
            deployment_ready = deployment is not None and deployment.is_verified_production
        if deployment_ready:
            self._checkpoint(
                reports_dir,
                "research_completed",
                "generation_completed",
                "technical_gate_completed",
                "critics_completed",
                "acceptance_completed",
                "preview_deployment_completed" if preview else "deployment_completed",
            )
            return JobResult(
                job_id=job_id,
                run_dir=run_dir,
                publish=deployment,
                final_score=critique.score,
            )

        if preview:
            publish = self.preview_publisher.publish(
                run_dir=run_dir,
                site_dir=site_dir,
                source_url=instagram_url,
                run_id=job_id,
            )
        else:
            publish = self.publisher.publish(
                run_dir=run_dir,
                site_dir=site_dir,
                instagram_url=instagram_url,
                production=production,
            )
        write_json(reports_dir / "publish_result.json", publish)
        self._checkpoint(reports_dir, "acceptance_completed", "preview_deployment_completed" if preview else "deployment_completed")
        return JobResult(
            job_id=job_id,
            run_dir=run_dir,
            publish=publish,
            final_score=critique.score,
        )

    def _read_model(self, path: Path, model_type):
        if not path.is_file() or path.stat().st_size == 0:
            return None
        try:
            return model_type.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    @staticmethod
    def _critique_matches_site(provenance_path: Path, index_path: Path) -> bool:
        if not provenance_path.is_file() or not index_path.is_file():
            return False
        try:
            import json

            payload = json.loads(provenance_path.read_text(encoding="utf-8"))
            expected = str(payload.get("site_sha256", ""))
            critique_path = provenance_path.with_name(
                provenance_path.name.removesuffix(".provenance.json") + ".json"
            )
            expected_critique = str(payload.get("critique_sha256", ""))
            critique_matches = (
                not expected_critique
                or (
                    critique_path.is_file()
                    and SiteAgentOrchestrator._file_checksum(critique_path) == expected_critique
                )
            )
            return (
                bool(expected)
                and critique_matches
                and SiteAgentOrchestrator._site_checksum(index_path.parent) == expected
            )
        except (OSError, ValueError, AttributeError):
            return False

    @staticmethod
    def _file_checksum(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @classmethod
    def _acceptance_provenance(
        cls,
        *,
        acceptance_path: Path,
        site_dir: Path,
        studio_dir: Path | None,
    ) -> dict:
        screenshots: dict[str, str] = {}
        if studio_dir is not None:
            for name in ("desktop.png", "tablet.png", "mobile.png"):
                path = studio_dir / "final_reviews" / name
                if path.is_file():
                    screenshots[f"studio/final_reviews/{name}"] = cls._file_checksum(path)
        return {
            "site_sha256": cls._site_checksum(site_dir),
            "hash_scope": "html_css_js_tree",
            "acceptance_sha256": cls._file_checksum(acceptance_path),
            "screenshots": screenshots,
        }

    @classmethod
    def _acceptance_matches_site(
        cls,
        provenance_path: Path,
        *,
        acceptance_path: Path,
        site_dir: Path,
        studio_dir: Path | None,
    ) -> bool:
        if not provenance_path.is_file() or not acceptance_path.is_file():
            return False
        try:
            import json

            payload = json.loads(provenance_path.read_text(encoding="utf-8"))
            if payload.get("hash_scope") != "html_css_js_tree":
                return False
            if payload.get("site_sha256") != cls._site_checksum(site_dir):
                return False
            if payload.get("acceptance_sha256") != cls._file_checksum(acceptance_path):
                return False
            screenshots = payload.get("screenshots")
            if not isinstance(screenshots, dict):
                return False
            if studio_dir is None:
                return True
            for name in ("desktop.png", "tablet.png", "mobile.png"):
                key = f"studio/final_reviews/{name}"
                path = studio_dir / "final_reviews" / name
                if not path.is_file() or screenshots.get(key) != cls._file_checksum(path):
                    return False
            return True
        except (OSError, ValueError, AttributeError, TypeError):
            return False

    @staticmethod
    def _exact_duration_contract_passes(research: ResearchBrief, index_path: Path) -> bool:
        rules = " ".join(research.forbidden_claims).casefold()
        if "exact duration" not in rules:
            return True
        try:
            from bs4 import BeautifulSoup

            text = BeautifulSoup(index_path.read_text(encoding="utf-8"), "html.parser").get_text(" ")
        except (OSError, UnicodeError):
            return False
        forbidden = re.compile(
            r"(?:\b20\s*\+|\bover\s+20\b|\bпонад\s+20\b|\bбільше\s+20\b|"
            r"РїРѕРЅР°Рґ\s+20|Р±С–Р»СЊС€Рµ\s+20)",
            flags=re.IGNORECASE,
        )
        return forbidden.search(text) is None

    @staticmethod
    def _site_checksum(site_dir: Path) -> str:
        """Bind reusable reviews to every authored file, not only index.html."""
        digest = hashlib.sha256()
        for path in sorted(
            item for item in site_dir.rglob("*")
            if item.is_file() and item.suffix.lower() in {".html", ".css", ".js"}
        ):
            digest.update(path.relative_to(site_dir).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()

    def _read_json(self, path: Path):
        if not path.is_file() or not path.stat().st_size:
            return None
        try:
            import json
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    @staticmethod
    def _same_business_source(left: str, right: str) -> bool:
        try:
            return normalize_business_source(left)[0] == normalize_business_source(right)[0]
        except ValueError:
            return False

    def _checkpoint(self, reports_dir: Path, *names: str) -> None:
        path = reports_dir / "checkpoints.json"
        checkpoints: dict[str, str] = {}
        if path.is_file() and path.stat().st_size:
            try:
                import json

                checkpoints = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                checkpoints = {}
        timestamp = datetime.now(timezone.utc).isoformat()
        checkpoints.update({name: timestamp for name in names})
        write_json(path, checkpoints)

    def _fix(self, research, strategy, spec: SiteSpec, critique: CritiqueReport) -> SiteSpec:
        fixed = self.fixer_agent.run(research, strategy, spec, critique)
        return self._normalize_sparse_instagram_spec(research, fixed)

    def _normalize_sparse_instagram_spec(self, research, spec: SiteSpec) -> SiteSpec:
        evidence_text = " ".join(
            [research.niche, research.city, research.country, *research.unknowns]
        ).lower()
        is_sparse = any(token in evidence_text for token in ["unknown", "inferred", "likely"])
        if is_sparse:
            return self._sparse_contact_spec(research, spec)
        is_floral = any(
            token in " ".join([research.business_name, research.niche, research.instagram_url]).lower()
            for token in ["fleur", "flor", "flower", "floral"]
        )
        if not (is_sparse and is_floral):
            return spec

        name = re.sub(
            r"\s*\([^)]*(?:inferred|unknown|likely|not verified)[^)]*\)",
            "",
            research.business_name or "",
            flags=re.IGNORECASE,
        ).strip() or "Eliz de Fleur"
        handle = research.instagram_url.rstrip("/").split("/")[-1] or name
        if "_" in name or name.lower() == handle.lower():
            name = handle.replace("_", " ").title()
        spec.language = "en"
        spec.title = f"{name} | Instagram Requests"
        spec.meta_description = (
            f"Message {name} on Instagram to ask for current options, photos, "
            "price, timing, and handoff details."
        )
        spec.h1 = name
        spec.hero_subtitle = (
            "Eliz de Fleur lives on Instagram. Use Direct to ask what is available now, "
            "share a visual mood, and confirm the details before deciding."
        )
        spec.primary_cta = "Ask in Instagram Direct"
        spec.secondary_cta = "View Instagram Profile"
        spec.sections = [
            SectionSpec(
                id="choose-mood",
                title="Start from the profile",
                purpose="Start with the live visuals before sending a request.",
                content=[
                    "Use the live profile for current visuals and style cues.",
                    "Mention colors you prefer, colors to avoid, or a profile post that feels close.",
                    "Add a reference photo in Direct when it helps explain the look.",
                ],
                cta="",
            ),
            SectionSpec(
                id="send-request",
                title="Write one clear message",
                purpose="A clear first message helps the conversation move faster.",
                content=[
                    "Write one message with what you are asking about, the date, and who it is for.",
                    "Ask which options are available now.",
                    "Share a budget range if you want options shaped around it.",
                ],
                cta="Ask in Instagram Direct",
            ),
            SectionSpec(
                id="confirm-details",
                title="Confirm the essentials",
                purpose="Keep the practical details in the same Direct conversation.",
                content=[
                    "Ask for current photos or examples before choosing.",
                    "Confirm price, timing, location, payment, and handoff details in Direct.",
                    "Check whether pickup, delivery, or another handoff option is available.",
                ],
                cta="",
            ),
        ]
        spec.trust_points = [
            "The live Instagram profile is the reference point for current visuals and style.",
            "Direct conversation keeps price, timing, location, and handoff details clear before any decision.",
            "Reference images and color notes help explain the request without assuming a fixed catalog.",
        ]
        spec.process_steps = [
            "View the Instagram profile for the current visual mood.",
            "Send the occasion, date, colors, and any reference image in Direct.",
            "Ask what is available now and confirm price, location, timing, payment, and handoff details.",
        ]
        spec.gallery_assets = [
            asset for asset in spec.gallery_assets if asset.url.startswith(("http://", "https://"))
        ]
        spec.contact_lines = [
            f"Instagram profile: @{handle}",
            "Instagram Direct: ask for current photos, available options, price, timing, location, and handoff details.",
        ]
        spec.footer_note = f"For current options, message {name} on Instagram Direct."
        spec.no_fake_claims_checklist = [
            "No prices, reviews, awards, address, phone, email, hours, delivery area, or fixed catalog are claimed.",
            "Pickup, delivery, payment, and availability are presented only as details to confirm in Direct.",
            "The page uses the verified Instagram profile as the contact path.",
        ]
        return spec

    def _sparse_contact_spec(self, research, spec: SiteSpec) -> SiteSpec:
        """Make missing business data an honest, polished contact bridge."""
        path_parts = [part for part in urlparse(research.instagram_url).path.split("/") if part]
        handle = path_parts[-1] if path_parts else "instagram"
        spec.language = "uk"
        spec.title = f"@{handle} | Instagram Direct"
        spec.meta_description = f"\\u0412\\u0456\\u0434\\u043a\\u0440\\u0438\\u0439\\u0442\\u0435 @{handle} \\u0432 Instagram \\u0456 \\u043d\\u0430\\u043f\\u0438\\u0448\\u0456\\u0442\\u044c \\u0443 Direct, \\u0449\\u043e\\u0431 \\u0443\\u0442\\u043e\\u0447\\u043d\\u0438\\u0442\\u0438 \\u0434\\u0435\\u0442\\u0430\\u043b\\u0456."
        spec.h1 = f"@{handle} \\u2014 \\u0434\\u0435\\u0442\\u0430\\u043b\\u0456 \\u0432 Direct"
        spec.hero_subtitle = (
            f"\\u0412\\u0456\\u0434\\u043a\\u0440\\u0438\\u0439\\u0442\\u0435 @{handle} \\u0432 Instagram \\u0456 \\u043d\\u0430\\u043f\\u0438\\u0448\\u0456\\u0442\\u044c \\u0443 Direct. \\u0423 \\u043f\\u0435\\u0440\\u0435\\u043f\\u0438\\u0441\\u0446\\u0456 \\u043c\\u043e\\u0436\\u043d\\u0430 \\u0443\\u0442\\u043e\\u0447\\u043d\\u0438\\u0442\\u0438 \\u0444\\u043e\\u0440\\u043c\\u0430\\u0442, \\u0434\\u0430\\u0442\\u0443, \\u043b\\u043e\\u043a\\u0430\\u0446\\u0456\\u044e, \\u0443\\u043c\\u043e\\u0432\\u0438 \\u0442\\u0430 \\u0432\\u0430\\u0440\\u0442\\u0456\\u0441\\u0442\\u044c."
        )
        spec.primary_cta = "\\u041d\\u0430\\u043f\\u0438\\u0441\\u0430\\u0442\\u0438 \\u0432 Instagram Direct"
        spec.secondary_cta = "\\u0429\\u043e \\u043d\\u0430\\u043f\\u0438\\u0441\\u0430\\u0442\\u0438 \\u0432 Direct"
        spec.sections = [
            SectionSpec(
                id="message-guide",
                title="\\u041f\\u043e\\u0432\\u0456\\u0434\\u043e\\u043c\\u043b\\u0435\\u043d\\u043d\\u044f \\u0434\\u043b\\u044f Direct",
                purpose="",
                content=[
                    "\\u0414\\u043e\\u0431\\u0440\\u0438\\u0439 \\u0434\\u0435\\u043d\\u044c! \\u041c\\u0435\\u043d\\u0435 \\u0446\\u0456\\u043a\\u0430\\u0432\\u0438\\u0442\\u044c \\u0444\\u043e\\u0440\\u043c\\u0430\\u0442, \\u044f\\u043a\\u0438\\u0439 \\u0432\\u0438 \\u043f\\u0440\\u043e\\u043f\\u043e\\u043d\\u0443\\u0454\\u0442\\u0435 \\u043d\\u0430 [\\u0434\\u0430\\u0442\\u0430]. \\u041f\\u0456\\u0434\\u043a\\u0430\\u0436\\u0456\\u0442\\u044c, \\u0431\\u0443\\u0434\\u044c \\u043b\\u0430\\u0441\\u043a\\u0430, \\u0434\\u0435\\u0442\\u0430\\u043b\\u0456 \\u0442\\u0430 \\u0443\\u043c\\u043e\\u0432\\u0438.",
                    "\\u0414\\u043e\\u0434\\u0430\\u0439\\u0442\\u0435 \\u0437\\u0440\\u0443\\u0447\\u043d\\u0443 \\u043b\\u043e\\u043a\\u0430\\u0446\\u0456\\u044e, \\u043a\\u0456\\u043b\\u044c\\u043a\\u0456\\u0441\\u0442\\u044c \\u0433\\u043e\\u0441\\u0442\\u0435\\u0439 \\u044f\\u043a\\u0449\\u043e \\u0446\\u0435 \\u0434\\u043e\\u0440\\u0435\\u0447\\u043d\\u043e, \\u0442\\u0430 \\u043f\\u0438\\u0442\\u0430\\u043d\\u043d\\u044f \\u0449\\u043e\\u0434\\u043e \\u0432\\u0430\\u0440\\u0442\\u043e\\u0441\\u0442\\u0456.",
                    "\\u0410\\u043a\\u0442\\u0443\\u0430\\u043b\\u044c\\u043d\\u0456 \\u0434\\u0435\\u0442\\u0430\\u043b\\u0456 \\u0443\\u0442\\u043e\\u0447\\u043d\\u044e\\u0439\\u0442\\u0435 \\u0431\\u0435\\u0437\\u043f\\u043e\\u0441\\u0435\\u0440\\u0435\\u0434\\u043d\\u044c\\u043e \\u0432 Direct.",
                ],
            ),
        ]
        spec.trust_points = [
            "",
        ]
        spec.process_steps = [
            "",
        ]
        spec.gallery_assets = []
        spec.contact_lines = [
            f"Instagram: @{handle}",
            "\\u0412\\u0456\\u0434\\u043a\\u0440\\u0438\\u0439\\u0442\\u0435 \\u043f\\u0440\\u043e\\u0444\\u0456\\u043b\\u044c \\u0456 \\u043d\\u0430\\u043f\\u0438\\u0448\\u0456\\u0442\\u044c \\u0443 Direct.",
        ]
        spec.footer_note = "\\u0412\\u0456\\u0434\\u043a\\u0440\\u0438\\u0439\\u0442\\u0435 Instagram-\\u043f\\u0440\\u043e\\u0444\\u0456\\u043b\\u044c \\u0456 \\u043d\\u0430\\u043f\\u0438\\u0448\\u0456\\u0442\\u044c \\u0443 Direct, \\u0449\\u043e\\u0431 \\u0443\\u0442\\u043e\\u0447\\u043d\\u0438\\u0442\\u0438 \\u0434\\u0435\\u0442\\u0430\\u043b\\u0456."
        spec.no_fake_claims_checklist = [
            "Only the supplied Instagram profile is presented as a contact path.",
            "No services, prices, locations, reviews, or availability are claimed.",
        ]
        def decode(value: str) -> str:
            return value.encode("utf-8").decode("unicode_escape")

        for field in (
            "title",
            "meta_description",
            "h1",
            "hero_subtitle",
            "primary_cta",
            "secondary_cta",
            "footer_note",
        ):
            setattr(spec, field, decode(getattr(spec, field)))
        for section in spec.sections:
            section.title = decode(section.title)
            section.purpose = decode(section.purpose)
            section.content = [decode(item) for item in section.content]
        spec.trust_points = [decode(item) for item in spec.trust_points]
        spec.process_steps = [decode(item) for item in spec.process_steps]
        spec.contact_lines = [decode(item) for item in spec.contact_lines]
        return spec

    def _effective_evidence(
        self, reports_dir: Path, research: ResearchBrief, business: dict, *, force: bool = False,
    ) -> EvidenceAssessment:
        """Resolve evidence only; the immutable intake product type owns scope."""
        evidence = self._read_model(reports_dir / "01_evidence_assessment.json", EvidenceAssessment)
        if force or evidence is None or evidence.pipeline_schema_version != PIPELINE_SCHEMA_VERSION:
            evidence = assess_evidence(research)
        return evidence

    @staticmethod
    def _apply_provisional_preview_contract(business: dict, intake: dict, source_url: str) -> dict:
        """Fill safe preview decisions while preserving missing facts as production blockers."""
        payload = dict(business or {})
        research = dict(payload.get("research") or {})
        public_text = " ".join(
            str(value or "") for value in (
                intake.get("title"), intake.get("description"), intake.get("public_text")
            )
        )
        lowered = public_text.lower()
        exact_twenty_years = bool(
            re.search(r"\b20\s*(?:рок(?:ів|и|у)|years?)\b", lowered)
        ) and not bool(
            re.search(r"(?:20\s*\+|понад\s*20|більше\s*20|over\s*20)", lowered)
        )

        def preserve_exact_duration(value):
            """Never promote an exact source duration into a plus/over claim."""
            if not exact_twenty_years:
                return value
            if isinstance(value, dict):
                return {key: preserve_exact_duration(item) for key, item in value.items()}
            if isinstance(value, list):
                return [preserve_exact_duration(item) for item in value]
            if not isinstance(value, str):
                return value
            replacements = (
                (r"\bover\s+20\s+years\b", "20 years"),
                (r"\b20\s*\+\s*years\b", "20 years"),
                (r"понад\s+20\s+років", "20 років"),
                (r"20\s*\+\s*років", "20 років"),
            )
            result = value
            for pattern, replacement in replacements:
                result = re.sub(pattern, replacement, result, flags=re.I)
            return result

        research = preserve_exact_duration(research)
        research["instagram_url"] = source_url
        research["requested_product_type"] = "full_commercial_site"
        research["business_name"] = research.get("business_name") or intake.get("business_name") or "Business"
        if not research.get("primary_language"):
            research["primary_language"] = "uk" if re.search(r"[іїєґІЇЄҐ]", public_text) else "en"
        if not research.get("city") and any(token in lowered for token in ("київ", "kyiv", "kiev")):
            research["city"] = "Київ"
        dental_tokens = {
            "коронки": "Коронки", "імпланти": "Імплантація", "вініри": "Вініри",
            "брекети": "Ортодонтія", "стоматолог": "Стоматологічна допомога", "dental": "Dental care",
        }
        inferred_services = [label for token, label in dental_tokens.items() if token in lowered]
        if not research.get("niche") and inferred_services:
            research["niche"] = "Стоматологічна клініка"
        if not research.get("services_or_products"):
            research["services_or_products"] = list(dict.fromkeys(inferred_services)) or [research.get("niche") or "Business services"]
        if not research.get("sells"):
            research["sells"] = research["services_or_products"][:6]
        if not research.get("contacts"):
            research["contacts"] = [f"Instagram: {source_url}"]
        exact_product = " та ".join(research["services_or_products"][:3])
        if not research.get("product_identity"):
            research["product_identity"] = {
                "exact_product": exact_product,
                "evidence_sources": [source_url],
                "confidence": "high" if inferred_services else "medium",
            }
        themes = list(research.get("content_themes") or [])
        default_themes = (
            ("Послуги та напрямки допомоги", "offer"),
            ("Підхід до консультації та вибору рішення", "process"),
            ("Як зв’язатися й уточнити план", "conversion"),
        )
        known_labels = {str(item.get("label", "")).casefold() for item in themes if isinstance(item, dict)}
        for label, role in default_themes:
            if len(themes) >= 3:
                break
            if label.casefold() not in known_labels:
                themes.append({"label": label, "decision_role": role, "evidence_sources": [source_url]})
        research["content_themes"] = themes
        verified = list(research.get("verified_facts") or [])
        if not verified and (intake.get("title") or intake.get("description")):
            verified.append({
                "source": source_url,
                "value": " | ".join(filter(None, (str(intake.get("title", "")), str(intake.get("description", "")))))[:800],
                "confidence": "high",
            })
        research["verified_facts"] = verified
        blockers = list(research.get("unknowns") or [])
        contacts_text = " ".join(research.get("contacts") or []).lower()
        missing = []
        if not re.search(r"\+?\d[\d\s()\-]{7,}", contacts_text):
            missing.append("phone")
        if "@" not in contacts_text:
            missing.append("email")
        if not research.get("visible_prices_offers"):
            missing.append("public_price_numbers")
        missing.extend(["customer-approved About history", "customer-approved production CTA wording"])
        for item in missing:
            message = f"Production blocker: {item} is not yet customer-confirmed."
            if message not in blockers:
                blockers.append(message)
        research["unknowns"] = blockers
        forbidden = list(research.get("forbidden_claims") or [])
        for claim in (
            "Do not invent prices, discounts, staff, reviews, credentials, outcomes, guarantees, or medical claims.",
            "Preview media is not authorised for customer production or portfolio claims.",
        ):
            if claim not in forbidden:
                forbidden.append(claim)
        if exact_twenty_years:
            duration_rule = "Do not upgrade the verified exact duration of 20 years to over 20 years or 20+."
            if duration_rule not in forbidden:
                forbidden.append(duration_rule)
        research["forbidden_claims"] = forbidden
        provenance = list(research.get("content_provenance") or [])
        if not provenance:
            provenance.extend([
                {"field": "business_identity", "value": research["business_name"], "status": "verified_fact", "sources": [source_url]},
                {"field": "brand_philosophy", "value": "Calm, clear guidance centred on the visitor's next decision.", "status": "inferred_brand_copy", "sources": [source_url]},
                {"field": "faq", "value": "Questions are generated from the confirmed service context; answers avoid unsupported clinical promises.", "status": "generated_demo_content", "sources": [source_url]},
            ])
        for item in missing:
            provenance.append({"field": item, "status": "missing_required_fact", "production_blocker": True, "sources": []})
        research["content_provenance"] = provenance
        payload["research"] = research
        payload["recommended_scope"] = "full_site"
        payload["target_audience"] = payload.get("target_audience") or "People comparing the confirmed services and deciding how to start a conversation."
        payload["buying_context"] = payload.get("buying_context") or "Visitors need service clarity, a credible sense of the business, and a low-friction route to ask about their situation."
        payload["positioning"] = payload.get("positioning") or ["A decision-oriented presentation of the business's confirmed services."]
        payload["customer_questions"] = payload.get("customer_questions") or [
            "Which service direction fits my situation?", "What happens before a final plan is agreed?", "How do I ask about timing and cost?"
        ]
        payload["brand_media_signals"] = payload.get("brand_media_signals") or ["Use exact business-profile media only in the isolated preview."]
        payload["missing_content_manifest"] = [f"production:{item}" for item in missing]
        return payload

    def _job_id(self, instagram_url: str) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        handle = instagram_url.rstrip("/").split("/")[-1] or "instagram"
        handle = re.sub(r"[^a-zA-Z0-9_-]+", "-", handle).strip("-")[:40] or "instagram"
        return f"{stamp}-{handle}"
