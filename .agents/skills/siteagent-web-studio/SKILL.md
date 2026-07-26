---
name: siteagent-web-studio
description: Create an evidence-grounded, bespoke static business website for SiteAgent production or fixture work. Use when approved evidence needs real concept prototypes, screenshot-led selection, a full HTML/CSS/JS build, material creative iteration, or a creative acceptance decision.
---

# SiteAgent Web Studio

Read the project brain before starting, especially `VISION.md`,
`QUALITY_BAR.md`, `HUMAN_FEEDBACK.md`, and `REFERENCE_LIBRARY.md`.

Treat the business, evidence, available media, and approved page scope as the
brief. Do not use a category template.

The control plane supplies facts, prohibited claims, output paths, scope, and
quality contracts. The creative plane owns concept, narrative, page
composition, art direction, HTML/CSS/JS, and revision.

## Required inputs

Read the approved Studio input package. Do not read `.env`, credentials,
Telegram payloads, or unrelated run data.

Before concepts, confirm:

- exact product/service identity;
- allowed page scope: full site, intentional micro-site, or blocked;
- verified language;
- distinct content themes;
- usable media and media/claim consistency;
- conversion goal;
- prohibited claims.

If the product cannot be identified, stop. Do not hide uncertainty behind
abstract `experience`, `premium`, `unique`, or `unforgettable` copy.

## Required guidance

Apply project-local frontend design, UI/UX, storytelling, conversion copy, media,
responsive, accessibility, anti-template, and reference-library guidance.
Record paths/checksums in provenance.

## Concept workflow

1. Inspect evidence, scope, media, audience, and references.
2. Build materially different real HTML concepts. For a full Level A site,
   create three; for an approved sparse micro-site, follow the configured scope.
3. Concepts must differ in central idea, composition, hero, density, media,
   typography, CTA treatment, and signature element—not only color or text.
4. Render desktop and mobile screenshots before selection.
5. Compare commercial clarity, brand fit, originality, media usage, mobile
   quality, and similarity to prior work.
6. Select with screenshot evidence and list mandatory improvements.
7. Expand the selected idea without replacing it with a generic template.
8. Review and materially revise weak composition, copy, media, or conversion.

## Content rules

- The first meaningful desktop and mobile viewport identifies the offer and CTA.
- Every section adds a distinct useful meaning.
- Current-detail caveats appear once and never become the narrative.
- Do not create filler sections for visual rhythm.
- Do not invent prices, proof, staff, reviews, routes, menus, guarantees, or services.
- If evidence supports only a short page, build a strong short page.

## Design rules

Avoid generic AI landing aesthetics, universal narrow columns, anonymous
rounded-card grids, decorative gradients, repeated dark CTA footers, generic
luxury/editorial styling without brand evidence, and category-selected layouts.

Use media deliberately. Do not destroy the only useful image with excessive
overlays or make visual claims the media contradicts. Every asset must retain
one canonical provenance type: `user_provided_business_asset`,
`verified_official_business_asset`, `licensed_stock_asset`,
`ai_generated_original`, or `reference_only`. Never render `reference_only`.

Missing real business photos do not block an isolated preview. Follow the
checksum-bound media plan and use original generated visuals for atmosphere,
service visualization, object/lifestyle scenes, abstract compositions,
textures, decoration, or illustration. Mark every rendered generated media
element with `data-media-provenance="ai_generated_original"` and its approved
`data-media-claim-role`. Never portray generated media as real staff, a named
professional or owner, the actual premises or company work, a before/after
case, review, certificate, award, document, client record, or result evidence.
Omit or neutrally reframe an evidence section when real evidence is absent.

References are principles to transform, not layouts to copy.

Treat the functional site shell as a gate, not a visual template:

- keep primary navigation available while a scrollable page moves; use a
  sticky/fixed header unless a one-screen scope records an explicit equivalent;
- provide a semantic footer with navigation appropriate to the declared IA, a
  primary conversion action, and only verified social/contact routes;
- keep primary CTA text fully visible inside its clickable box in default,
  hover, focus and active states, with at least a 44×44 CSS-pixel target;
- offset sticky in-page controls below the persistent header.

Color, shape, column count and footer composition remain concept-specific.

## Completion

Leave valid static files in the required workspace. The control plane validates,
fingerprints, promotes, publishes, and delivers. Do not invoke Telegram,
Cloudflare, git push, or legacy Jinja yourself.

Do not approve the result without screenshot-led commercial, UX, copy, media,
responsive, accessibility, technical, and anti-template review. Browser QA must
scroll-test the header, inspect the complete footer, and check primary CTA text
geometry on desktop, tablet and mobile for every declared page.

For isolated one-link previews, source public business facts from the bounded
research ledger and keep exact numeric language exact. Media is usable only
when its canonical provenance and target rights allow it; a supplied logo is
an authorised business asset, while unlicensed research imagery remains
`reference_only`. Do not turn source/provenance notes into customer-facing
copy; communicate the verified fact naturally and leave missing confirmations
in the production-blocker artifact.
