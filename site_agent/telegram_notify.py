from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from site_agent.config import settings
from site_agent.models import PublishResult
from site_agent.preview import PreviewDeploymentResult


class TelegramNotifier:
    def __init__(self, token: str | None = None) -> None:
        self.token = token or settings.telegram_bot_token

    def send_done(self, chat_id: int, publish: PublishResult) -> dict[str, str | int]:
        if not publish.is_verified_production:
            raise ValueError("Telegram success requires a live-verified HTTPS deployment.")
        if not self.token:
            raise RuntimeError("Telegram success requires TELEGRAM_BOT_TOKEN.")
        return asyncio.run(self._send_done(chat_id, publish))

    def validate_preview_ready(
        self,
        business_name: str,
        preview: PreviewDeploymentResult,
    ) -> str:
        """Fail before any Telegram request unless this is an isolated preview."""
        normalized_name = " ".join(business_name.split())
        if not normalized_name:
            raise ValueError("Telegram preview notification requires a business name.")
        if len(normalized_name) > 200:
            raise ValueError("Telegram preview notification business name is too long.")
        parsed = urlsplit(preview.preview_url)
        host = (parsed.hostname or "").lower()
        root_host = f"{preview.project_name}.pages.dev"
        if (
            preview.provider != "cloudflare_pages_preview"
            or preview.environment != "preview"
            or preview.verification_status != "verified"
            or not preview.preview_url.startswith("https://")
            or preview.deployment_url != preview.preview_url
            or not preview.deployment_id
            or not preview.project_name.startswith("siteagent-preview-")
            or not preview.branch.startswith("preview-")
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in {None, 443}
            or bool(parsed.query)
            or bool(parsed.fragment)
            or host == root_host
            or not host.endswith(f".{root_host}")
        ):
            raise ValueError(
                "Telegram preview notification requires a verified isolated preview deployment."
            )
        if not self.token:
            raise RuntimeError("Telegram preview notification requires TELEGRAM_BOT_TOKEN.")
        return normalized_name

    def send_preview_ready(
        self,
        chat_id: int,
        *,
        business_name: str,
        preview: PreviewDeploymentResult,
        attempt_id: str,
    ) -> dict[str, str | int]:
        normalized_name = self.validate_preview_ready(business_name, preview)
        if not attempt_id.strip():
            raise ValueError("Telegram preview notification requires an attempt ID.")
        return asyncio.run(
            self._send_preview_ready(
                chat_id,
                business_name=normalized_name,
                preview=preview,
                attempt_id=attempt_id,
            )
        )

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

    async def _send_preview_ready(
        self,
        chat_id: int,
        *,
        business_name: str,
        preview: PreviewDeploymentResult,
        attempt_id: str,
    ) -> dict[str, str | int]:
        bot = Bot(self.token)
        message: Any = await bot.send_message(
            chat_id=chat_id,
            text=(
                "Сайт готов к проверке\n\n"
                f"Бизнес: {business_name}\n"
                f"Preview: {preview.preview_url}\n\n"
                "Это закрытая тестовая версия:\n"
                "- noindex,nofollow;\n"
                "- не является production;\n"
                "- домен клиента не подключён;\n"
                "- после проверки можно отправить правки."
            ),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Открыть сайт", url=preview.preview_url)]]
            ),
            disable_web_page_preview=True,
        )
        date = getattr(message, "date", None)
        return {
            "status": "accepted",
            "sent_at": (date if isinstance(date, datetime) else datetime.now(timezone.utc)).isoformat(),
            "preview_url_sha256": hashlib.sha256(preview.preview_url.encode("utf-8")).hexdigest(),
            "deployment_id": preview.deployment_id,
            "attempt_id": attempt_id,
        }

    async def _send_failure(self, chat_id: int) -> None:
        bot = Bot(self.token)
        await bot.send_message(
            chat_id=chat_id,
            text="Не удалось завершить работу. Подробности смотрите в логах сервера.",
        )
