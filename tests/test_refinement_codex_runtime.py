from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from site_agent.config import settings
from site_agent.refinement import (
    CodexRefinementExecutor,
    CodexRefinementReviewer,
    RefinementError,
    RefinementImplementationResult,
    RefinementRequest,
    RefinementRuntimeError,
    RefinementSession,
    RefinementStatus,
    SiteRefinementOrchestrator,
    _resolved_refinement_executable,
)
from site_agent.models import TechnicalGate
from tests.test_site_refinement import FiveWidthInspector, PassingExecutor, PassingReviewer


FAKE_CODEX = r"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

args = sys.argv[1:]
project = Path(args[args.index("-C") + 1])
output = Path(args[args.index("-o") + 1])
sandbox = args[args.index("--sandbox") + 1]
mode = project.joinpath("fake_mode.txt").read_text(encoding="utf-8").strip()
if mode == "early_child_success":
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    project.joinpath("child.pid").write_text(str(child.pid), encoding="utf-8")
if mode == "no_stdin_timeout":
    time.sleep(60)
prompt = sys.stdin.read()
session_match = re.search(r'"session_id"\s*:\s*"([^"]+)"', prompt)
iteration_match = re.search(r'"iteration"\s*:\s*(-?\d+)', prompt)
session_id = session_match.group(1) if session_match else ""
iteration = int(iteration_match.group(1)) if iteration_match else -1

implementation = {
    "summary": "Fake executor completed.",
    "changed_files": ["index.html"],
    "completed_requirement_ids": [],
    "open_requirement_ids": [],
    "rejected_requirements": {},
    "blockers": [],
    "remaining_differences": [],
    "functional_qa_passed": True,
    "content_qa_passed": True,
    "animation_qa_passed": True,
    "business_data_applied": False,
    "placeholders_absent": True,
    "browser_review_performed": True,
    "functional_scenarios": [],
}
review = {
    "decision": "accept",
    "visual_qa_passed": True,
    "responsive_qa_passed": True,
    "requirements_match": True,
    "reference_comparison_passed": True,
    "functional_qa_passed": True,
    "content_qa_passed": True,
    "animation_qa_passed": True,
    "issues": [],
    "remaining_differences": [],
    "summary": "Fake reviewer accepted.",
}

print("fake stdout", flush=True)
print("fake stderr", file=sys.stderr, flush=True)
if mode in {"timeout", "child_timeout"}:
    if mode == "child_timeout":
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        project.joinpath("child.pid").write_text(str(child.pid), encoding="utf-8")
    time.sleep(60)
elif mode == "nonzero":
    raise SystemExit(7)
elif mode == "missing":
    pass
elif mode == "empty":
    output.write_bytes(b"")
elif mode == "malformed":
    output.write_text("{not-json", encoding="utf-8")
elif mode == "schema_invalid":
    output.write_text(json.dumps({
        "session_id": session_id, "iteration": iteration, "unexpected": True,
    }), encoding="utf-8")
else:
    if mode == "executor_success":
        project.joinpath("index.html").write_text("<!doctype html><title>Changed</title>", encoding="utf-8")
    if mode == "reviewer_modify":
        project.joinpath("index.html").write_text("reviewer mutation", encoding="utf-8")
    if mode == "reviewer_modify_ignored":
        project.joinpath("node_modules").mkdir(exist_ok=True)
        project.joinpath("node_modules", "reviewer-write.txt").write_text("mutation", encoding="utf-8")
    if mode == "child_success":
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        project.joinpath("child.pid").write_text(str(child.pid), encoding="utf-8")
    secret = os.environ.get("SITEAGENT_RUNTIME_SECRET", "")
    if secret:
        print(secret, flush=True)
    if mode == "large_output":
        print("x" * 10000, flush=True)
    payload = {**(review if sandbox == "read-only" else implementation),
               "session_id": session_id, "iteration": iteration}
    if mode == "session_mismatch":
        payload = {**payload, "session_id": "another-session", "iteration": 99}
    output.write_text(json.dumps(payload), encoding="utf-8")
