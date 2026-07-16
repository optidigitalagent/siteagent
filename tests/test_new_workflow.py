from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from site_agent.media import CloudinaryUploader, MediaCandidate, MediaInputBlocked, MediaPreparer
from site_agent.reference_import import normalize_url, reference_id
from site_agent.workflow import WorkflowConfigurationError, implementation_package, selected_references, validate_role_providers
from site_agent.config import Settings


class FakeUploader:
    def upload(self, path: Path, *, public_id: str) -> str:
        return f"https://res.cloudinary.com/siteagent/image/upload/{public_id}.jpg"


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


if __name__ == "__main__":
    unittest.main()
