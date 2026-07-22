from __future__ import annotations

import json
import shutil
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image, ImageChops, ImageDraw

from site_agent import cli
from site_agent.critic import TechnicalInspector
from site_agent.models import TechnicalGate
from site_agent.refinement import (
    FunctionalScenarioEvidence,
    RefinementAttachmentInput,
    RefinementBusinessData,
    RefinementError,
    RefinementImplementationResult,
    RefinementRequest,
    RefinementReviewResult,
    RefinementSession,
    RefinementStatus,
    RequirementState,
    SiteRefinementOrchestrator,
    _business_data_matches,
    _codex_sandbox_executable,
    _functional_coverage_passes,
    _numeric_claims_safe,
    _localhost_endpoint_open,
    _project_manifest,
    _sandboxed_command,
    _validate_local_command,
)


class PassingExecutor:
    def run(self, *, session, iteration_dir, attachments):
        Path(session.project_path, "index.html").write_text(
            f"<!doctype html><title>Refined iteration {session.iteration}</title>",
            encoding="utf-8",
        )
        return RefinementImplementationResult(
            summary="Implemented the active scoped requirements.",
            changed_files=["index.html"],
            completed_requirement_ids=[item.id for item in session.active_requirements],
            functional_qa_passed=True,
            content_qa_passed=True,
            animation_qa_passed=True,
            business_data_applied=False,
            placeholders_absent=True,
            browser_review_performed=True,
            functional_scenarios=[],
        )


class BlockingExecutor(PassingExecutor):
    def run(self, *, session, iteration_dir, attachments):
        result = super().run(
            session=session, iteration_dir=iteration_dir, attachments=attachments
        )
        result.blockers = ["Contacts are missing for the final contact path."]
        return result


class PassingReviewer:
    def review(self, *, session, iteration_dir, implementation, gate, screenshots):
        return RefinementReviewResult(
            decision="accept",
            visual_qa_passed=True,
            responsive_qa_passed=True,
            requirements_match=True,
            reference_comparison_passed=True,
            functional_qa_passed=True,
            content_qa_passed=True,
            animation_qa_passed=True,
            summary="Independent refinement review passed.",
        )


