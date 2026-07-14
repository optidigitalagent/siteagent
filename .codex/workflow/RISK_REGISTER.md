# Risk Register

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Railway filesystem is not shared with local Codex | Telegram URL is not visible locally | Enable `TELEGRAM_INBOX_GIT_SYNC=true` and use repo-backed inbox |
| Railway cannot push to GitHub | Inbox sync fails | Configure GitHub integration or tokenized remote URL |
| OpenAI key missing | Generation cannot run | `.env`/Railway vars must include `OPENAI_API_KEY` |
| Playwright browser missing | Critic gate fails | Dockerfile installs Chromium with Playwright deps |
| Cloudflare credentials missing locally | Production job cannot publish | Fail closed with setup guidance; never return `file://` |
| Wrangler output/schema changes | Deployment metadata parsing fails | Pin Wrangler major version and cover representative JSON in tests |
| Local system disk is full | npm cannot install Wrangler or Wrangler cannot write local state | Free disk space or configure npm cache on a disk with capacity before real deployment |
| Cloudflare deployment propagation delay | Immediate live check fails | Bounded retry with backoff before declaring failure |
| Oversized or sensitive file in site output | Broken upload or data exposure | Preflight every file, reject traversal, secrets, reports, and files over 25 MiB |
| Deterministic Pages name collides | Another project could be overwritten | Stable URL marker ownership check and bounded hash-suffix retry |
| Public queue exposes client links | Privacy risk | Use private repo for `website-agent` inbox |
