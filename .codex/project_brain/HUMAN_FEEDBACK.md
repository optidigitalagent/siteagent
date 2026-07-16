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

## Manual-workflow rebuild recovery (2026-07-16)

- A recovered architectural skeleton is not evidence that the manual-equivalent
  workflow exists. Before calibrations, require screenshot-led reference analysis,
  trait-based cross-category retrieval, auditable non-destructive Instagram media
  preparation, readable research/design handoffs, and role/prompt provenance.
- Never treat catalog order, DOM headings, or generic placeholder analysis as a
  creative reference decision. Individual reference failures are recoverable; they
  must not silently lower the standard for successful records.

## Botanika Form calibration follow-up (2026-07-16)

- An approved commercial or art-direction report may never retain a failed check
  whose own recommendation says it must be resolved before promotion. Commercial
  signals must work for the verified page language and evidence-backed value
  language, and a failed required signal blocks calibration approval.
- Calibration comparisons must contain native, separately inspectable desktop
  and mobile viewport/full-page captures. A full-page board must be at least
  1800px wide and must not use unwrapped report text that causes hidden overflow.
- Fixture or stock imagery must be declared per asset, tied to the final HTML
  checksum with used/not-used status, and visibly disclosed. It is never business
  portfolio proof and blocks production reuse until rights and authorised
  business-media provenance exist.

## Botanika Form human calibration decision (2026-07-16)

- The human calibration record approves Botanika Form Concept C and passes the
  creative-quality calibration only. This decision preserves the concept and its
  calibration artifacts; it is not production approval.
- Every displayed Botanika Form portfolio/media asset is controlled fixture or
  stock material, not verified Botanika Form work. Production promotion must
  deterministically remain blocked while any selected/rendered asset has
  `fixture_stock` or `stock` provenance, even if the global human-calibration
  gate is later cleared.
- The fixture-only disclosure belongs solely to calibration evidence. A valid
  production build must reject fixture media rather than removing or hiding that
  warning, and must not contain calibration-only footer/disclosure text.
- Keep `CREATIVE_STUDIO_HUMAN_CALIBRATION_REQUIRED=true` globally. Human approval
  of one fixture never authorises a production rollout or publication.

## Reference importer crash-recovery lesson (2026-07-16)

- A browser/driver cleanup error must never be allowed to discard saved screenshot work or
  suppress catalog finalization. Resume logic must distinguish a checksum-valid completed
  analysis, a captured record needing analysis only, and a capture failure needing a fresh
  browser.
- Screenshot-analysis output needs a strict complete schema, Pydantic validation, bounded
  repair, and safely retained raw responses. A model choosing its own field names is a
  failed analysis, never a reason to invent empty values or mark a record complete.

## Autonomous reference-library decision (2026-07-16)

- Routine reference selection, traits, curation, exclusion, screenshot review and crash recovery
  are agent-owned. A manual review/export file is not a production gate and accidental clicks
  must be marked machine-readable invalid, never interpreted as latent preference.
- Award galleries introduce candidates only. Selection requires a resolved original live site,
  screenshot evidence, Curator/Auditor agreement, bounded learning scope for incomplete pages,
  duplicate suppression and an active-library decision separate from raw records.
