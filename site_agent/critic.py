from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from playwright.sync_api import Error, sync_playwright

from site_agent.models import CritiqueReport, ResearchBrief, SiteSpec, StrategyBrief, TechnicalGate
from site_agent.design_quality import EvidenceAssessment, assess_studio_readiness
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
                self._take_screenshot(desktop, artifacts_dir / "desktop.png")
                desktop_metrics = self._collect_metrics(desktop)
                observations["desktop"] = json.dumps(desktop_metrics, ensure_ascii=False, indent=2)

                tablet = browser.new_page(viewport={"width": 768, "height": 1024}, is_mobile=True)
                tablet.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                self._watch_network(tablet, failed_network_requests)
                tablet.goto(url, wait_until="networkidle")
                self._take_screenshot(tablet, artifacts_dir / "tablet.png")
                tablet_metrics = self._collect_metrics(tablet)
                observations["tablet"] = json.dumps(tablet_metrics, ensure_ascii=False, indent=2)

                mobile = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True)
                mobile.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                self._watch_network(mobile, failed_network_requests)
                mobile.goto(url, wait_until="networkidle")
                self._take_screenshot(mobile, artifacts_dir / "mobile.png")
                mobile_metrics = self._collect_metrics(mobile)
                observations["mobile"] = json.dumps(mobile_metrics, ensure_ascii=False, indent=2)
            finally:
                browser.close()

        missing_images = list(
            dict.fromkeys(desktop_metrics["missingImages"] + tablet_metrics["missingImages"] + mobile_metrics["missingImages"])
        )
        broken_links = list(dict.fromkeys(desktop_metrics["brokenLinks"] + tablet_metrics["brokenLinks"] + mobile_metrics["brokenLinks"]))
        small_tap_targets = list(
            dict.fromkeys(desktop_metrics["smallTapTargets"] + tablet_metrics["smallTapTargets"] + mobile_metrics["smallTapTargets"])
        )
        horizontal_scroll = bool(desktop_metrics["horizontalScroll"] or tablet_metrics["horizontalScroll"] or mobile_metrics["horizontalScroll"])
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
                f"Tablet viewport: {tablet_metrics['viewport']}",
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

    def _take_screenshot(self, page, path: Path) -> None:
        """Retry a transient Chromium capture failure before failing the quality gate."""
        # Chromium's full-page capture does not always paint below-fold lazy
        # media in a file:// review. Traverse the page once so screenshot-led
        # criticism sees the same authorised proof a visitor can scroll to.
        page.evaluate(
            """async () => {
              const max = Math.max(document.documentElement.scrollHeight, document.body.scrollHeight);
              const step = Math.max(window.innerHeight * 0.8, 320);
              for (let y = 0; y < max; y += step) {
                window.scrollTo(0, y);
                await new Promise(resolve => setTimeout(resolve, 35));
              }
              await Promise.all(Array.from(document.images).map(image => image.complete
                ? Promise.resolve()
                : Promise.race([
                    new Promise(resolve => {
                      image.addEventListener('load', resolve, {once: true});
                      image.addEventListener('error', resolve, {once: true});
                    }),
                    new Promise(resolve => setTimeout(resolve, 1000)),
                  ])
              ));
              window.scrollTo(0, 0);
              await new Promise(resolve => setTimeout(resolve, 120));
            }"""
        )
        last_error: Error | None = None
        for attempt in range(3):
            try:
                page.screenshot(path=path, full_page=True)
                return
            except Error as exc:
                last_error = exc
                if attempt == 2:
                    break
                page.wait_for_timeout(250 * (attempt + 1))
        assert last_error is not None
        raise last_error

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
                  const style = window.getComputedStyle(el);
                  if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) return false;
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
        evidence: EvidenceAssessment | None = None,
    ) -> CritiqueReport:
        technical_gate, observations = self.inspector.inspect(index_path, artifacts_dir)
        public_spec = self._public_site_spec(site_spec)
        scope = evidence or assess_studio_readiness(research)
        return self.llm.structured(
            system=prompts.CRITIC_SYSTEM,
            user=prompts.CRITIC_USER.format(
                research_json=research.model_dump_json(indent=2),
                strategy_json=strategy.model_dump_json(indent=2),
                site_spec_json=public_spec.model_dump_json(indent=2),
                scope_json=json.dumps({
                    "level": scope.level.value,
                    "scope": scope.page_scope.value,
                    "exact_product": scope.exact_product,
                    "required_concepts": scope.required_concepts,
                    "rules": {
                        "micro_site": "Require an offer, real proof/process, and a conversion close. Do not require a gallery, FAQ, team, reviews, certificates, price list, or a longer full-site path.",
                        "full_site": "Require a complete commercial path appropriate to the sourced themes and media.",
                        "blocked": "No site may be approved; evidence is insufficient for creative output.",
                    },
                }, ensure_ascii=False, indent=2),
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
