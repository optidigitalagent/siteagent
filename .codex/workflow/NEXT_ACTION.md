# Next Action

First make the Git worktree clean enough for the configured inbox `git pull --rebase`
(without discarding unrelated changes), then send a new real Instagram URL to the Telegram
bot so it creates a `pending` queue item. Run `python -m site_agent.cli go`, inspect the
resulting business URL with the remote Playwright gate, confirm its Telegram success
message and `done` queue state, then republish the same generated site to prove the Pages
project and stable production URL are reused.
