from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from site_agent.media import CloudinaryUploader, MediaCandidate, MediaInputBlocked, MediaPreparer
from site_agent.reference_import import ReferenceImporter, normalize_url, reference_id
from site_agent.workflow import WorkflowConfigurationError, implementation_package, selected_references, validate_role_providers, write_markdown
from site_agent.config import Settings


class FakeUploader:
    def upload(self, path: Path, *, public_id: str) -> str:
        return f"https://res.cloudinary.com/siteagent/image/upload/{public_id}.jpg"


class FakePage:
    url = "https://example.com/final"
    def goto(self, *args, **kwargs): pass
    def title(self): return "Reference"
    def screenshot(self, *, path, **kwargs): Image.new("RGB", (1200, 800), "#446688").save(path)
    def close(self): pass


class FakeBrowser:
    def new_page(self, **kwargs): return FakePage()


class FakeReferenceAnalyst:
    def analyze(self, **kwargs):
        return ({"business_context": "boutique hospitality", "audience": "design-conscious travellers", "conversion_goal": "request a booking", "first_viewport_logic": "offer, location and booking action", "information_architecture": ["arrival", "rooms", "booking"], "narrative_storytelling": "arrival to reservation", "composition_grid": "asymmetric editorial grid", "spacing_rhythm": "generous pauses", "typography": "serif display with quiet sans", "palette_contrast": "warm neutral contrast", "media_treatment": "full-bleed room photography", "motion_interaction": "subtle hover reveals", "cta_strategy": "persistent booking action", "desktop_behavior": "split hero", "mobile_behavior": "stacked booking path", "learn": ["make booking visible"], "do_not_copy": ["do not copy split hero"], "reusable_cross_category_traits": ["clear CTA", "media rhythm", "quiet type"], "traits": ["editorial", "conversion-led", "media-led"]}, {"provider": "openai", "model": "test", "prompt_version": "test", "prompt_checksum": "a", "input_checksum": "b", "output_checksum": "c", "timestamp": "now", "used": True})


