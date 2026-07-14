# site-agent / website-agent

Autonomous website agent for turning one Instagram business link into a published commercial website.

## Telegram + Codex Flow

The production flow is deliberately quiet:

1. A user sends an Instagram URL to the Telegram bot.
2. Railway saves the job in `.codex/inbox/telegram_jobs.json`, synchronizes the queue, and replies:

```text
Окей, работа запущена.
Напиши в Codex: го
```

3. On the local Codex machine, run:

```powershell
python -m site_agent.cli go
```

4. Local Codex claims the job, researches the business, builds the site, runs technical and desktop/mobile critic checks, and fixes issues up to `MAX_FIX_ITERATIONS`.
5. The final critic result must pass the technical gate, visual and business approval, score at least `88`, and contain no `critical` or `high` issues. A separate acceptance audit records this decision before publishing.
6. Local Codex uploads only `runs/<job_id>/site/` directly to Cloudflare Pages with Wrangler.
7. After the stable public HTTPS URL passes live HTML and asset verification, Telegram receives:

```text
Готово:

Сайт:
https://<project-name>.pages.dev
```

Railway runs only the Telegram bot and queue synchronization. It does not generate, test, or publish sites. Cloudflare stores and serves each generated static site; no per-site GitHub repository is required. For Railway + Codex handoff, the bot commits the inbox file and `go` pulls it before claiming a job. `go` automatically uses Git sync when this repository has a remote; set `TELEGRAM_INBOX_GIT_SYNC=true` explicitly in nonstandard environments.

## Quality Contract

The system is designed around a small web-studio workflow, not a generic landing-page generator:

- research separates verified Instagram facts from assumptions;
- strategy picks a niche-specific site structure and CTA;
- copy is concrete, short, and honest;
- design uses real brand/media signals where available;
- critic blocks delivery on any `critical` or `high` issue;
- fixer repairs the business/design problem, not only CSS;
- acceptance and deployment are blocked unless every quality gate passes;
- Telegram success is blocked unless Cloudflare live verification passes.

## Local Codex Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
Copy-Item .env.example .env
node --version
npm --version
npx --version
```

Fill `.env` locally.

Generation variables:

- `LLM_PROVIDER=codex` uses the installed local Codex CLI; `LLM_PROVIDER=openai` uses the OpenAI API.
- `CODEX_COMMAND=codex`
- `CODEX_MODEL` is optional; empty uses the local Codex default.
- `OPENAI_API_KEY` and `OPENAI_MODEL` are needed only with `LLM_PROVIDER=openai`.
- `TELEGRAM_BOT_TOKEN` is needed locally only when Codex should send the final Telegram response.

Cloudflare Pages Direct Upload variables, local machine only:

```env
HOSTING_PROVIDER=cloudflare_pages
PUBLISH_REQUIRED=true
CLOUDFLARE_ACCOUNT_ID=
CLOUDFLARE_API_TOKEN=
CLOUDFLARE_PAGES_PRODUCTION_BRANCH=main
CLOUDFLARE_PROJECT_PREFIX=siteagent
```

Install the current Node.js LTS release if `node`, `npm`, or `npx` is missing. The pipeline invokes `npx --yes wrangler@4` non-interactively and passes `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` only through the subprocess environment. Create a custom Cloudflare API token scoped to the target account with `Account / Cloudflare Pages / Edit` permission.

Manual local preview is opt-in and is never a production fallback:

```env
HOSTING_PROVIDER=local
PUBLISH_REQUIRED=false
```

The previous Git publisher remains available only as the deprecated explicit provider `HOSTING_PROVIDER=git`, using `PUBLISH_REMOTE_URL`, `PUBLIC_REPO_URL`, and `PUBLISH_BRANCH`. Missing Cloudflare configuration never falls back to Git or `file://`.

Telegram inbox sync variables:

- `TELEGRAM_QUEUE_PATH=.codex/inbox/telegram_jobs.json`
- `TELEGRAM_INBOX_GIT_SYNC=true` forces Git sync.
- `TELEGRAM_INBOX_GIT_REMOTE_URL` is the authenticated GitHub remote used by Railway to push queue updates.
- `TELEGRAM_INBOX_GIT_BRANCH=main`

## Railway

Railway is bot-only. It must not generate or publish sites and does not need `OPENAI_API_KEY`, Cloudflare credentials, `PUBLISH_REMOTE_URL`, `PUBLIC_REPO_URL`, Playwright, Node.js, Wrangler, or browser tooling.

Create or connect the Railway project named `website-agent` to this repository. The repository includes:

- `Dockerfile` with Python, Git, and Telegram inbox dependencies only;
- `railway.json` with the Telegram bot start command;
- `Procfile` fallback start command.

Set Railway variables from `.env.railway.example`:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_INBOX_GIT_SYNC=true`
- `TELEGRAM_INBOX_GIT_REMOTE_URL=https://x-access-token:<GITHUB_TOKEN>@github.com/optidigitalagent/siteagent.git`
- `TELEGRAM_INBOX_GIT_BRANCH=main`

Railway needs repository push access only to synchronize `.codex/inbox/telegram_jobs.json`. Cloudflare credentials must never be configured in Railway.

## Commands

Run the Telegram bot:

```powershell
python -m site_agent.telegram_bot
```

Run one job directly from a URL:

```powershell
python -m site_agent.cli "https://www.instagram.com/example/"
```

Run the next production Telegram job:

```powershell
python -m site_agent.cli go
```

Output artifacts are written to `runs/<job_id>/`:

- `site/index.html`
- `site/assets/`
- `generation_reports/`
- `critique_reports/`
- `deployment.json`

`deployment.json` contains provider, project, production/deployment URLs, deployment ID, timestamp, and verification status. It never contains Cloudflare credentials. A failed deployment is recorded there and prevents queue completion and the Telegram success message.

## Publishing Safety

Before Direct Upload, the publisher requires a non-empty site directory and `index.html`, rejects symlinks and path escape, credentials, `.env` files, prompts, and internal reports, enforces Cloudflare's 20,000-file limit, and blocks files over 25 MiB. The project name is deterministic from the normalized Instagram URL, so repeat runs update the same Pages project while businesses with similar names receive different stable hashes.

After upload, the pipeline reads the latest production deployment and retries live verification. It requires HTTPS, HTTP 200, non-empty HTML, the current site's marker, no standard Cloudflare error page, and successful responses for local assets referenced by the page.

## Tests

Run all local tests and build checks:

```powershell
python -m unittest discover -s tests -v
python -m compileall site_agent scripts tests
python scripts/smoke_build.py
```

The real Cloudflare Direct Upload smoke test is opt-in and reads credentials only from the local environment:

```powershell
$env:RUN_CLOUDFLARE_SMOKE='1'
python -m unittest tests.test_cloudflare_smoke -v
```

## Development Agent Workflow

`.codex/workflow/` is the project memory and dispatcher. `.codex/skills/` contains role instructions for goal intake, planning, implementation, QA, review, live verification, deployment, acceptance audit, and handoff.

When the user says only `го` or `go`, Codex runs `python -m site_agent.cli go` and does not ask for the Instagram URL again.
