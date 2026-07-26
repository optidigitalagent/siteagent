from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from site_agent.models import TechnicalGate
from site_agent.refinement import (
    ReferenceAnalysisResult,
    ReferenceScopeEvidence,
    RefinementAttachment,
    RefinementImplementationResult,
    RefinementReviewResult,
    RefinementSession,
    SiteRefinementOrchestrator,
    _reference_scope_rejection_reasons,
)


class RefinementReferenceScopeTests(unittest.TestCase):
    def make_session(self, root: Path, **mapping_updates) -> tuple[
            SiteRefinementOrchestrator, RefinementSession]:
        project = root / "project"
        project.mkdir()
        (project / "index.html").write_text("<!doctype html>", encoding="utf-8")
        mapping = {
            "id": "asset-reference", "original_name": "hero.png",
            "stored_path": "inputs/hero.png", "sha256": "0" * 64,
            "kind": "reference", "target_page": "index.html",
            "target_section": "hero", "target_component": "hero-layout",
            "target_properties": ["composition", "spacing"],
            "interpretation": "Transfer only the split hero layout.",
            "transfer": ["two-column composition", "measured whitespace"],
            "added_at": "now",
        }
        mapping.update(mapping_updates)
        workflow = SiteRefinementOrchestrator(runs_dir=root / "runs")
        session = RefinementSession(
            session_id="reference-scope", project_id="project",
            project_path=str(project), user_goal="Refine only the hero layout",
            scope=["index.html#hero"],
            attachments=[RefinementAttachment(**mapping)],
            baseline_path="baseline/baseline.json",
            created_at="now", updated_at="now",
        )
        baseline = workflow.session_dir(session.session_id) / session.baseline_path
        baseline.parent.mkdir(parents=True)
        baseline.write_text(json.dumps({"observations": {}}), encoding="utf-8")
        return workflow, session

    @staticmethod
    def implementation(**evidence_updates) -> RefinementImplementationResult:
        evidence = {
            "attachment_id": "asset-reference", "target_page": "index.html",
            "target_section": "hero", "target_component": "hero-layout",
            "properties": ["composition", "spacing"],
            "changed_files": ["index.html"],
            "evidence": "Only the hero layout changed in the rendered comparison.",
        }
        evidence.update(evidence_updates)
        return RefinementImplementationResult(
            summary="Complete", changed_files=["index.html"],
            functional_qa_passed=True, content_qa_passed=True,
            animation_qa_passed=True, placeholders_absent=True,
            browser_review_performed=True,
            reference_scope_evidence=[ReferenceScopeEvidence(**evidence)],
        )

    @staticmethod
    def review() -> RefinementReviewResult:
        return RefinementReviewResult(
            decision="accept", visual_qa_passed=True,
            responsive_qa_passed=True, requirements_match=True,
            reference_comparison_passed=True, functional_qa_passed=True,
            content_qa_passed=True, animation_qa_passed=True,
            summary="Accepted",
        )

    def test_exact_component_and_property_scope_is_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, session = self.make_session(Path(temporary))
            self.assertEqual(
                _reference_scope_rejection_reasons(session, self.implementation()), []
            )

    def test_missing_component_or_property_scope_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, session = self.make_session(
                Path(temporary), target_component="", target_properties=[]
            )
            reasons = _reference_scope_rejection_reasons(session, self.implementation())
            self.assertIn(
                "Reference asset-reference lacks a specific component.", reasons
            )
            self.assertIn(
                "Reference asset-reference has no property-level transfer scope.", reasons
            )

    def test_implementation_cannot_widen_component_or_properties(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, session = self.make_session(Path(temporary))
            reasons = _reference_scope_rejection_reasons(
                session,
                self.implementation(
                    target_component="whole-page",
                    properties=["composition", "spacing", "color"],
                ),
            )
            self.assertIn(
                "Reference asset-reference implementation scope does not exactly match its mapping.",
                reasons,
            )

    def test_scope_evidence_must_name_a_computed_changed_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, session = self.make_session(Path(temporary))
            reasons = _reference_scope_rejection_reasons(
                session, self.implementation(changed_files=["unreported.css"])
            )
            self.assertIn(
                "Reference asset-reference scope evidence names an unrecorded changed file.",
                reasons,
            )

    def test_mapping_cannot_escape_explicit_page_section_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, session = self.make_session(Path(temporary), target_section="cards")
            reasons = _reference_scope_rejection_reasons(session, self.implementation())
            self.assertIn(
                "Reference asset-reference page/section scope is outside the requested scope.",
                reasons,
            )

    def test_broad_analysis_mapping_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValidationError, "specific page, section, component"):
            ReferenceAnalysisResult(
                target_page="global", target_section="all",
                target_component="sitewide",
                target_properties=["composition"],
                match_kind="visual_direction", interpretation="Apply broadly",
                transfer=["composition"],
            )

    def test_ambiguous_analysis_requires_and_preserves_a_blocker(self) -> None:
        analysis = ReferenceAnalysisResult(
            target_page="", target_section="", target_component="",
            target_properties=[], match_kind="visual_direction",
            interpretation="", transfer=[], ambiguous=True,
            blocker="The user did not identify which card this reference targets.",
        )
        self.assertTrue(analysis.ambiguous)
        with self.assertRaisesRegex(ValidationError, "requires a blocker reason"):
            ReferenceAnalysisResult(
                target_page="", target_section="", target_component="",
                target_properties=[], match_kind="visual_direction",
                interpretation="", transfer=[], ambiguous=True, blocker="",
            )

    def test_candidate_rejects_missing_scope_evidence_despite_positive_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workflow, session = self.make_session(Path(temporary))
            implementation = self.implementation()
            implementation.reference_scope_evidence = []
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
                session, implementation, self.review(), TechnicalGate(passed=True),
                observations,
                {"build": {"passed": True}, "tests": [{"passed": True}]},
                rejection_reasons=reasons,
            )
            self.assertFalse(allowed)
            self.assertIn(
                "Reference asset-reference requires exactly one implementation scope record.",
                reasons,
            )


if __name__ == "__main__":
    unittest.main()