class NewWorkflowContractTests(unittest.TestCase):
    def test_reference_normalization_removes_tracking_and_fragment(self) -> None:
        normalized = normalize_url("HTTPS://Example.COM/path?utm_source=x&keep=yes#hero")
        self.assertEqual(normalized, "https://example.com/path?keep=yes")
        self.assertEqual(reference_id(normalized), "example-com-path")

    def test_selected_references_requires_three_captured_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "catalog.json").write_text(json.dumps({"references": [{"capture_status": "captured"}] * 2}), encoding="utf-8")
            with self.assertRaisesRegex(WorkflowConfigurationError, "at least three"):
                selected_references(root)

    def test_reference_ranking_scores_entire_catalog_not_first_six(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            records = []
            for index in range(7):
                records.append({"id": f"ref-{index}", "capture_status": "captured", "analysis_status": "completed", "screenshot_paths": ["desktop.png", "mobile.png"], "traits": ["generic"], "search_text": "generic", "business_context": "generic"})
            records[-1].update({"traits": ["cinematic", "conversion-led", "gallery-rhythm"], "search_text": "cinematic conversion-led gallery-rhythm private dining", "business_context": "private dining"})
            (root / "catalog.json").write_text(json.dumps({"references": records}), encoding="utf-8")
            selected = selected_references(root, business_research={"research": {"niche": "private dining", "brand_atmosphere": "cinematic"}})
            self.assertEqual(selected[0]["id"], "ref-6")
            self.assertIn("selection_rationale", selected[0])

    def test_reference_import_persists_screenshot_analysis_and_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = ReferenceImporter(root, analyst=FakeReferenceAnalyst(), seeds=())._import_one(FakeBrowser(), "https://example.com/")
            self.assertEqual(result["analysis_status"], "completed")
            self.assertTrue((root / "example-com" / "desktop.png").is_file())
            self.assertEqual(result["analysis_provenance"]["provider"], "openai")
            self.assertNotIn("Requires visual review", json.dumps(result))

    def test_authorised_media_is_deduplicated_and_receives_cloudinary_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / "original.png"
            Image.new("RGB", (1200, 800), "#123456").save(source)
            manifest = MediaPreparer(uploader=FakeUploader()).prepare([
                MediaCandidate(source, user_authorized=True, allowed_for_public_site=True),
                MediaCandidate(source, user_authorized=True, allowed_for_public_site=True),
            ], root / "prepared")
            self.assertEqual(manifest["deduplicated_count"], 1)
            media = manifest["media"][0]
            self.assertTrue(media["url"].startswith("https://res.cloudinary.com/"))
            self.assertTrue(media["user_authorized"])
            self.assertEqual(media["source_kind"], "business")
            self.assertTrue((root / "prepared" / "preview_contact_sheet.jpg").is_file())

    def test_ambiguous_instagram_chrome_is_not_destructively_cropped(self) -> None:
        image = Image.new("RGB", (1200, 900), "#888888")
        crop = MediaPreparer._instagram_crop(image)
        self.assertIsNone(crop["coordinates"])
        self.assertFalse(crop["manual_review_required"])

    def test_existing_authorised_cloudinary_asset_is_reused(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config = Settings(_env_file=None, CLOUDINARY_CLOUD_NAME="siteagent")
            manifest = MediaPreparer(config=config).prepare([MediaCandidate(existing_cloudinary_url="https://res.cloudinary.com/siteagent/image/upload/v1/existing.jpg", user_authorized=True, allowed_for_public_site=True, business_id="orange", original_origin="client Cloudinary library")], Path(temp))
            self.assertEqual(manifest["media"][0]["cloudinary_version"], "existing")
            self.assertEqual(manifest["media"][0]["url"], "https://res.cloudinary.com/siteagent/image/upload/v1/existing.jpg")

    def test_media_rejects_unapproved_or_missing_input_before_design(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "original.png"; Image.new("RGB", (600, 600)).save(source)
            with self.assertRaisesRegex(MediaInputBlocked, "user_authorized"):
                MediaPreparer(uploader=FakeUploader()).prepare([MediaCandidate(source)], Path(temp) / "prepared")

    def test_provider_contract_has_explicit_defaults_and_rejects_drift(self) -> None:
        config = Settings(_env_file=None, RESEARCH_STRATEGIST_PROVIDER="openai", DESIGN_DIRECTOR_PROVIDER="openai", SITE_BUILDER_PROVIDER="codex")
        validate_role_providers(config)
        bad = Settings(_env_file=None, RESEARCH_STRATEGIST_PROVIDER="codex", DESIGN_DIRECTOR_PROVIDER="openai", SITE_BUILDER_PROVIDER="codex")
        with self.assertRaisesRegex(WorkflowConfigurationError, "RESEARCH_STRATEGIST_PROVIDER"):
            validate_role_providers(bad)

    def test_implementation_package_is_checksummed_and_contains_no_template_instruction(self) -> None:
        package = implementation_package(
            business_research={"research": {"business_name": "Orange"}}, media_manifest={"media": []},
            design_brief={"central_idea": "a specific studio visit"}, references=[{"id": "one"}],
        )
        self.assertEqual(len(package["sha256"]), 64)
        self.assertTrue(package["acceptance_contract"]["no_reference_copying"])

    def test_workflow_markdown_is_a_readable_handoff_not_json_fence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "business_research.md"
            write_markdown(path, "Business research", {"research": {"business_name": "Orange", "product_identity": {"exact_product": "colour services"}, "primary_language": "uk", "verified_facts": [{"source": "bio", "value": "Kyiv"}]}, "recommended_scope": "micro_site"})
            value = path.read_text(encoding="utf-8")
            self.assertIn("## Business identity", value)
            self.assertNotIn("```json", value)


if __name__ == "__main__":
    unittest.main()
