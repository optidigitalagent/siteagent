# Agent Workflow Contract

## Codex Go Command

When the user writes only `го` or `go` in this project, run:

```powershell
python -m site_agent.cli go
```

This command must claim the next Telegram inbox job from `.codex/inbox/telegram_jobs.json`, generate the website, publish it, and send the final Telegram response. Do not ask the user to paste the Instagram link again.

## Research Agent

Input: one Instagram URL plus public scrape context.

Output: `ResearchBrief`.

Must identify verified facts, unknowns, forbidden claims, real media candidates, contacts, niche, language, location signals, offers/prices when visible, and brand atmosphere. Missing data must stay missing; the agent must recommend Instagram/Direct CTAs instead of inventing facts.

## Brand / Strategy Agent

Input: `ResearchBrief`.

Output: `StrategyBrief`.

Must define target customer, business reason to choose, customer fears/questions, niche-specific sections, primary/secondary CTA, tone, visual direction, and business logic. One-page is the default unless the business clearly needs more.

## Design + Copy Agent

Input: `ResearchBrief`, `StrategyBrief`.

Output: `SiteSpec`.

Must create customer-facing copy that is specific, short, and honest. It must include a strong hero, meaningful CTA, niche-fit sections, trust without fake proof, process, contacts, final CTA, and media choices. Generic AI phrases, fake reviews, fake numbers, fake staff, fake prices, and lorem ipsum are forbidden.

## Builder

Input: `SiteSpec`.

Output: `site/index.html`, `site/assets/`.

Uses a deterministic renderer to protect typography, spacing, contrast, mobile layout, and CTA consistency. The renderer may use real Instagram assets when available and must still build an honest site when assets are missing.

## Visual Director / Critic

Input: rendered site, screenshots, technical inspection, briefs.

Output: `CritiqueReport`.

Must inspect desktop and mobile. Delivery is blocked by technical gate failure, score below `88`, missing visual/business approval, or any `critical`/`high` issue.

## Fixer

Input: `CritiqueReport`, current `SiteSpec`.

Output: updated `SiteSpec`.

Must fix the actual problem: weak hero, wrong CTA, generic copy, missing niche logic, bad mobile, fake facts, poor hierarchy, or weak trust. CSS-only tweaks are insufficient for business/design issues.

## Telegram Bot

Start response:

```text
Окей, работа запущена.
Напиши в Codex: го
```

Final response:

```text
Готово:
[site url]
Репозиторий: [repo url]
```

No progress logs, reports, HTML files, ZIPs, or explanations are sent to the user unless verbose mode is explicitly enabled.

## Development Agent Workflow

The development workflow state lives in `.codex/workflow/`. Agents and reviewers pass state through these files, not through user-facing narration:

- `GLOBAL_GOAL.md` - high-level product goal and acceptance criteria.
- `GOAL.md` - current technical goal.
- `GOAL_PROGRESS.md` - progress journal.
- `NEXT_ACTION.md` - exactly one next action.
- `SCENARIO_MATRIX.md` - happy, negative, adversarial, browser, backend, deployment scenarios.
- `REVIEW_REPORT.md` - reviewer findings.
- `RISK_REGISTER.md` - risks and mitigations.
- `DECISIONS.md` - important decisions.
- `DEPLOYMENT_CHECKLIST.md` - deploy and verification checklist.

Use `.codex/skills/` roles for website project development: intake, context research, goal analysis, scenario design, planning, implementation, QA, frontend/backend review, design/content/brand/responsive/accessibility/SEO/performance review, live QA, failure analysis, deployment verification, acceptance audit, and handoff.
