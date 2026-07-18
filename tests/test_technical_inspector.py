from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from site_agent.critic import TechnicalInspector


class TechnicalInspectorTests(unittest.TestCase):
    def test_hidden_mobile_call_is_not_a_small_tap_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            page = Path(temp) / "index.html"
            page.write_text("<style>.mobile-call{display:none}</style><a class='mobile-call' href='tel:+380000000000'>Call</a><a style='display:inline-flex;min-width:44px;min-height:44px' href='tel:+380000000000'>Visible call</a>", encoding="utf-8")
            gate, _ = TechnicalInspector().inspect(page, Path(temp) / "artifacts")
            self.assertTrue(gate.passed, gate.small_tap_targets)

    def test_control_inside_hidden_result_is_not_a_small_tap_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            page = Path(temp) / "index.html"
            page.write_text(
                "<div hidden><button>Copy prepared message</button><a href='https://example.com'>Open profile</a></div>",
                encoding="utf-8",
            )
            gate, _ = TechnicalInspector().inspect(page, Path(temp) / "artifacts")
            self.assertTrue(gate.passed, gate.small_tap_targets)

    def test_pending_lazy_image_is_not_classified_as_broken(self) -> None:
        class RecordingPage:
            script = ""

            def evaluate(self, script):
                self.script = script
                return {
                    "viewport": "390x844", "scrollWidth": 390, "clientWidth": 390,
                    "horizontalScroll": False, "missingImages": [], "brokenLinks": [],
                    "smallTapTargets": [], "headings": [], "buttons": [],
                    "sectionIds": [], "bodyTextSample": "",
                }

        page = RecordingPage()
        TechnicalInspector()._collect_metrics(page)
        self.assertIn("img.complete && img.naturalWidth === 0", page.script)
        self.assertNotIn("!img.complete || img.naturalWidth === 0", page.script)


if __name__ == "__main__":
    unittest.main()
