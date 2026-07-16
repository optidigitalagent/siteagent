# site-agent / website-agent

## Design-quality pipeline

New runs use pipeline schema v2 before the existing publisher: research →
evidence/media assessment → business brief and UX/story contracts → three visual
directions → selected token system and responsive contract → deterministic build
→ browser technical inspection + critic council → acceptance audit → the existing
Cloudflare and Telegram delivery sequence. The pipeline never silently falls
back to a generic generator: Level C evidence is recorded as
`insufficient_evidence` and cannot publish; Level B is an intentionally
text-led, honest contact path rather than an empty multi-section page.

Artifacts are written beneath `runs/<job>/generation_reports/`, notably
`01_evidence_assessment.json`, `04_business_brief.json`,
`04_ux_architecture.json`, `04_narrative_strategy.json`,
`04_visual_directions.json`, `04_design_system.json`,
`04_media_manifest.json`, `04_builder_context.json`, and a quality report per
iteration. Schema v1 artifacts remain valid for completed legacy jobs.

Quality is category-gated: business, UX, story, design, copy, accessibility,
responsive, anti-template, and technical floors must all pass. A high/critical
issue, unsupported claim, placeholder phrase, or repeated full-layout
fingerprint blocks deployment even if the technical score is high.

### Pinned design skills

The reviewed, vendored sources live in `.agents/skills/`; production reads only
those local copies and never remote `main`. Their sources, SHA commits, checksums
and review date are in `.agents/skills/skills.lock.json`: `frontend-design`
(Anthropic), `ui-ux-pro-max` (NextLevelBuilder), and
`web-design-guidelines` (Vercel Labs). To update one, review the pinned source,
vendor it locally, recalculate its checksum, update the lock, validate the
ui-ux data script, and run the complete test suite. These skills are guidance;
they do not supply runtime credentials or execute remote scripts during a job.

Internal contracts are under `.codex/skills/siteagent-*`. Add a critic by
recording its inputs, deterministic evidence, failure conditions and acceptance
condition, then add its floor in `site_agent/design_quality.py` and a focused
test. Add a fixture by using only deterministic evidence and assert its
fingerprint, CTA, structure and gate outcome.

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
# Creative build modes

New local production jobs default to `SITE_BUILDER=codex_studio`. The Python control plane first
creates cited research, an authorised Cloudinary media manifest, trait-selected reference rationale
and a Design Director implementation brief; Codex receives the immutable package, validates the
rendered output and then uses the existing publisher/Telegram delivery path. The optional IDE
plugin lives in `plugins/siteagent-web-studio`; its source of truth remains `.agents/skills`, so
runtime never depends on a manual Codex IDE install.

`SITE_BUILDER=legacy_template` keeps the former Jinja renderer available solely for legacy
compatibility and controlled tests. It is explicit: Studio failures are retryable and never fall
back to Jinja. Studio artifacts live in `runs/<job_id>/studio/`, including the input package,
concepts, screenshots, comparison, selected build and provenance.

The rollout default `CREATIVE_STUDIO_HUMAN_CALIBRATION_REQUIRED=true` blocks production publishing
after creative acceptance until a human has reviewed the real fixture comparison evidence. It does
not affect the bot-only Railway runtime, which must not receive Codex/browser/Cloudflare settings.

## Strategy and media prerequisites

`RESEARCH_STRATEGIST_PROVIDER=openai`, `DESIGN_DIRECTOR_PROVIDER=openai`, and
`SITE_BUILDER_PROVIDER=codex` are separate required roles. Studio work fails closed unless
`runs/<job>/media_input/manifest.json` declares local business media with both
`user_authorized` and `allowed_for_public_site` set to `true`; accepted assets are uploaded to
Cloudinary before Design Director runs. Scraped Instagram/CDN URLs, stock and fixture media are
never acceptable production media.

Import the approved reference library locally before calibration:

```powershell
python -m site_agent.reference_import
```

Refresh autonomous discovery from curated award sources with:

```powershell
python -m site_agent.reference_import --refresh-discovery
```

Award and gallery pages are discovery inputs only. SiteAgent resolves an original live URL,
captures desktop/mobile evidence, then records separate Curator/Auditor active-or-excluded
decisions in `references/site_designs/reference_decisions.json`. Production reference selection
fails closed unless there are enough high-confidence active records; the optional local
`human_review` pages are diagnostics only and cannot influence selection, ranking or exclusion.
