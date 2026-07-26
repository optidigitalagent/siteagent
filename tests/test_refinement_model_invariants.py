from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from site_agent.models import (
    AcceptanceAuditResult,
    CritiqueIssue,
    CritiqueReport,
    IssueSeverity,
    TechnicalGate,
)
from site_agent.refinement import (
    RefinementImplementationResult,
    RefinementReviewIssue,
    RefinementReviewResult,
    RefinementSession,
    SiteRefinementOrchestrator,
)


def valid_acceptance(**updates) -> AcceptanceAuditResult:
    values = {
        "approved": True,
        "technical_gate_passed": True,
        "visual_director_approved": True,
        "business_approved": True,
        "score": 88,
        "no_blocking_issues": True,
        "index_present": True,
        "reasons": [],
        "audited_at": "now",
    }
    values.update(updates)
    return AcceptanceAuditResult(**values)


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


class ApprovalModelInvariantTests(unittest.TestCase):
    def test_valid_acceptance_remains_approved(self) -> None:
        self.assertTrue(valid_acceptance().approved)

    def test_every_acceptance_prerequisite_forces_fail_closed(self) -> None:
        cases = (
            {"technical_gate_passed": False},
            {"visual_director_approved": False},
            {"business_approved": False},
            {"score": 87},
            {"no_blocking_issues": False},
            {"index_present": False},
            {"reasons": ["A downstream approval artifact is missing."]},
            {"category_scores": {"copy": 79}, "quality_floors": {"copy": 80}},
            {"category_scores": {}, "quality_floors": {"copy": 80}},
            {"category_scores": {"copy": 0}, "quality_floors": {}},
        )
        for values in cases:
            with self.subTest(values=values):
                result = valid_acceptance(**values)
                self.assertFalse(result.approved)
                self.assertTrue(result.reasons)

    def test_acceptance_scores_and_unexplained_rejection_are_invalid(self) -> None:
        for score in (-1, 101):
            with self.subTest(score=score):
                with self.assertRaises(ValidationError):
                    valid_acceptance(score=score)
        with self.assertRaisesRegex(ValidationError, "requires at least one reason"):
            valid_acceptance(approved=False)
        with self.assertRaisesRegex(ValidationError, "between 0 and 100"):
            valid_acceptance(category_scores={"copy": 101})

    def test_critique_delivery_checks_every_approval_dimension(self) -> None:
        base = {
            "score": 88,
            "technical_gate": TechnicalGate(passed=True),
            "visual_director_approved": True,
            "business_approved": True,
            "issues": [],
            "summary": "Accepted",
        }
        self.assertTrue(CritiqueReport(**base).approved_for_delivery)
        cases = (
            {"technical_gate": TechnicalGate(
                passed=True, console_errors=["ReferenceError"]
            )},
            {"visual_director_approved": False},
            {"business_approved": False},
            {"score": 87},
            {"issues": [CritiqueIssue(
                severity=IssueSeverity.high, area="technical",
                problem="Broken", why_it_matters="Blocks delivery", fix="Repair",
            )]},
        )
        for values in cases:
            with self.subTest(values=values):
                report = CritiqueReport(**(base | values))
                self.assertFalse(report.approved_for_delivery)

    def test_refinement_acceptance_normalizes_contradictions_to_revise(self) -> None:
        base = {
            "decision": "accept",
            "visual_qa_passed": True,
            "responsive_qa_passed": True,
            "requirements_match": True,
            "reference_comparison_passed": True,
            "functional_qa_passed": True,
            "content_qa_passed": True,
            "animation_qa_passed": True,
            "summary": "Accepted",
        }
        self.assertEqual(RefinementReviewResult(**base).decision, "accept")
        false_flags = (
            "visual_qa_passed", "responsive_qa_passed", "requirements_match",
            "reference_comparison_passed", "functional_qa_passed",
            "content_qa_passed", "animation_qa_passed",
            "reference_property_scope_verified",
        )
        for field in false_flags:
            with self.subTest(field=field):
                self.assertEqual(
                    RefinementReviewResult(**(base | {field: False})).decision,
                    "revise",
                )
        issue = RefinementReviewIssue(
            severity="p1", area="hero", problem="Scope escaped",
            required_fix="Restore the scoped component.",
        )
        self.assertEqual(
            RefinementReviewResult(**(base | {"issues": [issue]})).decision,
            "revise",
        )
        self.assertEqual(
            RefinementReviewResult(**(
                base | {"remaining_differences": ["Hero spacing still differs."]}
            )).decision,
            "revise",
        )


if __name__ == "__main__":
    unittest.main()
