"""Resumable, non-mutating importer for the approved reference library."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.sync_api import sync_playwright

SEED_URLS = (
    "https://optidigitalagent.github.io/eliz-de-fleur-site-20260711095843/", "http://belladentclinik.kr.ua/", "https://optidigitalagent.github.io/orange-beauty-studio/", "https://optidigitalagent.github.io/atmosfera-site/", "https://optidigitalagent.github.io/drivepark/", "https://optidigitalagent.github.io/yourdental1/", "https://optidigitalagent.github.io/yourdental2/", "https://optidigitalagent.github.io/hollywood2/", "https://optidigitalagent.github.io/hollywood1/", "https://optidigitalagent.github.io/kafespeka2/", "https://uniquerabbitstudios.com/", "https://optidigitalagent.github.io/kirkovsky/", "https://newartem855-netizen.github.io/-ZVD/", "https://defolixx.github.io/SunSity/", "https://optidigitalagent.github.io/hereta/", "https://optidigitalagent.github.io/orange2/", "https://optidigitalagent.github.io/orange1/", "https://optidigitalagent.github.io/dentistry_kievskaya2/", "https://optidigitalagent.github.io/dentistry_kievskaya1/", "https://newartem855-netizen.github.io/auratop1/", "https://newartem855-netizen.github.io/Panem-Digital-Agency/", "https://eurozet.ua/", "https://webgoalz.com/", "https://zaffiraxis.github.io/status1/", "https://zaffiraxis.github.io/silk-road-rent-car/index.html#why", "https://zaffiraxis.github.io/margo-salon/", "https://iodent.dental/", "https://parkrestaurant.kyiv.ua/")

def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode([(key, value) for key, value in parse_qsl(parts.query) if not key.lower().startswith(("utm_", "fbclid", "gclid"))])
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", query, ""))

def reference_id(url: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", urlsplit(url).netloc + urlsplit(url).path).strip("-")[:80]

class ReferenceImporter:
    def __init__(self, root: Path = Path("references/site_designs")) -> None:
        self.root = root

    def run(self) -> dict:
        self.root.mkdir(parents=True, exist_ok=True)
        results = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                for source in SEED_URLS:
                    results.append(self._import_one(browser, normalize_url(source)))
            finally:
                browser.close()
        catalog = {"schema_version": 1, "references": results}
        (self.root / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
        return catalog

    def _import_one(self, browser, url: str) -> dict:
        folder = self.root / reference_id(url)
        record = folder / "reference.json"
        if record.is_file():
            prior = json.loads(record.read_text(encoding="utf-8"))
            if prior.get("capture_status") == "captured":
                return prior
        folder.mkdir(parents=True, exist_ok=True)
        try:
            desktop = browser.new_page(viewport={"width": 1440, "height": 1100})
            desktop.goto(url, wait_until="networkidle", timeout=45_000)
            title = desktop.title()
            desktop.screenshot(path=str(folder / "desktop.png"), full_page=True)
            mobile = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True)
            mobile.goto(url, wait_until="networkidle", timeout=45_000)
            mobile.screenshot(path=str(folder / "mobile.png"), full_page=True)
            structure = desktop.evaluate("""() => ({
              headings: [...document.querySelectorAll('h1,h2,h3')].slice(0, 12).map(node => node.textContent.trim()).filter(Boolean),
              links: [...document.querySelectorAll('a')].slice(0, 30).map(node => node.textContent.trim()).filter(Boolean),
              image_count: document.images.length,
              section_count: document.querySelectorAll('section, main > div, article').length,
              has_video: Boolean(document.querySelector('video'))
            })""")
            traits = ["media-led" if structure["image_count"] >= 4 else "copy-led", "dense" if structure["section_count"] >= 6 else "focused"]
            if structure["has_video"]:
                traits.append("motion-capable")
            record_data = {
                "id": folder.name, "title": title or folder.name, "source_url": url,
                "normalized_url": url, "screenshot_paths": ["desktop.png", "mobile.png"],
                "business_context": "Captured reference; classify commercially before use.",
                "audience": "To be inferred from verified public content.",
                "conversion_goal": "Inspect visible calls to action before selecting traits.",
                "first_viewport": {"headings": structure["headings"][:3], "calls_to_action": structure["links"][:5]},
                "composition": {"section_count": structure["section_count"], "image_count": structure["image_count"]},
                "narrative": "Derived from captured heading order; never copied.",
                "typography": "Requires visual review of captured screenshots.",
                "palette_contrast": "Requires visual review of captured screenshots.",
                "media_treatment": "video" if structure["has_video"] else "static/mixed",
                "interaction": "Requires browser inspection.", "mobile_behavior": "Captured in mobile.png.",
                "traits": traits, "search_text": " ".join(traits + structure["headings"]),
                "learn": ["Use only the recorded trait combination, not the source layout."],
                "do_not_copy": ["This source is reference material, never a template."],
                "capture_status": "captured", "content_hash": hashlib.sha256((title + url).encode()).hexdigest(),
            }
            desktop.close(); mobile.close()
        except Exception as exc:
            record_data = {"id": folder.name, "title": folder.name, "source_url": url, "traits": [], "learn": [], "do_not_copy": ["This source is reference material, never a template."], "capture_status": "failed", "error": str(exc)[:500]}
        record.write_text(json.dumps(record_data, ensure_ascii=False, indent=2), encoding="utf-8")
        return record_data

def main() -> None:
    print(json.dumps(ReferenceImporter().run(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
