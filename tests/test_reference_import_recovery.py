from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from site_agent.llm import LLMClient, StructuredOutputError
from site_agent.reference_import import ReferenceAnalysis, ReferenceImporter


def valid_analysis() -> dict:
    return {
        "business_context": "boutique hospitality", "audience": "design-conscious travellers",
        "conversion_goal": "request a booking", "first_viewport_logic": "offer and booking action",
        "information_architecture": ["arrival", "rooms", "booking"],
        "narrative_storytelling": "arrival to reservation", "composition_grid": "asymmetric editorial grid",
        "spacing_rhythm": "generous pauses", "typography": "serif display with quiet sans",
        "palette_contrast": "warm neutral contrast", "media_treatment": "full-bleed room photography",
        "motion_interaction": "subtle hover reveals", "cta_strategy": "persistent booking action",
        "desktop_behavior": "split hero", "mobile_behavior": "stacked booking path",
        "learn": ["make booking visible"], "do_not_copy": ["do not copy split hero"],
        "reusable_cross_category_traits": ["clear CTA", "media rhythm", "quiet type"],
        "traits": ["editorial", "conversion-led", "media-led"],
    }


class RecordingAnalyst:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    def analyze(self, **kwargs):
        self.calls += 1
        if self.fail:
            raise RuntimeError("model produced incomplete analysis")
        return valid_analysis(), {"provider": "test", "model": "test", "used": True}


class FakePage:
    def __init__(self, label: str) -> None:
        self.label = label
        self.url = f"https://example.com/{label}"
        self.closed = False

    def goto(self, *args, **kwargs) -> None:
        return None

    def title(self) -> str:
        return f"Reference {self.label}"

    def screenshot(self, *, path: str, **kwargs) -> None:
        Image.new("RGB", (1200, 800), "#446688").save(path)

    def close(self) -> None:
        self.closed = True


class FakeBrowser:
    def __init__(self, *, disconnect_at_new_page: int | None = None, close_error: bool = False) -> None:
        self.new_page_calls = 0
        self.disconnect_at_new_page = disconnect_at_new_page
        self.close_error = close_error

    def new_page(self, **kwargs):
        self.new_page_calls += 1
        if self.new_page_calls == self.disconnect_at_new_page:
            raise RuntimeError("Connection closed while reading from the driver")
        return FakePage(str(self.new_page_calls))

    def close(self) -> None:
        if self.close_error:
            raise RuntimeError("Connection closed while reading from the driver")


class FakePlaywrightContext:
    def __init__(self, browsers: list[FakeBrowser]) -> None:
        self.browsers = browsers
        self.chromium = SimpleNamespace(launch=self.launch)
        self.launches = 0

    def launch(self):
        self.launches += 1
        return self.browsers.pop(0)

    def __enter__(self):
        return self

    def __exit__(self, *args) -> bool:
        return False


class FakeCompletions:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.responses.pop(0)))])


def fake_llm(responses: list[str]) -> tuple[LLMClient, FakeCompletions]:
    completions = FakeCompletions(responses)
    llm = LLMClient.__new__(LLMClient)
    llm.provider = "openai"
    llm.model = "test-model"
    llm.client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return llm, completions


