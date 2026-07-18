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

## Authorised business-media calibration (2026-07-17)

- The user explicitly authorises proven Orange Beauty Studio and Bella Dent Clinic business media for public-site use only when the asset-to-business link is documented. Such assets may be recorded as `source_kind=business`, `user_authorized=true`, and `allowed_for_public_site=true`.
- This approval never extends to stock, fixture, reference captures, third-party portfolios, or an asset whose business linkage cannot be proven. Existing business-site code is media-origin evidence only; it is not design, layout, copy, or structure input.
- A Level B micro-site must be reviewed against its configured limit (one concept, at most three semantic sections and two image treatments). Critics must not demand a full-site gallery as a condition of approval; instead they must assess whether the bounded proof and conversion path are commercially sufficient.

## Bella Level B critic calibration (2026-07-17)

- A critic must not downgrade a compliant Level B micro-site into a “thin redirect” merely because verified evidence lacks a direct contact method, clinical process, prices, outcomes, or a fuller decision path. Those missing facts are a reason to keep the product compact, not material to invent.
- An explicit CTA that names the visitor's consultation intent and transparently opens the verified official site is a valid conversion path when no verified direct route exists. High-severity findings need a concrete scope, evidence, copy, visual, or technical failure; scope-correct concision is not one.

## Full-site product audit rejection (2026-07-18)

- Orange Beauty Studio and Bella Dent Clinic were technically stable but rejected as commercial websites. Their old 89/100 and 100/100 results measured compliance with an invalid, evidence-shrunk micro-site scope and are not product readiness.
- A normal business request defaults to a full commercial website. Evidence controls allowed claims and can block with an exact missing-content manifest; it must never silently change the ordered product into a micro-site. Micro-sites are only for explicit campaign, teaser, event, link-in-bio or narrow lead-magnet requests.
- Full-site acceptance requires a complete customer journey: identity/value, services, proof, brand/about, trust/process, commercial decision, evidence-backed objection handling and final conversion. Three semantic sections, a redirect, repeated CTA or clean technical report cannot compensate for missing coverage.
- Acceptance needs an independent Product Director who sees the request, research, final site/screenshots and media provenance but not internal critic scores or scope-shrink rationale. The human gate remains enabled until a golden result is visually and product-wise approved.

## Golden calibration integrity and recovery (2026-07-18)

- A manual baseline for the same business must be excluded not only from the
  builder prompt but also from reference discovery, selected references, design
  inputs, implementation packages, and critic context until after the final
  site bytes are fixed. A post-build comparison cannot retroactively make a
  contaminated run blind.
- Recovery must preserve complete, checksum-clean work, but every reusable
  critic/review must be bound to the full authored HTML/CSS/JS tree. An
  `index.html`-only checksum is insufficient because CSS or secondary-page
  changes can materially alter the product.
- Multi-page Product Director acceptance must verify the requested page set,
  navigation, language controls, portfolio behavior, and conversion form, not
  infer a complete product from the home page alone.

## Eliz human product audit and preview contract (2026-07-18)

- The user accepts Eliz de Fleur Concept C as a high-quality full commercial
  website with limited revisions. Preserve its design, CTA system and complete
  Portfolio; the only required visual correction is clearer header/footer
  navigation typography without weakening the editorial language.
- A successful human-audit candidate must be delivered as an isolated public
  preview URL. Preview is not customer production: use a separate project/run
  identity, `noindex,nofollow` in HTML and response headers, authorised media
  only, no custom domain, no Telegram production delivery and no mutation of
  the customer production project.
- A preview form may use an honest `copy_to_clipboard`, `mailto`, Instagram,
  Telegram or visual-demo fallback. It must never claim backend delivery that
  did not occur, and the reported `form_mode` is part of the handoff.
- Creative/demo copy is allowed when provenance distinguishes verified facts,
  inferred brand copy, generated demo content and missing required facts.
  Numeric prices, staff, licences, reviews, guarantees, addresses and similar
  factual claims remain blocked unless verified. Factual demo placeholders
  block production until confirmed, replaced or safely reframed.
- Plan a separate future `SiteRevisionAgent` for edits to an existing project:
  preserve its design system and business context, publish a new preview after
  QA, and update production only after explicit approval. Do not merge it into
  the new-site generation path.
