from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from site_agent.config import settings
from site_agent.telegram_bot import main


WORKSPACE = Path("/workspace")


def prepare_git_workspace() -> None:
    if not settings.telegram_inbox_git_sync:
        return
    if not settings.telegram_inbox_git_remote_url:
        raise RuntimeError("TELEGRAM_INBOX_GIT_REMOTE_URL is required when git sync is enabled.")

    if WORKSPACE.exists():
        shutil.rmtree(WORKSPACE)

    _git(
        "clone",
        "--branch",
        settings.telegram_inbox_git_branch,
        "--single-branch",
        settings.telegram_inbox_git_remote_url,
        str(WORKSPACE),
    )
    os.chdir(WORKSPACE)


def _git(*args: str) -> None:
    result = subprocess.run(["git", *args], text=True, capture_output=True, check=False)
    if result.returncode != 0:
        message = _redact(result.stderr or result.stdout or "git command failed")
        raise RuntimeError(message)


def _redact(message: str) -> str:
    if settings.telegram_inbox_git_remote_url:
        message = message.replace(settings.telegram_inbox_git_remote_url, "[REMOTE_URL]")
    return re.sub(r"x-access-token:[^@\s]+@", "x-access-token:[REDACTED]@", message)


if __name__ == "__main__":
    prepare_git_workspace()
    main()
