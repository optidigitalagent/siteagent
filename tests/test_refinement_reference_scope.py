from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from site_agent.models import TechnicalGate
from site_agent.refinement import (
    ReferenceAnalysisResult,
    ReferencePropertyVerification,
    ReferenceScopeEvidence,
    RefinementAttachment,
    RefinementAttachmentInput,
    RefinementImplementationResult,
    RefinementRequest,
    RefinementRequirement,
    RefinementReviewResult,
    RefinementSession,
    RequirementChangeEvidence,
    RequirementSourceVerification,
    RequirementState,
    SiteRefinementOrchestrator,
    _merge_reference_analysis_without_widening,
    _payload_sha,
    _planned_requirement_ids,
    _reference_scope_rejection_reasons,
    _reference_source_verification_reasons,
    _requirement_authority_checksum,
    _requirement_change_rejection_reasons,
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
            "target_locator": "#hero",
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
    def property_verifications(*properties: str, verifiable: bool = True):
        return [ReferencePropertyVerification(
            property=property_name, target_component="hero-layout",
            changed_files=["index.html"], target_locator="#hero",
            before=f"baseline {property_name}",
            after=f"changed {property_name}", verifiable=verifiable,
        ) for property_name in properties]

    @staticmethod
    def implementation(**evidence_updates) -> RefinementImplementationResult:
        evidence = {
            "attachment_id": "asset-reference", "target_page": "index.html",
            "target_section": "hero", "target_component": "hero-layout",
            "target_locator": "#hero",
            "properties": ["composition", "spacing"],
            "changed_files": ["index.html"],
            "evidence": "Only the hero layout changed in the rendered comparison.",
            "property_verifications": RefinementReferenceScopeTests.property_verifications(
                "composition", "spacing"
            ),
            "scope_isolated": True,
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
            reference_property_scope_verified=True,
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

    def test_every_reference_changed_file_needs_property_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, session = self.make_session(Path(temporary))
            implementation = self.implementation(
                changed_files=["index.html", "evil.js"]
            )
            implementation.changed_files.append("evil.js")
            reasons = _reference_scope_rejection_reasons(session, implementation)
            self.assertIn(
                "Reference asset-reference lacks exact changed-file verification coverage.",
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
                target_locator="body",
                target_properties=["composition"],
                match_kind="visual_direction", interpretation="Apply broadly",
                transfer=["composition"],
            )
        for page, section, component in (
            ("all pages", "hero", "hero-layout"),
            ("all-pages", "hero", "hero-layout"),
            ("index.html", "every section", "hero-layout"),
            ("index.html", "every_section", "hero-layout"),
            ("index.html", "hero", "all components"),
            ("site-wide", "hero", "hero-layout"),
            ("full-site", "hero", "hero-layout"),
            ("entire website", "hero", "hero-layout"),
            ("globally", "hero", "hero-layout"),
            ("pagewide", "hero", "hero-layout"),
            ("index.html", "hero", "all-components"),
            ("everything", "hero", "hero-layout"),
        ):
            with self.subTest(page=page, section=section, component=component):
                with self.assertRaises(ValidationError):
                    ReferenceAnalysisResult(
                        target_page=page, target_section=section,
                        target_component=component,
                        target_locator="#hero",
                        target_properties=["composition"],
                        match_kind="visual_direction", interpretation="Scoped",
                        transfer=["composition"],
                    )

    def test_ambiguous_analysis_requires_and_preserves_a_blocker(self) -> None:
        analysis = ReferenceAnalysisResult(
            target_page="", target_section="", target_component="",
            target_locator="",
            target_properties=[], match_kind="visual_direction",
            interpretation="", transfer=[], ambiguous=True,
            blocker="The user did not identify which card this reference targets.",
        )
        self.assertTrue(analysis.ambiguous)
        with self.assertRaisesRegex(ValidationError, "requires a blocker reason"):
            ReferenceAnalysisResult(
                target_page="", target_section="", target_component="",
                target_locator="",
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

    def test_candidate_rejects_unresolved_explicit_component(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workflow, session = self.make_session(
                Path(temporary), target_component=""
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
                session, self.implementation(), self.review(),
                TechnicalGate(passed=True), observations,
                {"build": {"passed": True}, "tests": [{"passed": True}]},
                rejection_reasons=reasons,
            )
            self.assertFalse(allowed)
            self.assertIn(
                "Reference asset-reference lacks a specific component.", reasons
            )

    def test_legacy_reference_loads_and_normalizes_property_names(self) -> None:
        legacy = RefinementAttachment(
            id="legacy", original_name="legacy.png", stored_path="inputs/legacy.png",
            sha256="0" * 64, kind="reference", target_page="index.html",
            target_section="hero",
            transfer=[" composition ", "component shape", "responsive behavior"],
            added_at="now",
        )
        self.assertEqual(
            legacy.target_properties,
            ["composition", "shape", "responsive_behavior"],
        )
        session = RefinementSession.model_validate_json(RefinementSession(
            session_id="legacy", project_id="project", project_path="project",
            user_goal="Refine hero", attachments=[legacy],
            created_at="now", updated_at="now",
        ).model_dump_json())
        self.assertEqual(session.attachments[0].target_section, "hero")

    def test_empty_and_duplicate_properties_are_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, session = self.make_session(
                Path(temporary),
                target_properties=[
                    "", " Composition ", "composition", "component-shape",
                    "responsive behavior", "responsive_behavior",
                ],
            )
            self.assertEqual(
                session.attachments[0].target_properties,
                ["composition", "shape", "responsive_behavior"],
            )
        explicit_empty = RefinementAttachmentInput(
            path="reference.png", kind="reference", target_page="index.html",
            target_section="hero", target_properties=[], transfer=["color"],
        )
        self.assertEqual(explicit_empty.target_properties, [])

    def test_analysis_cannot_replace_component_or_expand_properties(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, session = self.make_session(Path(temporary))
            analysis = ReferenceAnalysisResult(
                target_page="index.html", target_section="hero",
                target_component="site-header",
                target_locator="#site-header",
                target_properties=["composition", "spacing", "color"],
                match_kind="visual_direction", interpretation="Broader mapping",
                transfer=["composition", "color"],
            )
            merged, conflicts = _merge_reference_analysis_without_widening(
                session.attachments[0], analysis
            )
            self.assertIsNone(merged)
            self.assertEqual(
                set(conflicts),
                {"target_component", "target_locator", "target_properties"},
            )
            self.assertEqual(session.attachments[0].target_component, "hero-layout")
            self.assertEqual(
                session.attachments[0].target_properties,
                ["composition", "spacing"],
            )

    def test_orchestrator_blocks_automatic_scope_widening_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            (project / "index.html").write_text("<!doctype html>", encoding="utf-8")
            reference = root / "hero.png"
            reference.write_bytes(b"reference")
            workflow = SiteRefinementOrchestrator(runs_dir=root / "runs")
            session = workflow.start(RefinementRequest(
                project=str(project), goal="Refine the hero",
                scope=["index.html#hero"],
                attachments=[RefinementAttachmentInput(
                    path=str(reference), kind="reference",
                    target_page="index.html", target_section="hero",
                    target_component="hero-layout",
                    target_locator="#hero",
                    target_properties=["composition"],
                )],
            ), session_id="automatic-widening", execute=False)
            widened = ReferenceAnalysisResult(
                target_page="index.html", target_section="hero",
                target_component="site-header",
                target_locator="#site-header",
                target_properties=["composition", "color"],
                match_kind="visual_direction", interpretation="Broader mapping",
                transfer=["composition", "color"],
            )
            with patch("site_agent.refinement._invoke_codex_model", return_value=widened):
                workflow._analyze_unmapped_references(session, root / "iteration")
            mapping = session.attachments[0]
            self.assertEqual(mapping.target_component, "hero-layout")
            self.assertEqual(mapping.target_properties, ["composition"])
            self.assertTrue(any(
                "tried to widen or replace explicit scope" in blocker
                for blocker in session.blockers
            ))

    def test_orchestrator_does_not_fill_explicit_empty_property_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            (project / "index.html").write_text("<!doctype html>", encoding="utf-8")
            reference = root / "hero.png"
            reference.write_bytes(b"reference")
            workflow = SiteRefinementOrchestrator(runs_dir=root / "runs")
            session = workflow.start(RefinementRequest(
                project=str(project), goal="Refine the hero",
                scope=["index.html#hero"],
                attachments=[RefinementAttachmentInput(
                    path=str(reference), kind="reference",
                    target_page="index.html", target_section="hero",
                    target_component="hero-layout", target_locator="#hero",
                    target_properties=[], transfer=["color"],
                )],
            ), session_id="explicit-empty-properties", execute=False)
            analysis = ReferenceAnalysisResult(
                target_page="index.html", target_section="hero",
                target_component="hero-layout", target_locator="#hero",
                target_properties=["color"], match_kind="visual_direction",
                interpretation="Use the reference color", transfer=["color"],
            )
            with patch("site_agent.refinement._invoke_codex_model", return_value=analysis):
                workflow._analyze_unmapped_references(session, root / "iteration")
            self.assertEqual(session.attachments[0].target_properties, [])
            self.assertTrue(any("target_properties" in blocker
                                for blocker in session.blockers))

    def test_analysis_only_fills_missing_legacy_component(self) -> None:
        legacy = RefinementAttachment(
            id="legacy", original_name="legacy.png", stored_path="inputs/legacy.png",
            sha256="0" * 64, kind="reference", target_page="index.html",
            target_section="hero", transfer=["composition"], added_at="now",
        )
        analysis = ReferenceAnalysisResult(
            target_page="index.html", target_section="hero",
            target_component="hero-layout", target_locator="#hero",
            target_properties=["composition"],
            match_kind="visual_direction", interpretation="Use the hero composition",
            transfer=["composition"],
        )
        merged, conflicts = _merge_reference_analysis_without_widening(legacy, analysis)
        self.assertEqual(conflicts, [])
        self.assertIsNotNone(merged)
        assert merged is not None
        self.assertEqual(merged.target_component, "hero-layout")
        self.assertEqual(merged.target_properties, ["composition"])

    def test_unattributed_change_outside_reference_scope_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, session = self.make_session(Path(temporary))
            implementation = self.implementation()
            implementation.changed_files.append("styles.css")
            reasons = _requirement_change_rejection_reasons(session, implementation)
            self.assertIn(
                "Computed changes lack reference or requirement attribution: styles.css.",
                reasons,
            )

    def test_requirement_can_authorize_change_outside_reference_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, session = self.make_session(Path(temporary))
            session.requirements.append(RefinementRequirement(
                id="req-cards", text="Tighten card spacing",
                state=RequirementState.COMPLETED, scope=["index.html#cards"],
                created_at="now", iteration=0, resolution="Implemented",
            ))
            implementation = self.implementation()
            implementation.changed_files.append("styles.css")
            implementation.completed_requirement_ids = ["req-cards"]
            implementation.requirement_change_evidence = [RequirementChangeEvidence(
                requirement_id="req-cards", changed_files=["styles.css"],
                scope=["index.html#cards"],
                evidence="The styles.css diff implements the independent cards requirement.",
            )]
            self.assertEqual(
                _requirement_change_rejection_reasons(
                    session, implementation,
                    authorized_requirement_ids={"req-cards"},
                ),
                [],
            )
            self.assertEqual(
                _reference_scope_rejection_reasons(session, implementation), []
            )

    def test_unknown_or_superseded_requirement_cannot_authorize_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, session = self.make_session(Path(temporary))
            session.requirements.append(RefinementRequirement(
                id="req-old", text="Old direction", state=RequirementState.SUPERSEDED,
                created_at="now", iteration=0, resolution="Replaced",
            ))
            for requirement_id, expected in (
                ("req-missing", "unknown requirement"),
                ("req-old", "non-authorizing requirement"),
            ):
                with self.subTest(requirement_id=requirement_id):
                    implementation = self.implementation()
                    implementation.changed_files.append("styles.css")
                    implementation.requirement_change_evidence = [RequirementChangeEvidence(
                        requirement_id=requirement_id, changed_files=["styles.css"],
                        evidence="Claimed attribution.",
                    )]
                    reasons = _requirement_change_rejection_reasons(
                        session, implementation
                    )
                    self.assertTrue(any(expected in reason for reason in reasons))

    def test_stale_completed_requirement_is_not_in_the_current_change_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, session = self.make_session(Path(temporary))
            session.iteration = 9
            session.requirements.append(RefinementRequirement(
                id="req-old-hero", text="Refine hero",
                state=RequirementState.COMPLETED, scope=["index.html#hero"],
                created_at="then", iteration=0, resolution="Completed earlier",
            ))
            implementation = self.implementation()
            implementation.changed_files.append("footer.css")
            implementation.completed_requirement_ids = ["req-old-hero"]
            implementation.requirement_change_evidence = [RequirementChangeEvidence(
                requirement_id="req-old-hero", changed_files=["footer.css"],
                scope=["index.html#hero"], evidence="Claimed stale attribution.",
            )]
            reasons = _requirement_change_rejection_reasons(
                session, implementation,
                authorized_requirement_ids={"req-current-footer"},
            )
            self.assertTrue(any("outside the current implementation plan" in item
                                for item in reasons))

    def test_forged_plan_cannot_replace_current_membership_with_stale_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, session = self.make_session(root)
            session.iteration = 9
            current = RefinementRequirement(
                id="req-current", text="Refine current hero",
                state=RequirementState.ACTIVE, scope=["index.html#hero"],
                created_at="now", iteration=9,
            )
            stale = RefinementRequirement(
                id="req-stale", text="Old completed direction",
                state=RequirementState.COMPLETED, scope=["index.html#hero"],
                created_at="then", iteration=0, resolution="Done earlier",
            )
            session.requirements.extend([current, stale])
            iteration_dir = root / "iteration"
            snapshot = iteration_dir / "pre_change_snapshot"
            snapshot.mkdir(parents=True)
            honest_plan = {
                "schema_version": 2,
                "session_id": session.session_id,
                "project_id": session.project_id,
                "iteration": session.iteration,
                "active_requirements": [current.model_dump(mode="json")],
                "requirements_authority_sha256": _requirement_authority_checksum(
                    session.requirements
                ),
                "immutable_constraints": [], "scope": session.scope,
                "reference_mappings": [],
            }
            session.current_change_plan_sha256 = _payload_sha(honest_plan)
            forged = dict(honest_plan)
            forged["active_requirements"] = [stale.model_dump(mode="json")]
            (iteration_dir / "change_plan.json").write_text(
                json.dumps(forged), encoding="utf-8"
            )
            self.assertEqual(_planned_requirement_ids(snapshot, session), set())

    def test_reference_locator_must_match_requested_section_and_not_be_global(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, wrong = self.make_session(Path(temporary), target_locator="#cards")
            reasons = _reference_scope_rejection_reasons(wrong)
            self.assertTrue(any("target locator does not match" in item
                                for item in reasons))
        for locator in ("body", "html", ":root", "body#hero", "html#hero", ":root#hero"):
            with self.subTest(locator=locator):
                with self.assertRaises(ValidationError):
                    ReferenceAnalysisResult(
                        target_page="index.html", target_section="hero",
                        target_component="hero-layout", target_locator=locator,
                        target_properties=["composition"], match_kind="exact",
                        interpretation="Use only the hero layout.", transfer=[],
                    )

    def test_only_exact_id_attribute_is_a_section_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, exact = self.make_session(
                Path(temporary), target_locator='[id="hero"]'
            )
            self.assertEqual(_reference_scope_rejection_reasons(exact), [])
        for locator in (
            '[data-id="hero"]', '[foo-id="hero"]',
            '[data-target="#hero"]', 'footer[data-target="#hero"]',
        ):
            with self.subTest(locator=locator), tempfile.TemporaryDirectory() as temporary:
                _, spoofed = self.make_session(
                    Path(temporary), target_locator=locator
                )
                self.assertTrue(any(
                    "target locator does not match" in item
                    for item in _reference_scope_rejection_reasons(spoofed)
                ))

    def test_unverifiable_property_change_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, session = self.make_session(Path(temporary))
            implementation = self.implementation(
                property_verifications=self.property_verifications(
                    "composition", "spacing", verifiable=False
                )
            )
            reasons = _reference_scope_rejection_reasons(session, implementation)
            self.assertTrue(any("unverifiable change evidence" in item for item in reasons))

    def test_missing_duplicate_or_nonisolated_property_proof_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, session = self.make_session(Path(temporary))
            missing = self.implementation(
                property_verifications=self.property_verifications("composition")
            )
            self.assertTrue(any("exact per-property verification" in item
                                for item in _reference_scope_rejection_reasons(
                                    session, missing
                                )))
            duplicate = self.implementation(
                property_verifications=self.property_verifications(
                    "composition", "composition", "spacing"
                )
            )
            self.assertTrue(any("exact per-property verification" in item
                                for item in _reference_scope_rejection_reasons(
                                    session, duplicate
                                )))
            nonisolated = self.implementation(scope_isolated=False)
            self.assertTrue(any("not proven isolated" in item
                                for item in _reference_scope_rejection_reasons(
                                    session, nonisolated
                                )))

    def test_material_property_outside_allowlist_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, session = self.make_session(Path(temporary))
            implementation = self.implementation(
                property_verifications=self.property_verifications(
                    "composition", "spacing", "color"
                )
            )
            reasons = _reference_scope_rejection_reasons(session, implementation)
            self.assertIn(
                "Reference asset-reference verifies a property outside its allowlist.",
                reasons,
            )

    def test_property_verification_must_match_snapshot_and_current_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, session = self.make_session(root)
            before_rule = "#hero{display:grid;padding:1rem}"
            after_rule = "#hero{display:grid;padding:2rem}"
            Path(session.project_path, "index.html").write_text(
                after_rule, encoding="utf-8"
            )
            snapshot = root / "snapshot"
            snapshot.mkdir()
            (snapshot / "index.html").write_text(before_rule, encoding="utf-8")
            verifications = [ReferencePropertyVerification(
                property=property_name, target_component="hero-layout",
                changed_files=["index.html"], target_locator="#hero",
                before=before_rule, after=after_rule, verifiable=True,
            ) for property_name in ("composition", "spacing")]
            implementation = self.implementation(
                property_verifications=verifications
            )
            self.assertEqual(
                _reference_source_verification_reasons(
                    session, implementation, snapshot
                ),
                [],
            )
            implementation.reference_scope_evidence[0].property_verifications[0].after = (
                "executor assertion not present in source"
            )
            reasons = _reference_source_verification_reasons(
                session, implementation, snapshot
            )
            self.assertTrue(any("does not match" in item for item in reasons))

    def test_same_file_out_of_scope_change_needs_requirement_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, session = self.make_session(
                root, target_properties=["composition"]
            )
            session.requirements.append(RefinementRequirement(
                id="req-cards", text="Change the cards",
                state=RequirementState.COMPLETED, scope=["index.html#cards"],
                created_at="now", iteration=0, resolution="Implemented",
            ))
            before_hero = "#hero{display:block}"
            after_hero = "#hero{display:grid}"
            before_cards = "#cards{gap:1rem}"
            after_cards = "#cards{gap:2rem}"
            snapshot = root / "snapshot"
            snapshot.mkdir()
            (snapshot / "index.html").write_text(
                before_hero + before_cards, encoding="utf-8"
            )
            Path(session.project_path, "index.html").write_text(
                after_hero + after_cards, encoding="utf-8"
            )
            implementation = self.implementation(
                properties=["composition"],
                property_verifications=[ReferencePropertyVerification(
                    property="composition", target_component="hero-layout",
                    changed_files=["index.html"], target_locator="#hero",
                    before=before_hero, after=after_hero, verifiable=True,
                )],
            )
            reasons = _reference_source_verification_reasons(
                session, implementation, snapshot
            )
            self.assertTrue(any("outside its verified" in item for item in reasons))

            implementation.completed_requirement_ids = ["req-cards"]
            implementation.requirement_change_evidence = [RequirementChangeEvidence(
                requirement_id="req-cards", changed_files=["index.html"],
                scope=["index.html#cards"],
                source_verifications=[RequirementSourceVerification(
                    changed_file="index.html", target_locator="#cards",
                    before=before_cards, after=after_cards, verifiable=True,
                )],
                evidence="The cards hunk implements the separate cards requirement.",
            )]
            self.assertEqual(
                _reference_source_verification_reasons(
                    session, implementation, snapshot
                ),
                [],
            )
            self.assertEqual(
                _requirement_change_rejection_reasons(
                    session, implementation,
                    authorized_requirement_ids={"req-cards"},
                ),
                [],
            )

    def test_actual_css_property_outside_allowlist_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, session = self.make_session(root)
            before_rule = "#hero{display:grid;padding:1rem}"
            after_rule = "#hero{display:grid;padding:2rem;color:red}"
            snapshot = root / "snapshot"
            snapshot.mkdir()
            (snapshot / "index.html").write_text(before_rule, encoding="utf-8")
            Path(session.project_path, "index.html").write_text(
                after_rule, encoding="utf-8"
            )
            implementation = self.implementation(
                property_verifications=[ReferencePropertyVerification(
                    property=property_name, target_component="hero-layout",
                    changed_files=["index.html"], target_locator="#hero",
                    before=before_rule, after=after_rule, verifiable=True,
                ) for property_name in ("composition", "spacing")]
            )
            reasons = _reference_source_verification_reasons(
                session, implementation, snapshot
            )
            self.assertTrue(any("outside the verified reference property allowlist"
                                in item for item in reasons))

    def test_background_image_is_not_authorized_by_color_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, session = self.make_session(root, target_properties=["color"])
            before_rule = "#hero{background:#fff}"
            after_rule = "#hero{background:url(photo.jpg) center/cover}"
            snapshot = root / "snapshot"
            snapshot.mkdir()
            (snapshot / "index.html").write_text(before_rule, encoding="utf-8")
            Path(session.project_path, "index.html").write_text(
                after_rule, encoding="utf-8"
            )
            implementation = self.implementation(
                properties=["color"],
                property_verifications=[ReferencePropertyVerification(
                    property="color", target_component="hero-layout",
                    changed_files=["index.html"], target_locator="#hero",
                    before=before_rule, after=after_rule, verifiable=True,
                )],
            )
            reasons = _reference_source_verification_reasons(
                session, implementation, snapshot
            )
            self.assertTrue(any("outside the verified reference property allowlist"
                                in item for item in reasons))

    def test_custom_color_property_cannot_hide_a_photography_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, session = self.make_session(root, target_properties=["color"])
            before_rule = "#hero{--color-bg:#fff}"
            after_rule = "#hero{--color-bg:url(photo.jpg)}"
            snapshot = root / "snapshot"
            snapshot.mkdir()
            (snapshot / "index.html").write_text(before_rule, encoding="utf-8")
            Path(session.project_path, "index.html").write_text(after_rule, encoding="utf-8")
            implementation = self.implementation(
                properties=["color"],
                property_verifications=[ReferencePropertyVerification(
                    property="color", target_component="hero-layout",
                    changed_files=["index.html"], target_locator="#hero",
                    before=before_rule, after=after_rule, verifiable=True,
                )],
            )
            reasons = _reference_source_verification_reasons(
                session, implementation, snapshot
            )
            self.assertTrue(any("outside the verified reference property allowlist"
                                in item for item in reasons))

    def test_translate_transform_is_not_authorized_as_scale(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, session = self.make_session(root, target_properties=["scale"])
            before_rule = "#hero{transform:scale(1)}"
            after_rule = "#hero{transform:translateX(100vw)}"
            snapshot = root / "snapshot"
            snapshot.mkdir()
            (snapshot / "index.html").write_text(before_rule, encoding="utf-8")
            Path(session.project_path, "index.html").write_text(after_rule, encoding="utf-8")
            implementation = self.implementation(
                properties=["scale"],
                property_verifications=[ReferencePropertyVerification(
                    property="scale", target_component="hero-layout",
                    changed_files=["index.html"], target_locator="#hero",
                    before=before_rule, after=after_rule, verifiable=True,
                )],
            )
            reasons = _reference_source_verification_reasons(
                session, implementation, snapshot
            )
            self.assertTrue(any("outside the verified reference property allowlist"
                                in item for item in reasons))

    def test_plain_locator_cannot_hide_a_broad_css_hunk(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, session = self.make_session(
                root, target_locator="hero", target_properties=["composition"]
            )
            before_rule = "#hero{display:block}\nfooter{display:block}"
            after_rule = "#hero{display:flex}\nfooter{display:none}"
            snapshot = root / "snapshot"
            snapshot.mkdir()
            (snapshot / "index.html").write_text(before_rule, encoding="utf-8")
            Path(session.project_path, "index.html").write_text(after_rule, encoding="utf-8")
            implementation = self.implementation(
                target_locator="hero", properties=["composition"],
                property_verifications=[ReferencePropertyVerification(
                    property="composition", target_component="hero-layout",
                    changed_files=["index.html"], target_locator="hero",
                    before=before_rule, after=after_rule, verifiable=True,
                )],
            )
            self.assertTrue(_reference_scope_rejection_reasons(session, implementation))
            self.assertTrue(_reference_source_verification_reasons(
                session, implementation, snapshot
            ))

    def test_mixed_css_and_content_hunk_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, session = self.make_session(
                root, target_locator='id="hero"',
                target_properties=["composition"],
            )
            before_markup = (
                '<section id="hero" style="display:block"><h1>Old</h1></section>'
            )
            after_markup = (
                '<section id="hero" style="display:grid"><h1>Invented claim</h1></section>'
            )
            snapshot = root / "snapshot"
            snapshot.mkdir()
            (snapshot / "index.html").write_text(before_markup, encoding="utf-8")
            Path(session.project_path, "index.html").write_text(after_markup, encoding="utf-8")
            implementation = self.implementation(
                target_locator='id="hero"', properties=["composition"],
                property_verifications=[ReferencePropertyVerification(
                    property="composition", target_component="hero-layout",
                    changed_files=["index.html"], target_locator='id="hero"',
                    before=before_markup, after=after_markup, verifiable=True,
                )],
            )
            reasons = _reference_source_verification_reasons(
                session, implementation, snapshot
            )
            self.assertTrue(any("outside the verified reference property allowlist"
                                in item for item in reasons))

    def test_non_css_reference_change_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, session = self.make_session(
                root, target_locator='id="hero"',
                target_properties=["composition"],
            )
            before_markup = '<section id="hero"><h1>Old</h1></section>'
            after_markup = '<section id="hero"><h1>Invented claim</h1></section>'
            snapshot = root / "snapshot"
            snapshot.mkdir()
            (snapshot / "index.html").write_text(before_markup, encoding="utf-8")
            Path(session.project_path, "index.html").write_text(
                after_markup, encoding="utf-8"
            )
            implementation = self.implementation(
                target_locator='id="hero"', properties=["composition"],
                property_verifications=[ReferencePropertyVerification(
                    property="composition", target_component="hero-layout",
                    changed_files=["index.html"], target_locator='id="hero"',
                    before=before_markup, after=after_markup, verifiable=True,
                )],
            )
            reasons = _reference_source_verification_reasons(
                session, implementation, snapshot
            )
            self.assertTrue(any("outside the verified reference property allowlist"
                                in item for item in reasons))


if __name__ == "__main__":
    unittest.main()
