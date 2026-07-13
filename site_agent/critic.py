from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from playwright.sync_api import sync_playwright

from site_agent.models import CritiqueReport, ResearchBrief, SiteSpec, StrategyBrief, TechnicalGate
from site_agent import prompts

if TYPE_CHECKING:
    from site_agent.llm import LLMClient


class TechnicalInspector:
    def inspect(self, index_path: Path, artifacts_dir: Path) -> tuple[TechnicalGate, dict[str, str]]:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        url = index_path.resolve().as_uri()
        console_errors: list[str] = []
        observations: dict[str, str] = {}

        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                desktop = browser.new_page(viewport={"width": 1440, "height": 1100})
                desktop.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                desktop.goto(url, wait_until="networkidle")
                desktop.screenshot(path=artifacts_dir / "desktop.png", full_page=True)
                desktop_metrics = self._collect_metrics(desktop)
                observations["desktop"] = json.dumps(desktop_metrics, ensure_ascii=False, indent=2)

                mobile = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True)
                mobile.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                mobile.goto(url, wait_until="networkidle")
                mobile.screenshot(path=artifacts_dir / "mobile.png", full_page=True)
                mobile_metrics = self._collect_metrics(mobile)
                observations["mobile"] = json.dumps(mobile_metrics, ensure_ascii=False, indent=2)
            finally:
                browser.close()

        missing_images = list(
            dict.fromkeys(desktop_metrics["missingImages"] + mobile_metrics["missingImages"])
        )
        broken_links = list(dict.fromkeys(desktop_metrics["brokenLinks"] + mobile_metrics["brokenLinks"]))
        small_tap_targets = list(
            dict.fromkeys(desktop_metrics["smallTapTargets"] + mobile_metrics["smallTapTargets"])
        )
        horizontal_scroll = bool(desktop_metrics["horizontalScroll"] or mobile_metrics["horizontalScroll"])
        gate = TechnicalGate(
            passed=not (horizontal_scroll or missing_images or console_errors or broken_links or small_tap_targets),
            horizontal_scroll=horizontal_scroll,
            missing_images=missing_images,
            console_errors=console_errors,
            broken_links=broken_links,
            small_tap_targets=small_tap_targets,
            notes=[
                f"Desktop viewport: {desktop_metrics['viewport']}",
                f"Mobile viewport: {mobile_metrics['viewport']}",
            ],
        )
        return gate, observations

    def _collect_metrics(self, page):
        return page.evaluate(
            """
            () => {
              const doc = document.documentElement;
              const body = document.body;
              const horizontalScroll = doc.scrollWidth > doc.clientWidth + 1 || body.scrollWidth > body.clientWidth + 1;
              const missingImages = Array.from(document.images)
                .filter(img => !img.complete || img.naturalWidth === 0)
                .map(img => img.currentSrc || img.src || img.alt || "unknown image");
              const brokenLinks = Array.from(document.querySelectorAll("a[href]"))
                .map(a => a.getAttribute("href"))
                .filter(href => !href || href === "#" || href.startsWith("javascript:"));
              const smallTapTargets = Array.from(document.querySelectorAll("a, button"))
                .filter(el => {
                  const r = el.getBoundingClientRect();
                  return r.width < 44 || r.height < 44;
                })
                .map(el => (el.textContent || el.getAttribute("aria-label") || el.tagName).trim().slice(0, 80));
              const headings = Array.from(document.querySelectorAll("h1,h2")).map(h => h.textContent.trim());
              const buttons = Array.from(document.querySelectorAll("a.btn,button")).map(b => b.textContent.trim());
              const sectionIds = Array.from(document.querySelectorAll("main section")).map(s => s.id || s.className || "section");
              return {
                viewport: `${window.innerWidth}x${window.innerHeight}`,
                scrollWidth: doc.scrollWidth,
                clientWidth: doc.clientWidth,
                horizontalScroll,
                missingImages,
                brokenLinks,
                smallTapTargets,
                headings,
                buttons,
                sectionIds,
                bodyTextSample: document.body.innerText.replace(/\\s+/g, " ").trim().slice(0, 1800)
              };
            }
            """
        )


class CriticAgent:
    def __init__(self, llm: "LLMClient", inspector: TechnicalInspector | None = None) -> None:
        self.llm = llm
        self.inspector = inspector or TechnicalInspector()

    def run(
        self,
        *,
        index_path: Path,
        artifacts_dir: Path,
        research: ResearchBrief,
        strategy: StrategyBrief,
        site_spec: SiteSpec,
    ) -> CritiqueReport:
        technical_gate, observations = self.inspector.inspect(index_path, artifacts_dir)
        return self.llm.structured(
            system=prompts.CRITIC_SYSTEM,
            user=prompts.CRITIC_USER.format(
                research_json=research.model_dump_json(indent=2),
                strategy_json=strategy.model_dump_json(indent=2),
                site_spec_json=site_spec.model_dump_json(indent=2),
                technical_json=technical_gate.model_dump_json(indent=2),
                desktop_observations=observations["desktop"],
                mobile_observations=observations["mobile"],
            ),
            schema=CritiqueReport,
        )
