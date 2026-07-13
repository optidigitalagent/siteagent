# Decisions

- Telegram bot does not generate sites directly; it only accepts URL and writes a pending job.
- Codex command `go` owns execution, QA, publishing, and final Telegram notification.
- Queue defaults to local file and supports optional Git sync for Railway handoff.
- Railway deployment uses Dockerfile to guarantee Playwright Chromium dependencies.
- Website quality gates remain strict: score >= 88, no critical/high issues, technical pass, visual/business approval.
