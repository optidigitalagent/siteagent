# Deployment Checklist

- Repository is pushed to the GitHub repo used by Railway, ideally `website-agent`.
- Railway project is named `website-agent` and deploys this repo.
- Railway variables are set from `.env.example`.
- `TELEGRAM_BOT_TOKEN` is valid.
- `OPENAI_API_KEY` is valid.
- `TELEGRAM_INBOX_GIT_SYNC=true` if Railway and Codex are not on the same filesystem.
- Railway has permission to push `.codex/inbox/telegram_jobs.json` when Git sync is enabled.
- Local `.env` selects `HOSTING_PROVIDER=cloudflare_pages` and `PUBLISH_REQUIRED=true`.
- Local `.env` contains `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`; Railway does not.
- Cloudflare token has Account / Cloudflare Pages / Edit permission for the selected account.
- Node.js, npm, and npx are available on the local Codex machine.
- Send a test Instagram URL to Telegram.
- In Codex run `python -m site_agent.cli go`.
- Confirm `runs/<job_id>/deployment.json` records a verified production deployment.
- Confirm the stable `https://<project>.pages.dev` URL opens without authentication.
- Confirm Telegram receives only the public site URL and no repository or local path.
