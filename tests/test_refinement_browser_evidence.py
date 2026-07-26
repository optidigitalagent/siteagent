from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from PIL import Image
from playwright.sync_api import Error

from site_agent.critic import TechnicalInspector
from site_agent.models import TechnicalGate
from site_agent.refinement import (
    RefinementImplementationResult,
    RequirementChangeEvidence,
    RefinementRequirement,
    RefinementReviewResult,
    RefinementSession,
    RequirementState,
    SiteRefinementOrchestrator,
    _browser_evidence_rejection_reasons,
    _copy_project_snapshot,
    _payload_sha,
    _project_manifest,
    _requirement_authority_checksum,
)


class FixtureInspector:
    profiles = {
        "desktop_1440": "1440x1100",
        "desktop_1024": "1024x900",
        "tablet_768": "768x1024",
        "mobile_390": "390x844",
        "mobile_360": "360x800",
        "reduced_motion": "390x844",
    }
    captures = {
        "desktop.png": (1440, 8),
        "desktop_1024.png": (1024, 8),
        "tablet.png": (768, 8),
        "mobile.png": (390, 8),
        "mobile_360.png": (360, 8),
        "reduced_motion.png": (390, 8),
        "interaction_desktop_1440.png": (1440, 8),
        "interaction_desktop_1024.png": (1024, 8),
        "interaction_tablet_768.png": (768, 8),
        "interaction_mobile_390.png": (390, 8),
        "interaction_mobile_360.png": (360, 8),
    }

    def inspect_url(self, url, artifacts_dir):
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        observations = {
            name: json.dumps({"viewport": viewport})
            for name, viewport in self.profiles.items()
        }
        for name, size in self.captures.items():
            Image.new("RGB", size, "white").save(artifacts_dir / name)
        gate = TechnicalGate(passed=True)
        (artifacts_dir / "technical_gate.json").write_text(
            gate.model_dump_json(indent=2), encoding="utf-8"
        )
        (artifacts_dir / "observations.json").write_text(
            json.dumps({"url": url, **observations}), encoding="utf-8"
        )
        return gate, observations


class RefinementBrowserEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        self.project.mkdir()
        (self.project / "index.html").write_text(
            "<!doctype html><title>Candidate</title>", encoding="utf-8"
        )
        self.workflow = SiteRefinementOrchestrator(
            runs_dir=self.root / "runs", inspector=FixtureInspector()
        )
        self.session = RefinementSession(
            session_id="browser-binding", project_id="project",
            project_path=str(self.project), user_goal="Refine the page",
            requirements=[RefinementRequirement(
                id="req-complete", text="Refine the page",
                state=RequirementState.COMPLETED, created_at="now", iteration=0,
                resolution="Implemented and browser verified.",
            )],
            baseline_path="baseline/baseline.json",
            created_at="now", updated_at="now",
        )
        baseline = self.workflow.session_dir(self.session.session_id) / self.session.baseline_path
        baseline.parent.mkdir(parents=True, exist_ok=True)
        baseline.write_text(json.dumps({"observations": {}}), encoding="utf-8")
        self.artifact_root = (
            self.workflow.session_dir(self.session.session_id) / "iterations" / "000"
        )
        self.snapshot_dir = self.artifact_root / "pre_change_snapshot"
        _copy_project_snapshot(self.project, self.snapshot_dir)
        plan = {
            "schema_version": 2,
            "session_id": self.session.session_id,
            "project_id": self.session.project_id,
            "iteration": self.session.iteration,
            "active_requirements": [self.session.requirements[0].model_dump(mode="json")],
            "requirements_authority_sha256": _requirement_authority_checksum(
                self.session.requirements
            ),
            "immutable_constraints": [],
            "scope": [],
            "reference_mappings": [],
        }
        (self.artifact_root / "change_plan.json").write_text(
            json.dumps(plan), encoding="utf-8"
        )
        self.session.current_change_plan_sha256 = _payload_sha(plan)
        self.browser_dir = self.artifact_root / "browser_qa"
        self.source_sha = _project_manifest(self.project)["tree_sha256"]
        self.gate, self.observations = self.workflow._inspect_targets(
            [(self.project / "index.html").resolve().as_uri()],
            self.browser_dir, self.project,
            session_id=self.session.session_id, iteration=0,
            source_tree_sha256=self.source_sha,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @property
    def manifest_path(self) -> Path:
        return self.browser_dir / "browser_evidence_manifest.json"

    def reasons(self) -> list[str]:
        return _browser_evidence_rejection_reasons(
            self.browser_dir, artifact_root=self.artifact_root,
            session_id=self.session.session_id, iteration=self.session.iteration,
            source_tree_sha256=_project_manifest(self.project)["tree_sha256"],
        )

    def edit_manifest(self, edit) -> None:
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        edit(manifest)
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def candidate_allowed(self, reasons: list[str], *, observations=None,
                          route_count: int = 1) -> bool:
        implementation = RefinementImplementationResult(
            summary="Complete", changed_files=["index.html"],
            completed_requirement_ids=["req-complete"],
            functional_qa_passed=True, content_qa_passed=True,
            animation_qa_passed=True, placeholders_absent=True,
            browser_review_performed=True,
            requirement_change_evidence=[RequirementChangeEvidence(
                requirement_id="req-complete",
                changed_files=["index.html"],
                evidence="The computed index.html change implements req-complete.",
            )],
        )
        review = RefinementReviewResult(
            decision="accept", visual_qa_passed=True,
            responsive_qa_passed=True, requirements_match=True,
            reference_comparison_passed=True, functional_qa_passed=True,
            content_qa_passed=True, animation_qa_passed=True,
            summary="Accepted",
        )
        commands = {"build": {"passed": True}, "tests": [{"passed": True}]}
        self.last_candidate_inputs = (implementation, review, commands)
        return self.workflow._candidate_allowed(
            self.session, implementation, review, self.gate,
            observations or self.observations, commands,
            browser_dir=self.browser_dir, route_count=route_count,
            snapshot_dir=self.snapshot_dir,
            rejection_reasons=reasons,
        )

    def test_current_source_bound_evidence_passes(self) -> None:
        self.assertEqual(self.reasons(), [])

    def test_source_change_invalidates_evidence_and_candidate(self) -> None:
        (self.project / "index.html").write_text("changed after capture", encoding="utf-8")
        reasons: list[str] = []
        self.assertFalse(self.candidate_allowed(reasons))
        self.assertIn("browser evidence source tree mismatch.", reasons)
        self.assertIn("stale browser evidence after source change.", reasons)
        implementation, review, commands = self.last_candidate_inputs
        self.workflow._write_report(
            self.session, self.artifact_root, implementation, review, self.gate,
            commands, candidate_rejection_reasons=reasons,
        )
        report = json.loads(
            (self.artifact_root / "candidate_report.json").read_text(encoding="utf-8")
        )
        self.assertIn(
            "stale browser evidence after source change.",
            report["candidate_readiness"]["rejection_reasons"],
        )

    def test_previous_iteration_evidence_is_rejected(self) -> None:
        self.edit_manifest(lambda manifest: manifest.update(iteration=1))
        self.assertIn("browser evidence belongs to a different iteration.", self.reasons())

    def test_malformed_manifest_and_routes_are_candidate_denials(self) -> None:
        self.manifest_path.write_text("[]", encoding="utf-8")
        self.assertEqual(
            self.reasons(), ["browser evidence manifest is missing or invalid."]
        )
        self.workflow._inspect_targets(
            [(self.project / "index.html").resolve().as_uri()],
            self.browser_dir, self.project,
            session_id=self.session.session_id, iteration=0,
            source_tree_sha256=self.source_sha,
        )
        (self.browser_dir / "routes.json").write_text("[]", encoding="utf-8")
        self.assertIn("missing route/viewport browser evidence.", self.reasons())

    def test_wrong_viewport_dimensions_are_rejected(self) -> None:
        Image.new("RGB", (391, 8), "white").save(
            self.browser_dir / "00-index" / "mobile.png"
        )
        self.assertIn("viewport width mismatch in browser evidence.", self.reasons())

    def test_invalid_png_is_rejected_with_candidate_report_reason(self) -> None:
        (self.browser_dir / "00-index" / "mobile.png").write_bytes(b"not-a-png")
        reasons: list[str] = []
        self.assertFalse(self.candidate_allowed(reasons))
        self.assertIn("invalid PNG in browser evidence.", reasons)
        implementation, review, commands = self.last_candidate_inputs
        self.workflow._write_report(
            self.session, self.artifact_root, implementation, review, self.gate,
            commands, candidate_rejection_reasons=reasons,
        )
        report = json.loads(
            (self.artifact_root / "candidate_report.json").read_text(encoding="utf-8")
        )
        self.assertIn(
            "invalid PNG in browser evidence.",
            report["candidate_readiness"]["rejection_reasons"],
        )

    def test_screenshot_checksum_mismatch_is_rejected(self) -> None:
        Image.new("RGB", (390, 8), "black").save(
            self.browser_dir / "00-index" / "mobile.png"
        )
        self.assertIn("screenshot checksum mismatch in browser evidence.", self.reasons())

    def test_observations_checksum_mismatch_is_rejected(self) -> None:
        observations = self.browser_dir / "00-index" / "observations.json"
        observations.write_text("{}", encoding="utf-8")
        self.assertIn("observations checksum mismatch in browser evidence.", self.reasons())

    def test_missing_route_viewport_is_rejected(self) -> None:
        self.edit_manifest(lambda manifest: manifest["entries"].__setitem__(
            slice(None), [entry for entry in manifest["entries"]
                          if not (entry["evidence_type"] == "normal"
                                  and entry["viewport_width"] == 360)]
        ))
        self.assertIn("missing route/viewport browser evidence.", self.reasons())

    def test_duplicate_screenshot_reuse_is_rejected(self) -> None:
        def duplicate(manifest):
            manifest["entries"][1]["screenshot_path"] = manifest["entries"][0]["screenshot_path"]

        self.edit_manifest(duplicate)
        self.assertIn("duplicate screenshot reuse in browser evidence.", self.reasons())

    def test_reduced_motion_does_not_replace_normal_viewport(self) -> None:
        self.edit_manifest(lambda manifest: manifest["entries"].__setitem__(
            slice(None), [entry for entry in manifest["entries"]
                          if not (entry["evidence_type"] == "normal"
                                  and entry["viewport_width"] == 390)]
        ))
        self.assertTrue(any(
            entry["evidence_type"] == "reduced-motion"
            and entry["viewport_width"] == 390
            for entry in json.loads(self.manifest_path.read_text(encoding="utf-8"))["entries"]
        ))
        self.assertIn("missing route/viewport browser evidence.", self.reasons())

    def test_baseline_screenshot_cannot_satisfy_candidate_evidence(self) -> None:
        baseline_image = self.artifact_root.parents[1] / "baseline" / "browser" / "desktop.png"
        baseline_image.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1440, 8), "white").save(baseline_image)

        def use_baseline(manifest):
            manifest["entries"][0]["screenshot_path"] = "../../../baseline/browser/desktop.png"

        self.edit_manifest(use_baseline)
        self.assertIn(
            "baseline or previous-iteration screenshot cannot satisfy candidate browser evidence.",
            self.reasons(),
        )

    def test_browser_artifact_root_link_is_rejected(self) -> None:
        external = self.root / "external-browser-evidence"
        self.browser_dir.rename(external)
        try:
            self.browser_dir.symlink_to(external, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"directory symlinks are unavailable: {exc}")
        self.assertIn(
            "browser evidence symlink/junction escapes the current iteration artifact root.",
            self.reasons(),
        )

    def test_actual_url_from_another_route_is_rejected(self) -> None:
        self.edit_manifest(lambda manifest: manifest["entries"][0].update(
            actual_url=(self.project / "about.html").resolve().as_uri()
        ))
        self.assertIn("browser evidence belongs to a different route.", self.reasons())

    def test_actual_url_from_another_hash_route_is_rejected(self) -> None:
        self.edit_manifest(lambda manifest: manifest["entries"][0].update(
            actual_url=manifest["entries"][0]["requested_url"] + "#other-route"
        ))
        self.assertIn("browser evidence belongs to a different route.", self.reasons())

    def test_valid_full_matrix_remains_candidate_compatible(self) -> None:
        reasons: list[str] = []
        self.assertTrue(self.candidate_allowed(reasons), reasons)
        self.assertEqual(reasons, [])

    def test_valid_multi_route_full_matrix_remains_candidate_compatible(self) -> None:
        (self.project / "about.html").write_text(
            "<!doctype html><title>About</title>", encoding="utf-8"
        )
        source_sha = _project_manifest(self.project)["tree_sha256"]
        gate, observations = self.workflow._inspect_targets(
            [
                (self.project / "index.html").resolve().as_uri(),
                (self.project / "about.html").resolve().as_uri(),
            ],
            self.browser_dir, self.project,
            session_id=self.session.session_id, iteration=0,
            source_tree_sha256=source_sha,
        )
        self.gate = gate
        self.assertEqual(self.reasons(), [])
        reasons: list[str] = []
        self.assertTrue(self.candidate_allowed(
            reasons, observations=observations, route_count=2
        ), reasons)


class ScreenshotRetryTests(unittest.TestCase):
    def test_playwright_error_retries_and_second_capture_succeeds(self) -> None:
        page = Mock()
        page.screenshot.side_effect = [Error("transient capture failure"), None]
        TechnicalInspector()._take_screenshot(page, Path("capture.png"))
        self.assertEqual(page.screenshot.call_count, 2)
        page.wait_for_timeout.assert_called_once_with(250)


if __name__ == "__main__":
    unittest.main()
