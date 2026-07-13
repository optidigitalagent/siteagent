# site-agent / website-agent

Autonomous website agent for turning one Instagram business link into a published commercial website.

## Telegram + Codex Flow

The production flow is deliberately quiet:

1. User sends an Instagram URL to the Telegram bot.
2. Bot saves the URL into `.codex/inbox/telegram_jobs.json` and replies:

```text
Окей, работа запущена.
Напиши в Codex: го
```

3. In Codex, open this project and write `го` or run:

```powershell
python -m site_agent.cli go
```

4. Codex takes the pending Telegram URL, researches it, builds the site, runs desktop/mobile critic checks, fixes up to `MAX_FIX_ITERATIONS`, publishes, and sends Telegram only:

```text
Готово:
[site url]
Репозиторий: [repo url]
```

For local-only development the queue is a file. For Railway + Codex handoff, the bot commits the inbox file and `go` pulls it before claiming a job. In this repository `go` automatically uses git sync when a git remote is configured; set `TELEGRAM_INBOX_GIT_SYNC=true` explicitly in nonstandard environments.

## Quality Contract

The system is designed around a small web-studio workflow, not a generic landing-page generator:

- research separates verified Instagram facts from assumptions;
- strategy picks a niche-specific site structure and CTA;
- copy is concrete, short, and human;
- design uses real brand/media signals where available;
- critic blocks delivery on any `critical` or `high` issue;
- fixer repairs the actual business/design problem, not only CSS;
- final delivery requires technical gate pass, visual approval, score `>= 88`, and no `critical`/`high` issues.

## Local Codex Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
Copy-Item .env.example .env
```

Fill `.env`.

Local Codex/generation variables:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `TELEGRAM_BOT_TOKEN` only if Codex should send the final Telegram message after publishing

Publishing generated site repository:

- `PUBLISH_REMOTE_URL`
- `PUBLIC_REPO_URL`
- `PUBLISH_BRANCH`

Telegram inbox sync for local Codex handoff:

- `TELEGRAM_QUEUE_PATH=.codex/inbox/telegram_jobs.json`
- `TELEGRAM_INBOX_GIT_SYNC=true` to force git sync; `go` auto-enables it when this repo has a git remote
- `TELEGRAM_INBOX_GIT_REMOTE_URL` with an authenticated GitHub remote URL when Railway must push queue updates
- `TELEGRAM_INBOX_GIT_BRANCH=main`

## Railway

Railway is bot-only. It must not generate sites and does not need `OPENAI_API_KEY`, `PUBLISH_REMOTE_URL`, `PUBLIC_REPO_URL`, Playwright, or browser tooling.

Create or connect the Railway project named `website-agent` to this GitHub repository. The repo includes:

- `Dockerfile` with Python, git, and Telegram inbox dependencies only;
- `railway.json` with the Telegram bot start command;
- `Procfile` fallback start command.

Set Railway variables from `.env.railway.example`:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_INBOX_GIT_SYNC=true`
- `TELEGRAM_INBOX_GIT_REMOTE_URL=https://x-access-token:<GITHUB_TOKEN>@github.com/optidigitalagent/siteagent.git`
- `TELEGRAM_INBOX_GIT_BRANCH=main`

Railway needs repository push access only so it can commit the inbox file. Site generation and publishing happen later from Codex when you write `го`.

## Commands

Run Telegram bot:

```powershell
python -m site_agent.telegram_bot
```

Run one job from URL:

```powershell
python -m site_agent.cli "https://www.instagram.com/example/"
```

Run next Telegram job:

```powershell
python -m site_agent.cli go
```

Output artifacts are written to `runs/<job_id>/`:

- `site/index.html`
- `site/assets/`
- `generation_reports/`
- `critique_reports/`

If publishing env vars are absent, the CLI uses a local `file://` URL instead of deploying.

## Development Agent Workflow

`.codex/workflow/` is the project memory and dispatcher. `.codex/skills/` contains role instructions for goal intake, planning, implementation, QA, review, live verification, deployment, acceptance audit, and handoff.

When the user says only `го`/`go`, the expected Codex action is to run `python -m site_agent.cli go`, not to ask for a URL.
