# Scenario Matrix

| Scenario | Expected Result | Evidence |
| --- | --- | --- |
| Telegram receives Instagram URL | Queue file gets a pending job and bot replies with Codex `го` instruction | Queue JSON + bot log |
| Codex `go` with pending job | Job becomes running, pipeline starts from stored URL | CLI output + queue JSON |
| Codex `go` with no jobs | CLI says no pending jobs and exits cleanly | CLI output |
| Generation passes QA | Publisher returns site/repo URL and Telegram final response is sent | `publish_result.json` + Telegram message |
| Critic blocks site | Fixer loop runs up to max iterations | critique reports |
| Publishing env missing | Local `file://` site URL is returned | CLI output |
| Railway deploy | Bot starts with `python -m site_agent.telegram_bot` | Railway logs |
| Git inbox sync enabled | Bot commits queue change, Codex pulls before claim | git history |
