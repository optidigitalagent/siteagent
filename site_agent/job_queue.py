from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from site_agent.config import settings


class TelegramJob(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    instagram_url: str
    chat_id: int
    user_id: int | None = None
    status: str = "pending"
    received_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    site_url: str = ""
    repo_url: str = ""
    error: str = ""


class TelegramJobQueue:
    def __init__(self, path: Path | None = None, git_sync: bool | None = None) -> None:
        self.path = path or settings.telegram_queue_path
        self.git_sync = settings.telegram_inbox_git_sync if git_sync is None else git_sync

    def enqueue(self, instagram_url: str, *, chat_id: int, user_id: int | None = None) -> TelegramJob:
        self.pull()
        jobs = self._read()
        job = TelegramJob(instagram_url=instagram_url, chat_id=chat_id, user_id=user_id)
        jobs.append(job)
        self._write(jobs)
        self.push(f"Add Telegram site job {job.id}")
        return job

    def claim_next(self) -> TelegramJob | None:
        self.pull()
        jobs = self._read()
        for index, job in enumerate(jobs):
            if job.status == "pending":
                job.status = "running"
                job.updated_at = self._now()
                jobs[index] = job
                self._write(jobs)
                self.push(f"Claim Telegram site job {job.id}")
                return job
        return None

    def next_pending(self) -> TelegramJob | None:
        self.pull()
        for job in self._read():
            if job.status == "pending":
                return job
        return None

    def complete(self, job_id: str, *, site_url: str, repo_url: str) -> TelegramJob:
        return self._update(
            job_id,
            status="done",
            site_url=site_url,
            repo_url=repo_url,
            error="",
            commit_message=f"Complete Telegram site job {job_id}",
        )

    def fail(self, job_id: str, error: str) -> TelegramJob:
        return self._update(
            job_id,
            status="failed",
            error=error[:2000],
            commit_message=f"Fail Telegram site job {job_id}",
        )

    def pending_count(self) -> int:
        self.pull()
        return sum(1 for job in self._read() if job.status == "pending")

    def _update(self, job_id: str, *, commit_message: str, **changes: str) -> TelegramJob:
        self.pull()
        jobs = self._read()
        for index, job in enumerate(jobs):
            if job.id == job_id:
                for key, value in changes.items():
                    setattr(job, key, value)
                job.updated_at = self._now()
                jobs[index] = job
                self._write(jobs)
                self.push(commit_message)
                return job
        raise KeyError(f"Telegram job not found: {job_id}")

    def pull(self) -> None:
        if not self.git_sync:
            return
        self._configure_remote()
        self._git("pull", "--rebase", settings.telegram_inbox_git_remote, settings.telegram_inbox_git_branch)

    def push(self, message: str) -> None:
        if not self.git_sync:
            return
        self._configure_remote()
        self._git("config", "user.name", settings.telegram_inbox_git_user_name)
        self._git("config", "user.email", settings.telegram_inbox_git_user_email)
        self._git("add", str(self.path))
        staged = self._git("diff", "--cached", "--quiet", "--", str(self.path), check=False)
        if staged.returncode == 0:
            return
        if staged.returncode != 1:
            raise RuntimeError(staged.stderr or staged.stdout or "git diff --cached failed")
        self._git("commit", "-m", message)
        self._git("push", settings.telegram_inbox_git_remote, f"HEAD:{settings.telegram_inbox_git_branch}")

    def _read(self) -> list[TelegramJob]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"Telegram queue must be a JSON list: {self.path}")
        return [TelegramJob.model_validate(item) for item in payload]

    def _write(self, jobs: list[TelegramJob]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [job.model_dump(mode="json") for job in jobs]
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["git", *args],
            cwd=Path.cwd(),
            text=True,
            capture_output=True,
            check=False,
        )
        if check and result.returncode != 0:
            command = self._redact("git " + " ".join(args))
            output = self._redact(result.stderr or result.stdout or "")
            raise RuntimeError(f"{command} failed: {output}")
        return result

    def _configure_remote(self) -> None:
        if settings.telegram_inbox_git_remote_url:
            self._git(
                "remote",
                "set-url",
                settings.telegram_inbox_git_remote,
                settings.telegram_inbox_git_remote_url,
            )

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _redact(self, value: str) -> str:
        if settings.telegram_inbox_git_remote_url:
            value = value.replace(settings.telegram_inbox_git_remote_url, "[REMOTE_URL]")
        return re.sub(r"x-access-token:[^@\s]+@", "x-access-token:[REDACTED]@", value)
