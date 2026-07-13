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

For local-only development the queue is a file. For Railway + Codex handoff, set `TELEGRAM_INBOX_GIT_SYNC=true` in both Railway and the Codex environment so the bot commits the inbox file and `go` pulls it before claiming a job.

## Quality Contract

The system is designed around a small web-studio workflow, not a generic landing-page generator:

- research separates verified Instagram facts from assumptions;
- strategy picks a niche-specific site structure and CTA;
- copy is concrete, short, and human;
- design uses real brand/media signals where available;
- critic blocks delivery on any `critical` or `high` issue;
- fixer repairs the actual business/design problem, not only CSS;
- final delivery requires technical gate pass, visual approval, score `>= 88`, and no `critical`/`high` issues.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
Copy-Item .env.example .env
```

Fill `.env`.

Required:

- `OPENAI_API_KEY`
- `TELEGRAM_BOT_TOKEN`

Publishing generated site repository:

- `PUBLISH_REMOTE_URL`
- `PUBLIC_REPO_URL`
- `PUBLISH_BRANCH`

Telegram inbox sync for Railway handoff:

- `TELEGRAM_QUEUE_PATH=.codex/inbox/telegram_jobs.json`
- `TELEGRAM_INBOX_GIT_SYNC=true`
- `TELEGRAM_INBOX_GIT_BRANCH=main`

## Railway

Create or connect the Railway project named `website-agent` to this GitHub repository. The repo includes:

- `Dockerfile` with Python, git, dependencies, and Playwright Chromium;
- `railway.json` with the Telegram bot start command;
- `Procfile` fallback start command.

Set Railway variables from `.env.example`. If `TELEGRAM_INBOX_GIT_SYNC=true`, Railway must have push access to the repository, for example through the connected GitHub integration or a remote URL/token configured in the deployment environment.

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
