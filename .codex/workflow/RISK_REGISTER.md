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
| Studio child invocation can hang after partial artifacts | A stale `running` task state can mask an incomplete build | Preserve concepts/selection, stop only the known child process, require a separate staged build plus fresh technical and independent visual review before promotion |
| Fixture/stock imagery is mistaken for business portfolio proof | False commercial claims or unlicensed production media | Record per-asset source classification, final-use report and visible fixture disclosure; block production until authorised business media and rights provenance exist |
| Fixture-only disclosure is stripped while fixture media remains | A calibration artifact can masquerade as a production portfolio site | Promotion validates selected media provenance before stripping calibration markers; fixture/stock media fails closed, while valid production rejects calibration-only text |
| Cloudinary or authorised media is unavailable | A builder could substitute stock, fixture, or fragile scrape URLs | Block at media-input before Design Director/Codex and list missing authorised assets |
| Reference library is absent or incomplete | Design direction can revert to generic/category patterns | Require three captured trait references before design; importer is resumable and records failures |
