from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from site_agent.agents import FixerAgent, ResearchAgent, SiteSpecAgent, StrategyAgent
from site_agent.builder import SiteBuilder
from site_agent.config import settings
from site_agent.critic import CriticAgent
from site_agent.json_io import write_json
from site_agent.llm import LLMClient
from site_agent.models import CritiqueReport, PublishResult, SiteSpec
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
    def __init__(self) -> None:
        llm = LLMClient()
        self.research_agent = ResearchAgent(llm)
        self.strategy_agent = StrategyAgent(llm)
        self.site_spec_agent = SiteSpecAgent(llm)
        self.critic_agent = CriticAgent(llm)
        self.fixer_agent = FixerAgent(llm)
        self.builder = SiteBuilder()
        self.publisher = Publisher()

    def run(self, instagram_url: str) -> JobResult:
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

        spec = self.site_spec_agent.run(research, strategy)
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
                publish = self.publisher.publish(run_dir=run_dir, site_dir=site_dir)
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
        return fixed

    def _job_id(self, instagram_url: str) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        handle = instagram_url.rstrip("/").split("/")[-1] or "instagram"
        handle = re.sub(r"[^a-zA-Z0-9_-]+", "-", handle).strip("-")[:40] or "instagram"
        return f"{stamp}-{handle}"

