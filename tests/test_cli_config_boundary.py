from __future__ import annotations

import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from site_agent import cli
from site_agent.config import DOTENV_DISABLED, ENV_FILE, REPOSITORY_ROOT, Settings
from site_agent.refinement import RefinementRequest, SiteRefinementOrchestrator


@contextmanager
def working_directory(path: Path):
    original = Path.cwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original)


class CliBoundaryTests(unittest.TestCase):
    def test_unknown_refinement_typo_fails_closed(self) -> None:
        with patch.object(sys, "argv", ["site-agent", "refinement-statr"]), \
             patch.object(cli, "SiteAgentOrchestrator") as build_orchestrator, \
             patch.object(cli, "SiteRefinementOrchestrator") as refinement_orchestrator, \
             patch.object(cli, "run_pending_job") as pending, \
             patch.object(cli, "run_instagram_url") as direct:
            with self.assertRaises(SystemExit) as raised:
                cli.main()

        self.assertEqual(raised.exception.code, 2)
        build_orchestrator.assert_not_called()
        refinement_orchestrator.assert_not_called()
        pending.assert_not_called()
        direct.assert_not_called()

    def test_arbitrary_word_does_not_start_build(self) -> None:
        with patch.object(sys, "argv", ["site-agent", "hello"]), \
             patch.object(cli, "SiteAgentOrchestrator") as build_orchestrator, \
             patch.object(cli, "SiteRefinementOrchestrator") as refinement_orchestrator, \
             patch.object(cli, "run_pending_job") as pending, \
             patch.object(cli, "run_instagram_url") as direct:
            with self.assertRaises(SystemExit) as raised:
                cli.main()

        self.assertEqual(raised.exception.code, 2)
        build_orchestrator.assert_not_called()
        refinement_orchestrator.assert_not_called()
        pending.assert_not_called()
        direct.assert_not_called()

    def test_valid_supported_url_uses_existing_direct_handler(self) -> None:
        url = "https://www.instagram.com/example/?igsh=compatible"
        with patch.object(sys, "argv", ["site-agent", url]), \
             patch.object(cli, "run_instagram_url") as direct, \
             patch.object(cli, "run_pending_job") as pending, \
             patch.object(cli, "SiteRefinementOrchestrator") as refinement:
            cli.main()

        direct.assert_called_once_with(url)
        pending.assert_not_called()
        refinement.assert_not_called()

    def test_go_uses_existing_build_handler(self) -> None:
        with patch.object(sys, "argv", ["site-agent", "go"]), \
             patch.object(cli, "run_pending_job") as pending, \
             patch.object(cli, "run_instagram_url") as direct, \
             patch.object(cli, "SiteRefinementOrchestrator") as refinement:
            cli.main()

        pending.assert_called_once_with()
        direct.assert_not_called()
        refinement.assert_not_called()

    def test_refinement_status_uses_only_refinement_handler(self) -> None:
        with patch.object(
            sys,
            "argv",
            ["site-agent", "refinement-status", "--session-id", "session-1"],
        ), patch.object(cli, "run_refinement_status") as status, \
             patch.object(cli, "run_pending_job") as pending, \
             patch.object(cli, "run_instagram_url") as direct:
            cli.main()

        status.assert_called_once_with("session-1")
        pending.assert_not_called()
        direct.assert_not_called()

    def test_direct_url_requires_http_scheme_and_hostname(self) -> None:
        self.assertTrue(cli._is_supported_direct_url("https://instagram.com/example/"))
        self.assertTrue(cli._is_supported_direct_url("http://example.com/business"))
        for value in (
            "instagram.com/example",
            "ftp://instagram.com/example",
            "https:///example",
            "https://example.com:invalid/path",
            "https://user:password@example.com/path",
            "https://example.com/path with space",
            "hello",
        ):
            with self.subTest(value=value):
                self.assertFalse(cli._is_supported_direct_url(value))


class StableConfigRootTests(unittest.TestCase):
    def _settings_without_environment(self, **values: object) -> Settings:
        with patch.dict(os.environ, {}, clear=True):
            return Settings(_env_file=None, **values)

    def test_default_runs_root_is_independent_from_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            with working_directory(Path(first)):
                first_settings = self._settings_without_environment()
            with working_directory(Path(second)):
                second_settings = self._settings_without_environment()

        expected = (REPOSITORY_ROOT / "runs").resolve()
        self.assertEqual(first_settings.runs_dir, expected)
        self.assertEqual(second_settings.runs_dir, expected)
        self.assertIsInstance(first_settings.runs_dir, Path)

    def test_relative_environment_runs_root_is_independent_from_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            with patch.dict(os.environ, {"RUNS_DIR": "relative-runs"}, clear=True):
                with working_directory(Path(first)):
                    first_settings = Settings(_env_file=None)
                with working_directory(Path(second)):
                    second_settings = Settings(_env_file=None)

        expected = (REPOSITORY_ROOT / "relative-runs").resolve()
        self.assertEqual(first_settings.runs_dir, expected)
        self.assertEqual(second_settings.runs_dir, expected)

    def test_absolute_environment_runs_root_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as target:
            absolute = Path(target).resolve()
            with patch.dict(os.environ, {"RUNS_DIR": str(absolute)}, clear=True):
                configured = Settings(_env_file=None)

        self.assertEqual(configured.runs_dir, absolute)

    def test_default_env_file_is_bound_to_repository_root(self) -> None:
        self.assertEqual(Path(ENV_FILE).resolve(), (REPOSITORY_ROOT / ".env").resolve())
        if DOTENV_DISABLED:
            self.assertIsNone(Settings.model_config["env_file"])
        else:
            self.assertEqual(
                Path(Settings.model_config["env_file"]).resolve(),
                ENV_FILE.resolve(),
            )

    def test_refinement_session_lookup_survives_cwd_change(self) -> None:
        with tempfile.TemporaryDirectory() as project_temp, \
             tempfile.TemporaryDirectory() as first, \
             tempfile.TemporaryDirectory() as second, \
             tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as runs_temp:
            project = Path(project_temp) / "existing-site"
            project.mkdir()
            (project / "index.html").write_text(
                "<!doctype html><title>Existing site</title>",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"RUNS_DIR": runs_temp}, clear=True):
                with working_directory(Path(first)):
                    first_settings = Settings(_env_file=None)
                    created = SiteRefinementOrchestrator(
                        runs_dir=first_settings.runs_dir
                    ).start(
                        RefinementRequest(project=str(project), goal="Change the hero"),
                        session_id="cwd-stable-session",
                        execute=False,
                    )
                with working_directory(Path(second)):
                    second_settings = Settings(_env_file=None)
                    second_workflow = SiteRefinementOrchestrator(
                        runs_dir=second_settings.runs_dir
                    )
                    loaded = second_workflow.load(created.session_id)

        self.assertEqual(first_settings.runs_dir, second_settings.runs_dir)
        self.assertEqual(loaded.session_id, created.session_id)
        self.assertEqual(
            second_workflow.session_dir(loaded.session_id) / "session.json",
            first_settings.runs_dir
            / "refinement"
            / created.session_id
            / "session.json",
        )


if __name__ == "__main__":
    unittest.main()
