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
        return self._inspect_url(index_path.resolve().as_uri(), artifacts_dir)

    def inspect_url(self, url: str, artifacts_dir: Path) -> tuple[TechnicalGate, dict[str, str]]:
        """Inspect a live HTTPS deployment using the same desktop/mobile gate as local builds."""
        if not url.startswith(("https://", "http://", "file://")):
            raise ValueError("Inspection target must be an http(s) URL or file URI.")
        return self._inspect_url(url, artifacts_dir)

    def _inspect_url(self, url: str, artifacts_dir: Path) -> tuple[TechnicalGate, dict[str, str]]:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        console_errors: list[str] = []
        failed_network_requests: list[str] = []
        observations: dict[str, str] = {}

        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                desktop = browser.new_page(viewport={"width": 1440, "height": 1100})
                desktop.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                self._watch_network(desktop, failed_network_requests)
                desktop.goto(url, wait_until="networkidle")
                desktop.screenshot(path=artifacts_dir / "desktop.png", full_page=True)
                desktop_metrics = self._collect_metrics(desktop)
                observations["desktop"] = json.dumps(desktop_metrics, ensure_ascii=False, indent=2)

                mobile = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True)
                mobile.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                self._watch_network(mobile, failed_network_requests)
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
        failed_network_requests = list(dict.fromkeys(failed_network_requests))
        gate = TechnicalGate(
            passed=not (
                horizontal_scroll
                or missing_images
                or console_errors
                or failed_network_requests
                or broken_links
                or small_tap_targets
            ),
            horizontal_scroll=horizontal_scroll,
            missing_images=missing_images,
            console_errors=console_errors,
            failed_network_requests=failed_network_requests,
            broken_links=broken_links,
            small_tap_targets=small_tap_targets,
            notes=[
                f"Desktop viewport: {desktop_metrics['viewport']}",
                f"Mobile viewport: {mobile_metrics['viewport']}",
            ],
        )
        (artifacts_dir / "technical_gate.json").write_text(
            gate.model_dump_json(indent=2), encoding="utf-8"
        )
        (artifacts_dir / "observations.json").write_text(
            json.dumps({"url": url, **observations}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return gate, observations

    def _watch_network(self, page, failures: list[str]) -> None:
        page.on(
            "requestfailed",
            lambda request: failures.append(
                f"{request.method} {request.url} ({request.failure or 'request failed'})"
            ),
        )
        page.on(
            "response",
            lambda response: failures.append(
                f"{response.status} {response.request.method} {response.url}"
            )
            if response.status >= 400
            else None,
        )

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
        public_spec = self._public_site_spec(site_spec)
        return self.llm.structured(
            system=prompts.CRITIC_SYSTEM,
            user=prompts.CRITIC_USER.format(
                research_json=research.model_dump_json(indent=2),
                strategy_json=strategy.model_dump_json(indent=2),
                site_spec_json=public_spec.model_dump_json(indent=2),
                technical_json=technical_gate.model_dump_json(indent=2),
                desktop_observations=observations["desktop"],
                mobile_observations=observations["mobile"],
            ),
            schema=CritiqueReport,
        )

    def _public_site_spec(self, site_spec: SiteSpec) -> SiteSpec:
        public_spec = site_spec.model_copy(deep=True)
        for section in public_spec.sections:
            section.purpose = ""
        public_spec.gallery_assets = [
            asset
            for asset in public_spec.gallery_assets
            if asset.url.startswith(("http://", "https://"))
        ]
        return public_spec
