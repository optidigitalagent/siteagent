# Goal Progress

- Added Telegram queue design for URL handoff.
- Added CLI `go` / `го` command contract.
- Added Railway/Docker deployment files.
- Linked Railway project `website-agent` and created service `website-agent`.
- Set non-secret Railway runtime variables for queue/git sync and runtime behavior.
- Added `.codex/workflow` project memory.
- Added `.codex/skills` role instructions for website development and QA.
- Verified `python -m compileall site_agent scripts`.
- Verified `python scripts/smoke_build.py`.
- Verified `python -m site_agent.cli go` with no pending jobs.
- Verified queue enqueue/claim/complete smoke test on a temporary JSON file.
- Verified Playwright technical gate on smoke site.

Blocked for live bot deploy until secrets are configured:

- `OPENAI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `PUBLISH_REMOTE_URL`
- `PUBLIC_REPO_URL`
