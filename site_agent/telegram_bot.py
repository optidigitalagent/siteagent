from __future__ import annotations

import asyncio
import logging
import re

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

from site_agent.config import settings
from site_agent.job_queue import TelegramJobQueue


LOG = logging.getLogger(__name__)
INSTAGRAM_RE = re.compile(r"https?://(www\.)?instagram\.com/[^\s]+", re.IGNORECASE)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text or not update.effective_chat:
        return

    match = INSTAGRAM_RE.search(update.message.text)
    if not match:
        return

    instagram_url = match.group(0).rstrip(").,]")
    try:
        await asyncio.to_thread(
            TelegramJobQueue().enqueue,
            instagram_url,
            chat_id=update.effective_chat.id,
            user_id=update.effective_user.id if update.effective_user else None,
        )
    except Exception:
        LOG.exception("Failed to enqueue Telegram job for %s", instagram_url)
        if settings.send_verbose_telegram_logs:
            await update.message.reply_text(
                "Не удалось принять задачу. Подробности смотрите в логах сервера."
            )
        return

    await update.message.reply_text("Окей, работа запущена.\nНапиши в Codex: го")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required.")
    app = ApplicationBuilder().token(settings.telegram_bot_token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()


if __name__ == "__main__":
    main()
