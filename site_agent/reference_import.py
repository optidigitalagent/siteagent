"""Resumable screenshot-led importer for the approved reference library."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.sync_api import sync_playwright
from pydantic import BaseModel, Field

from site_agent.config import settings
from site_agent.llm import LLMClient
from site_agent.workflow import checksum

SEED_URLS = (
    "https://optidigitalagent.github.io/eliz-de-fleur-site-20260711095843/", "http://belladentclinik.kr.ua/", "https://optidigitalagent.github.io/orange-beauty-studio/", "https://optidigitalagent.github.io/atmosfera-site/", "https://optidigitalagent.github.io/drivepark/", "https://optidigitalagent.github.io/yourdental1/", "https://optidigitalagent.github.io/yourdental2/", "https://optidigitalagent.github.io/hollywood2/", "https://optidigitalagent.github.io/hollywood1/", "https://optidigitalagent.github.io/kafespeka2/", "https://uniquerabbitstudios.com/", "https://optidigitalagent.github.io/kirkovsky/", "https://newartem855-netizen.github.io/-ZVD/", "https://defolixx.github.io/SunSity/", "https://optidigitalagent.github.io/hereta/", "https://optidigitalagent.github.io/orange2/", "https://optidigitalagent.github.io/orange1/", "https://optidigitalagent.github.io/dentistry_kievskaya2/", "https://optidigitalagent.github.io/dentistry_kievskaya1/", "https://newartem855-netizen.github.io/auratop1/", "https://newartem855-netizen.github.io/Panem-Digital-Agency/", "https://eurozet.ua/", "https://webgoalz.com/", "https://zaffiraxis.github.io/status1/", "https://zaffiraxis.github.io/silk-road-rent-car/index.html#why", "https://zaffiraxis.github.io/margo-salon/", "https://iodent.dental/", "https://parkrestaurant.kyiv.ua/",
)
ANALYSIS_PROMPT_VERSION = "reference-analyst-v1"


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode([(key, value) for key, value in parse_qsl(parts.query) if not key.lower().startswith(("utm_", "fbclid", "gclid"))])
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", query, ""))


def reference_id(url: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", urlsplit(url).netloc + urlsplit(url).path).strip("-")[:80]


class ReferenceAnalysis(BaseModel):
    business_context: str
    audience: str
    conversion_goal: str
    first_viewport_logic: str
    information_architecture: list[str] = Field(min_length=1)
    narrative_storytelling: str
    composition_grid: str
    spacing_rhythm: str
    typography: str
    palette_contrast: str
    media_treatment: str
    motion_interaction: str
    cta_strategy: str
    desktop_behavior: str
    mobile_behavior: str
    learn: list[str] = Field(min_length=1)
    do_not_copy: list[str] = Field(min_length=1)
    reusable_cross_category_traits: list[str] = Field(min_length=3)
    traits: list[str] = Field(min_length=3)


class ScreenshotAnalyst(Protocol):
    def analyze(self, *, desktop: Path, mobile: Path, url: str, title: str) -> tuple[dict[str, Any], dict[str, Any]]: ...


class OpenAIReferenceAnalyst:
    system = """You are the screenshot-led Reference Analyst for a bespoke web studio. Analyse the supplied desktop and mobile captures as visual evidence, not DOM metadata. Fill every field with a concrete observation. Do not use placeholders such as 'requires visual review', 'to be inferred', or 'inspect visible CTA'. References teach transferable principles only: explicitly state what must not be copied."""

    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient(provider=settings.reference_analyst_provider)

    def analyze(self, *, desktop: Path, mobile: Path, url: str, title: str) -> tuple[dict[str, Any], dict[str, Any]]:
        user = f"Reference URL: {url}\nPage title: {title}\nThe first image is desktop and the second is mobile. Return a complete visual analysis."
        analysis = self.llm.multimodal_structured(system=self.system, user=user, image_paths=[desktop, mobile], schema=ReferenceAnalysis)
        output = analysis.model_dump()
        provenance = {"role": "Reference Analyst", "provider": self.llm.provider, "model": self.llm.model, "prompt_version": ANALYSIS_PROMPT_VERSION, "prompt_checksum": checksum({"system": self.system, "user": user}), "input_checksum": checksum({"url": url, "title": title, "desktop_sha256": _file_hash(desktop), "mobile_sha256": _file_hash(mobile)}), "output_checksum": checksum(output), "timestamp": _timestamp(), "used": True}
        return output, provenance


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json_atomic(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


class ReferenceImporter:
    def __init__(self, root: Path = Path("references/site_designs"), *, analyst: ScreenshotAnalyst | None = None, seeds: tuple[str, ...] = SEED_URLS) -> None:
        self.root, self.analyst, self.seeds = root, analyst, seeds

    def run(self) -> dict:
        self.root.mkdir(parents=True, exist_ok=True)
        results = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                for source in self.seeds:
                    results.append(self._import_one(browser, normalize_url(source)))
                    self._checkpoint(results)
            finally:
                browser.close()
        catalog = {"schema_version": 2, "generated_at": _timestamp(), "references": results}
        catalog["catalog_checksum"] = checksum(catalog)
        _write_json_atomic(self.root / "catalog.json", catalog)
        return catalog

    def _checkpoint(self, results: list[dict]) -> None:
        _write_json_atomic(self.root / "import_checkpoints.json", {"schema_version": 1, "updated_at": _timestamp(), "completed": [item.get("id") for item in results if item.get("analysis_status") == "completed"], "failed": [item.get("id") for item in results if item.get("capture_status") == "failed" or item.get("analysis_status") == "failed"]})

    def _complete_and_intact(self, prior: dict, folder: Path) -> bool:
        if prior.get("capture_status") != "captured" or prior.get("analysis_status") != "completed":
            return False
        artifacts = prior.get("capture", {}).get("screenshots", {})
        return all((folder / name).is_file() and _file_hash(folder / name) == digest for name, digest in artifacts.items())

    def _import_one(self, browser, url: str) -> dict:
        folder = self.root / reference_id(url); folder.mkdir(parents=True, exist_ok=True)
        record = folder / "reference.json"
        prior = json.loads(record.read_text(encoding="utf-8")) if record.is_file() else {}
        if self._complete_and_intact(prior, folder):
            return prior
        desktop_path, mobile_path = folder / "desktop.png", folder / "mobile.png"
        try:
            desktop = browser.new_page(viewport={"width": 1440, "height": 1100})
            mobile = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True)
            try:
                desktop.goto(url, wait_until="networkidle", timeout=45_000)
                title = desktop.title() or folder.name
                desktop.screenshot(path=str(desktop_path), full_page=True)
                mobile.goto(url, wait_until="networkidle", timeout=45_000)
                mobile.screenshot(path=str(mobile_path), full_page=True)
                final_url = desktop.url
            finally:
                desktop.close(); mobile.close()
        except Exception as exc:
            result = {"id": folder.name, "title": prior.get("title", folder.name), "source_url": url, "normalized_url": url, "capture_status": "failed", "analysis_status": "not_started", "failure": {"stage": "capture", "message": str(exc)[:500], "timestamp": _timestamp(), "attempt": int(prior.get("failure", {}).get("attempt", 0)) + 1}, "traits": [], "learn": [], "do_not_copy": ["The source is unavailable and cannot be used as a template."]}
            _write_json_atomic(record, result); return result
        capture = {"captured_at": _timestamp(), "final_url": final_url, "screenshots": {"desktop.png": _file_hash(desktop_path), "mobile.png": _file_hash(mobile_path)}, "browser_viewports": {"desktop": [1440, 1100], "mobile": [390, 844]}}
        try:
            analyst = self.analyst or OpenAIReferenceAnalyst()
            analysis, provenance = analyst.analyze(desktop=desktop_path, mobile=mobile_path, url=url, title=title)
            result = {"id": folder.name, "title": title, "source_url": url, "normalized_url": url, "screenshot_paths": ["desktop.png", "mobile.png"], "capture_status": "captured", "analysis_status": "completed", "capture": capture, "analysis": analysis, "analysis_provenance": provenance, **analysis}
            result["content_hash"] = checksum({"capture": capture, "analysis": analysis})
        except Exception as exc:
            result = {"id": folder.name, "title": title, "source_url": url, "normalized_url": url, "screenshot_paths": ["desktop.png", "mobile.png"], "capture_status": "captured", "analysis_status": "failed", "capture": capture, "failure": {"stage": "analysis", "message": str(exc)[:500], "timestamp": _timestamp(), "attempt": int(prior.get("failure", {}).get("attempt", 0)) + 1}, "traits": [], "learn": [], "do_not_copy": ["Captured source must not be selected until screenshot analysis completes."]}
        _write_json_atomic(record, result)
        return result


def main() -> None:
    print(json.dumps(ReferenceImporter().run(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
