from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from telegram import Bot

from site_agent.config import settings
from site_agent.models import PublishResult


class TelegramNotifier:
    def __init__(self, token: str | None = None) -> None:
        self.token = token or settings.telegram_bot_token

    def send_done(self, chat_id: int, publish: PublishResult) -> dict[str, str | int]:
        if not publish.is_verified_production:
            raise ValueError("Telegram success requires a live-verified HTTPS deployment.")
        if not self.token:
            raise RuntimeError("Telegram success requires TELEGRAM_BOT_TOKEN.")
        return asyncio.run(self._send_done(chat_id, publish))

    def send_failure(self, chat_id: int) -> None:
        if not self.token or not settings.send_verbose_telegram_logs:
            return
        asyncio.run(self._send_failure(chat_id))

    async def _send_done(self, chat_id: int, publish: PublishResult) -> dict[str, str | int]:
        bot = Bot(self.token)
        message: Any = await bot.send_message(
            chat_id=chat_id,
            text=f"Готово:\n\nСайт:\n{publish.production_url}",
            disable_web_page_preview=True,
        )
        date = getattr(message, "date", None)
        # Queue state can be synchronized through Git.  Retain only a
        # non-sensitive acknowledgement that Telegram accepted the delivery;
        # chat and message identifiers must never become a Git artifact.
        return {
            "status": "accepted",
            "sent_at": (date if isinstance(date, datetime) else datetime.now(timezone.utc)).isoformat(),
        }

    async def _send_failure(self, chat_id: int) -> None:
        bot = Bot(self.token)
        await bot.send_message(
            chat_id=chat_id,
            text="Не удалось завершить работу. Подробности смотрите в логах сервера.",
        )
