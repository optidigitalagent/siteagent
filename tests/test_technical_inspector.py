from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from site_agent.critic import TechnicalInspector


class TechnicalInspectorTests(unittest.TestCase):
    @staticmethod
    def _shell(content: str) -> str:
        return f"""<!doctype html><style>
          body{{margin:0}} header{{position:sticky;top:0;z-index:2;min-height:48px;background:white}}
          main{{min-height:1200px}} a,button{{min-width:44px;min-height:44px;display:inline-flex;align-items:center}}
        </style><header>Header</header><main id='main'>{content}</main>
        <footer><nav><a href='#main'>Home</a><a href='#details'>Details</a></nav>
        <a data-site-cta='primary' href='mailto:hello@example.com'><span>Contact us</span></a></footer>"""

    def test_hidden_mobile_call_is_not_a_small_tap_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            page = Path(temp) / "index.html"
            page.write_text(self._shell("<style>.mobile-call{display:none}</style><a class='mobile-call' href='tel:+380000000000'>Call</a><a href='tel:+380000000000'>Visible call</a>"), encoding="utf-8")
            gate, _ = TechnicalInspector().inspect(page, Path(temp) / "artifacts")
            self.assertTrue(gate.passed, gate.small_tap_targets)

    def test_control_inside_hidden_result_is_not_a_small_tap_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            page = Path(temp) / "index.html"
            page.write_text(self._shell("<div hidden><button>Copy prepared message</button><a href='https://example.com'>Open profile</a></div>"), encoding="utf-8")
            gate, _ = TechnicalInspector().inspect(page, Path(temp) / "artifacts")
            self.assertTrue(gate.passed, gate.small_tap_targets)

    def test_shell_gate_rejects_scrolling_header_missing_footer_and_clipped_cta(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            page = Path(temp) / "index.html"
            page.write_text("""<!doctype html><style>
              header{position:relative} main{min-height:1200px}
              a{min-width:44px;min-height:44px;display:inline-flex}.broken span{width:10px;height:10px;overflow:hidden}
            </style><header>Header</header><main><a class='broken' data-site-cta='primary' href='contact.html'><span>Prepare an enquiry</span></a></main>""", encoding="utf-8")
            gate, _ = TechnicalInspector().inspect(page, Path(temp) / "artifacts")
            self.assertFalse(gate.passed)
            self.assertTrue(gate.persistent_header_issues)
            self.assertTrue(gate.footer_issues)
            self.assertIn("Prepare an enquiry", gate.clipped_primary_ctas)

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