class ScopedReferenceExecutor:
    def run(self, *, session, iteration_dir, attachments):
        index = Path(session.project_path, "index.html")
        source = index.read_text(encoding="utf-8")
        if 'id="cards" data-immutable="unchanged"' not in source:
            raise AssertionError("The unrelated cards section changed before scoped refinement.")
        with Image.open(attachments[0]) as reference:
            reference = reference.convert("RGB")
            left = reference.getpixel((reference.width // 4, reference.height // 2))
            right = reference.getpixel((reference.width * 3 // 4, reference.height // 2))
        visual_rule = (
            "#hero[data-reference-applied=\"hero-composition\"]{"
            f"background:linear-gradient(90deg,rgb{left} 0 50%,rgb{right} 50% 100%);"
            "color:#fff}"
        )
        index.write_text(
            source.replace("</style>", visual_rule + "</style>", 1).replace(
                'id="hero"', 'id="hero" data-reference-applied="hero-composition"', 1
            ),
            encoding="utf-8",
        )
        return RefinementImplementationResult(
            summary="Applied the supplied composition reference to the hero only.",
            completed_requirement_ids=[item.id for item in session.active_requirements],
            functional_qa_passed=True,
            content_qa_passed=True,
            animation_qa_passed=True,
            placeholders_absent=True,
            browser_review_performed=True,
            functional_scenarios=[FunctionalScenarioEvidence(
                kind="cta", target="mailto:studio@example.test",
                states_checked=["default", "keyboard focus"], passed=True,
                evidence="Primary contact CTA rendered and remained reachable at every target width.",
            )],
        )


class ScopedReferenceReviewer(PassingReviewer):
    def review(self, *, session, iteration_dir, implementation, gate, screenshots):
        source = Path(session.project_path, "index.html").read_text(encoding="utf-8")
        scoped = 'id="hero" data-reference-applied="hero-composition"' in source
        unrelated = 'id="cards" data-immutable="unchanged"' in source
        session_dir = iteration_dir.parents[1]
        reference_path = session_dir / session.attachments[0].stored_path
        current_path = next((iteration_dir / "browser_qa").rglob("desktop.png"))
        baseline_path = session_dir / "baseline" / "browser" / "desktop.png"
        with Image.open(reference_path) as reference, Image.open(current_path) as current, \
             Image.open(baseline_path) as baseline:
            reference = reference.convert("RGB")
            current = current.convert("RGB")
            baseline = baseline.convert("RGB")
            colors = {
                reference.getpixel((reference.width // 4, reference.height // 2)),
                reference.getpixel((reference.width * 3 // 4, reference.height // 2)),
            }
            current_pixels = set(current.get_flattened_data())
            baseline_pixels = set(baseline.get_flattened_data())
            visual_transfer = colors.issubset(current_pixels) and not colors.issubset(baseline_pixels)
            crop_top = int(current.height * 0.55)
            global_isolation = ImageChops.difference(
                current.crop((0, crop_top, current.width, current.height)),
                baseline.crop((0, crop_top, baseline.width, baseline.height)),
            ).getbbox() is None
        result = super().review(
            session=session, iteration_dir=iteration_dir, implementation=implementation,
            gate=gate, screenshots=screenshots,
        )
        if not (scoped and unrelated and visual_transfer and global_isolation
                and gate.passed and screenshots):
            return result.model_copy(update={
                "decision": "revise", "reference_comparison_passed": False,
                "summary": "Scoped reference evidence did not pass independent review.",
            })
        return result


class FiveWidthInspector:
    widths = {
        "desktop_1440": "1440x1100",
        "desktop_1024": "1024x900",
        "tablet_768": "768x1024",
        "mobile_390": "390x844",
        "mobile_360": "360x800",
    }

    def inspect_url(self, url, artifacts_dir):
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        gate = TechnicalGate(passed=True)
        (artifacts_dir / "technical_gate.json").write_text(
            gate.model_dump_json(indent=2), encoding="utf-8"
        )
        observations = {
            name: json.dumps({"viewport": viewport})
            for name, viewport in self.widths.items()
        }
        captures = {
            "desktop.png": (1440, 64), "desktop_1024.png": (1024, 64),
            "tablet.png": (768, 64), "mobile.png": (390, 64),
            "mobile_360.png": (360, 64), "reduced_motion.png": (390, 64),
            "interaction_desktop_1440.png": (1440, 64),
            "interaction_desktop_1024.png": (1024, 64),
            "interaction_tablet_768.png": (768, 64),
            "interaction_mobile_390.png": (390, 64),
            "interaction_mobile_360.png": (360, 64),
        }
        for name, size in captures.items():
            Image.new("RGB", size, "white").save(artifacts_dir / name)
        (artifacts_dir / "observations.json").write_text(
            json.dumps(observations), encoding="utf-8"
        )
        return gate, observations


def make_project(root: Path) -> Path:
    project = root / "existing-site"
    project.mkdir()
    project.joinpath("index.html").write_text(
        "<!doctype html><title>Existing site</title>", encoding="utf-8"
    )
    return project


def make_browser_ready_project(root: Path) -> Path:
    project = root / "reference-site"
    project.mkdir()
    project.joinpath("index.html").write_text("""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Existing studio</title><style>
*{box-sizing:border-box}body{margin:0;font:18px/1.5 system-ui;color:#17202a;background:#f7f3eb}
header{position:sticky;top:0;z-index:2;background:#17202a;color:white;padding:12px 5vw}
a{color:inherit}.control{display:inline-flex;min-width:48px;min-height:48px;align-items:center;padding:10px 16px}
nav{display:flex;gap:12px;flex-wrap:wrap}main section{padding:12vh 7vw;min-height:70vh}
#hero{display:grid;place-items:center;background:#d9c6a2}#cards{background:#fff}
footer{padding:40px 5vw;background:#17202a;color:white}h1{font-size:clamp(2.2rem,7vw,6rem);max-width:12ch}
</style></head><body>
<header><nav aria-label="Primary"><a class="control" href="#hero">Home</a><a class="control" href="#cards">Work</a></nav></header>
<main><section id="hero"><div><h1>A considered existing studio</h1><a class="control" data-site-cta="primary" href="mailto:studio@example.test">Contact the studio</a></div></section>
<section id="cards" data-immutable="unchanged"><h2>Selected work</h2><p>This section must remain unchanged.</p></section></main>
<footer><nav aria-label="Footer"><a class="control" href="#hero">Home</a><a class="control" href="#cards">Work</a></nav><a class="control" href="mailto:studio@example.test">Email</a></footer>
</body></html>""", encoding="utf-8")
    return project


class RefinementStateTests(unittest.TestCase):
    def test_session_ids_cannot_escape_refinement_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workflow = SiteRefinementOrchestrator(runs_dir=Path(temp) / "runs")
            for session_id in (".", "..", ".hidden", "bad..segment"):
                with self.subTest(session_id=session_id), self.assertRaises(RefinementError):
                    workflow.session_dir(session_id)

    def test_refinement_artifacts_cannot_be_selected_as_projects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            artifact = root / "runs" / "refinement" / "session" / "candidate"
            artifact.mkdir(parents=True)
            (artifact / "index.html").write_text("candidate", encoding="utf-8")
            workflow = SiteRefinementOrchestrator(runs_dir=root / "runs")
            with self.assertRaises(RefinementError):
                workflow.resolve_project(str(artifact))

    def test_default_command_runner_wraps_commands_in_codex_workspace_sandbox(self) -> None:
        if not shutil.which("node"):
            self.skipTest("Node is unavailable")
        try:
            sandbox = _codex_sandbox_executable()
        except RefinementError as exc:
            self.skipTest(str(exc))
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            wrapped = _sandboxed_command(["node", "sandbox-check.js"], project)
            self.assertEqual(Path(wrapped[0]), sandbox)
            self.assertEqual(wrapped[1:4], ["sandbox", "-P", ":workspace"])
            self.assertEqual(Path(wrapped[5]), project.resolve())
            self.assertEqual(wrapped[6], "--")

    def test_requirements_accumulate_across_messages(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, runs = Path(temp), Path(temp) / "runs"
            project = make_project(root)
            workflow = SiteRefinementOrchestrator(runs_dir=runs)
            first = workflow.start(
                RefinementRequest(project=str(project), goal="Change the hero"),
                session_id="accumulate", execute=False,
            )
            second = workflow.continue_session(
                first.session_id,
                RefinementRequest(feedback=["Change the cards"]),
                execute=False,
            )
            self.assertEqual(
                [item.text for item in second.requirements],
                ["Change the hero", "Change the cards"],
            )
            self.assertTrue(all(item.state is RequirementState.ACTIVE for item in second.requirements))

    def test_explicit_supersession_retains_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, runs = Path(temp), Path(temp) / "runs"
            project = make_project(root)
            workflow = SiteRefinementOrchestrator(runs_dir=runs)
            first = workflow.start(
                RefinementRequest(project=str(project), goal="Use a light hero"),
                session_id="replace", execute=False,
            )
            old_id = first.requirements[0].id
            second = workflow.continue_session(
                "replace",
                RefinementRequest(feedback=["Replace it with a dark hero"], supersedes=[old_id]),
                execute=False,
            )
            self.assertEqual(second.requirements[0].state, RequirementState.SUPERSEDED)
            self.assertEqual([item.text for item in second.active_requirements],
                             ["Replace it with a dark hero"])

    def test_new_feedback_after_candidate_returns_to_implementing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, runs = Path(temp), Path(temp) / "runs"
            project = make_project(root)
            workflow = SiteRefinementOrchestrator(
                runs_dir=runs, executor=PassingExecutor(),
                reviewer=PassingReviewer(), inspector=FiveWidthInspector(),
            )
            candidate = workflow.start(
                RefinementRequest(project=str(project), goal="Refine the hero"),
                session_id="resume", execute=True,
            )
            self.assertEqual(candidate.status, RefinementStatus.CANDIDATE_READY)
            resumed = workflow.continue_session(
                "resume", RefinementRequest(feedback=["Tighten card spacing"]),
                execute=False,
            )
            self.assertEqual(resumed.status, RefinementStatus.IMPLEMENTING)
            self.assertEqual([item.text for item in resumed.active_requirements],
                             ["Tighten card spacing"])

    def test_missing_contacts_do_not_stop_safe_design_work(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, runs = Path(temp), Path(temp) / "runs"
            project = make_project(root)
            workflow = SiteRefinementOrchestrator(
                runs_dir=runs, executor=BlockingExecutor(),
                reviewer=PassingReviewer(), inspector=FiveWidthInspector(),
            )
            result = workflow.start(
                RefinementRequest(project=str(project), goal="Redesign only the cards"),
                session_id="partial", execute=True,
            )
            self.assertEqual(result.requirements[0].state, RequirementState.COMPLETED)
            self.assertEqual(result.status, RefinementStatus.BLOCKED)
            self.assertIn("Contacts are missing", result.blockers[0])

    def test_hero_reference_stays_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, runs = Path(temp), Path(temp) / "runs"
            project = make_project(root)
            reference = root / "hero.png"
            reference.write_bytes(b"reference")
            workflow = SiteRefinementOrchestrator(runs_dir=runs)
            session = workflow.start(RefinementRequest(
                project=str(project), goal="Match the hero composition",
                attachments=[RefinementAttachmentInput(
                    path=str(reference), kind="reference", target_page="home",
                    target_section="hero", interpretation="Use the split composition only",
                    transfer=["composition", "spacing"],
                )],
            ), session_id="reference", execute=False)
            mapping = session.attachments[0]
            self.assertEqual(mapping.target_section, "hero")
            self.assertNotIn("global", mapping.transfer)
            self.assertFalse(session.blockers)


class RefinementCandidateTests(unittest.TestCase):
    def test_failed_baseline_browser_capture_blocks_before_implementation(self) -> None:
        class FailingInspector:
            def inspect_url(self, url, artifacts_dir):
                raise RuntimeError("baseline browser unavailable")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = make_project(root)
            executor = Mock(wraps=PassingExecutor())
            workflow = SiteRefinementOrchestrator(
                runs_dir=root / "runs", executor=executor,
                reviewer=PassingReviewer(), inspector=FailingInspector(),
            )
            result = workflow.start(
                RefinementRequest(project=str(project), goal="Refine hero"),
                session_id="baseline-block", execute=True,
            )
            self.assertEqual(result.status, RefinementStatus.BLOCKED)
            executor.run.assert_not_called()

    def test_failed_baseline_can_be_archived_and_recaptured_on_continue(self) -> None:
        class RecoveringInspector(FiveWidthInspector):
            def __init__(self):
                self.fail = True

            def inspect_url(self, url, artifacts_dir):
                if self.fail:
                    raise RuntimeError("baseline browser unavailable")
                return super().inspect_url(url, artifacts_dir)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = make_project(root)
            inspector = RecoveringInspector()
            workflow = SiteRefinementOrchestrator(
                runs_dir=root / "runs", executor=PassingExecutor(),
                reviewer=PassingReviewer(), inspector=inspector,
            )
            blocked = workflow.start(
                RefinementRequest(project=str(project), goal="Refine hero"),
                session_id="baseline-retry", execute=True,
            )
            self.assertEqual(blocked.status, RefinementStatus.BLOCKED)
            inspector.fail = False
            result = workflow.continue_session(
                "baseline-retry", RefinementRequest(feedback=["Retry the same safe work"]),
                execute=True,
            )
            self.assertEqual(result.status, RefinementStatus.CANDIDATE_READY)
            self.assertTrue(any(
                (workflow.session_dir("baseline-retry") / "baseline_attempts").iterdir()
            ))

    def test_command_guard_rejects_direct_and_inline_external_actions(self) -> None:
        for command in (
            "curl https://example.test/hook", "git -c alias.ship=push ship",
            "powershell -EncodedCommand ZgBvAG8=", "python -c print(1)",
            "node --eval fetch('https://example.test')", "wrangler pages deploy dist",
        ):
            with self.subTest(command=command), self.assertRaises(RefinementError):
                _validate_local_command(command)

    def test_command_guard_checks_package_lifecycle_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            project.joinpath("package.json").write_text(json.dumps({
                "scripts": {
                    "prebuild": "wrangler pages deploy dist",
                    "build": "vite build",
                    "postbuild": "echo complete",
                }
            }), encoding="utf-8")
            with self.assertRaises(RefinementError):
                _validate_local_command("npm run build", project)

    def test_entry_path_must_stay_inside_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = make_project(root)
            outside = root / "outside.html"
            outside.write_text("outside", encoding="utf-8")
            workflow = SiteRefinementOrchestrator(runs_dir=root / "runs")
            session = RefinementSession(
                session_id="entry", project_id="site", project_path=str(project),
                user_goal="test", entry_path="../outside.html",
                created_at="now", updated_at="now",
            )
            with self.assertRaises(RefinementError):
                workflow._browser_target(session)

    def test_project_manifest_fails_closed_on_links(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = make_project(Path(temp))
            with patch("site_agent.refinement._unsafe_project_link", return_value=True):
                with self.assertRaises(RefinementError):
                    _project_manifest(project)

    def test_functional_scenario_target_must_exist_as_the_primary_cta(self) -> None:
        implementation = RefinementImplementationResult(
            summary="claimed", functional_qa_passed=True,
            functional_scenarios=[FunctionalScenarioEvidence(
                kind="cta", target="mailto:wrong@example.test",
                states_checked=["default"], passed=True, evidence="claimed",
            )],
        )
        observations = {"desktop": json.dumps({
            "viewport": "1440x1100", "primaryCtaCount": 1,
            "actionLinks": [{
                "href": "mailto:verified@example.test", "primary": True, "contact": True,
            }],
        })}
        self.assertFalse(_functional_coverage_passes(implementation, observations))

    def test_confirmed_contact_is_bound_to_the_actual_cta_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = make_project(root)
            workflow = SiteRefinementOrchestrator(runs_dir=root / "runs")
            session = RefinementSession(
                session_id="contact-binding", project_id="site", project_path=str(project),
                user_goal="test", business_data=RefinementBusinessData(
                    contacts=["verified@example.test"]
                ), baseline_path="baseline/baseline.json", created_at="now", updated_at="now",
            )
            session_dir = workflow.session_dir(session.session_id)
            (session_dir / "baseline").mkdir(parents=True)
            baseline_observations = {"desktop": json.dumps({
                "bodyText": "Old contact", "actionLinks": [],
            })}
            (session_dir / "baseline" / "baseline.json").write_text(
                json.dumps({"observations": baseline_observations}), encoding="utf-8"
            )
            observations = {"desktop": json.dumps({
                "bodyText": "verified@example.test",
                "actionLinks": [{
                    "href": "mailto:wrong@example.test", "primary": True, "contact": True,
                }],
            })}
            self.assertFalse(_business_data_matches(session, observations, session_dir))

    def test_reused_number_cannot_authorize_a_new_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = make_project(root)
            workflow = SiteRefinementOrchestrator(runs_dir=root / "runs")
            session = RefinementSession(
                session_id="numeric-context", project_id="site", project_path=str(project),
                user_goal="test", business_data=RefinementBusinessData(
                    address="20 Main Street"
                ), baseline_path="baseline/baseline.json", created_at="now", updated_at="now",
            )
            session_dir = workflow.session_dir(session.session_id)
            (session_dir / "baseline").mkdir(parents=True)
            (session_dir / "baseline" / "baseline.json").write_text(json.dumps({
                "observations": {"desktop": json.dumps({"bodyText": "Address: 20 Main Street."})}
            }), encoding="utf-8")
            observations = {"desktop": json.dumps({
                "bodyText": "Address: 20 Main Street. Trusted for 20 years."
            })}
            self.assertFalse(_numeric_claims_safe(session, observations, session_dir))

    def test_spelled_out_number_is_treated_as_a_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = make_project(root)
            workflow = SiteRefinementOrchestrator(runs_dir=root / "runs")
            session = RefinementSession(
                session_id="word-number", project_id="site", project_path=str(project),
                user_goal="test", baseline_path="baseline/baseline.json",
                created_at="now", updated_at="now",
            )
            session_dir = workflow.session_dir(session.session_id)
            (session_dir / "baseline").mkdir(parents=True)
            (session_dir / "baseline" / "baseline.json").write_text(json.dumps({
                "observations": {"desktop": json.dumps({"bodyText": "Existing studio."})}
            }), encoding="utf-8")
            observations = {"desktop": json.dumps({"bodyText": "Trusted for twenty years."})}
            self.assertFalse(_numeric_claims_safe(session, observations, session_dir))

    def test_exact_number_cannot_gain_inflating_modifiers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = make_project(root)
            workflow = SiteRefinementOrchestrator(runs_dir=root / "runs")
            session = RefinementSession(
                session_id="exact-number", project_id="site", project_path=str(project),
                user_goal="test", business_data=RefinementBusinessData(texts=["20 years"]),
                baseline_path="baseline/baseline.json", created_at="now", updated_at="now",
            )
            session_dir = workflow.session_dir(session.session_id)
            (session_dir / "baseline").mkdir(parents=True)
            (session_dir / "baseline" / "baseline.json").write_text(json.dumps({
                "observations": {"desktop": json.dumps({"bodyText": "Existing studio."})}
            }), encoding="utf-8")
            for claim in (
                "Over 20 years.", "20+ years.", "At least 20 years.",
                "Nearly 20 years.", "Up to 20 years.", "Fewer than 20 years.",
            ):
                with self.subTest(claim=claim):
                    observations = {"desktop": json.dumps({"bodyText": claim})}
                    self.assertFalse(_numeric_claims_safe(session, observations, session_dir))

    def test_business_data_must_be_present_in_rendered_observations(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, runs = Path(temp), Path(temp) / "runs"
            project = make_project(root)
            workflow = SiteRefinementOrchestrator(runs_dir=runs)
            session = RefinementSession(
                session_id="business", project_id="site", project_path=str(project),
                user_goal="test", business_data=RefinementBusinessData(
                    contacts=["verified@example.test"]
                ), created_at="now", updated_at="now",
                baseline_path="baseline/baseline.json",
            )
            session_dir = workflow.session_dir(session.session_id)
            (session_dir / "baseline").mkdir(parents=True)
            (session_dir / "baseline" / "baseline.json").write_text(
                json.dumps({"observations": {"desktop": json.dumps({"bodyText": "Old copy"})}}),
                encoding="utf-8",
            )
            implementation = PassingExecutor().run(
                session=session, iteration_dir=root, attachments=[]
            )
            review = PassingReviewer().review(
                session=session, iteration_dir=root, implementation=implementation,
                gate=TechnicalGate(passed=True), screenshots=[],
            )
            observations = {
                name: json.dumps({"viewport": viewport, "bodyText": "Old copy"})
                for name, viewport in FiveWidthInspector.widths.items()
            }
            commands = {"build": {"passed": True}, "tests": [{"passed": True}]}
            self.assertFalse(workflow._candidate_allowed(
                session, implementation, review, TechnicalGate(passed=True),
                observations, commands,
            ))

    def test_candidate_is_denied_without_all_five_browser_widths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = make_project(root)
            workflow = SiteRefinementOrchestrator(runs_dir=root / "runs")
            session = RefinementSession(
                session_id="gate", project_id="site", project_path=str(project),
                user_goal="test", created_at="now", updated_at="now",
            )
            implementation = PassingExecutor().run(
                session=session, iteration_dir=root, attachments=[]
            )
            review = PassingReviewer().review(
                session=session, iteration_dir=root, implementation=implementation,
                gate=TechnicalGate(passed=True), screenshots=[],
            )
            observations = {
                name: json.dumps({"viewport": viewport})
                for name, viewport in FiveWidthInspector.widths.items()
                if name != "mobile_360"
            }
            commands = {
                "build": {"passed": True}, "tests": [{"passed": True}],
            }
            self.assertFalse(workflow._candidate_allowed(
                session, implementation, review, TechnicalGate(passed=True),
                observations, commands,
            ))

    def test_acceptance_rejects_source_changed_after_candidate_qa(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, runs = Path(temp), Path(temp) / "runs"
            project = make_project(root)
            workflow = SiteRefinementOrchestrator(
                runs_dir=runs, executor=PassingExecutor(),
                reviewer=PassingReviewer(), inspector=FiveWidthInspector(),
            )
            session = workflow.start(
                RefinementRequest(project=str(project), goal="Refine hero"),
                session_id="stale", execute=True,
            )
            self.assertEqual(session.status, RefinementStatus.CANDIDATE_READY)
            project.joinpath("index.html").write_text("changed after QA", encoding="utf-8")
            with self.assertRaises(RefinementError):
                workflow.accept("stale")

    def test_acceptance_rejects_changed_browser_observations_or_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, runs = Path(temp), Path(temp) / "runs"
            project = make_project(root)
            workflow = SiteRefinementOrchestrator(
                runs_dir=runs, executor=PassingExecutor(),
                reviewer=PassingReviewer(), inspector=FiveWidthInspector(),
            )
            session = workflow.start(
                RefinementRequest(project=str(project), goal="Refine hero"),
                session_id="evidence", execute=True,
            )
            self.assertEqual(session.status, RefinementStatus.CANDIDATE_READY)
            observations = (
                workflow.session_dir("evidence") / "iterations" / "000" /
                "browser_qa" / "00-index" / "observations.json"
            )
            observations.write_text("{}", encoding="utf-8")
            with self.assertRaises(RefinementError):
                workflow.accept("evidence")

            session = workflow.load("evidence")
            observations.write_text(json.dumps({
                name: json.dumps({"viewport": viewport})
                for name, viewport in FiveWidthInspector.widths.items()
            }), encoding="utf-8")
            session.candidate_artifact_sha256[
                "browser_qa/00-index/observations.json"
            ] = __import__("hashlib").sha256(observations.read_bytes()).hexdigest()
            workflow._save(session)
            baseline = workflow.session_dir("evidence") / session.baseline_path
            baseline.write_text("{}", encoding="utf-8")
            with self.assertRaises(RefinementError):
                workflow.accept("evidence")

    def test_route_viewport_evidence_cannot_be_split_across_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = make_project(root)
            workflow = SiteRefinementOrchestrator(runs_dir=root / "runs")
            session = RefinementSession(
                session_id="routes", project_id="site", project_path=str(project),
                user_goal="test", created_at="now", updated_at="now",
            )
            implementation = PassingExecutor().run(
                session=session, iteration_dir=root, attachments=[]
            )
            review = PassingReviewer().review(
                session=session, iteration_dir=root, implementation=implementation,
                gate=TechnicalGate(passed=True), screenshots=[],
            )
            widths = list(FiveWidthInspector.widths.values())
            observations = {
                **{f"00-home:w{i}": json.dumps({"viewport": value})
                   for i, value in enumerate(widths[:3])},
                **{f"01-about:w{i}": json.dumps({"viewport": value})
                   for i, value in enumerate(widths[3:])},
            }
            commands = {"build": {"passed": True}, "tests": [{"passed": True}]}
            self.assertFalse(workflow._candidate_allowed(
                session, implementation, review, TechnicalGate(passed=True),
                observations, commands, route_count=2,
            ))

    def test_candidate_requires_decodable_width_bound_screenshot_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = make_project(root)
            workflow = SiteRefinementOrchestrator(runs_dir=root / "runs")
            session = RefinementSession(
                session_id="captures", project_id="site", project_path=str(project),
                user_goal="test", created_at="now", updated_at="now",
            )
            implementation = PassingExecutor().run(
                session=session, iteration_dir=root, attachments=[]
            )
            review = PassingReviewer().review(
                session=session, iteration_dir=root, implementation=implementation,
                gate=TechnicalGate(passed=True), screenshots=[],
            )
            observations = {
                name: json.dumps({"viewport": viewport})
                for name, viewport in FiveWidthInspector.widths.items()
            }
            browser = root / "browser"
            route = browser / "00-index"
            route.mkdir(parents=True)
            for name in ("desktop.png", "desktop_1024.png", "tablet.png",
                         "mobile.png", "mobile_360.png", "reduced_motion.png",
                         "interaction_desktop_1440.png", "interaction_desktop_1024.png",
                         "interaction_tablet_768.png", "interaction_mobile_390.png",
                         "interaction_mobile_360.png"):
                (route / name).write_bytes(b"not-a-png")
            commands = {"build": {"passed": True}, "tests": [{"passed": True}]}
            self.assertFalse(workflow._candidate_allowed(
                session, implementation, review, TechnicalGate(passed=True),
                observations, commands, browser_dir=browser,
            ))

    def test_acceptance_rejects_changed_baseline_image_and_recovery_snapshot(self) -> None:
        for session_id, target_kind in (("baseline-image", "baseline"), ("snapshot-tree", "snapshot")):
            with self.subTest(target_kind=target_kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                project = make_project(root)
                workflow = SiteRefinementOrchestrator(
                    runs_dir=root / "runs", executor=PassingExecutor(),
                    reviewer=PassingReviewer(), inspector=FiveWidthInspector(),
                )
                session = workflow.start(
                    RefinementRequest(project=str(project), goal="Refine hero"),
                    session_id=session_id, execute=True,
                )
                self.assertEqual(session.status, RefinementStatus.CANDIDATE_READY)
                if target_kind == "baseline":
                    target = (workflow.session_dir(session_id) / "baseline" / "browser" /
                              "00-index" / "desktop.png")
                else:
                    target = (workflow.session_dir(session_id) / "iterations" / "000" /
                              "pre_change_snapshot" / "index.html")
                target.write_bytes(target.read_bytes() + b"tampered")
                with self.assertRaises(RefinementError):
                    workflow.accept(session_id)

    def test_managed_server_is_stopped_when_browser_stage_raises(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = make_project(root)
            workflow = SiteRefinementOrchestrator(runs_dir=root / "runs")
            session = RefinementSession(
                session_id="server", project_id="site", project_path=str(project),
                user_goal="test", start_command="serve", preview_url="http://127.0.0.1:9999",
                created_at="now", updated_at="now",
            )
            process = Mock()
            process.poll.return_value = -15
            evidence = root / "evidence"
            with patch.object(workflow, "_start_server", return_value=process), \
                 patch.object(workflow, "_stop_server") as stop:
                with self.assertRaisesRegex(RuntimeError, "browser failure"):
                    with workflow._managed_server(session, evidence):
                        raise RuntimeError("browser failure")
            stop.assert_called_once_with(process)
            lifecycle = json.loads((evidence / "server_lifecycle.json").read_text(encoding="utf-8"))
            self.assertIn("stopped_at", lifecycle)
            self.assertEqual(lifecycle["return_code"], -15)
            self.assertTrue(lifecycle["cleanup_verified"])

    def test_live_tcp_listener_is_not_mistaken_for_completed_cleanup(self) -> None:
        process = Mock()
        process.poll.return_value = -15
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        try:
            self.assertTrue(_localhost_endpoint_open(f"http://127.0.0.1:{port}"))
            with patch("site_agent.refinement._localhost_endpoint_open", return_value=True):
                self.assertFalse(SiteRefinementOrchestrator._server_cleanup_verified(
                    process, f"http://127.0.0.1:{port}"
                ))
        finally:
            listener.close()
        unused = socket.socket()
        unused.bind(("127.0.0.1", 0))
        unused_port = unused.getsockname()[1]
        unused.close()
        self.assertFalse(_localhost_endpoint_open(f"http://127.0.0.1:{unused_port}"))
        wildcard = socket.socket()
        wildcard.bind(("0.0.0.0", 0))
        wildcard.listen()
        wildcard_port = wildcard.getsockname()[1]
        try:
            self.assertTrue(
                _localhost_endpoint_open(f"http://127.0.0.1:{wildcard_port}")
            )
        finally:
            wildcard.close()
        if socket.has_ipv6:
            dual_stack = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            try:
                dual_stack.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
                dual_stack.bind(("::", 0))
                dual_stack.listen()
                dual_port = dual_stack.getsockname()[1]
                self.assertTrue(
                    _localhost_endpoint_open(f"http://127.0.0.1:{dual_port}")
                )
            except OSError:
                pass  # The platform advertises IPv6 but does not permit dual-stack sockets.
            finally:
                dual_stack.close()

    def test_start_server_refuses_preexisting_non_http_listener(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = make_project(root)
            listener = socket.socket()
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]
            workflow = SiteRefinementOrchestrator(runs_dir=root / "runs")
            session = RefinementSession(
                session_id="occupied", project_id="site", project_path=str(project),
                user_goal="test", start_command="node server.js",
                preview_url=f"http://127.0.0.1:{port}", created_at="now", updated_at="now",
            )
            try:
                with self.assertRaisesRegex(RefinementError, "already has a listener"):
                    workflow._start_server(session, root / "evidence")
            finally:
                listener.close()


class RefinementBrowserIntegrationTests(unittest.TestCase):
    def test_reference_is_implemented_reviewed_and_rendered_only_in_scoped_hero(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root, runs = Path(temp), Path(temp) / "runs"
            project = make_browser_ready_project(root)
            reference = root / "hero-reference.png"
            reference_image = Image.new("RGB", (320, 180), "#c97842")
            ImageDraw.Draw(reference_image).rectangle((160, 0, 319, 179), fill="#20344a")
            reference_image.save(reference)
            workflow = SiteRefinementOrchestrator(
                runs_dir=runs, executor=ScopedReferenceExecutor(),
                reviewer=ScopedReferenceReviewer(),
                inspector=TechnicalInspector(viewport_profile="refinement"),
            )
            result = workflow.start(RefinementRequest(
                project=str(project), goal="Apply this reference only to the home hero",
                scope=["index.html#hero"],
                attachments=[RefinementAttachmentInput(
                    path=str(reference), kind="reference", target_page="index.html",
                    target_section="hero", interpretation="Use only the hero composition",
                    transfer=["composition", "spacing"],
                )],
            ), session_id="real-reference-cycle", execute=True)
            self.assertEqual(result.status, RefinementStatus.CANDIDATE_READY)
            source = project.joinpath("index.html").read_text(encoding="utf-8")
            self.assertIn('id="hero" data-reference-applied="hero-composition"', source)
            self.assertIn("linear-gradient", source)
            self.assertIn('id="cards" data-immutable="unchanged"', source)
            iteration = workflow.session_dir("real-reference-cycle") / "iterations" / "000"
            self.assertEqual(
                len(list((iteration / "browser_qa").rglob("desktop.png"))), 1,
            )
            self.assertTrue((iteration / "independent_review.json").is_file())


class RefinementCliTests(unittest.TestCase):
    def test_build_mode_go_dispatch_is_unchanged(self) -> None:
        with patch.object(sys, "argv", ["site-agent", "go"]), \
             patch.object(cli, "run_pending_job") as run_pending:
            cli.main()
        run_pending.assert_called_once_with()

    def test_direct_url_build_dispatch_is_unchanged(self) -> None:
        url = "https://www.instagram.com/example/"
        with patch.object(sys, "argv", ["site-agent", url]), \
             patch.object(cli, "run_instagram_url") as run_url:
            cli.main()
        run_url.assert_called_once_with(url)

    def test_refinement_command_uses_separate_dispatch(self) -> None:
        with patch.object(
            sys, "argv",
            ["site-agent", "refinement-status", "--session-id", "session-1"],
        ), patch.object(cli, "run_refinement_status") as status, \
             patch.object(cli, "run_pending_job") as build:
            cli.main()
        status.assert_called_once_with("session-1")
        build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
