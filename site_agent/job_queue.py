from __future__ import annotations

import json
import hashlib
import os
import re
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
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
    telegram_preview_notification_status: Literal["not_started", "sending", "sent", "unknown"] = "not_started"
    telegram_preview_receipt: dict[str, str | int] = Field(default_factory=dict)
    telegram_preview_notification_url: str = ""
    telegram_preview_notification_deployment_id: str = ""
    telegram_preview_notification_attempt_id: str = ""
    telegram_preview_notified_at: str = ""
    telegram_preview_notification_error: str = ""
    telegram_preview_resend_authorization: dict[str, str] = Field(default_factory=dict)
    telegram_preview_notification_history: list[dict[str, str]] = Field(default_factory=list)
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
        if (
            not preview_url.startswith("https://")
            or not deployment_id
            or not project_name.startswith("siteagent-preview-")
            or not branch.startswith("preview-")
        ):
            raise ValueError("Complete isolated preview metadata is required.")
        self.pull()
        updated: TelegramJob | None = None
        with self._exclusive_queue_lock():
            jobs = self._read()
            for index, job in enumerate(jobs):
                if job.id != job_id:
                    continue
                if job.telegram_notification_status != "not_started":
                    raise PreviewRecoveryNotAllowed(job_id, "Telegram delivery has started")
                timestamp = self._now()
                preview_changed = (
                    self._canonical_preview_url(job.preview_url),
                    job.preview_deployment_id,
                ) != (
                    self._canonical_preview_url(preview_url),
                    deployment_id,
                )
                if preview_changed:
                    self._remember_preview_notification_state(job)
                    prior = self._preview_notification_history_entry(
                        job,
                        preview_url=preview_url,
                        deployment_id=deployment_id,
                    )
                    job.telegram_preview_notification_status = (
                        prior.get("status", "not_started") if prior else "not_started"
                    )
                    if prior and prior.get("status") == "sent":
                        job.telegram_preview_receipt = {
                            "status": "accepted",
                            "sent_at": prior.get("notified_at", ""),
                            "preview_url_sha256": prior.get("preview_url_sha256", ""),
                            "deployment_id": prior.get("deployment_id", ""),
                            "attempt_id": prior.get("attempt_id", ""),
                        }
                    else:
                        job.telegram_preview_receipt = {}
                    job.telegram_preview_notification_url = preview_url if prior else ""
                    job.telegram_preview_notification_deployment_id = deployment_id if prior else ""
                    job.telegram_preview_notification_attempt_id = (
                        prior.get("attempt_id", "") if prior else ""
                    )
                    job.telegram_preview_notified_at = (
                        prior.get("notified_at", "") if prior else ""
                    )
                    job.telegram_preview_notification_error = ""
                    job.telegram_preview_resend_authorization = {}
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
                updated = job
                break
        if updated is None:
            raise KeyError(f"Telegram job not found: {job_id}")
        self.push(f"Record one-link preview {job_id}")
        return updated

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
        if not preview_url.startswith("https://") or not deployment_id:
            raise ValueError("Preview URL and deployment ID are required.")
        self.pull()
        updated: TelegramJob | None = None
        with self._exclusive_queue_lock():
            jobs = self._read()
            for index, job in enumerate(jobs):
                if job.id != job_id:
                    continue
                same_preview = (
                    job.preview_url,
                    job.preview_deployment_id,
                ) == (
                    preview_url,
                    deployment_id,
                )
                if (
                    job.status != "preview_ready"
                    or job.telegram_notification_status != "not_started"
                    or (
                        job.telegram_preview_notification_status != "not_started"
                        and not same_preview
                    )
                ):
                    raise PreviewRecoveryNotAllowed(
                        job_id, "historical preview is not side-effect safe"
                    )
                timestamp = self._now()
                job.run_id = job.run_id or job.id
                job.run_dir = run_dir
                job.preview_url = preview_url
                job.preview_deployment_id = deployment_id
                job.preview_project_name = project_name
                job.preview_branch = branch
                job.workflow_lane = "preview"
                job.recovery_eligible = True
                job.checkpoints.update(checkpoints)
                job.recovery_events.append(f"preview_metadata_reconciled:{timestamp}")
                job.updated_at = timestamp
                jobs[index] = job
                self._write(jobs)
                updated = job
                break
        if updated is None:
            raise KeyError(f"Telegram job not found: {job_id}")
        self.push(f"Reconcile one-link preview metadata {job_id}")
        return updated

    def record_production_authorization(
        self,
        job_id: str,
        authorization: dict[str, Any],
    ) -> TelegramJob:
        """Record a separately approved production lane without completing it."""
        self.pull()
        updated: TelegramJob | None = None
        with self._exclusive_queue_lock():
            jobs = self._read()
            for index, job in enumerate(jobs):
                if job.id != job_id:
                    continue
                if job.telegram_preview_notification_status == "sending":
                    raise PreviewNotificationNotAllowed(
                        job_id, "preview notification is in flight"
                    )
                job.workflow_lane = "production"
                job.production_authorization = authorization
                job.updated_at = self._now()
                jobs[index] = job
                self._write(jobs)
                updated = job
                break
        if updated is None:
            raise KeyError(f"Telegram job not found: {job_id}")
        self.push(f"Authorize production promotion {job_id}")
        return updated

    def mark_preview_notification_sending(
        self,
        job_id: str,
        *,
        preview_url: str,
        deployment_id: str,
        authorized_resend: bool = False,
    ) -> TelegramJob:
        """Persist one exact preview attempt before Telegram API access."""
        self.pull()
        updated: TelegramJob | None = None
        with self._exclusive_queue_lock():
            jobs = self._read()
            for index, job in enumerate(jobs):
                if job.id != job_id:
                    continue
                self._validate_preview_notification_target(
                    job,
                    preview_url=preview_url,
                    deployment_id=deployment_id,
                )
                if authorized_resend:
                    authorization = job.telegram_preview_resend_authorization
                    if (
                        authorization.get("preview_url_sha256") != self._url_checksum(preview_url)
                        or authorization.get("deployment_id") != deployment_id
                        or not authorization.get("authorized_at")
                        or not authorization.get("reason")
                        or authorization.get("consumed_at")
                    ):
                        raise PreviewNotificationNotAllowed(
                            job_id,
                            "preview resend is not explicitly authorized for this deployment",
                        )
                elif job.telegram_preview_notification_status != "not_started":
                    raise PreviewNotificationNotAllowed(
                        job_id,
                        f"notification state is {job.telegram_preview_notification_status}",
                    )
                elif self._preview_notification_history_entry(
                    job,
                    preview_url=preview_url,
                    deployment_id=deployment_id,
                ):
                    raise PreviewNotificationNotAllowed(
                        job_id, "this preview notification key was already attempted"
                    )
                timestamp = self._now()
                attempt_id = uuid4().hex
                job.telegram_preview_notification_status = "sending"
                job.telegram_preview_receipt = {}
                job.telegram_preview_notification_url = preview_url
                job.telegram_preview_notification_deployment_id = deployment_id
                job.telegram_preview_notification_attempt_id = attempt_id
                job.telegram_preview_notified_at = ""
                job.telegram_preview_notification_error = ""
                if authorized_resend:
                    job.telegram_preview_resend_authorization.update(
                        {
                            "consumed_at": timestamp,
                            "attempt_id": attempt_id,
                        }
                    )
                job.recovery_events.append(
                    f"preview_notification_sending:{timestamp}:{attempt_id}"
                )
                job.updated_at = timestamp
                jobs[index] = job
                self._write(jobs)
                updated = job
                break
        if updated is None:
            raise KeyError(f"Telegram job not found: {job_id}")
        self.push(f"Start Telegram preview notification {job_id}")
        return updated

    def record_preview_notification_sent(
        self,
        job_id: str,
        receipt: dict[str, str | int],
    ) -> TelegramJob:
        return self._record_preview_notification_sent(job_id, receipt, resend=False)

    def record_preview_resend_sent(
        self,
        job_id: str,
        receipt: dict[str, str | int],
    ) -> TelegramJob:
        return self._record_preview_notification_sent(job_id, receipt, resend=True)

    def _record_preview_notification_sent(
        self,
        job_id: str,
        receipt: dict[str, str | int],
        *,
        resend: bool,
    ) -> TelegramJob:
        allowed = {
            "status",
            "sent_at",
            "preview_url_sha256",
            "deployment_id",
            "attempt_id",
        }
        if set(receipt) != allowed or any(
            not isinstance(receipt.get(key), str) for key in allowed
        ):
            raise ValueError("Telegram preview receipt contains unsafe or incomplete fields.")
        self.pull()
        updated: TelegramJob | None = None
        with self._exclusive_queue_lock():
            jobs = self._read()
            for index, job in enumerate(jobs):
                if job.id != job_id:
                    continue
                if job.telegram_preview_notification_status != "sending":
                    raise PreviewNotificationNotAllowed(job_id, "notification is not sending")
                self._validate_preview_notification_target(
                    job,
                    preview_url=job.telegram_preview_notification_url,
                    deployment_id=job.telegram_preview_notification_deployment_id,
                )
                expected = {
                    "status": "accepted",
                    "preview_url_sha256": hashlib.sha256(
                        job.telegram_preview_notification_url.encode("utf-8")
                    ).hexdigest(),
                    "deployment_id": job.telegram_preview_notification_deployment_id,
                    "attempt_id": job.telegram_preview_notification_attempt_id,
                }
                if any(receipt.get(key) != value for key, value in expected.items()):
                    raise ValueError("Telegram preview receipt does not match the active attempt.")
                sent_at = str(receipt.get("sent_at", ""))
                try:
                    parsed_sent_at = datetime.fromisoformat(sent_at)
                except ValueError as exc:
                    raise ValueError("Telegram preview receipt has invalid sent_at.") from exc
                if len(sent_at) > 64 or parsed_sent_at.utcoffset() is None:
                    raise ValueError("Telegram preview receipt has invalid sent_at.")
                sent_at = parsed_sent_at.isoformat()
                timestamp = self._now()
                job.status = "preview_ready"
                job.workflow_lane = "preview"
                job.telegram_preview_notification_status = "sent"
                job.telegram_preview_receipt = {**receipt, "sent_at": sent_at}
                job.telegram_preview_notified_at = sent_at
                job.telegram_preview_notification_error = ""
                if resend:
                    job.telegram_preview_resend_authorization["completed_at"] = timestamp
                self._remember_preview_notification_state(job)
                event = "preview_resend_sent" if resend else "preview_notification_sent"
                job.recovery_events.append(f"{event}:{timestamp}")
                job.updated_at = timestamp
                jobs[index] = job
                self._write(jobs)
                updated = job
                break
        if updated is None:
            raise KeyError(f"Telegram job not found: {job_id}")
        self.push(f"Record Telegram preview receipt {job_id}")
        return updated

    def mark_preview_notification_unknown(self, job_id: str, error: str) -> TelegramJob:
        safe_error = self._redact_preview_notification_error(error)
        self.pull()
        updated: TelegramJob | None = None
        with self._exclusive_queue_lock():
            jobs = self._read()
            for index, job in enumerate(jobs):
                if job.id != job_id:
                    continue
                if job.telegram_preview_notification_status != "sending":
                    raise PreviewNotificationNotAllowed(job_id, "notification is not sending")
                self._validate_preview_notification_target(
                    job,
                    preview_url=job.telegram_preview_notification_url,
                    deployment_id=job.telegram_preview_notification_deployment_id,
                )
                timestamp = self._now()
                job.status = "preview_ready"
                job.workflow_lane = "preview"
                job.telegram_preview_notification_status = "unknown"
                job.telegram_preview_notification_error = safe_error
                self._remember_preview_notification_state(job)
                job.recovery_events.append(f"preview_notification_unknown:{timestamp}")
                job.updated_at = timestamp
                jobs[index] = job
                self._write(jobs)
                updated = job
                break
        if updated is None:
            raise KeyError(f"Telegram job not found: {job_id}")
        self.push(f"Record uncertain Telegram preview notification {job_id}")
        return updated

    def authorize_preview_resend(self, job_id: str, *, reason: str) -> TelegramJob:
        normalized_reason = " ".join(reason.split())[:500]
        if not normalized_reason:
            raise ValueError("Preview resend authorization requires a reason.")
        self.pull()
        updated: TelegramJob | None = None
        with self._exclusive_queue_lock():
            jobs = self._read()
            for index, job in enumerate(jobs):
                if job.id != job_id:
                    continue
                self._validate_preview_notification_target(
                    job,
                    preview_url=job.preview_url,
                    deployment_id=job.preview_deployment_id,
                )
                if job.telegram_preview_notification_status not in {
                    "sending",
                    "sent",
                    "unknown",
                }:
                    raise PreviewNotificationNotAllowed(
                        job_id, "there is no prior delivery to resend"
                    )
                timestamp = self._now()
                job.telegram_preview_resend_authorization = {
                    "authorized_at": timestamp,
                    "reason": normalized_reason,
                    "preview_url_sha256": self._url_checksum(job.preview_url),
                    "deployment_id": job.preview_deployment_id,
                }
                job.recovery_events.append(f"preview_resend_authorized:{timestamp}")
                job.updated_at = timestamp
                jobs[index] = job
                self._write(jobs)
                updated = job
                break
        if updated is None:
            raise KeyError(f"Telegram job not found: {job_id}")
        self.push(f"Authorize Telegram preview resend {job_id}")
        return updated

    def _validate_preview_notification_target(
        self,
        job: TelegramJob,
        *,
        preview_url: str,
        deployment_id: str,
    ) -> None:
        if (
            job.status != "preview_ready"
            or job.workflow_lane != "preview"
            or job.preview_url != preview_url
            or job.preview_deployment_id != deployment_id
            or not preview_url.startswith("https://")
            or not deployment_id
            or job.site_url
            or job.repo_url
            or bool(job.production_authorization)
        ):
            raise PreviewNotificationNotAllowed(
                job.id, "job is not an exact isolated preview notification target"
            )

    def _remember_preview_notification_state(self, job: TelegramJob) -> None:
        if (
            job.telegram_preview_notification_status not in {"sending", "sent", "unknown"}
            or not job.telegram_preview_notification_url
            or not job.telegram_preview_notification_deployment_id
        ):
            return
        checksum = self._url_checksum(job.telegram_preview_notification_url)
        job.telegram_preview_notification_history = [
            item
            for item in job.telegram_preview_notification_history
            if not (
                item.get("preview_url_sha256") == checksum
                and item.get("deployment_id")
                == job.telegram_preview_notification_deployment_id
            )
        ]
        job.telegram_preview_notification_history.append(
            {
                "status": job.telegram_preview_notification_status,
                "preview_url_sha256": checksum,
                "deployment_id": job.telegram_preview_notification_deployment_id,
                "attempt_id": job.telegram_preview_notification_attempt_id,
                "notified_at": job.telegram_preview_notified_at,
                "receipt_status": str(job.telegram_preview_receipt.get("status", "")),
            }
        )

    def _preview_notification_history_entry(
        self,
        job: TelegramJob,
        *,
        preview_url: str,
        deployment_id: str,
    ) -> dict[str, str] | None:
        checksum = self._url_checksum(preview_url)
        return next(
            (
                item
                for item in reversed(job.telegram_preview_notification_history)
                if item.get("preview_url_sha256") == checksum
                and item.get("deployment_id") == deployment_id
            ),
            None,
        )

    @staticmethod
    def _url_checksum(url: str) -> str:
        canonical = TelegramJobQueue._canonical_preview_url(url)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _canonical_preview_url(url: str) -> str:
        parsed = urlsplit(url)
        scheme = parsed.scheme.lower()
        host = (parsed.hostname or "").lower()
        port = parsed.port
        authority = host if port in {None, 443} else f"{host}:{port}"
        path = parsed.path.rstrip("/")
        return urlunsplit((scheme, authority, path, parsed.query, parsed.fragment))

    def _redact_preview_notification_error(self, error: str) -> str:
        normalized = error.casefold()
        if "timeout" in normalized or "timed out" in normalized:
            return "telegram_transport_timeout"
        if "token" in normalized and ("missing" in normalized or "required" in normalized):
            return "telegram_preflight_missing_token"
        return "telegram_transport_uncertain"

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
        temporary = self.path.with_name(f"{self.path.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temporary, self.path)
        finally:
            if temporary.exists():
                temporary.unlink()

    @contextmanager
    def _exclusive_queue_lock(self, timeout_seconds: float = 10.0):
        """Serialize compare-and-set transitions across local worker processes."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_name(f"{self.path.name}.lock")
        with lock_path.open("a+b") as handle:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            deadline = time.monotonic() + timeout_seconds
            while True:
                try:
                    handle.seek(0)
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError as exc:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Timed out waiting for the Telegram queue lock.") from exc
                    time.sleep(0.05)
            try:
                yield
            finally:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

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


class PreviewNotificationNotAllowed(RuntimeError):
    """A preview notification would violate isolation or at-most-once delivery."""

    def __init__(self, job_id: str, reason: str) -> None:
        self.job_id = job_id
        super().__init__(f"Preview notification is not allowed for job {job_id}: {reason}.")