"""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def process_is_alive(pid: int) -> bool:
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0 and f'"{pid}"' in result.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class RefinementCodexRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.project.joinpath("index.html").write_text(
            "<!doctype html><title>Original</title>", encoding="utf-8"
        )
        self.fake_codex = self.root / "fake_codex.py"
        self.fake_codex.write_text(textwrap.dedent(FAKE_CODEX), encoding="utf-8")
        self.iteration = self.root / "runs" / "refinement" / "session" / "iterations" / "000"
        self.iteration.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def session(self) -> RefinementSession:
        return RefinementSession(
            session_id="session",
            project_id="project",
            project_path=str(self.project),
            user_goal="Refine the existing site",
            created_at="2026-07-26T00:00:00+00:00",
            updated_at="2026-07-26T00:00:00+00:00",
        )

    @contextmanager
    def runtime_settings(self):
        with patch.multiple(
            settings,
            refinement_codex_executable=str(self.fake_codex),
            refinement_codex_model="",
            codex_model="",
            refinement_graceful_termination_timeout_seconds=1,
            refinement_max_stdout_bytes=4096,
            refinement_max_stderr_bytes=4096,
        ):
            yield

    def set_mode(self, mode: str) -> None:
        self.project.joinpath("fake_mode.txt").write_text(mode, encoding="utf-8")

    def runtime(self, role: str) -> tuple[Path, dict]:
        directory = self.iteration / ("implementation" if role == "executor" else "independent_review")
        path = directory / "runtime.json"
        return directory, json.loads(path.read_text(encoding="utf-8"))

    def test_successful_executor_runtime_persists_streams_hashes_and_typed_result(self) -> None:
        self.set_mode("executor_success")
        with self.runtime_settings():
            result = CodexRefinementExecutor(timeout=5).run(
                session=self.session(), iteration_dir=self.iteration, attachments=[]
            )
        self.assertIsInstance(result, RefinementImplementationResult)
        directory, evidence = self.runtime("executor")
        self.assertEqual(evidence["result_parsing_status"], "validated")
        self.assertFalse(evidence["timed_out"])
        self.assertEqual(evidence["cleanup_status"], "confirmed")
        self.assertEqual(evidence["working_directory"], str(self.project.resolve()))
        self.assertIn(
            "sandbox_workspace_write.network_access=false",
            evidence["command_arguments"],
        )
        self.assertEqual(evidence["stdout_sha256"], sha256(directory / "stdout.log"))
        self.assertEqual(evidence["stderr_sha256"], sha256(directory / "stderr.log"))
        self.assertIn("fake stdout", (directory / "stdout.log").read_text(encoding="utf-8"))
        self.assertIn("fake stderr", (directory / "stderr.log").read_text(encoding="utf-8"))

    def test_successful_reviewer_runtime_preserves_project_manifest(self) -> None:
        self.set_mode("reviewer_success")
        implementation = RefinementImplementationResult(summary="Ready")
        before = sha256(self.project / "index.html")
        with self.runtime_settings():
            result = CodexRefinementReviewer(timeout=5).review(
                session=self.session(), iteration_dir=self.iteration,
                implementation=implementation, gate=TechnicalGate(passed=True), screenshots=[],
            )
        self.assertEqual(result.decision, "accept")
        _, evidence = self.runtime("reviewer")
        self.assertEqual(evidence["project_tree_hash_before"], evidence["project_tree_hash_after"])
        self.assertFalse(evidence["project_modified_by_reviewer"])
        self.assertEqual(before, sha256(self.project / "index.html"))

    def test_executor_timeout_is_controlled_and_evidence_survives(self) -> None:
        self.set_mode("timeout")
        started = time.monotonic()
        with self.runtime_settings(), self.assertRaises(RefinementRuntimeError) as caught:
            CodexRefinementExecutor(timeout=1).run(
                session=self.session(), iteration_dir=self.iteration, attachments=[]
            )
        self.assertLess(time.monotonic() - started, 8)
        self.assertIn("timeout", caught.exception.reason)
        directory, evidence = self.runtime("executor")
        self.assertTrue(evidence["timed_out"])
        self.assertEqual(evidence["cleanup_status"], "confirmed")
        self.assertTrue((directory / "stdout.log").is_file())
        self.assertTrue((directory / "stderr.log").is_file())

    def test_timeout_bounds_nonreading_stdin_process(self) -> None:
        self.set_mode("no_stdin_timeout")
        session = self.session()
        session.user_goal = "x" * (2 * 1024 * 1024)
        started = time.monotonic()
        with self.runtime_settings(), self.assertRaises(RefinementRuntimeError) as caught:
            CodexRefinementExecutor(timeout=1).run(
                session=session, iteration_dir=self.iteration, attachments=[]
            )
        self.assertLess(time.monotonic() - started, 8)
        self.assertIn("timeout", caught.exception.reason)

    def test_timeout_terminates_child_process_tree(self) -> None:
        self.set_mode("child_timeout")
        with self.runtime_settings(), self.assertRaises(RefinementRuntimeError):
            CodexRefinementExecutor(timeout=1).run(
                session=self.session(), iteration_dir=self.iteration, attachments=[]
            )
        child_pid = int(self.project.joinpath("child.pid").read_text(encoding="utf-8"))
        deadline = time.monotonic() + 3
        while process_is_alive(child_pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        _, evidence = self.runtime("executor")
        self.assertFalse(process_is_alive(child_pid), evidence)
        self.assertFalse(evidence["detected_remaining_processes"])

    def test_successful_parent_cannot_leave_child_process_running(self) -> None:
        self.set_mode("child_success")
        with self.runtime_settings():
            CodexRefinementExecutor(timeout=5).run(
                session=self.session(), iteration_dir=self.iteration, attachments=[]
            )
        child_pid = int(self.project.joinpath("child.pid").read_text(encoding="utf-8"))
        deadline = time.monotonic() + 3
        while process_is_alive(child_pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        _, evidence = self.runtime("executor")
        self.assertFalse(process_is_alive(child_pid), evidence)
        self.assertEqual(evidence["cleanup_status"], "confirmed")

    def test_child_spawned_before_prompt_is_job_contained(self) -> None:
        self.set_mode("early_child_success")
        with self.runtime_settings():
            CodexRefinementExecutor(timeout=5).run(
                session=self.session(), iteration_dir=self.iteration, attachments=[]
            )
        child_pid = int(self.project.joinpath("child.pid").read_text(encoding="utf-8"))
        deadline = time.monotonic() + 3
        while process_is_alive(child_pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        _, evidence = self.runtime("executor")
        self.assertFalse(process_is_alive(child_pid), evidence)
        self.assertEqual(evidence["cleanup_status"], "confirmed")

    def test_nonzero_exit_fails_closed_with_durable_streams(self) -> None:
        self.set_mode("nonzero")
        with self.runtime_settings(), self.assertRaisesRegex(RefinementRuntimeError, "non-zero"):
            CodexRefinementExecutor(timeout=5).run(
                session=self.session(), iteration_dir=self.iteration, attachments=[]
            )
        directory, evidence = self.runtime("executor")
        self.assertEqual(evidence["return_code"], 7)
        self.assertTrue((directory / "stdout.log").is_file())
        self.assertTrue((directory / "stderr.log").is_file())

    def test_missing_executable_fails_closed_with_runtime_evidence(self) -> None:
        self.set_mode("executor_success")
        missing = self.root / "missing-codex-executable"
        with self.runtime_settings(), \
                patch.object(settings, "refinement_codex_executable", str(missing)), \
                self.assertRaises(RefinementRuntimeError):
            CodexRefinementExecutor(timeout=5).run(
                session=self.session(), iteration_dir=self.iteration, attachments=[]
            )
        directory, evidence = self.runtime("executor")
        self.assertIn("executable not found", evidence["failure_reason"])
        self.assertEqual(evidence["cleanup_status"], "not_started")
        self.assertTrue((directory / "stdout.log").is_file())

    def test_shell_wrapper_executable_is_rejected_before_launch(self) -> None:
        wrapper = self.root / "not-codex.cmd"
        wrapper.write_text("@exit /b 0", encoding="utf-8")
        with patch.object(settings, "refinement_codex_executable", str(wrapper)), \
                self.assertRaises(RefinementError):
            _resolved_refinement_executable()

    def test_default_windows_launcher_uses_native_resolver(self) -> None:
        with patch.object(settings, "refinement_codex_executable", ""), \
                patch("site_agent.refinement._codex_sandbox_executable",
                      return_value=Path(sys.executable)):
            executable, prefix = _resolved_refinement_executable()
        self.assertEqual(Path(executable), Path(sys.executable))
        self.assertEqual(prefix, [str(Path(sys.executable))])

    def test_default_launcher_fails_closed_when_native_resolver_fails(self) -> None:
        with patch.object(settings, "refinement_codex_executable", ""), \
                patch("site_agent.refinement._codex_sandbox_executable",
                      side_effect=RefinementError("native unavailable")), \
                self.assertRaises(RefinementError):
            _resolved_refinement_executable()

    def test_setup_failure_is_controlled_and_persists_runtime_evidence(self) -> None:
        self.set_mode("executor_success")
        result_path = self.iteration / "implementation" / "result.json"
        result_path.mkdir(parents=True)
        with self.runtime_settings(), self.assertRaises(RefinementRuntimeError) as caught:
            CodexRefinementExecutor(timeout=5).run(
                session=self.session(), iteration_dir=self.iteration, attachments=[]
            )
        _, evidence = self.runtime("executor")
        self.assertIn("runtime setup", caught.exception.reason)
        self.assertEqual(evidence["result_parsing_status"], "setup_failed")

    def test_preflight_link_failure_persists_runtime_evidence(self) -> None:
        self.set_mode("executor_success")
        with self.runtime_settings(), \
                patch("site_agent.refinement._unsafe_project_link",
                      side_effect=lambda path: path.name == "result.json"), \
                self.assertRaises(RefinementRuntimeError) as caught:
            CodexRefinementExecutor(timeout=5).run(
                session=self.session(), iteration_dir=self.iteration, attachments=[]
            )
        _, evidence = self.runtime("executor")
        self.assertTrue(caught.exception.evidence_path)
        self.assertEqual(evidence["result_parsing_status"], "artifact_escape")

    def test_empty_result_fails_closed(self) -> None:
        self.set_mode("empty")
        with self.runtime_settings(), self.assertRaises(RefinementRuntimeError):
            CodexRefinementExecutor(timeout=5).run(
                session=self.session(), iteration_dir=self.iteration, attachments=[]
            )
        _, evidence = self.runtime("executor")
        self.assertEqual(evidence["result_parsing_status"], "empty")

    def test_malformed_json_fails_closed(self) -> None:
        self.set_mode("malformed")
        with self.runtime_settings(), self.assertRaises(RefinementRuntimeError):
            CodexRefinementExecutor(timeout=5).run(
                session=self.session(), iteration_dir=self.iteration, attachments=[]
            )
        _, evidence = self.runtime("executor")
        self.assertEqual(evidence["result_parsing_status"], "malformed_json")

    def test_missing_result_removes_stale_artifact_and_fails_closed(self) -> None:
        self.set_mode("missing")
        output = self.iteration / "implementation" / "result.json"
        output.parent.mkdir(parents=True)
        output.write_text(json.dumps({"summary": "stale success"}), encoding="utf-8")
        with self.runtime_settings(), self.assertRaises(RefinementRuntimeError):
            CodexRefinementExecutor(timeout=5).run(
                session=self.session(), iteration_dir=self.iteration, attachments=[]
            )
        _, evidence = self.runtime("executor")
        self.assertEqual(evidence["result_parsing_status"], "missing")
        self.assertFalse(output.exists())

    def test_schema_invalid_result_fails_closed(self) -> None:
        self.set_mode("schema_invalid")
        with self.runtime_settings(), self.assertRaises(RefinementRuntimeError):
            CodexRefinementExecutor(timeout=5).run(
                session=self.session(), iteration_dir=self.iteration, attachments=[]
            )
        _, evidence = self.runtime("executor")
        self.assertEqual(evidence["result_parsing_status"], "schema_invalid")

    def test_result_bound_to_another_session_is_rejected(self) -> None:
        self.set_mode("session_mismatch")
        with self.runtime_settings(), self.assertRaises(RefinementRuntimeError):
            CodexRefinementExecutor(timeout=5).run(
                session=self.session(), iteration_dir=self.iteration, attachments=[]
            )
        _, evidence = self.runtime("executor")
        self.assertEqual(evidence["result_parsing_status"], "session_mismatch")

    def test_stdout_capture_is_bounded_and_marked_truncated(self) -> None:
        self.set_mode("large_output")
        with self.runtime_settings(), \
                patch.object(settings, "refinement_max_stdout_bytes", 1024):
            CodexRefinementExecutor(timeout=5).run(
                session=self.session(), iteration_dir=self.iteration, attachments=[]
            )
        directory, evidence = self.runtime("executor")
        self.assertTrue(evidence["stdout_truncated"])
        self.assertLessEqual((directory / "stdout.log").stat().st_size, 1024)

    def test_reviewer_project_mutation_is_recorded_and_rejected(self) -> None:
        self.set_mode("reviewer_modify")
        with self.runtime_settings(), self.assertRaisesRegex(RefinementRuntimeError, "modified"):
            CodexRefinementReviewer(timeout=5).review(
                session=self.session(), iteration_dir=self.iteration,
                implementation=RefinementImplementationResult(summary="Ready"),
                gate=TechnicalGate(passed=True), screenshots=[],
            )
        _, evidence = self.runtime("reviewer")
        self.assertTrue(evidence["project_modified_by_reviewer"])
        self.assertIn("index.html", evidence["project_manifest_diff"]["modified"])

    def test_reviewer_mutation_in_previously_ignored_tree_is_rejected(self) -> None:
        self.set_mode("reviewer_modify_ignored")
        with self.runtime_settings(), self.assertRaisesRegex(RefinementRuntimeError, "modified"):
            CodexRefinementReviewer(timeout=5).review(
                session=self.session(), iteration_dir=self.iteration,
                implementation=RefinementImplementationResult(summary="Ready"),
                gate=TechnicalGate(passed=True), screenshots=[],
            )
        _, evidence = self.runtime("reviewer")
        self.assertTrue(evidence["project_modified_by_reviewer"])
        self.assertIn(
            "node_modules/reviewer-write.txt",
            evidence["project_manifest_diff"]["added"],
        )

    def test_reviewer_read_only_success_has_empty_diff(self) -> None:
        self.set_mode("reviewer_success")
        with self.runtime_settings():
            CodexRefinementReviewer(timeout=5).review(
                session=self.session(), iteration_dir=self.iteration,
                implementation=RefinementImplementationResult(summary="Ready"),
                gate=TechnicalGate(passed=True), screenshots=[],
            )
        _, evidence = self.runtime("reviewer")
        self.assertEqual(evidence["project_manifest_diff"], {
            "added": [], "modified": [], "deleted": [],
        })

    def test_reviewer_integrity_allows_stable_internal_dependency_symlink(self) -> None:
        target = self.project / "node_modules" / "package" / "tool.js"
        target.parent.mkdir(parents=True)
        target.write_text("console.log('tool')", encoding="utf-8")
        bin_dir = self.project / "node_modules" / ".bin"
        bin_dir.mkdir(parents=True)
        link = bin_dir / "tool"
        try:
            link.symlink_to(Path("..") / "package" / "tool.js")
        except OSError as exc:
            self.skipTest(f"file symlinks are unavailable: {exc}")
        self.set_mode("reviewer_success")
        with self.runtime_settings():
            CodexRefinementReviewer(timeout=5).review(
                session=self.session(), iteration_dir=self.iteration,
                implementation=RefinementImplementationResult(summary="Ready"),
                gate=TechnicalGate(passed=True), screenshots=[],
            )
        _, evidence = self.runtime("reviewer")
        self.assertFalse(evidence["project_modified_by_reviewer"])

    def test_runtime_evidence_survives_malformed_output_failure(self) -> None:
        self.set_mode("malformed")
        with self.runtime_settings(), self.assertRaises(RefinementRuntimeError):
            CodexRefinementExecutor(timeout=5).run(
                session=self.session(), iteration_dir=self.iteration, attachments=[]
            )
        directory, evidence = self.runtime("executor")
        self.assertTrue((directory / "runtime.json").is_file())
        self.assertEqual(evidence["failure_reason"], "result artifact contains malformed JSON")
        self.assertEqual(evidence["result_artifact_sha256"], sha256(directory / "result.json"))

    def test_secret_like_environment_values_are_not_persisted(self) -> None:
        secret = "checkpoint-secret-value-42"
        self.set_mode("executor_success")
        with patch.dict(os.environ, {"SITEAGENT_RUNTIME_SECRET": secret}), self.runtime_settings():
            CodexRefinementExecutor(timeout=5).run(
                session=self.session(), iteration_dir=self.iteration, attachments=[]
            )
        directory, _ = self.runtime("executor")
        persisted = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in (directory / "runtime.json", directory / "stdout.log", directory / "stderr.log")
        )
        self.assertNotIn(secret, persisted)

    def test_candidate_cannot_pass_after_executor_runtime_failure(self) -> None:
        self.set_mode("timeout")
        workflow = SiteRefinementOrchestrator(
            runs_dir=self.root / "orchestrator-runs",
            executor=CodexRefinementExecutor(timeout=1),
            reviewer=PassingReviewer(), inspector=FiveWidthInspector(),
        )
        with self.runtime_settings():
            result = workflow.start(
                RefinementRequest(project=str(self.project), goal="Refine hero"),
                session_id="executor-failure", execute=True,
            )
        self.assertEqual(result.status, RefinementStatus.BLOCKED)
        self.assertNotEqual(result.status, RefinementStatus.CANDIDATE_READY)
        self.assertFalse(result.last_qa_result["runtime_failure"]["candidate_allowed"])

    def test_candidate_cannot_pass_after_reviewer_runtime_failure(self) -> None:
        self.set_mode("nonzero")
        workflow = SiteRefinementOrchestrator(
            runs_dir=self.root / "orchestrator-runs",
            executor=PassingExecutor(),
            reviewer=CodexRefinementReviewer(timeout=5), inspector=FiveWidthInspector(),
        )
        with self.runtime_settings():
            result = workflow.start(
                RefinementRequest(project=str(self.project), goal="Refine hero"),
                session_id="reviewer-failure", execute=True,
            )
        self.assertEqual(result.status, RefinementStatus.BLOCKED)
        self.assertNotEqual(result.status, RefinementStatus.CANDIDATE_READY)
        self.assertEqual(result.last_qa_result["runtime_failure"]["role"], "reviewer")


if __name__ == "__main__":
    unittest.main()
