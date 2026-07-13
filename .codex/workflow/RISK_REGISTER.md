# Risk Register

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Railway filesystem is not shared with local Codex | Telegram URL is not visible locally | Enable `TELEGRAM_INBOX_GIT_SYNC=true` and use repo-backed inbox |
| Railway cannot push to GitHub | Inbox sync fails | Configure GitHub integration or tokenized remote URL |
| OpenAI key missing | Generation cannot run | `.env`/Railway vars must include `OPENAI_API_KEY` |
| Playwright browser missing | Critic gate fails | Dockerfile installs Chromium with Playwright deps |
| Publishing remote missing | Final URL is local file URL | Set `PUBLISH_REMOTE_URL` and `PUBLIC_REPO_URL` |
| Public queue exposes client links | Privacy risk | Use private repo for `website-agent` inbox |
