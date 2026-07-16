# Durable Human Feedback

This file records reusable lessons from manual reviews. Add new lessons; do not
rewrite history to make previous failures look successful.

## Repository integrity follow-up

- `.agents/skills` remains the creative-skill source of truth. Any plugin mirror
  update must be synchronized from it; checksum validation must remain strict.
- Workflow-document semantic checks must normalize Markdown whitespace before
  asserting prose phrases, while retaining the underlying production-contract
  assertion.

## Infrastructure lessons

- Telegram → local Codex → Cloudflare → Telegram works and must not regress.
- Production cannot return `file://`.
- Recovery must reuse valid artifacts and avoid duplicate deployment or delivery.

## Template-generation rejection

The first quality pipeline produced restaurant, dental, decorator, and school
fixtures that were structurally different in metadata but visually the same
template. Changing section names, colors, CTA text, or order is not bespoke
design.

Lesson: deterministic composition and category-to-layout mapping cannot own the
creative build.

## Night Yacht calibration v1 rejection

The `Evening field notes / Night, Noted` result was visually distinctive but
commercially weak. It repeated instructions to ask in Direct, buried the offer,
darkened the only image, used dead desktop space, and behaved like an editorial
exercise.

Lesson: creative concept must serve the business. Art direction cannot replace
product, desire, proof, and conversion.

## Night Yacht calibration v2 rejection

The brighter redesign improved composition and CTA placement but remained a thin
three-section page built from one repeated idea. `Private evening water
experiences` did not identify the actual product. `Private / Evening / Water`
was filler. Daylight media conflicted with evening positioning. The site still
looked like a generic editorial luxury system.

Lesson:

- Do not build a full site from insufficient evidence.
- Identify the exact product before concepts.
- Select micro-site scope or block the job.
- Do not treat Instagram caveats as content.
- Generic aesthetic polish is not brand fit.
- The first mobile viewport must include the offer and CTA.
- Human rejection overrides internal scores and must create regression coverage.

## Readiness-gate follow-up (2026-07-15)

- A business name, broad niche, one atmospheric offer, one image, and a chosen
  language are not enough for a full SiteAgent page. Night Yacht is insufficient
  evidence, not a micro-site: it lacks an exact product, confirmed language,
  sourced content themes, and media fit.
- Full-site readiness now requires a sourced exact product, confirmed language,
  at least three distinct sourced themes, and five to eight deduplicated usable
  media assets. Sparse but identified evidence may only receive a concise
  micro-site; anything weaker blocks before Studio work.
- The Botanika Form controlled fixture establishes the next calibration bar:
  Ukrainian event floristry, four sourced themes, six media, product/CTA in the
  first viewport, materially distinct A/B/C concepts, and an independent
  screenshot-led acceptance. Its remaining mobile media-pause note is medium
  and non-blocking.

## Working preference

The user wants the main Codex agent to act as a demanding Project Director:
remember the product goal, inspect what subagents actually made, criticize weak
results, order material rework, and persist lessons so the user does not have to
repeat the same brief in every chat.
