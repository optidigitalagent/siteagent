# Deployment Checklist

- Repository is pushed to the GitHub repo used by Railway, ideally `website-agent`.
- Railway project is named `website-agent` and deploys this repo.
- Railway variables are set from `.env.example`.
- `TELEGRAM_BOT_TOKEN` is valid.
- `OPENAI_API_KEY` is valid.
- `TELEGRAM_INBOX_GIT_SYNC=true` if Railway and Codex are not on the same filesystem.
- Railway has permission to push `.codex/inbox/telegram_jobs.json` when Git sync is enabled.
- Publishing vars point to the generated site repo.
- Send a test Instagram URL to Telegram.
- In Codex run `python -m site_agent.cli go`.
- Confirm Telegram receives final site and repository URLs.
