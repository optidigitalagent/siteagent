from __future__ import annotations

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
from site_agent.media import MediaInputBlocked, MediaPreparer, authorised_media_assets
from site_agent.models import (
    AcceptanceAuditResult,
    CritiqueReport,
    PublishResult,
    ResearchBrief,
    SiteSpec,
    StrategyBrief,
)
from site_agent.models import SectionSpec
from site_agent.publisher import Publisher
from site_agent.product_director import ProductDirectorAuditor
from site_agent.studio import CodexStudioRunner, StudioError, assert_production_promotion_allowed
from site_agent.workflow import WorkflowConfigurationError, checksum, implementation_package, role_provenance, selected_references, validate_role_providers, write_markdown


class GenerationBlocked(RuntimeError):
    pass


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
    ) -> JobResult | CalibrationResult:
        """Run or resume one job without replacing valid prior checkpoints."""
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
                business = self._read_json(reports_dir / "01_business_research.json")
                if business is None or business.get("research", {}).get("instagram_url") != instagram_url or not (reports_dir / "01_business_research.provenance.json").is_file():
                    if self.research_strategist is None:
                        self.research_strategist = ResearchStrategist(LLMClient(provider=settings.research_strategist_provider))
                    result = self.research_strategist.run(instagram_url)
                    business = result.model_dump()
                    write_json(reports_dir / "01_business_research.json", business)
                    write_markdown(reports_dir / "business_research.md", "Business research", business)
                    write_json(reports_dir / "01_business_research.provenance.json", role_provenance(role="Research Strategist", provider=self.research_strategist.llm.provider, model=self.research_strategist.llm.model, prompt_version="research-strategist-v1", prompt={"role": "research_strategist"}, inputs={"instagram_url": instagram_url}, output=business))
                research = ResearchBrief.model_validate(business["research"])
                write_json(reports_dir / "01_research.json", research)
                self._checkpoint(reports_dir, "research_strategist_completed", "research_completed")
                media_path = run_dir / settings.media_input_dir / "manifest.json"
                media_manifest = self._read_json(reports_dir / "02_authorised_media_manifest.json")
                if media_manifest is None:
                    candidates = self.media_preparer.load_candidates(media_path)
                    media_manifest = self.media_preparer.prepare(candidates, run_dir / "prepared_media")
                    write_json(reports_dir / "02_authorised_media_manifest.json", media_manifest)
                self.media_preparer.validate_manifest(media_manifest)
                # Readiness is based on the actual authorised Cloudinary assets,
                # never the scraped public URL list returned by research.
                research.best_media = authorised_media_assets(media_manifest)
                write_json(reports_dir / "01_research.json", research)
                self._checkpoint(reports_dir, "media_prepared", "media_input_completed")
                evidence = self._effective_evidence(reports_dir, research, business)
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
                package = implementation_package(business_research=business, media_manifest=media_manifest, design_brief=design, references=references)
                write_json(reports_dir / "04_implementation_package.json", package)
                write_json(reports_dir / "04_implementation_package.provenance.json", {"role": "Implementation Package", "input_checksum": checksum(package["input_checksums"]), "output_checksum": package["sha256"], "used": True})
                self._checkpoint(reports_dir, "design_director_completed", "implementation_package_prepared", "generation_completed")
            except (WorkflowConfigurationError, MediaInputBlocked, KeyError, ValueError) as exc:
                self._checkpoint(reports_dir, "media_input_blocked")
                raise GenerationBlocked(str(exc)) from exc
        else:
            research = self._read_model(reports_dir / "01_research.json", ResearchBrief)
            if research is None or research.instagram_url != instagram_url:
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
            critique = self._read_model(
                critiques_dir / f"critique_iteration_{iteration}.json", CritiqueReport
            )
            if critique is None:
                index_path = site_dir / "index.html"
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
                write_json(critiques_dir / f"critique_iteration_{iteration}.json", critique)
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
                )
                write_json(reports_dir / "acceptance_audit.json", acceptance)
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
                publish = self.publisher.publish(
                    run_dir=run_dir,
                    site_dir=site_dir,
                    instagram_url=instagram_url,
                    production=production,
                )
                write_json(reports_dir / "publish_result.json", publish)
                if quality is not None:
                    record_fingerprint(settings.runs_dir / "design_fingerprint_history.json", quality.fingerprint, limit=settings.quality_history_limit)
                self._checkpoint(reports_dir, "deployment_completed")
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
    ) -> JobResult | None:
        """Reuse a delivered-quality build; only publish when deployment is absent."""
        research = self._read_model(reports_dir / "01_research.json", ResearchBrief)
        critique = self._read_model(
            run_dir / "critique_reports" / "critique_iteration_1.json", CritiqueReport
        )
        index_path = site_dir / "index.html"
        if (
            research is None
            or research.instagram_url != instagram_url
            or critique is None
            or not critique.approved_for_delivery
            or not index_path.is_file()
            or index_path.stat().st_size == 0
        ):
            return None

        acceptance = self._read_model(
            reports_dir / "acceptance_audit.json", AcceptanceAuditResult
        )
        if acceptance is None or not acceptance.approved:
            acceptance = self.acceptance_auditor.audit(critique=critique, site_dir=site_dir)
            write_json(reports_dir / "acceptance_audit.json", acceptance)
        if not acceptance.approved:
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

        deployment = self._read_model(run_dir / "deployment.json", PublishResult)
        if deployment is not None and deployment.is_verified_production:
            self._checkpoint(
                reports_dir,
                "research_completed",
                "generation_completed",
                "technical_gate_completed",
                "critics_completed",
                "acceptance_completed",
                "deployment_completed",
            )
            return JobResult(
                job_id=job_id,
                run_dir=run_dir,
                publish=deployment,
                final_score=critique.score,
            )

        publish = self.publisher.publish(
            run_dir=run_dir,
            site_dir=site_dir,
            instagram_url=instagram_url,
            production=production,
        )
        write_json(reports_dir / "publish_result.json", publish)
        self._checkpoint(reports_dir, "acceptance_completed", "deployment_completed")
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

    def _read_json(self, path: Path):
        if not path.is_file() or not path.stat().st_size:
            return None
        try:
            import json
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

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
        self, reports_dir: Path, research: ResearchBrief, business: dict,
    ) -> EvidenceAssessment:
        """Resolve evidence only; the immutable intake product type owns scope."""
        evidence = self._read_model(reports_dir / "01_evidence_assessment.json", EvidenceAssessment)
        if evidence is None or evidence.pipeline_schema_version != PIPELINE_SCHEMA_VERSION:
            evidence = assess_evidence(research)
        return evidence

    def _job_id(self, instagram_url: str) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        handle = instagram_url.rstrip("/").split("/")[-1] or "instagram"
        handle = re.sub(r"[^a-zA-Z0-9_-]+", "-", handle).strip("-")[:40] or "instagram"
        return f"{stamp}-{handle}"
