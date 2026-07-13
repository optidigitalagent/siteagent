from __future__ import annotations

import argparse

from site_agent.job_queue import TelegramJobQueue
from site_agent.orchestrator import SiteAgentOrchestrator
from site_agent.telegram_notify import TelegramNotifier


GO_ALIASES = {"go", "го"}


def run_instagram_url(instagram_url: str) -> None:
    result = SiteAgentOrchestrator().run(instagram_url)
    print("Готово:")
    print(result.publish.site_url)
    print(f"Репозиторий: {result.publish.repo_url}")


def run_pending_job() -> None:
    queue = TelegramJobQueue()
    job = queue.claim_next()
    if job is None:
        print("Нет pending-задач из Telegram.")
        return

    notifier = TelegramNotifier()
    try:
        result = SiteAgentOrchestrator().run(job.instagram_url)
    except Exception as exc:
        queue.fail(job.id, str(exc))
        notifier.send_failure(job.chat_id)
        raise

    queue.complete(
        job.id,
        site_url=result.publish.site_url,
        repo_url=result.publish.repo_url,
    )
    notifier.send_done(job.chat_id, result.publish)
    print("Готово:")
    print(result.publish.site_url)
    print(f"Репозиторий: {result.publish.repo_url}")


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
