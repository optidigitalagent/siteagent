from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from site_agent.reference_discovery import (
    AwardPageAdapter,
    DiscoveryCandidate,
    OriginalLiveSiteResolver,
    ReferenceAuditor,
    ReferenceCurator,
    decide_library,
    write_decisions,
)
from site_agent.workflow import WorkflowConfigurationError, selected_references


def analysis() -> dict:
    return {
        "information_architecture": ["offer", "proof", "contact"], "traits": ["editorial storytelling", "calm minimal", "mobile-first conversion"],
        "reusable_cross_category_traits": ["clear first viewport", "media rhythm", "visible CTA"],
        "learn": ["keep CTA visible", "separate proof from offer"], "do_not_copy": ["the exact split hero"],
        "desktop_behavior": "asymmetric editorial hero", "mobile_behavior": "stacked conversion path",
        "first_viewport_logic": "offer with CTA", "cta_strategy": "persistent contact action",
    }


def screenshot(path: Path, color: str) -> str:
    image = Image.new("RGB", (1000 if path.name == "desktop.png" else 700, 1000), color)
    ImageDraw.Draw(image).rectangle((70, 70, 630, 300), fill="#ffffff")
    image.save(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(root: Path, item_id: str, *, final_url: str = "https://example.com/", title: str = "Example") -> dict:
    folder = root / item_id; folder.mkdir(parents=True)
    hashes = {name: screenshot(folder / name, "#234567" if name == "desktop.png" else "#876543") for name in ("desktop.png", "mobile.png")}
    return {"id": item_id, "title": title, "normalized_url": "https://example.com/", "capture_status": "captured", "analysis_status": "completed", "screenshot_paths": list(hashes), "capture": {"final_url": final_url, "screenshots": hashes}, "analysis": analysis()}


class Response:
    def __init__(self, url: str, text: str) -> None:
        self.url, self.text = url, text
    def raise_for_status(self) -> None: pass


class Session:
    def __init__(self, pages: dict[str, str]) -> None: self.pages = pages
    def get(self, url: str, **kwargs): return Response(url, self.pages[url])


class ReferenceDiscoveryTests(unittest.TestCase):
    def test_award_adapter_and_original_resolver_keep_gallery_and_live_urls_separate(self) -> None:
        listing = "https://www.cssdesignawards.com/wotd-award-winners"
        detail = "https://www.cssdesignawards.com/sites/example/"
        session = Session({listing: f'<a href="{detail}">Example studio</a>', detail: '<a href="https://example.com/" title="Visit website">Visit website</a>'})
        adapter = AwardPageAdapter("css_design_awards", listing, "WOTD", 2026)
        candidate = adapter.discover(limit=1, session=session)[0]
        self.assertEqual(candidate.source, "css_design_awards")
        self.assertEqual(candidate.award, "WOTD")
        self.assertEqual(OriginalLiveSiteResolver().resolve(candidate, session=session)["original_url"], "https://example.com/")

    def test_blank_and_redirect_records_are_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            item = record(root, "bad", final_url="https://unrelated.example/")
            Image.new("RGB", (700, 1000), "white").save(root / "bad" / "desktop.png")
            result = decide_library([item], root)["decisions"][0]
            self.assertEqual(result["decision"], "excluded")
            self.assertIn("blank", result["rejection_reasons"])
            self.assertIn("unrelated_redirect", result["rejection_reasons"])

    def test_failed_critical_asset_and_login_wall_are_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            item = record(root, "blocked")
            item["capture"]["failed_critical_assets"] = [{"resource_type": "script", "url": "https://example.com/app.js"}]
            item["analysis"]["business_context"] = "A login wall requires authentication required before the page can be seen."
            result = decide_library([item], root)["decisions"][0]
            self.assertEqual(result["decision"], "excluded")
            self.assertIn("critical_assets_missing", result["rejection_reasons"])
            self.assertIn("login_wall", result["rejection_reasons"])

    def test_near_duplicate_is_automatically_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = record(root, "first")
            second = record(root, "second")
            result = decide_library([first, second], root)
            decisions = {item["reference_id"]: item for item in result["decisions"]}
            self.assertEqual(decisions["first"]["decision"], "active")
            self.assertEqual(decisions["second"]["decision"], "excluded")
            self.assertIn("near_duplicate", decisions["second"]["rejection_reasons"])

    def test_selection_fails_closed_without_three_active_audited_references(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            records = [record(root, f"ref-{index}") for index in range(3)]
            (root / "catalog.json").write_text(json.dumps({"references": records, "decision_artifact": "reference_decisions.json"}), encoding="utf-8")
            (root / "reference_decisions.json").write_text(json.dumps({"decisions": [{"reference_id": "ref-0", "decision": "active", "confidence": 96}]}), encoding="utf-8")
            with self.assertRaisesRegex(WorkflowConfigurationError, "at least three"):
                selected_references(root)

    def test_decision_layer_is_separate_from_raw_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = record(root, "one")
            before = json.dumps(raw, sort_keys=True)
            decisions = write_decisions(root, [raw])
            self.assertTrue((root / "reference_decisions.json").is_file())
            self.assertEqual(json.dumps(raw, sort_keys=True), before)
            self.assertIn("scope_of_learning", decisions["decisions"][0])


if __name__ == "__main__":
    unittest.main()
