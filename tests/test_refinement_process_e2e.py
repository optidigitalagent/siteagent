from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


class RefinementProcessE2ETests(unittest.TestCase):
    def _environment(self, runs_dir: Path) -> dict[str, str]:
        allowed = {
            name: value
            for name, value in os.environ.items()
            if name.upper() in {
                "COMSPEC",
                "PATH",
                "PATHEXT",
                "SYSTEMDRIVE",
                "SYSTEMROOT",
                "TEMP",
                "TMP",
                "WINDIR",
            }
        }
        allowed.update({
            "CLOUDINARY_API_KEY": "",
            "CLOUDINARY_API_SECRET": "",
            "CLOUDFLARE_ACCOUNT_ID": "",
            "CLOUDFLARE_API_TOKEN": "",
            "OPENAI_API_KEY": "",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONPATH": str(REPOSITORY_ROOT),
            "PYTHONUTF8": "1",
            "PYTHON_DOTENV_DISABLED": "1",
            "RUNS_DIR": str(runs_dir),
            "TELEGRAM_BOT_TOKEN": "",
            "TELEGRAM_INBOX_GIT_SYNC": "false",
        })
        return allowed

    def _run_cli(
        self,
        *arguments: str,
        cwd: Path,
        environment: dict[str, str],
    ) -> dict[str, object]:
        completed = subprocess.run(
            [sys.executable, "-m", "site_agent.cli", *arguments],
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
        )
        return json.loads(completed.stdout)

    def _assert_dotenv_disabled(
        self,
        *,
        cwd: Path,
        environment: dict[str, str],
    ) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import json; "
                    "from site_agent.config import DOTENV_DISABLED, Settings; "
                    "print(json.dumps({'disabled': DOTENV_DISABLED, "
                    "'env_file': Settings.model_config.get('env_file')}))"
                ),
            ],
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            json.loads(completed.stdout),
            {"disabled": True, "env_file": None},
        )

    def test_refinement_cli_persists_across_processes_and_working_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "existing-site"
            runs_dir = root / "runs"
            first_cwd = root / "first-cwd"
            second_cwd = root / "second-cwd"
            project.mkdir()
            first_cwd.mkdir()
            second_cwd.mkdir()
            original = "<!doctype html><title>Existing site</title>"
            project.joinpath("index.html").write_text(original, encoding="utf-8")
            environment = self._environment(runs_dir)
            session_id = "process-e2e-session"

            self._assert_dotenv_disabled(cwd=first_cwd, environment=environment)

            started = self._run_cli(
                "refinement-start",
                "--project",
                str(project),
                "--request",
                "Make the hero clearer",
                "--session-id",
                session_id,
                "--no-execute",
                cwd=first_cwd,
                environment=environment,
            )
            loaded = self._run_cli(
                "refinement-status",
                "--session-id",
                session_id,
                cwd=second_cwd,
                environment=environment,
            )
            continued = self._run_cli(
                "refinement-continue",
                "--session-id",
                session_id,
                "--request",
                "Keep the existing cards unchanged",
                "--no-execute",
                cwd=second_cwd,
                environment=environment,
            )

            self.assertEqual(started["session_id"], session_id)
            self.assertEqual(started["mode"], "site_refinement")
            self.assertEqual(loaded, started)
            self.assertEqual(continued["session_id"], session_id)
            self.assertEqual(continued["mode"], "site_refinement")
            self.assertEqual(continued["status"], "IMPLEMENTING")
            self.assertEqual(continued["open_tasks"], [])
            self.assertEqual(project.joinpath("index.html").read_text(encoding="utf-8"), original)

            session_path = runs_dir / "refinement" / session_id / "session.json"
            session = json.loads(session_path.read_text(encoding="utf-8"))
            active_text = [
                item["text"]
                for item in session["requirements"]
                if item["state"] == "active"
            ]
            self.assertEqual(
                active_text,
                ["Make the hero clearer", "Keep the existing cards unchanged"],
            )


if __name__ == "__main__":
    unittest.main()
