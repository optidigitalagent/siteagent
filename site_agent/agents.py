from __future__ import annotations

from site_agent.instagram import InstagramScraper
from site_agent.llm import LLMClient
from site_agent.models import BusinessResearch, CritiqueReport, DesignImplementationBrief, MediaAsset, ResearchBrief, SiteSpec, StrategyBrief
from site_agent import prompts


class ResearchAgent:
    def __init__(self, llm: LLMClient, scraper: InstagramScraper | None = None) -> None:
        self.llm = llm
        self.scraper = scraper or InstagramScraper()

    def run(self, instagram_url: str) -> ResearchBrief:
        scraped = self.scraper.fetch(instagram_url)
        brief = self.llm.structured(
            system=prompts.RESEARCH_SYSTEM,
            user=prompts.RESEARCH_USER.format(
                instagram_url=instagram_url,
                scraped_context=scraped.to_context(),
            ),
            schema=ResearchBrief,
        )
        if scraped.image_urls and not brief.best_media:
            brief.best_media = [
                MediaAsset(url=url, kind="image", alt=brief.business_name, recommended_use="gallery")
                for url in scraped.image_urls[:8]
            ]
        return brief


class ResearchStrategist:
    """New research plane. It owns the rich cited artifact, not page design."""

    def __init__(self, llm: LLMClient, scraper: InstagramScraper | None = None) -> None:
        self.llm = llm
        self.scraper = scraper or InstagramScraper()

    def run(self, instagram_url: str) -> BusinessResearch:
        scraped = self.scraper.fetch(instagram_url)
        return self.llm.structured(
            system=prompts.RESEARCH_STRATEGIST_SYSTEM,
            user=prompts.RESEARCH_STRATEGIST_USER.format(
                instagram_url=instagram_url, scraped_context=scraped.to_context()
            ),
            schema=BusinessResearch,
        )


class DesignDirector:
    """Independent art-direction plane; Codex receives its completed package."""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def run(self, research: BusinessResearch, media_manifest: dict, references: list[dict]) -> DesignImplementationBrief:
        return self.llm.structured(
            system=prompts.DESIGN_DIRECTOR_SYSTEM,
            user=prompts.DESIGN_DIRECTOR_USER.format(
                research_json=research.model_dump_json(indent=2),
                media_json=__import__("json").dumps(media_manifest, ensure_ascii=False, indent=2),
                references_json=__import__("json").dumps(references, ensure_ascii=False, indent=2),
            ),
            schema=DesignImplementationBrief,
        )


class StrategyAgent:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def run(self, research: ResearchBrief) -> StrategyBrief:
        return self.llm.structured(
            system=prompts.STRATEGY_SYSTEM,
            user=prompts.STRATEGY_USER.format(research_json=research.model_dump_json(indent=2)),
            schema=StrategyBrief,
        )


class SiteSpecAgent:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def run(self, research: ResearchBrief, strategy: StrategyBrief, design_guidance: str = "") -> SiteSpec:
        return self.llm.structured(
            system=prompts.SITE_SPEC_SYSTEM,
            user=prompts.SITE_SPEC_USER.format(
                research_json=research.model_dump_json(indent=2),
                strategy_json=strategy.model_dump_json(indent=2),
                design_guidance=design_guidance,
            ),
            schema=SiteSpec,
        )


class FixerAgent:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def run(
        self,
        research: ResearchBrief,
        strategy: StrategyBrief,
        site_spec: SiteSpec,
        critique: CritiqueReport,
    ) -> SiteSpec:
        return self.llm.structured(
            system=prompts.FIXER_SYSTEM,
            user=prompts.FIXER_USER.format(
                research_json=research.model_dump_json(indent=2),
                strategy_json=strategy.model_dump_json(indent=2),
                site_spec_json=site_spec.model_dump_json(indent=2),
                critique_json=critique.model_dump_json(indent=2),
            ),
            schema=SiteSpec,
        )
