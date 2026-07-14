from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from site_agent.config import settings
from site_agent.job_queue import TelegramJobQueue
from site_agent.orchestrator import SiteAgentOrchestrator
from site_agent.telegram_notify import TelegramNotifier


GO_ALIASES = {"go", "го"}


def run_instagram_url(instagram_url: str) -> None:
    result = SiteAgentOrchestrator().run(instagram_url)
    print("Готово:")
    print(result.publish.production_url)


def run_pending_job() -> None:
    queue = _pending_job_queue()
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

    orchestrator = SiteAgentOrchestrator()
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

    notifier = TelegramNotifier()
    try:
        result = orchestrator.run(job.instagram_url, production=True)
        if not result.publish.is_verified_production:
            raise RuntimeError(
                "Production publishing did not return a live-verified HTTPS deployment."
            )
    except Exception as exc:
        queue.fail(job.id, str(exc))
        notifier.send_failure(job.chat_id)
        raise

    queue.complete(
        job.id,
        site_url=result.publish.production_url,
        repo_url=result.publish.repo_url,
    )
    notifier.send_done(job.chat_id, result.publish)
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a commercial site from an Instagram URL or run the next Telegram job."
    )
    parser.add_argument("command_or_url")
    args = parser.parse_args()

    if args.command_or_url.lower() in GO_ALIASES:
        run_pending_job()
    else:
        run_instagram_url(args.command_or_url)


if __name__ == "__main__":
    main()