class ReferenceImportRecoveryTests(unittest.TestCase):
    def test_browser_close_error_keeps_completed_record_and_finalizes_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            context = FakePlaywrightContext([FakeBrowser(close_error=True)])
            with patch("site_agent.reference_import.sync_playwright", return_value=context):
                catalog = ReferenceImporter(root, analyst=RecordingAnalyst(), seeds=("https://example.com/",)).run()
            self.assertEqual(catalog["references"][0]["analysis_status"], "completed")
            self.assertTrue((root / "catalog.json").is_file())
            report = json.loads((root / "import_report.json").read_text(encoding="utf-8"))
            self.assertIn("browser_close", [warning["stage"] for warning in report["cleanup_warnings"]])

    def test_browser_disconnect_restarts_and_resumes_same_unfinished_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            context = FakePlaywrightContext([FakeBrowser(disconnect_at_new_page=3), FakeBrowser()])
            with patch("site_agent.reference_import.sync_playwright", return_value=context):
                catalog = ReferenceImporter(
                    root, analyst=RecordingAnalyst(), seeds=("https://example.com/a", "https://example.com/b"), max_browser_restarts=2
                ).run()
            self.assertEqual(context.launches, 2)
            self.assertEqual(len(catalog["completed"]), 2)
            self.assertEqual(catalog["browser_restart_counts"]["example-com-b"], 1)

    def test_failed_analysis_reuses_intact_screenshots_and_completed_record_is_not_reanalysed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            failing = RecordingAnalyst(fail=True)
            importer = ReferenceImporter(root, analyst=failing, seeds=())
            first = importer._import_one(FakeBrowser(), "https://example.com/")
            self.assertEqual(first["analysis_status"], "failed")
            desktop = root / "example-com" / "desktop.png"
            original_hash = first["capture"]["screenshots"]["desktop.png"]
            succeeding = RecordingAnalyst()
            retried = ReferenceImporter(root, analyst=succeeding, seeds=())._import_one(None, "https://example.com/")
            self.assertEqual(retried["analysis_status"], "completed")
            self.assertEqual(retried["capture"]["screenshots"]["desktop.png"], original_hash)
            self.assertEqual(succeeding.calls, 1)
            never_called = RecordingAnalyst(fail=True)
            completed = ReferenceImporter(root, analyst=never_called, seeds=())._import_one(None, "https://example.com/")
            self.assertEqual(completed["analysis_status"], "completed")
            self.assertEqual(never_called.calls, 0)
            self.assertTrue(desktop.is_file())

    def test_strict_schema_repair_retry_uses_exact_schema_and_accepts_corrected_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp) / "capture.png"
            Image.new("RGB", (32, 32), "#223344").save(image)
            llm, completions = fake_llm([json.dumps({"pageTitle": "wrong"}), json.dumps(valid_analysis())])
            result = llm.multimodal_structured_with_debug(
                system="system", user="user", image_paths=[image], schema=ReferenceAnalysis, max_repair_attempts=1
            )
            self.assertEqual(result.value.business_context, "boutique hospitality")
            self.assertEqual(result.repair_count, 1)
            self.assertEqual(len(completions.calls), 2)
            schema = completions.calls[0]["response_format"]["json_schema"]["schema"]
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(completions.calls[0]["response_format"]["json_schema"]["name"], "ReferenceAnalysis")
            self.assertIn("previous response failed Pydantic validation", completions.calls[1]["messages"][1]["content"][0]["text"])

    def test_invalid_structured_response_remains_failed_after_bounded_retries(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp) / "capture.png"
            Image.new("RGB", (32, 32), "#223344").save(image)
            llm, completions = fake_llm([json.dumps({"pageTitle": "wrong"}), json.dumps({"referenceURL": "wrong"})])
            with self.assertRaises(StructuredOutputError) as raised:
                llm.multimodal_structured_with_debug(
                    system="system", user="user", image_paths=[image], schema=ReferenceAnalysis, max_repair_attempts=1
                )
            self.assertEqual(len(completions.calls), 2)
            self.assertEqual(len(raised.exception.responses), 2)
            self.assertEqual(raised.exception.repair_count, 1)

    def test_catalog_finalization_survives_cleanup_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            context = FakePlaywrightContext([FakeBrowser(close_error=True)])
            with patch("site_agent.reference_import.sync_playwright", return_value=context):
                ReferenceImporter(root, analyst=RecordingAnalyst(), seeds=("https://example.com/",)).run()
            catalog = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
            self.assertEqual(len(catalog["references"]), 1)
            self.assertEqual(catalog["references"][0]["analysis_status"], "completed")


if __name__ == "__main__":
    unittest.main()
