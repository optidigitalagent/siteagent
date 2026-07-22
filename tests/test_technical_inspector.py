from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

from site_agent.critic import TechnicalInspector


class TechnicalInspectorTests(unittest.TestCase):
    @staticmethod
    def _shell(content: str) -> str:
        return f"""<!doctype html><style>
          body{{margin:0}} header{{position:sticky;top:0;z-index:2;min-height:48px;background:white}}
          main{{min-height:1200px}} a,button{{min-width:44px;min-height:44px;display:inline-flex;align-items:center}}
        </style><header>Header</header><main id='main'><span id='details'></span>{content}</main>
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

    def test_refinement_profile_records_all_required_widths_and_reduced_motion(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            page = Path(temp) / "index.html"
            page.write_text(self._shell("<section id='details'><h1>Refinement fixture</h1></section>"), encoding="utf-8")
            artifacts = Path(temp) / "strict"
            gate, observations = TechnicalInspector(viewport_profile="refinement").inspect(
                page, artifacts
            )
            self.assertTrue(gate.passed, gate.model_dump())
            for key in ("desktop_1440", "desktop_1024", "tablet_768", "mobile_390", "mobile_360", "reduced_motion"):
                self.assertIn(key, observations)
            for name in (
                "desktop.png", "desktop_1024.png", "tablet.png", "mobile.png",
                "mobile_360.png", "reduced_motion.png",
                "interaction_desktop_1440.png", "interaction_desktop_1024.png",
                "interaction_tablet_768.png", "interaction_mobile_390.png",
                "interaction_mobile_360.png",
            ):
                self.assertTrue((artifacts / name).is_file(), name)

    def test_interaction_qa_neutralizes_form_network_writes(self) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(service_workers="block")
            try:
                inspector = TechnicalInspector(viewport_profile="refinement")
                guard = inspector._install_refinement_network_guard(
                    page, "file:///siteagent-form-fixture.html"
                )
                page.goto("data:text/html,<title>init-probe</title>")
                init_probe = page.evaluate("""() => {
                  window.open('https://example.test/init-popup');
                  return window.__siteagentQaBlocked;
                }""")
                self.assertEqual(init_probe[0]["method"], "POPUP")
                guard["blocked"].clear()
                guard["initial_issues"].clear()
                page.evaluate("() => window.__siteagentQaBlocked.splice(0)")
                page.set_content("""<!doctype html><form>
                  <input name='email' type='email' required>
                  <button type='submit'>Send</button><p role='status'></p>
                </form><script>
                  document.querySelector('form').addEventListener('submit', async event => {
                    event.preventDefault();
                    const response = await fetch('https://example.test/write', {
                      method: 'POST', body: 'email=qa@example.test'
                    });
                    document.querySelector('[role=status]').textContent = String(response.status);
                  });
                </script>""")
                result = inspector._exercise_interactions(page, guard)
            finally:
                browser.close()
        self.assertTrue(result["networkWritesPrevented"])
        self.assertEqual(result["networkWritesPrevented"][0]["method"], "POST")
        self.assertIn("form-valid", result["checked"])
        self.assertTrue(result["passed"], result["issues"])

    def test_refinement_guard_is_installed_before_load_and_blocks_lifecycle_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            page = Path(temp) / "index.html"
            page.write_text(self._shell("""<script>
              fetch('https://example.test/on-load', {method:'POST'}).catch(() => {});
              navigator.sendBeacon('https://example.test/beacon', 'qa');
              window.open('https://example.test/popup');
              try { new WebSocket('wss://example.test/socket'); } catch (_) {}
              addEventListener('unload', () => {
                fetch('https://example.test/unload-write', {
                  method:'POST', body:'qa', keepalive:true
                }).catch(() => {});
              });
            </script>"""), encoding="utf-8")
            gate, observations = TechnicalInspector(
                viewport_profile="refinement"
            ).inspect(page, Path(temp) / "artifacts")
        self.assertFalse(gate.passed)
        self.assertTrue(any("during refinement page load" in issue
                            for issue in gate.functional_issues))
        desktop = __import__("json").loads(observations["desktop_1440"])
        methods = {item["method"] for item in
                   desktop["interactionChecks"]["networkWritesPrevented"]}
        self.assertTrue(
            {"POST", "BEACON", "POPUP", "WEBSOCKET"}.issubset(methods), methods
        )
        self.assertTrue(any(
            item["url"].endswith("/unload-write") for item in
            desktop["interactionChecks"]["networkWritesPrevented"]
        ))

    def test_file_refinement_guard_blocks_reads_outside_allowed_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project"
            project.mkdir()
            Image.new("RGB", (8, 8), "red").save(root / "outside.png")
            page = project / "index.html"
            page.write_text(self._shell(
                "<img src='../outside.png' alt='must stay outside'>"
            ), encoding="utf-8")
            gate, observations = TechnicalInspector(
                viewport_profile="refinement"
            ).inspect(page, root / "artifacts")
        self.assertFalse(gate.passed)
        desktop = __import__("json").loads(observations["desktop_1440"])
        self.assertTrue(any(
            item["url"].endswith("outside.png") for item in
            desktop["interactionChecks"]["networkWritesPrevented"]
        ))

    def test_file_links_cannot_escape_allowed_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project"
            project.mkdir()
            outside = root / "outside.html"
            outside.write_text("outside", encoding="utf-8")
            page = project / "index.html"
            page.write_text(self._shell(
                f"<a href='../outside.html'>Relative escape</a>"
                f"<a href='{outside.resolve().as_uri()}'>Absolute escape</a>"
            ), encoding="utf-8")
            gate, observations = TechnicalInspector(
                viewport_profile="refinement"
            ).inspect(page, root / "artifacts")
        self.assertFalse(gate.passed)
        desktop = __import__("json").loads(observations["desktop_1440"])
        escaping = [item for item in desktop["brokenLinks"]
                    if "escapes the project" in item]
        self.assertEqual(len(escaping), 2, desktop["brokenLinks"])

    def test_hidden_stale_form_status_does_not_count_as_submission_outcome(self) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(service_workers="block")
            try:
                inspector = TechnicalInspector(viewport_profile="refinement")
                guard = inspector._install_refinement_network_guard(
                    page, "file:///hidden-form-status.html"
                )
                page.set_content("""<!doctype html><form action='/missing-endpoint'>
                  <input name='email' type='email' required>
                  <button type='submit'>Send</button>
                  <p role='status' hidden>Previously sent</p>
                </form>""")
                result = inspector._exercise_interactions(page, guard)
            finally:
                browser.close()
        self.assertFalse(result["passed"])
        self.assertTrue(any("outcome is unverified" in issue for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
