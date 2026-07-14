from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from site_agent.config import settings
from site_agent.job_queue import InterruptedDeliveryUncertain, TelegramJobQueue
from site_agent.identifiers import stable_business_id
from site_agent.models import PublishResult
from site_agent.orchestrator import SiteAgentOrchestrator
from site_agent.publisher import LiveSiteVerifier
from site_agent.telegram_notify import TelegramNotifier


GO_ALIASES = {"go", "го"}


def run_instagram_url(instagram_url: str) -> None:
    result = SiteAgentOrchestrator().run(instagram_url)
    print("Готово:")
    print(result.publish.production_url)


def run_pending_job() -> None:
    queue = _pending_job_queue()
    try:
        interrupted = queue.next_interrupted()
        job = interrupted if getattr(interrupted, "status", None) == "running" else None
    except RuntimeError as exc:
        if queue.git_sync and not settings.telegram_inbox_git_sync:
            raise RuntimeError(
                "Не удалось автоматически синхронизировать Telegram inbox через git. "
                "Проверьте git remote/push-доступ или задайте TELEGRAM_INBOX_GIT_SYNC=true."
            ) from exc
        raise
    if job is None:
        try:
            pending_job = queue.next_pending()
        except RuntimeError as exc:
            if queue.git_sync and not settings.telegram_inbox_git_sync:
                raise RuntimeError(
                    "Не удалось автоматически синхронизировать Telegram inbox через git. "
                    "Проверьте git remote/push-доступ или задайте TELEGRAM_INBOX_GIT_SYNC=true."
                ) from exc
            raise
        if pending_job is None:
            print("Нет pending-задач из Telegram.")
            return
        try:
            job = queue.claim_next()
        except RuntimeError as exc:
            if queue.git_sync and not settings.telegram_inbox_git_sync:
                raise RuntimeError(
                    "Не удалось автоматически синхронизировать Telegram inbox через git. "
                    "Проверьте git remote/push-доступ или задайте TELEGRAM_INBOX_GIT_SYNC=true."
                ) from exc
            raise
        if job is None:
            print("Нет pending-задач из Telegram.")
            return

    stored_run_dir = getattr(job, "run_dir", "")
    run_dir = (
        stored_run_dir
        if isinstance(stored_run_dir, str) and stored_run_dir
        else str(_existing_run_dir(job.instagram_url) or settings.runs_dir / job.id)
    )
    if not job.run_dir:
        job = queue.set_run_dir(job.id, run_dir)

    orchestrator = SiteAgentOrchestrator()

    notifier = TelegramNotifier()
    try:
        result = orchestrator.run(
            job.instagram_url,
            production=True,
            run_id=job.id,
            run_path=Path(run_dir),
        )
        if not result.publish.is_verified_production:
            raise RuntimeError(
                "Production publishing did not return a live-verified HTTPS deployment."
            )
    except Exception as exc:
        queue.fail(job.id, str(exc))
        notifier.send_failure(job.chat_id)
        raise

    queue.record_checkpoints(
        job.id,
        research_completed="completed_and_valid",
        generation_completed="completed_and_valid",
        technical_gate_completed="completed_and_valid",
        critics_completed="completed_and_valid",
        acceptance_completed="completed_and_valid",
        deployment_completed="completed_and_valid",
        live_verified="completed_and_valid",
    )
    queue.mark_notification_sending(job.id)
    try:
        receipt = notifier.send_done(job.chat_id, result.publish)
    except Exception as exc:
        # A transport failure may happen after Telegram accepted the request.
        # Keep the job non-complete and require explicit delivery confirmation.
        queue.mark_notification_unknown(job.id, str(exc))
        raise InterruptedDeliveryUncertain(job.id) from exc
    queue.record_notification_sent(job.id, receipt)
    queue.complete(job.id, site_url=result.publish.production_url, repo_url=result.publish.repo_url)
    print("Готово:")
    print(result.publish.production_url)


def _pending_job_queue() -> TelegramJobQueue:
    if settings.telegram_inbox_git_sync:
        return TelegramJobQueue()

    if _has_git_remote():
        return TelegramJobQueue(git_sync=True)

    return TelegramJobQueue(git_sync=False)


def _has_git_remote() -> bool:
    result = subprocess.run(
        ["git", "remote", "get-url", settings.telegram_inbox_git_remote],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _existing_run_dir(instagram_url: str) -> Path | None:
    """Find the latest valid legacy run for this exact queue URL.

    Earlier queue entries did not persist a run directory.  Matching the
    validated research artifact lets an interrupted legacy job resume its own
    work rather than starting a timestamped duplicate.
    """
    candidates = sorted(
        (path for path in settings.runs_dir.iterdir() if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ) if settings.runs_dir.is_dir() else []
    for candidate in candidates:
        research_path = candidate / "generation_reports" / "01_research.json"
        try:
            payload = json.loads(research_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if payload.get("instagram_url") == instagram_url:
            return candidate
    return None


def run_authorized_manual_resend(job_id: str) -> None:
    """Send one explicitly authorized recovery notification without rerunning delivery work."""
    # A recovery command must not be blocked by unrelated user changes in the
    # worktree.  It updates only the already-local queue entry for this job.
    queue = TelegramJobQueue(git_sync=False)
    job = queue.get(job_id)
    run_dir = Path(job.run_dir) if job.run_dir else _existing_run_dir(job.instagram_url)
    if run_dir is None:
        raise RuntimeError(f"No persisted run directory found for Telegram job {job_id}.")
    deployment_path = run_dir / "deployment.json"
    try:
        publish = PublishResult.model_validate_json(deployment_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"No valid verified deployment record found for Telegram job {job_id}.") from exc
    if not publish.is_verified_production:
        raise RuntimeError("Manual resend requires a live-verified HTTPS deployment.")

    # This verifies the exact existing Pages URL and marker; it never invokes
    # research, generation, critics, acceptance, or Cloudflare upload.
    LiveSiteVerifier(retries=1).verify(
        publish.production_url,
        site_dir=run_dir / "site",
        expected_marker=stable_business_id(job.instagram_url),
    )

    queue.authorize_manual_resend(
        job.id,
        reason="User confirmed no legacy final message was received and authorized one resend.",
    )
    try:
        receipt = TelegramNotifier().send_done(job.chat_id, publish)
    except Exception as exc:
        queue.mark_notification_unknown(job.id, str(exc))
        raise RuntimeError(f"Telegram resend failed: {exc}") from exc
    queue.record_notification_sent(job.id, receipt)
    queue.complete(job.id, site_url=publish.production_url, repo_url=publish.repo_url)
    print("Готово:")
    print(publish.production_url)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a commercial site from an Instagram URL or run the next Telegram job."
    )
    parser.add_argument("command_or_url")
    parser.add_argument("--job-id")
    parser.add_argument("--authorize-manual-resend", action="store_true")
    args = parser.parse_args()

    if args.command_or_url.lower() in GO_ALIASES:
        run_pending_job()
    elif args.command_or_url == "manual-resend":
        if not args.authorize_manual_resend or not args.job_id:
            parser.error("manual-resend requires --job-id and --authorize-manual-resend")
        run_authorized_manual_resend(args.job_id)
    else:
        run_instagram_url(args.command_or_url)


if __name__ == "__main__":
    main()
