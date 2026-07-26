from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from site_agent.models import TechnicalGate
from site_agent.refinement import (
    RefinementImplementationResult,
    RefinementReviewResult,
    RefinementSession,
    SiteRefinementOrchestrator,
)


class TechnicalGateInvariantTests(unittest.TestCase):
    def test_clean_gate_and_non_blocking_notes_can_pass(self) -> None:
        gate = TechnicalGate(passed=True, notes=["390px viewport inspected"])
        self.assertTrue(gate.passed)
        self.assertEqual(gate.blocking_reasons, [])

    def test_every_existing_blocking_field_forces_fail_closed(self) -> None:
        cases = (
            {"horizontal_scroll": True},
            {"missing_images": ["hero.jpg"]},
            {"console_errors": ["ReferenceError"]},
            {"failed_network_requests": ["GET /hero.jpg -> 500"]},
            {"broken_links": ["/missing"]},
            {"small_tap_targets": ["#menu"]},
            {"persistent_header_issues": ["header scrolls away"]},
            {"footer_issues": ["missing conversion path"]},
            {"clipped_primary_ctas": ["#book"]},
            {"functional_issues": ["menu does not open"]},
            {"reduced_motion_issues": ["animation keeps running"]},
        )
        for values in cases:
            with self.subTest(values=values):
                gate = TechnicalGate(passed=True, **values)
                self.assertFalse(gate.passed)
                self.assertTrue(gate.blocking_reasons)

    def test_failed_gate_without_blocking_reason_is_invalid(self) -> None:
        with self.assertRaisesRegex(ValidationError, "requires blocking evidence"):
            TechnicalGate(passed=False, notes=["informational warning only"])
        with self.assertRaisesRegex(ValidationError, "requires blocking evidence"):
            TechnicalGate(passed=False, console_errors=["  "])

    def test_required_refinement_browser_evidence_cannot_be_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            (project / "index.html").write_text("<!doctype html>", encoding="utf-8")
            workflow = SiteRefinementOrchestrator(runs_dir=root / "runs")
            session = RefinementSession(
                session_id="browser-required", project_id="project",
                project_path=str(project), user_goal="Refine hero",
                baseline_path="baseline/baseline.json",
                created_at="now", updated_at="now",
            )
            baseline = workflow.session_dir(session.session_id) / session.baseline_path
            baseline.parent.mkdir(parents=True)
            baseline.write_text(json.dumps({"observations": {}}), encoding="utf-8")
            implementation = RefinementImplementationResult(
                summary="Complete", changed_files=["index.html"],
                functional_qa_passed=True, content_qa_passed=True,
                animation_qa_passed=True, placeholders_absent=True,
                browser_review_performed=True,
            )
            review = RefinementReviewResult(
                decision="accept", visual_qa_passed=True,
                responsive_qa_passed=True, requirements_match=True,
                reference_comparison_passed=True, functional_qa_passed=True,
                content_qa_passed=True, animation_qa_passed=True,
                summary="Accepted",
            )
            observations = {
                name: json.dumps({"viewport": viewport})
                for name, viewport in {
                    "desktop_1440": "1440x1100", "desktop_1024": "1024x900",
                    "tablet_768": "768x1024", "mobile_390": "390x844",
                    "mobile_360": "360x800",
                }.items()
            }
            reasons: list[str] = []
            allowed = workflow._candidate_allowed(
                session, implementation, review, TechnicalGate(passed=True),
                observations,
                {"build": {"passed": True}, "tests": [{"passed": True}]},
                browser_evidence_required=True, rejection_reasons=reasons,
            )
            self.assertFalse(allowed)
            self.assertIn("Mandatory browser evidence is missing.", reasons)


if __name__ == "__main__":
    unittest.main()
