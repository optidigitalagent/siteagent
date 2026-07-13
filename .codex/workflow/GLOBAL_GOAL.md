# Global Goal

Build and operate `website-agent`: a Telegram-driven autonomous website studio.

Acceptance criteria:

- Telegram accepts one Instagram URL and replies only with the quiet start message.
- The URL is persisted in `.codex/inbox/telegram_jobs.json` for Codex handoff.
- `python -m site_agent.cli go` claims the pending Telegram job without asking for the URL again.
- The site pipeline runs research, strategy, site spec, deterministic build, desktop/mobile critic, fixer loop, publish, and Telegram final response.
- Delivery is blocked unless technical gate passes, score is at least 88, visual/business approval is true, and no critical/high issue remains.
- Railway can run the Telegram bot as project `website-agent` using repository config.
