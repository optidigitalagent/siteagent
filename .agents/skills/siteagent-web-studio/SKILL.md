---
name: siteagent-web-studio
description: Create an evidence-grounded, bespoke static business website for SiteAgent production or fixture work. Use when a run has approved Level A/B evidence and needs concept prototypes, visual selection, a full HTML/CSS/JS build, screenshot-led iteration, or a creative acceptance decision.
---

# SiteAgent Web Studio

Treat the business, evidence and available media as the brief; do not use a category template.
The control plane supplies facts, prohibited claims, output paths and quality contracts. The
creative plane owns concept, narrative, page composition, art direction, HTML/CSS/JS, and revision.

## Required inputs

Read `studio/input/evidence.json`, `business_brief.json`, `media_manifest.json`,
`prohibited_claims.json` and `previous_site_constraints.json`. Do not read `.env`, credentials,
Telegram payloads or unrelated run data. Use only stated facts; missing facts require an Instagram
or Direct CTA, not an invention.

## Required guidance

Apply `$frontend-design`, `$ui-ux-pro-max`, `$siteagent-storytelling`,
`$siteagent-conversion-copy`, `$siteagent-media-director`, `$siteagent-responsive-design`,
`$siteagent-accessibility`, and `$siteagent-anti-template-critic`. If nested `$` activation is not
available, use their project-local instructions supplied in the task's `skill_guidance` block and
record their paths/checksums in build provenance.

## Workflow

1. Inspect evidence and media; identify one central creative idea for each candidate.
2. Build three actual prototypes at `studio/concepts/concept_a|b|c/index.html`. Each has a
   distinct central idea, composition, hero construction, information density, media strategy,
   typographic treatment, CTA treatment and signature element. Do not produce palette/font/text
   variants of one DOM layout.
3. Ensure each prototype has a full hero, narrative moment, decision/proof moment, CTA close and
   mobile behaviour. Use meaningful alt text, semantic landmarks, keyboard focus and reduced
   motion support.
4. Inspect the supplied desktop/mobile screenshots and write concise rationale to each
   `concept.md`. Review the concepts comparatively; selection without screenshots is forbidden.
5. Write `studio/concept_reviews/selected_concept.json` with the chosen concept, rejected
   alternatives, screenshot evidence, risks and mandatory improvements.
6. Extend the selected idea—not a generic template—into `studio/selected/source/`. Preserve its
   visual language and signature element while completing the story and responsive design.
7. Use real media only when suitable. Do not stretch low-resolution images, publish Instagram UI,
   or use an unsupported image as proof. Record actual use, crop and mobile behaviour in the
   media manifest.
8. Review the rendered desktop/tablet/mobile output. Address concrete findings materially; a
   color swap, minor spacing change or section reorder is not a redesign.

## Non-negotiable constraints

Avoid generic AI landing aesthetics, a universal narrow center column, anonymous rounded-card
grids, decorative gradients, repeated dark CTA footers, category-selected layouts, filler copy and
random ornament. Do not choose a concept before screenshot comparison or publish the first build.
Never change required output locations or include secrets in artifacts.

## Completion

Leave valid, static `index.html`, local assets and optional local CSS/JS only. The control plane
will validate, fingerprint, promote and publish; do not invoke Telegram, Cloudflare, git push or
the legacy Jinja renderer.
