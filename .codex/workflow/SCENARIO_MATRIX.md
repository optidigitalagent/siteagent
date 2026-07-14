# Scenario Matrix

| Scenario | Expected Result | Evidence |
| --- | --- | --- |
| Telegram receives Instagram URL | Queue file gets a pending job and bot replies with Codex `го` instruction | Queue JSON + bot log |
| Codex `go` with pending job | Job becomes running, pipeline starts from stored URL | CLI output + queue JSON |
| Codex `go` with no jobs | CLI says no pending jobs and exits cleanly | CLI output |
| Generation passes QA | Acceptance audit runs before publisher | `acceptance_audit.json` |
| Critic blocks site | Fixer loop runs up to max iterations | critique reports |
| Telegram production publishing env missing | Job fails; no `file://`, done status, or success Telegram message | queue JSON + `deployment.json` |
| Cloudflare project already exists for business | Deterministic project is reused and updated | mocked Wrangler calls + `deployment.json` |
| Cloudflare project is new | Project is created non-interactively, then deployed | mocked Wrangler calls + `deployment.json` |
| Direct Upload succeeds but live page fails | Job remains failed and success Telegram message is not sent | queue JSON + verification failure metadata |
| Explicit local development | `HOSTING_PROVIDER=local` and `PUBLISH_REQUIRED=false` returns a preview URI | unit test |
| Cloudflare credentials available | Opt-in smoke publishes static fixture and verifies stable HTTPS URL | smoke test output |
| Railway deploy | Bot starts with `python -m site_agent.telegram_bot` | Railway logs |
| Git inbox sync enabled | Bot commits queue change, Codex pulls before claim | git history |
