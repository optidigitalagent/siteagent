from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from site_agent.acceptance import AcceptanceAuditor
from site_agent.agents import FixerAgent, ResearchAgent, SiteSpecAgent, StrategyAgent
from site_agent.builder import SiteBuilder
from site_agent.config import settings
from site_agent.critic import CriticAgent
from site_agent.json_io import write_json
from site_agent.llm import LLMClient
from site_agent.models import CritiqueReport, PublishResult, SiteSpec
from site_agent.models import SectionSpec
from site_agent.publisher import Publisher


class GenerationBlocked(RuntimeError):
    pass


@dataclass
class JobResult:
    job_id: str
    run_dir: Path
    publish: PublishResult
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

    def run(self, instagram_url: str, *, production: bool = False) -> JobResult:
        job_id = self._job_id(instagram_url)
        run_dir = settings.runs_dir / job_id
        reports_dir = run_dir / "generation_reports"
        critiques_dir = run_dir / "critique_reports"
        site_dir = run_dir / "site"
        reports_dir.mkdir(parents=True, exist_ok=True)
        critiques_dir.mkdir(parents=True, exist_ok=True)

        research = self.research_agent.run(instagram_url)
        write_json(reports_dir / "01_research.json", research)

        strategy = self.strategy_agent.run(research)
        write_json(reports_dir / "02_strategy.json", strategy)

        spec = self._normalize_sparse_instagram_spec(
            research,
            self.site_spec_agent.run(research, strategy),
        )
        write_json(reports_dir / "03_site_spec_initial.json", spec)

        final_critique: CritiqueReport | None = None
        for iteration in range(1, settings.max_fix_iterations + 1):
            index_path = self.builder.build(
                site_dir=site_dir,
                research=research,
                strategy=strategy,
                spec=spec,
            )
            write_json(reports_dir / f"site_spec_iteration_{iteration}.json", spec)
            critique = self.critic_agent.run(
                index_path=index_path,
                artifacts_dir=critiques_dir / f"iteration_{iteration}",
                research=research,
                strategy=strategy,
                site_spec=spec,
            )
            write_json(critiques_dir / f"critique_iteration_{iteration}.json", critique)
            final_critique = critique
            if critique.approved_for_delivery:
                acceptance = self.acceptance_auditor.audit(
                    critique=critique,
                    site_dir=site_dir,
                )
                write_json(reports_dir / "acceptance_audit.json", acceptance)
                if not acceptance.approved:
                    raise GenerationBlocked(
                        "Acceptance audit blocked deployment: " + "; ".join(acceptance.reasons)
                    )
                publish = self.publisher.publish(
                    run_dir=run_dir,
                    site_dir=site_dir,
                    instagram_url=instagram_url,
                    production=production,
                )
                write_json(reports_dir / "publish_result.json", publish)
                return JobResult(
                    job_id=job_id,
                    run_dir=run_dir,
                    publish=publish,
                    final_score=critique.score,
                )
            spec = self._fix(research, strategy, spec, critique)

        assert final_critique is not None
        raise GenerationBlocked(
            "Final site did not pass quality gate: "
            f"score={final_critique.score}, "
            f"technical_gate={final_critique.technical_gate.passed}, "
            f"blocking_issues={final_critique.has_blocking_issues}"
        )

    def _fix(self, research, strategy, spec: SiteSpec, critique: CritiqueReport) -> SiteSpec:
        fixed = self.fixer_agent.run(research, strategy, spec, critique)
        return self._normalize_sparse_instagram_spec(research, fixed)

    def _normalize_sparse_instagram_spec(self, research, spec: SiteSpec) -> SiteSpec:
        evidence_text = " ".join(
            [research.niche, research.city, research.country, *research.unknowns]
        ).lower()
        is_sparse = any(token in evidence_text for token in ["unknown", "inferred", "likely"])
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

    def _job_id(self, instagram_url: str) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        handle = instagram_url.rstrip("/").split("/")[-1] or "instagram"
        handle = re.sub(r"[^a-zA-Z0-9_-]+", "-", handle).strip("-")[:40] or "instagram"
        return f"{stamp}-{handle}"
