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

Live end-to-end verification requires local runtime credentials:

- `TELEGRAM_BOT_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`
- `OPENAI_API_KEY` only when `LLM_PROVIDER=openai`

## Cloudflare Pages Production Publishing

- Audited the actual `go` path: `site_agent.cli.run_pending_job` ->
  `SiteAgentOrchestrator.run` -> `Publisher.publish` -> queue completion ->
  `TelegramNotifier.send_done`.
- Confirmed the root cause of the local URL: `Publisher.publish` intentionally returns
  `site/index.html` as a `file://` URI whenever `PUBLISH_REMOTE_URL` is empty.
- Confirmed there was no separate acceptance-audit implementation and no publisher test
  suite; final critic approval currently calls publish directly.
- Confirmed local Node.js, npm, and npx are installed. Cloudflare account credentials are
  not configured, so a real deployment remains conditional on local credential setup.
- Implemented `CloudflarePagesPublisher` behind the existing `Publisher` entry point,
  preserving explicit `local` preview and deprecated explicit `git` provider paths.
- Added deterministic normalized-Instagram project naming, marker-based ownership checks,
  preflight file protection, non-interactive pinned `wrangler@4`, structured deployment
  metadata, bounded live retries, and success-only Telegram delivery.
- Verified `python -m unittest discover -s tests -v`: 33 passed, 1 credential-gated smoke skipped.
- Verified `python -m compileall -q site_agent scripts tests`, `python -m pip check`,
  `python scripts/smoke_build.py`, and `npx --yes wrangler@4 --version` (`4.110.0`).
- Verified `.env.railway.example` contains no Cloudflare account/token variables and
  `git diff --check` passes.
- No `.env` exists in this workspace, so a live Cloudflare deployment, public URL,
  and remote desktop/mobile inspection could not be performed.

## Cloudflare Pages Smoke Deployment (2026-07-14)

- Local `.env` now provides the required Cloudflare account and API token values; their
  values were not printed or written to workflow state.
- The first opt-in smoke run exposed a Wrangler 4.110.0 compatibility issue:
  `WRANGLER_LOG=none` suppresses successful `--json` output, so project listing parsing
  failed before upload. Removed that log-level override while retaining disabled metrics
  and error reporting; the focused publisher suite passes (30 tests).
- Ran `$env:RUN_CLOUDFLARE_SMOKE='1'; python -m unittest tests.test_cloudflare_smoke -v`:
  Cloudflare Direct Upload, stable HTTPS HTML/marker verification, and completion all
  passed. Stable URL: https://siteagent-smoke-siteagent-cloudflare-smo-0fee21e595.pages.dev
- `python -m unittest discover -s tests -v` passes: 32 tests passed, 1 credential-gated
  smoke skipped because the opt-in environment flag was intentionally absent for that
  regression run. `python -m compileall -q site_agent tests` and `git diff --check` pass.
- Attempted the required desktop/mobile browser inspection. The browser-control runtime
  failed before opening a tab with `Cannot redefine property: process`; this is an
  environment integration issue, not a Pages response failure. Visual viewport evidence
  remains pending, while programmatic live HTML verification has passed.

## Remote Visual Verification (2026-07-14)

- Confirmed the `Cannot redefine property: process` failure is confined to Codex's
  embedded browser runtime: the project's installed Playwright Chromium opened the
  public Pages HTTPS URL successfully.
- Extended the existing `TechnicalInspector` with `inspect_url`, using the same
  desktop/mobile technical gate for a remote URL and recording console errors, failed
  network requests, observations, and screenshots in the artifacts directory.
- Inspected `https://siteagent-smoke-siteagent-cloudflare-smo-0fee21e595.pages.dev`:
  HTTP/HTTPS navigation and network-idle completed; console errors, failed requests,
  missing images, broken links, small tap targets, and horizontal overflow were all empty.
  Artifacts: `runs/smoke/technical_gate/{desktop.png,mobile.png,technical_gate.json,observations.json}`.
- Visual inspection also confirmed this URL is the intentionally minimal Cloudflare smoke
  fixture, not a generated business site. It cannot satisfy the Telegram production E2E
  acceptance criteria.
- The Telegram queue has no `pending` item. Its only historical item is `done` with an
  old local `file://` result, so `python -m site_agent.cli go` was not run and no Telegram
  success message was sent in this verification pass. A new Instagram URL must be sent to
  the Telegram bot before real business E2E and real-project idempotency can proceed.
- Regression evidence: `python -m unittest discover -s tests -v` -> 33 passed, 1 opt-in
  Cloudflare smoke skipped; `python -m compileall -q site_agent scripts tests`,
  `python -m pip check`, `python scripts/smoke_build.py`, and `git diff --check` passed.
- Attempting `python -m site_agent.cli go` did not claim anything: because a Git remote
  exists, the queue performs `git pull --rebase` before its pending check, and Git refused
  to pull over the pre-existing uncommitted worktree changes. No queue state changed and no
  Telegram message was sent. Do not stash, discard, or commit those user-owned changes as
  part of verification.
