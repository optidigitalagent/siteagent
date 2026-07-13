from __future__ import annotations

import asyncio

from telegram import Bot

from site_agent.config import settings
from site_agent.models import PublishResult


class TelegramNotifier:
    def __init__(self, token: str | None = None) -> None:
        self.token = token or settings.telegram_bot_token

    def send_done(self, chat_id: int, publish: PublishResult) -> None:
        if not self.token:
            return
        asyncio.run(self._send_done(chat_id, publish))

    def send_failure(self, chat_id: int) -> None:
        if not self.token or not settings.send_verbose_telegram_logs:
            return
        asyncio.run(self._send_failure(chat_id))

    async def _send_done(self, chat_id: int, publish: PublishResult) -> None:
        bot = Bot(self.token)
        await bot.send_message(
            chat_id=chat_id,
            text=f"Готово:\n{publish.site_url}\nРепозиторий: {publish.repo_url}",
            disable_web_page_preview=True,
        )

    async def _send_failure(self, chat_id: int) -> None:
        bot = Bot(self.token)
        await bot.send_message(
            chat_id=chat_id,
            text="Не удалось завершить работу. Подробности смотрите в логах сервера.",
        )
