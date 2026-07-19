from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from site_agent.config import settings
from site_agent.identifiers import normalize_instagram_url


RECOVERABLE_PREVIEW_FAILURE_PATTERNS = (
    "media_input/manifest.json",
    "media input manifest",
    "research failed",
    "research returned no",
    "scope blocked",
    "generation is blocked because evidence",
    "codex_studio_failed_retryable",
    "codex_studio_fixer_failed_retryable",
    "codex studio creative task failed with preserved retryable state",
    "acceptance audit blocked deployment",
    "blocked_insufficient_business_content",
)


class TelegramJob(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(default_factory=lambda: uuid4().hex)
    # ``run_id`` is explicit so recovery never has to derive a new run from a
    # failed queue item. Old queue entries are upgraded in memory to their id.
    run_id: str = ""
    instagram_url: str
    chat_id: int
    user_id: int | None = None
    status: str = "pending"
    received_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    site_url: str = ""
    repo_url: str = ""
    preview_url: str = ""
    preview_deployment_id: str = ""
    preview_project_name: str = ""
    preview_branch: str = ""
    requested_product_type: Literal["full_commercial_site"] = "full_commercial_site"
    error: str = ""
    # Stored checkpoints make recovery independent of volatile process memory.
    run_dir: str = ""
    checkpoints: dict[str, str] = Field(default_factory=dict)
    telegram_notification_status: Literal["not_started", "sending", "sent", "unknown"] = "not_started"
    telegram_preview_notification_status: Literal["not_started", "sent", "unknown"] = "not_started"
    telegram_receipt: dict[str, str | int] = Field(default_factory=dict)
    manual_resend_authorization: dict[str, str] = Field(default_factory=dict)
    recovery_events: list[str] = Field(default_factory=list)
    recovery_eligible: bool = True
    recovery_failure_code: str = ""
    workflow_lane: Literal["preview", "production"] = "preview"
    production_authorization: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if not self.run_id:
            self.run_id = self.id


class TelegramJobQueue:
    def __init__(self, path: Path | None = None, git_sync: bool | None = None) -> None:
        self.path = path or settings.telegram_queue_path
        self.git_sync = settings.telegram_inbox_git_sync if git_sync is None else git_sync

    def enqueue(self, instagram_url: str, *, chat_id: int, user_id: int | None = None) -> TelegramJob:
        self.pull()
        jobs = self._read()
        normalized_url = normalize_instagram_url(instagram_url)
        for existing in jobs:
            if (
                normalize_instagram_url(existing.instagram_url) == normalized_url
                and existing.status in {"pending", "running", "failed", "retryable", "preview_ready"}
            ):
                return existing
        job = TelegramJob(instagram_url=normalized_url, chat_id=chat_id, user_id=user_id)
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

    def next_interrupted(self) -> TelegramJob | None:
        """Return a resumable running job before any pending work.

        A job with a ``sending`` notification is intentionally not resumed:
        Telegram may already have accepted its success message before a crash.
        Repeating it would violate the no-duplicate-delivery guarantee.
        """
        self.pull()
        running = [job for job in self._read() if job.status == "running"]
        resumable = [
            job for job in running if job.telegram_notification_status == "not_started"
        ]
        if resumable:
            return max(resumable, key=lambda job: job.updated_at)
        uncertain = [
            job
            for job in running
            if job.telegram_notification_status in {"sending", "unknown"}
        ]
        if uncertain:
            raise InterruptedDeliveryUncertain(max(uncertain, key=lambda job: job.updated_at).id)
        return None

    def next_pending(self) -> TelegramJob | None:
        self.pull()
        for job in self._read():
            if job.status == "pending":
                return job
        return None

    def next_recoverable_preview(self) -> TelegramJob | None:
        """Select the newest pre-delivery preview failure without mutating it."""
        self.pull()
        candidates = []
        for job in self._read():
            normalized_error = job.error.casefold().replace("\\", "/")
            if (
                job.status == "failed"
                and job.workflow_lane == "preview"
                and job.recovery_eligible
                and job.telegram_notification_status == "not_started"
                and any(pattern in normalized_error for pattern in RECOVERABLE_PREVIEW_FAILURE_PATTERNS)
            ):
                candidates.append(job)
        return max(candidates, key=lambda job: job.updated_at) if candidates else None

    def complete(self, job_id: str, *, site_url: str, repo_url: str) -> TelegramJob:
        return self._update(
            job_id,
            status="done",
            site_url=site_url,
            repo_url=repo_url,
            error="",
            telegram_notification_status="sent",
            commit_message=f"Complete Telegram site job {job_id}",
        )

    def reclaim_failed_preview(self, job_id: str) -> TelegramJob:
        """Reclaim one known one-link intake failure without creating a new run.

        This intentionally excludes deployment and Telegram delivery failures.
        Those have separate recovery semantics because repeating them can create
        external side effects or duplicate customer messages.
        """
        jobs = self._read_with_pull()
        for index, job in enumerate(jobs):
            if job.id != job_id:
                continue
            if job.status != "failed":
                raise PreviewRecoveryNotAllowed(job_id, "job is not failed")
            if job.telegram_notification_status != "not_started":
                raise PreviewRecoveryNotAllowed(job_id, "Telegram delivery has started")
            normalized_error = job.error.casefold().replace("\\", "/")
            if not any(pattern in normalized_error for pattern in RECOVERABLE_PREVIEW_FAILURE_PATTERNS):
                raise PreviewRecoveryNotAllowed(job_id, "failure is not a research/media-input blocker")
            timestamp = self._now()
            prior_error = job.error[:500]
            job.status = "running"
            job.workflow_lane = "preview"
            job.error = ""
            job.run_id = job.run_id or job.id
            job.recovery_events.append(
                f"preview_reclaimed:{timestamp}:{prior_error}"
            )
            job.updated_at = timestamp
            jobs[index] = job
            self._write(jobs)
            self.push(f"Reclaim one-link preview job {job_id}")
            return job
        raise KeyError(f"Telegram job not found: {job_id}")

    def mark_preview_ready(
        self,
        job_id: str,
        *,
        preview_url: str,
        checkpoints: dict[str, str] | None = None,
        deployment_id: str = "",
        project_name: str = "",
        branch: str = "",
    ) -> TelegramJob:
        """Record a review preview without completing or delivering the job."""
        if not preview_url.startswith("https://"):
            raise ValueError("Preview URL must use HTTPS.")
        jobs = self._read_with_pull()
        for index, job in enumerate(jobs):
            if job.id != job_id:
                continue
            if job.telegram_notification_status != "not_started":
                raise PreviewRecoveryNotAllowed(job_id, "Telegram delivery has started")
            timestamp = self._now()
            job.status = "preview_ready"
            job.preview_url = preview_url
            job.preview_deployment_id = deployment_id
            job.preview_project_name = project_name
            job.preview_branch = branch
            job.workflow_lane = "preview"
            job.recovery_eligible = True
            job.recovery_failure_code = ""
            job.error = ""
            job.checkpoints.update(
                {
                    "ONE_LINK_SITE_PREVIEW_READY_FOR_USER_REVIEW": "completed_and_valid",
                    **(checkpoints or {}),
                }
            )
            job.recovery_events.append(f"preview_ready:{timestamp}")
            job.updated_at = timestamp
            jobs[index] = job
            self._write(jobs)
            self.push(f"Record one-link preview {job_id}")
            return job
        raise KeyError(f"Telegram job not found: {job_id}")

    def reconcile_preview_metadata(
        self,
        job_id: str,
        *,
        run_dir: str,
        preview_url: str,
        deployment_id: str,
        project_name: str,
        branch: str,
        checkpoints: dict[str, str],
    ) -> TelegramJob:
        """Backfill one verified historical preview without publishing it."""
        if not preview_url.startswith("https://"):
            raise ValueError("Preview URL must use HTTPS.")
        jobs = self._read_with_pull()
        for index, job in enumerate(jobs):
            if job.id != job_id:
                continue
            if job.status != "preview_ready" or job.telegram_notification_status != "not_started":
                raise PreviewRecoveryNotAllowed(job_id, "historical preview is not side-effect safe")
            timestamp = self._now()
            job.run_id = job.run_id or job.id
            job.run_dir = run_dir
            job.preview_url = preview_url
            job.preview_deployment_id = deployment_id
            job.preview_project_name = project_name
            job.preview_branch = branch
            job.workflow_lane = "preview"
            job.recovery_eligible = True
            job.telegram_preview_notification_status = "not_started"
            job.checkpoints.update(checkpoints)
            job.recovery_events.append(f"preview_metadata_reconciled:{timestamp}")
            job.updated_at = timestamp
            jobs[index] = job
            self._write(jobs)
            self.push(f"Reconcile one-link preview metadata {job_id}")
            return job
        raise KeyError(f"Telegram job not found: {job_id}")

    def record_production_authorization(
        self,
        job_id: str,
        authorization: dict[str, Any],
    ) -> TelegramJob:
        """Record a separately approved production lane without completing it."""
        return self._update(
            job_id,
            workflow_lane="production",
            production_authorization=authorization,
            commit_message=f"Authorize production promotion {job_id}",
        )

    def get(self, job_id: str) -> TelegramJob:
        for job in self._read_with_pull():
            if job.id == job_id:
                return job
        raise KeyError(f"Telegram job not found: {job_id}")

    def authorize_manual_resend(self, job_id: str, *, reason: str) -> TelegramJob:
        """Record explicit human authority before a delivery-uncertain resend.

        This is deliberately separate from normal recovery: unknown Telegram
        delivery is never retried automatically.
        """
        jobs = self._read_with_pull()
        for index, job in enumerate(jobs):
            if job.id != job_id:
                continue
            if job.telegram_notification_status == "sent":
                raise InterruptedDeliveryUncertain(job_id)
            timestamp = self._now()
            job.status = "running"
            job.error = ""
            job.telegram_notification_status = "sending"
            job.manual_resend_authorization = {
                "authorized_at": timestamp,
                "reason": reason[:500],
            }
            job.recovery_events.append(f"manual_resend_authorized:{timestamp}")
            job.updated_at = timestamp
            jobs[index] = job
            self._write(jobs)
            self.push(f"Authorize manual Telegram resend {job_id}")
            return job
        raise KeyError(f"Telegram job not found: {job_id}")

    def record_notification_sent(
        self, job_id: str, receipt: dict[str, str | int]
    ) -> TelegramJob:
        return self._update(
            job_id,
            telegram_notification_status="sent",
            telegram_receipt=receipt,
            commit_message=f"Record Telegram success receipt {job_id}",
        )

    def set_run_dir(self, job_id: str, run_dir: str) -> TelegramJob:
        return self._update(
            job_id,
            run_dir=run_dir,
            commit_message=f"Set Telegram site job run directory {job_id}",
        )

    def record_checkpoints(self, job_id: str, **checkpoints: str) -> TelegramJob:
        jobs = self._read_with_pull()
        for index, job in enumerate(jobs):
            if job.id == job_id:
                job.checkpoints.update({key: value for key, value in checkpoints.items() if value})
                job.updated_at = self._now()
                jobs[index] = job
                self._write(jobs)
                self.push(f"Checkpoint Telegram site job {job_id}")
                return job
        raise KeyError(f"Telegram job not found: {job_id}")

    def mark_notification_sending(self, job_id: str) -> TelegramJob:
        return self._update(
            job_id,
            telegram_notification_status="sending",
            commit_message=f"Start Telegram success notification {job_id}",
        )

    def mark_notification_unknown(self, job_id: str, error: str) -> TelegramJob:
        return self._update(
            job_id,
            status="retryable",
            telegram_notification_status="unknown",
            error=error[:2000],
            commit_message=f"Uncertain Telegram success notification {job_id}",
        )

    def fail(
        self,
        job_id: str,
        error: str,
        *,
        failure_code: str = "",
        recovery_eligible: bool | None = None,
    ) -> TelegramJob:
        normalized = error.casefold().replace("\\", "/")
        code = failure_code or (
            "BLOCKED_INSUFFICIENT_BUSINESS_CONTENT"
            if "blocked_insufficient_business_content" in normalized
            else "PREVIEW_RECOVERABLE_FAILURE"
            if any(pattern in normalized for pattern in RECOVERABLE_PREVIEW_FAILURE_PATTERNS)
            else "UNCLASSIFIED_FAILURE"
        )
        eligible = (
            any(pattern in normalized for pattern in RECOVERABLE_PREVIEW_FAILURE_PATTERNS)
            if recovery_eligible is None
            else recovery_eligible
        )
        return self._update(
            job_id,
            status="failed",
            error=error[:2000],
            recovery_failure_code=code,
            recovery_eligible=eligible,
            commit_message=f"Fail Telegram site job {job_id}",
        )

    def pending_count(self) -> int:
        self.pull()
        return sum(1 for job in self._read() if job.status == "pending")

    def _update(self, job_id: str, *, commit_message: str, **changes: Any) -> TelegramJob:
        jobs = self._read_with_pull()
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

    def _read_with_pull(self) -> list[TelegramJob]:
        self.pull()
        return self._read()

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


class InterruptedDeliveryUncertain(RuntimeError):
    """A process stopped while the Telegram success delivery was in flight."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        super().__init__(
            f"Telegram delivery for interrupted job {job_id} is uncertain; refusing a duplicate send."
        )


class PreviewRecoveryNotAllowed(RuntimeError):
    """A failed queue item is outside the side-effect-free preview recovery lane."""

    def __init__(self, job_id: str, reason: str) -> None:
        self.job_id = job_id
        super().__init__(f"Preview recovery is not allowed for job {job_id}: {reason}.")
