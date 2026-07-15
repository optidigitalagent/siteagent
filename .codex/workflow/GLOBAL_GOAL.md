# Global Goal

Build and operate `website-agent` as a Telegram-driven autonomous web studio.

## Product outcome

One Instagram business link becomes a bespoke, commercially useful, responsive
website that reflects the actual business rather than a reusable category
template.

## Production contract

- Telegram accepts one Instagram URL and writes a durable job to
  `.codex/inbox/telegram_jobs.json`.
- `python -m site_agent.cli go` claims or resumes the correct job without asking
  for the URL again.
- Local execution performs evidence research, scope selection, Codex Creative
  Studio generation, screenshot-led review, fixer iterations, acceptance,
  Cloudflare Pages deployment, live verification, and Telegram delivery.
- Railway remains bot-only.
- `SITE_BUILDER=codex_studio` is the production default.
- Legacy template generation is explicit compatibility mode only; no silent fallback.
- Crash recovery reuses valid concepts, builds, deployments, and delivery state.

## Quality contract

Delivery is blocked unless:

- evidence and product identity are sufficient for the selected page scope;
- the result is commercially clear and useful;
- the site matches verified facts and language evidence;
- the first meaningful viewport communicates the offer and CTA;
- copy, UX, story, media, accessibility, responsive, design, technical, and
  anti-template gates pass independently;
- no critical/high issue remains;
- the site is not a placeholder, filler page, editorial exercise, or category template;
- public Cloudflare verification passes;
- human calibration is approved when the rollout flag requires it.

Technical correctness or a high average score cannot compensate for a weak
business website.
