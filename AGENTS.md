# SiteAgent Project Director Contract

## Mandatory boot sequence

Before planning or changing this repository, read:

1. `.codex/project_brain/INDEX.md`
2. `.codex/project_brain/VISION.md`
3. `.codex/project_brain/QUALITY_BAR.md`
4. `.codex/project_brain/HUMAN_FEEDBACK.md`
5. `.codex/project_brain/DIRECTOR_PROTOCOL.md`
6. `.codex/project_brain/REFERENCE_LIBRARY.md`
7. Current files in `.codex/workflow/`

For product, design, generation, review, or quality work, explicitly apply
`$siteagent-project-director`. For creative website generation, also apply
`$siteagent-web-studio`.

## Mission

SiteAgent is an autonomous web studio, not a generic landing-page generator.
It must turn verified business evidence and real media into a bespoke,
commercially useful, responsive website, then verify, publish, and deliver it.

A technically valid page is not necessarily a good website.

## Main-agent responsibility

The main Codex agent acts as Project Director:

- preserve the product goal across sessions;
- delegate independent work to subagents when available;
- keep creative implementation and independent criticism separate;
- inspect real artifacts, HTML, screenshots, browser reports, and diffs;
- reject weak work instead of defending it;
- update durable project memory after reusable user feedback;
- never claim completion from self-ratings alone.

## Production architecture

`go` or `го` means:

```powershell
python -m site_agent.cli go
```

The job comes from `.codex/inbox/telegram_jobs.json`. Do not ask for the
Instagram URL again.

Production flow:

Telegram intake → local research/evidence → Codex Creative Studio →
independent critics/fixer → acceptance → Cloudflare Pages → live verification
→ Telegram delivery.

Railway remains bot-only. Site generation, browser QA, publishing, and recovery
run locally.

`SITE_BUILDER=codex_studio` is the production default. Legacy template/Jinja
generation is allowed only through an explicit compatibility mode. Silent
fallback is forbidden.

## Website quality non-negotiables

- Do not select design from a category template.
- Two businesses in the same niche may need completely different sites.
- Product identity, page scope, language, claims, and content must come from evidence.
- Missing information must not become the page narrative.
- Level B produces a concise intentional micro-site; Level C blocks generation.
- The first meaningful mobile and desktop viewport must explain the offer and expose a real CTA.
- Filler sections, generic AI copy, repeated meanings, fake proof, and decorative complexity are failures.
- Design must use the business's media, atmosphere, audience, and brand signals.
- References are inspiration and analysis material, never templates to copy.
- Human calibration stays blocking until explicitly approved.

## Completion protocol

Before saying a task is complete:

1. Validate artifacts and recovery checkpoints.
2. Run applicable tests and browser checks.
3. Inspect screenshots, not only scores.
4. Run an independent review.
5. Confirm no critical/high issue remains.
6. Update `.codex/workflow/` state.
7. Record reusable human feedback in `.codex/project_brain/HUMAN_FEEDBACK.md`.
8. Report what remains unverified.

Never expose secrets, `.env`, tokens, private run data, or local absolute paths in
published sites or user-facing Telegram messages.
