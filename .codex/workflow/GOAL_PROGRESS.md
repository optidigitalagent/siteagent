# Goal Progress

## Explicit go: Amidental production input gate (2026-07-19)

- Executed `python -m site_agent.cli go` from the user's explicit command. The
  CLI claimed the newer pending job `053656c35b5d4ef58221c5be7171b625` and
  persisted its Research Strategist artifacts and checkpoints.
- The run stopped fail-closed at `media_input_blocked`: no production-authorised
  media manifest exists, and research records the production scope as blocked
  pending confirmed identity, offer, language/location, contacts and conversion
  facts. The queue item is `failed` with the resumable run directory preserved.
- No site output, Cloudflare production upload, custom-domain mutation or
  Telegram success notification was created. The worktree remained clean after
  the CLI invocation.
- The prior Amidental run `f684eed531f74dd8995b2a58ac77739e` remains
  `preview_ready`; its verified noindex preview and 11 preview-only media assets
  were not changed or promoted to production rights.
- Recovery must reuse the failed job/run after explicit confirmation of current
  contact/business facts, production CTA/copy and production media rights. It
  must not enqueue a third copy or infer production authorisation from the
  existing preview.
- Independent read-only verification found a pre-existing high durability
  inconsistency: the older job remains `preview_ready`, and its exact run,
  verified deployment artifact and live noindex URL are intact, but its
  queue-level `preview_url`, `run_dir`, checkpoints and recovery events are
  empty. This invocation did not redeploy or mutate those preview artifacts.
  Queue metadata must be repaired only from the verified existing run and
  covered by a recovery regression before production work resumes.

## Autonomous reference-discovery migration (2026-07-16)

- Invalidated `references/site_designs/human_review/human_review_decisions.json` as accidental
  historical input. The diagnostic page no longer exports decisions and the active workflow no
  longer has a human reference-review checkpoint.
- Added `ReferenceDiscoveryAgent`, award-gallery adapters, original-live URL resolution,
  screenshot completeness/blank/404/redirect validation, bounded learning scope, Curator/Auditor
  decisions, visual near-duplicate suppression, separate active/excluded decisions and
  active-only integrity-checked selection.
- Refreshed from Awwwards through read-only local browser capture and screenshot analysis. The
  catalog now records 32 active high-confidence references and eight excluded records; Orange's
  broken redirect capture and the Kirkovsky GitHub Pages 404 are excluded automatically.
- No `go`, Telegram, Cloudflare, publishing or calibration run occurred. Orange Beauty Studio and
  Bella Dent Clinic remain blocked pending source research, authorised business-media manifests
  and Cloudinary configuration; reference assets cannot substitute for those inputs.

## Integrity Follow-up (2026-07-15)

- Re-synchronized the optional `siteagent-web-studio` plugin mirror from the
  repository-owned `.agents/skills` source without changing production skill
  resolution or checksum validation.
- Made the Global Goal contract test whitespace-normalized so Markdown wrapping
  cannot hide the current Codex Creative Studio production contract, while
  preserving its assertion against the legacy deterministic build wording.

## Structural Composition Remediation (2026-07-15)

- Replaced the fixed renderer content sequence with validated `PageComposition` and typed `SectionPlan` artifacts.
- Added purpose-driven journey compositions for experience, trust/service, portfolio, learning/outcome, and intentional sparse editorial pages.
- Persisted `design/page_composition.json` and `generation_reports/build_manifest.json`; legacy builder callers receive an inferred validated composition.
- Rebuilt fixture E2E evidence, structural audit, similarity breakdowns, score breakdowns, and local fixture comparison page/screenshot.
- Confirmed restaurant, dental, decorator, and school have different section sequences, hero types, closing patterns, and journey patterns; Level B passes, Level C does not start builder, and the yacht placeholder remains blocked.
- Verified full unittest discovery (57 passed, 1 opt-in Cloudflare smoke skipped), fixture E2E, compileall, pip check, smoke build, and diff check. No Telegram job, Cloudflare publish, live production verification, or Telegram delivery was performed.

- Added Telegram queue design for URL handoff.
- Added CLI `go` / `го` command contract.
- Added Railway/Docker deployment files.
- Linked Railway project `website-agent` and created service `website-agent`.
- Set non-secret Railway runtime variables for queue/git sync and runtime behavior.
- Added `.codex/workflow` project memory.
- Added `.codex/skills` role instructions for website development and QA.
- Verified `python -m compileall site_agent scripts`.
- Verified `python scripts/smoke_build.py`.
- Verified `python -m site_agent.cli go` with no pending jobs.
- Verified queue enqueue/claim/complete smoke test on a temporary JSON file.
- Verified Playwright technical gate on smoke site.

Live end-to-end verification requires local runtime credentials:

- `TELEGRAM_BOT_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`
- `OPENAI_API_KEY` only when `LLM_PROVIDER=openai`

## Cloudflare Pages Production Publishing

- Audited the actual `go` path: `site_agent.cli.run_pending_job` ->
  `SiteAgentOrchestrator.run` -> `Publisher.publish` -> queue completion ->
  `TelegramNotifier.send_done`.
- Confirmed the root cause of the local URL: `Publisher.publish` intentionally returns
  `site/index.html` as a `file://` URI whenever `PUBLISH_REMOTE_URL` is empty.
- Confirmed there was no separate acceptance-audit implementation and no publisher test
  suite; final critic approval currently calls publish directly.
- Confirmed local Node.js, npm, and npx are installed. Cloudflare account credentials are
  not configured, so a real deployment remains conditional on local credential setup.
- Implemented `CloudflarePagesPublisher` behind the existing `Publisher` entry point,
  preserving explicit `local` preview and deprecated explicit `git` provider paths.
- Added deterministic normalized-Instagram project naming, marker-based ownership checks,
  preflight file protection, non-interactive pinned `wrangler@4`, structured deployment
  metadata, bounded live retries, and success-only Telegram delivery.
- Verified `python -m unittest discover -s tests -v`: 33 passed, 1 credential-gated smoke skipped.
- Verified `python -m compileall -q site_agent scripts tests`, `python -m pip check`,
  `python scripts/smoke_build.py`, and `npx --yes wrangler@4 --version` (`4.110.0`).
- Verified `.env.railway.example` contains no Cloudflare account/token variables and
  `git diff --check` passes.
- No `.env` exists in this workspace, so a live Cloudflare deployment, public URL,
  and remote desktop/mobile inspection could not be performed.

## Cloudflare Pages Smoke Deployment (2026-07-14)

- Local `.env` now provides the required Cloudflare account and API token values; their
  values were not printed or written to workflow state.
- The first opt-in smoke run exposed a Wrangler 4.110.0 compatibility issue:
  `WRANGLER_LOG=none` suppresses successful `--json` output, so project listing parsing
  failed before upload. Removed that log-level override while retaining disabled metrics
  and error reporting; the focused publisher suite passes (30 tests).
- Ran `$env:RUN_CLOUDFLARE_SMOKE='1'; python -m unittest tests.test_cloudflare_smoke -v`:
  Cloudflare Direct Upload, stable HTTPS HTML/marker verification, and completion all
  passed. Stable URL: https://siteagent-smoke-siteagent-cloudflare-smo-0fee21e595.pages.dev
- `python -m unittest discover -s tests -v` passes: 32 tests passed, 1 credential-gated
  smoke skipped because the opt-in environment flag was intentionally absent for that
  regression run. `python -m compileall -q site_agent tests` and `git diff --check` pass.
- Attempted the required desktop/mobile browser inspection. The browser-control runtime
  failed before opening a tab with `Cannot redefine property: process`; this is an
  environment integration issue, not a Pages response failure. Visual viewport evidence
  remains pending, while programmatic live HTML verification has passed.

## Remote Visual Verification (2026-07-14)

- Confirmed the `Cannot redefine property: process` failure is confined to Codex's
  embedded browser runtime: the project's installed Playwright Chromium opened the
  public Pages HTTPS URL successfully.
- Extended the existing `TechnicalInspector` with `inspect_url`, using the same
  desktop/mobile technical gate for a remote URL and recording console errors, failed
  network requests, observations, and screenshots in the artifacts directory.
- Inspected `https://siteagent-smoke-siteagent-cloudflare-smo-0fee21e595.pages.dev`:
  HTTP/HTTPS navigation and network-idle completed; console errors, failed requests,
  missing images, broken links, small tap targets, and horizontal overflow were all empty.
  Artifacts: `runs/smoke/technical_gate/{desktop.png,mobile.png,technical_gate.json,observations.json}`.
- Visual inspection also confirmed this URL is the intentionally minimal Cloudflare smoke
  fixture, not a generated business site. It cannot satisfy the Telegram production E2E
  acceptance criteria.
- The Telegram queue has no `pending` item. Its only historical item is `done` with an
  old local `file://` result, so `python -m site_agent.cli go` was not run and no Telegram
  success message was sent in this verification pass. A new Instagram URL must be sent to
  the Telegram bot before real business E2E and real-project idempotency can proceed.
- Regression evidence: `python -m unittest discover -s tests -v` -> 33 passed, 1 opt-in
  Cloudflare smoke skipped; `python -m compileall -q site_agent scripts tests`,
  `python -m pip check`, `python scripts/smoke_build.py`, and `git diff --check` passed.
- Attempting `python -m site_agent.cli go` did not claim anything: because a Git remote
  exists, the queue performs `git pull --rebase` before its pending check, and Git refused
  to pull over the pre-existing uncommitted worktree changes. No queue state changed and no
  Telegram message was sent. Do not stash, discard, or commit those user-owned changes as
  part of verification.

## Interrupted Telegram Job Recovery Audit (2026-07-14)

- Audited queue job `d8176c55f451439cacf0e8a892ca97e7` for
  `https://www.instagram.com/jet_yacht_rest_kyiv?igsh=OGw2cGpsZHZjeHh1` without running
  `go`, claiming another job, regenerating the site, or uploading a replacement deployment.
- Reused the latest matching run
  `runs/20260714-074208-jet_yacht_rest_kyiv-igsh-OGw2cGpsZHZjeHh` and verified its valid
  research, strategy, SiteSpec, single critic/technical gate (91), acceptance audit, and
  Cloudflare deployment metadata. Local and remote Playwright gates passed at 1440x1100 and
  390x844 with no console/network errors, failed assets, broken links, small controls, or
  horizontal overflow. The stable Pages URL returned HTTPS 200 and the expected Instagram
  marker with no local URLs or paths.
- The only unrecoverable legacy boundary is Telegram receipt state: the prior CLI marked the
  queue `done` before invoking `send_done`, and it stored no message id/notification receipt.
  Therefore the legacy job's final Telegram success delivery is `unknown`; no resend was made
  because it could duplicate a customer message. Full evidence is in the run's
  `recovery_audit.json`.
- Added durable queue checkpoints, persisted run directories, interrupted-job selection ahead
  of pending jobs, legacy run discovery, safe artifact reuse, and an at-most-once Telegram
  notification state. A crash during Telegram delivery now leaves the job non-complete and
  explicitly blocks automatic resend rather than silently duplicating delivery.

## Authorized Legacy Telegram Resend Attempt (2026-07-14)

- The user confirmed that the legacy final Telegram message was not received and explicitly
  authorized one resend for `d8176c55f451439cacf0e8a892ca97e7`.
- The manual recovery command performed a fresh HTTPS 200 + expected business-marker check on
  `https://siteagent-jet-yacht-rest-kyiv-8e3e8f93c6.pages.dev` without running research,
  generation, critic, acceptance, or Cloudflare deployment.
- Before a Telegram API request could be made, the notifier failed with the exact controlled
  error `Telegram success requires TELEGRAM_BOT_TOKEN.` The queue is `retryable` with
  notification state `unknown`, no receipt, and the recorded manual authorization timestamp.
  No Telegram success message was sent and the deployed site was not changed.

## Creative Studio Migration (2026-07-15)

- Audited the template boundary: `compose_page()` creates `PageComposition/SectionPlan` before
  `SiteBuilder` renders `site.html.j2`, so the former path owns composition rather than Codex.
- Added repository-owned Web Studio and review skills under `.agents/skills/`, plus the optional
  validated `plugins/siteagent-web-studio` IDE mirror and stale-bundle checksum validation.
- Added `SITE_BUILDER=codex_studio` default, isolated `runs/<job>/studio` inputs/concepts/reviews,
  screenshot-first selection, atomic site promotion, Studio provenance, Art Director review and
  a calibration flag that blocks production rollout. Jinja is explicit `legacy_template` only.
- Deterministic Studio tests, full unittest discovery, compilation, pip check, skill/plugin
  validation and the legacy smoke build pass. The real four-business Codex fixture suite is
  opt-in through `CODEX_CREATIVE_E2E=1` and has not yet been visually approved.

## Night Yacht Crash Recovery (2026-07-15)

- Recovered the existing `runs/creative-studio-e2e/night_yacht` workspace without running
  Telegram, Cloudflare, other fixtures, the legacy Jinja renderer, or a new concept generation.
- Confirmed Concept B, `Evening field notes`, was the recorded selection and reused the existing
  A/B/C screenshots, comparison, selection rationale, selected source and initial final evidence.
- The only interrupted stage was the existing creative-fixer promotion: its revised static files
  were intact in `studio/selected/staging`, while the old history recorded an ACL blocker. The
  source was readable after restart, so the staged revision was atomically promoted to both
  `studio/selected/source` and `site`; metadata is in `studio/atomic_promotion.json`.
- Re-rendered desktop (1440x1100), tablet (768x1024), and mobile (390x844); the technical gate
  passed without console/network errors, broken links, missing images, small tap targets, or
  horizontal overflow. The follow-up Art Director review approved the fixed output at 90/100 with
  no critical/high findings. The sole unresolved medium issue is the supplied daylit yacht image's
  residual daylight read.
- Refreshed genuine fixer before/after evidence, the human calibration HTML/PNG package, and ran
  `python -m site_agent.creative_fixture_e2e --resume night_yacht`; it returned
  `completed_human_calibration_required` without another fixer iteration.
- Verified `python -m unittest discover -s tests -v` (64 passed, 1 opt-in Cloudflare smoke
  skipped), `python -m compileall -q site_agent scripts tests`, `python -m pip check`,
  `python scripts/smoke_build.py`, and `git diff --check`.

## Product Readiness and Botanika Form Calibration (2026-07-15)

- Added product identity, confirmed-language, sourced-theme, usable-media, and page-scope gates.
  Full scope now requires an exact sourced product, confirmed language, at least three distinct
  sourced themes, and five to eight deduplicated media assets. Micro scope is concise by
  contract; insufficient evidence blocks before Studio generation.
- Reclassified the rejected Night Yacht fixture as blocked/insufficient evidence. It has no
  exact product, language evidence, sourced themes, or adequate media, so it cannot create a
  replacement long page.
- Added the rich controlled `botanika_form` fixture: Ukrainian event floristry for weddings,
  private dinners, and branded events, with four sourced themes and six verified media URLs.
  All six URLs returned image responses during fixture preparation.
- Created and rendered materially different A/B/C concepts. Rejected A for tablet overflow and
  repeated editorial cadence, and B for a wedding-biased/operational read. Selected C,
  `Форма події`, for its clear product path, botanical collage, circular flower-mark and
  equal Roman-numeral treatment of all three formats.
- The first full-build child process timed out after concepts/selection without writing staging;
  its known child process was stopped and the selected concept was materially implemented in a
  separate staged build. The final revision enlarged CTA targets, controlled tablet collage
  collisions, preserved the selected signatures, and was promoted atomically to `site/`.
- Main-agent and independent screenshot review approved the final for human calibration: no
  critical/high issues; technical gate passes desktop/tablet/mobile with no overflow, failed
  assets, console/network errors, broken links, or small targets. One medium mobile media-pause
  rhythm note remains, recorded in `studio/art_director_report.json`.
- Generated the human-calibration comparison package under
  `runs/creative-studio-e2e/botanika_form/calibration/`. The fixture reports
  `completed_human_calibration_required`; no `go`, Telegram, Cloudflare, or deployment action
  was run. `CREATIVE_STUDIO_HUMAN_CALIBRATION_REQUIRED` remains true.
- Regression evidence: `python -m unittest discover -s tests -v` -> 80 passed, 1 opt-in
  Cloudflare smoke skipped; `python -m compileall -q site_agent scripts tests`,
  `python -m pip check`, `python scripts/smoke_build.py`, and `git diff --check` pass.

## Crash-Recovery Audit and Checkpoint Handoff (2026-07-16)

- Recovered from the workstation interruption without regenerating concepts, HTML, screenshots,
  reports, deployments, or Telegram delivery. `191ad4a` matched `origin/main`; there was no
  merge, rebase, lock, staged change, or untracked work. The coherent saved implementation was
  validated and pushed as `a6268cf`.
- Reused the Botanika Form final evidence directly: selected/staged/promoted HTML is byte-identical,
  final desktop/tablet/mobile technical evidence is clean, and the independent review has no
  critical or high finding. The active gate remains explicit human calibration only.
- Current pre-rollout follow-ups: do not treat the all-completed Studio task ledger as release
  authorization; human calibration remains external and blocking. Reconcile the historical
  `desire_created: false` versus approved-95 commercial report and the historical skill-provenance
  checksum mismatches before relying on either as a clean machine-enforced production signal.
- Fresh regression evidence: `python -m unittest discover -s tests -v` -> 81 passed, 1 opt-in
  Cloudflare smoke skipped; `python -m compileall -q site_agent scripts tests`, `python -m pip
  check`, `python scripts/smoke_build.py`, and `git diff --check` passed.

## Botanika Form approved-with-fixes calibration (2026-07-16)

- Preserved selected Concept C and revised only its promoted/source/staging full build:
  the first desktop and mobile viewport now explicitly names event floristry and
  decoration for weddings, private dinners and branded events, with the existing
  Direct CTA. The mobile material sequence is now one image paired directly with
  its explanation; the Concept C collage, flower-mark and three-format manifesto remain.
- Corrected accessibility and interaction defects found by independent review:
  manifesto text contrast is 5.66:1, the hero large-text contrast is 3.30:1,
  the tablet footer stacks intentionally, and the skip link moves keyboard focus
  to `main#main`.
- Fixed the commercial-report contradiction: `desire_created` now supports
  Ukrainian and evidence-backed value language, is required for approval, and
  is enforced again by art-direction calibration. The revised report is 100/100
  with no failed checks; historical skill snapshots were regenerated from the
  repository-owned skill source and plugin mirror validation passes.
- Added explicit per-asset fixture-stock provenance, truthful alt text, a final
  HTML SHA-256 used/not-used media report, visible non-portfolio disclosure, and
  a production-media block. The final uses four classified fixture-stock assets;
  two classified assets are not used.
- Regenerated the final human-calibration package: native `1440x1100` desktop,
  desktop full-page, `390x844` mobile, mobile full-page, and a no-overflow
  `1920x21788` comparison PNG. Independent Commercial/Copy/Media, Art/UX,
  Responsive, Accessibility and Technical reviews report no critical or high
  issue. Production remains blocked by the human calibration gate and fixture
  media provenance; no `go`, Telegram or Cloudflare action ran.
- Regression evidence: `python -m unittest discover -s tests -v` -> 84 passed,
  1 opt-in Cloudflare smoke skipped; `compileall`, `pip check`, `smoke_build`,
  and `git diff --check` passed.

## Botanika approval and Harbour Dental calibration (2026-07-16)

- Recorded the human decision for Botanika Form Concept C: `approved` human
  calibration and `passed` creative-quality calibration, but `production_ready:
  false`. All displayed Botanika media is fixture/stock reference material rather
  than verified Botanika Form work. The dedicated calibration metadata, project
  brain and workflow state preserve this distinction; the global human-calibration
  gate remains enabled.
- Hardened Studio promotion: rendered `fixture_stock`, `stock`, or `unknown`
  media fails closed from the normal orchestration path, delivery recovery, and
  direct publisher facade. The provenance report is bound to the final HTML hash;
  removal of a visible warning does not permit fixture media through, while any
  calibration-only footer/disclosure blocks an otherwise production-safe build.
- Added the controlled English `harbour_dental` full-site fixture: consultation-led
  adult dental care with routine hygiene, restorative planning and urgent
  consultation routes; decision-support proof; six classified fixture-stock media
  assets; and a Direct consultation CTA. It does not reuse Botanika’s floral
  editorial composition, palette, hero, collage, CTA, rhythm or signature.
- Created and screenshot-reviewed three materially different dental concepts.
  Independent criticism rejected B for tablet overflow and C for tablet/mobile
  breakdown; selected Concept A’s cobalt/graphite wayfinding system was materially
  revised after an undersized-control failure. Fresh 1440px, 768px, 390px and
  960px evidence has no overflow, failed media, console/network errors, broken
  links, small tap targets or hero collision. The independent critic approves it
  only for the next human-calibration package.
- Harbour Dental remains production-blocked because three rendered images are
  fixture-stock media. Its local package is under
  `runs/creative-studio-e2e/harbour_dental/calibration/`; no Telegram, Cloudflare
  or `go` action was performed.
- Verification for this change: `python -m unittest discover -s tests -v` ->
  91 passed, 1 opt-in Cloudflare smoke skipped; `python -m compileall -q
  site_agent scripts tests`, `python -m pip check`, `python scripts/smoke_build.py`,
  and `git diff --check` passed.

## Manual workflow rebuild and crash recovery (2026-07-16)

- Crash-recovery audit found `HEAD`, `origin/main`, and the confirmed remote commit
  `a970f25` identical, with no staged work and no merge/rebase/cherry-pick state.
  The sole untracked artifact was the supplied manual-workflow requirements document;
  it was preserved and adopted as the implementation contract.
- Replaced DOM-count/placeholder reference notes with a resumable screenshot-led
  Reference Analyst workflow. Desktop/mobile captures have byte hashes, per-record
  capture/analysis failure state, atomic catalog/checkpoint writes, and provider,
  model, prompt/input/output checksum provenance. Reference selection scores the
  entire analysed catalog using business, audience, level, atmosphere, conversion,
  media, emotion and structure traits, with a category-only cap and per-reference
  rationale.
- Replaced JSON-in-Markdown handoffs with readable cited business research and
  section-level Design Director documents. Research, Design Director and
  implementation-package records now contain role/input/output provenance.
- Hardened media preparation: source originals are retained, Instagram-chrome crop
  candidates expose coordinates/confidence/manual-review state, non-destructive
  contact sheets are produced, raw and prepared checksums dedupe inputs, quality
  and use classification are recorded, and explicitly authorised existing
  Cloudinary assets can be reused without reupload. Final Studio provenance now
  blocks any rendered external media URL missing from the authorised manifest.
- Added focused coverage for screenshot-analysis artifacts/provenance, trait ranking
  without first-six selection, readable Markdown, crop safety, contact sheets and
  authorised existing Cloudinary reuse. Verification: 102 tests passed, one
  credential-gated Cloudflare smoke skipped; `compileall`, `pip check`, smoke build
  and `git diff --check` passed. No `go`, Telegram, Cloudflare deployment, publishing
  or Orange/Bella calibration ran. Stop state: `READY_FOR_CREDENTIALLED_REFERENCE_IMPORT`.

## Reference-library importer recovery (2026-07-16)

- Audited the interrupted import without deleting its records or screenshots. Six captured
  records were resumable analysis failures, one was a capture failure, and no catalog had
  been finalized because browser cleanup could abort the old importer.
- Hardened the importer with bounded browser restart/recovery, cleanup warnings, atomic
  catalog/report finalization from durable records, checksum-aware resume, and a strict
  screenshot-analysis schema with a single validation-repair retry and safe raw-response
  debug artifacts. The code and regression suite were committed and pushed as `d717b46`.
- The resumed import finished all 28 seeds: 25 completed screenshot analyses, 0 analysis
  failures, 3 isolated `networkidle` capture timeouts (Drivepark, Unique Rabbit Studios,
  Webgoalz), and no cleanup warning. All completed capture hashes were revalidated against
  their records. `references/site_designs/import_report.json` reports
  `REFERENCE_LIBRARY_IMPORTED_READY_FOR_HUMAN_REVIEW`.
- No `go`, Telegram, Cloudflare, publishing, Orange Beauty Studio, Bella Dent Clinic, or
  human-calibration-gate action was performed.

## Local human review package (2026-07-16)

- Created a local-only, regenerated human-review package from the already saved reference
  artifacts: `references/site_designs/human_review/index.html`,
  `references/site_designs/human_review/trait_matrix.html`, and a separate seed
  `human_review_decisions.json`. Original imported `reference.json` records and screenshots
  remain immutable inputs; review controls export decisions separately and do not rerun AI
  analysis or access source sites.
- The index exposes the 25 completed analyses, catalog checksum/import date, Reference Analyst
  provenance, exact stored SHA-256 capture-pair recheck, the three resumable 45-second
  `networkidle` capture timeouts, per-record desktop/mobile screenshots and full visual-analysis
  fields, transferable traits, learnings, and non-copy constraints. All package navigation and
  image references are local; source URLs are visible/copyable but not live links.
- The trait matrix uses transparent rule-derived cross-category filters rather than business
  categories. It deliberately shows a horizontally scrollable table only inside its bounded
  matrix container, preserving viewport width on narrow screens.
- Independent artifact/UX review identified and the package visibly flags the Kirkovsky GitHub
  Pages 404, Orange Beauty Studio's blank/unrendered desktop capture, and mobile-file width
  mismatches for Panem, Hollywood 2, Kafe Speka, and Kirkovsky. These are selection safeguards,
  not silently accepted reference quality.
- Verification: `python -m compileall -q scripts/build_reference_human_review.py`, generator
  run plus `--check`, all 50 expected local capture files rehashed against catalog values,
  static local-link/image and secret-pattern checks, and local Playwright desktop/tablet/mobile
  viewport checks of both pages passed with no document horizontal overflow, console errors, or
  failed requests. Inspected desktop/mobile index and mobile trait-matrix screenshots. The
  full-page screenshot helper cannot rasterize this deliberately very tall 25-record board as a
  single bitmap, so viewport screenshot evidence is the applicable browser artifact.
- Stop checkpoint: `HUMAN_REFERENCE_LIBRARY_REVIEW`. No `go`, Telegram, Cloudflare, publishing,
  Orange Beauty Studio, or Bella Dent Clinic action was performed.

## Full-site product correction and Eliz recovery (2026-07-18)

- Preserved Concept C and recovered its material five-page build. Corrected the
  lazy-image and hidden-control inspector false positives, checksum-bounded
  staging recovery, canonical screenshot freshness, full-tree critic
  provenance, Polish language/commercial signals, and fail-closed multi-page
  Product Director coverage.
- Reverified the four reported Cloudinary failures as authorised business JPEGs
  returning HTTP 200 with delivery checksums identical to prepared files. No
  reupload was required. All five pages passed desktop/tablet/mobile technical
  inspection; interaction/accessibility checks covered keyboard focus,
  skip-link, navigation, PL/EN, filters, form errors/result fallback, reduced
  motion, and core AA contrast.
- Independent baseline review found and then re-approved a fixed tablet Services
  composition. Fresh critic 89, Art Director 89, Product Director 100, and
  acceptance 89 are approved with no critical/high issue. The final site is
  materially stronger than the manual one-page baseline in completeness, IA,
  media use, portfolio depth, mobile journey, and conversion.
- Verification: 47 focused tests passed; full suite 141 passed with one
  credential-gated Cloudflare smoke skipped; compileall, pip check, smoke build,
  diff check, and secret checks complete at final handoff.
- Calibration-integrity disclosure: the same-business manual baseline was
  present in selected reference/design inputs. The recovered product is ready
  for human quality audit but cannot be represented as a clean blind benchmark.
  A new isolated run is required if strict blindness is mandatory.
- Stop checkpoint: `AUTONOMOUS_FULL_SITE_AGENT_READY_FOR_HUMAN_AUDIT`. No `go`,
  Telegram, Cloudflare, or customer deployment ran; the human gate remains on.

## Eliz human-audit preview (2026-07-18)

- Recorded the human decision that Concept C passes product-quality calibration
  with limited revisions; strict-blind calibration is deferred and customer
  production remains unapproved.
- Preserved the full five-page design, CTA system and all 24 Portfolio items.
  Increased only navigation typography: header/menu labels are at least 14.4px,
  PL/EN and footer links 14px, footer metadata 12px. Existing rose+underline
  active state, visible 3px keyboard focus and 44px targets remain intact.
- Fresh local and live technical QA passed Home, Services, Portfolio, About and
  Contact at 1440×1100, 768×1024 and 390×844 with no overflow, missing media,
  broken links, failed requests, console errors or undersized targets. Live
  PL/EN, navigation, focus, filters 24/3/7/12/2 and the honest form fallback
  passed.
- Published only the dedicated Cloudflare `Preview` environment at
  `https://eb4d89cf.siteagent-preview-eliz-de-fleur-769afda793.pages.dev`.
  All five pages return HTTP 200 after redirects and expose `noindex,nofollow`
  through both robots meta and `X-Robots-Tag`.
- No production `go`, Telegram delivery, customer production deployment or
  custom-domain action ran. Stop checkpoint:
  `ELIZ_PREVIEW_READY_FOR_USER_REVIEW`.
- Independent post-fix acceptance passed with no critical/high issue. The full
  regression suite also remains green: 141 tests passed and one
  credential-gated Cloudflare production smoke was skipped.

## Eliz functional-shell revision preview (2026-07-18)

- Preserved the selected Concept C composition, copy system, media and all 24
  Portfolio items. Added a sticky header on every page, a full five-link footer
  with verified Instagram and enquiry action, and repaired the home-page
  enquiry CTA so its text is no longer compressed by the decorative-dot rule.
- Promoted the lesson into durable SiteAgent contracts: generation prompts,
  technical inspection, multi-page Product Director acceptance, quality bar,
  workflow scenarios/risks/decisions, relevant creative/review skills and
  regression tests now require a persistent navigation shell, useful footer
  and intact primary CTA without prescribing composition.
- Local and live Chromium QA passed Home, Services, Portfolio, About and Contact
  at 1440×1100, 768×1024 and 390×844. PL/EN, mobile menus, cross-page footer
  navigation, Portfolio filters `24/3/7/12/2`, invalid form focus and prepared
  enquiry output passed. Every live page returns 200 with both robots meta and
  `X-Robots-Tag: noindex, nofollow`.
- Independent revision review: `ACCEPT`, with no critical/high/medium/low issue
  requiring revision. Revision Product Director: 100/100. Full suite: 144
  passed, one credential-gated production smoke skipped; compileall, pip check,
  smoke build and diff check passed.
- Published only the existing isolated Cloudflare Preview project at
  `https://e77b3897.siteagent-preview-eliz-de-fleur-769afda793.pages.dev`.
  No production `go`, Telegram delivery, customer production deployment or
  custom-domain action ran. Stop checkpoint:
  `ELIZ_REVISION_PREVIEW_READY_FOR_USER_REVIEW`.

## Explicit production go and fail-closed evidence gate (2026-07-18)

- Executed `python -m site_agent.cli go` from the explicit user command and
  claimed the existing pending job without requesting its source URL again.
- Research completed and persisted a durable checkpoint, but resolved the
  requested full commercial site to `recommended_scope: blocked`: no verified
  business identity, exact product, language, content themes, contacts, offer,
  proof, or conversion route were available.
- The run then stopped at `media_input_blocked` because its authorised
  business-media manifest is absent. No site output, Cloudflare deployment,
  public URL, or Telegram success notification was created.
- Recovery must reuse `runs/f684eed531f74dd8995b2a58ac77739e`, add verified
  business facts and an authorised media manifest, and resume the same job.
  Duplicate generation or invented business facts remain prohibited.

## Amidental one-link isolated preview recovery (2026-07-18)

- Reclaimed the exact failed job/run `f684eed531f74dd8995b2a58ac77739e`
  without a duplicate queue item, production completion or Telegram delivery.
- Added bounded static/web/rendered-browser/official-site research fallbacks,
  a durable source ledger, exact-duration protection, preview-only business
  social-media provenance and 11 preserved/uploaded images.
- Produced and materially revised a bespoke full commercial Amidental Kiev
  site from three concepts. Final deterministic gates: technical pass at
  1440/768/390, commercial 100, semantic repetition pass, Product Director 100,
  independent final critic 94 and acceptance approved with no critical/high
  issue.
- Published only the dedicated Cloudflare Preview deployment at
  `https://748478b0.siteagent-preview-amidental-kiev-088e5323bc.pages.dev`.
  Live verification confirms exact business meta, HTTP 200, HTML and response
  noindex, crawler-blocking robots, loaded media, usable mobile menu/FAQ/footer
  and zero overflow/console/network failure. Production, custom domain and
  Telegram flags remain false.
- Fixed preview recovery defects exposed by the real run: Windows child-tree
  timeout handling, canonical source reuse, capitalized Wrangler deployment
  JSON, exact DOM marker validation and retryable acceptance failures.
- Current stop checkpoint:
  `ONE_LINK_SITE_PREVIEW_READY_FOR_USER_REVIEW`.

## One-link recovery audit hardening (2026-07-19)

- Audited recovery commit `e02922f` against current main and found a stale
  critic-provenance gap before merge: cached recovery could reuse approved
  acceptance/deployment after CSS, JavaScript or final screenshot changes.
- Added full HTML/CSS/JS critic binding, acceptance-report and final-screenshot
  binding, normalized-source recovery, fresh live preview verification and
  `preview_ready` consistency checks. A failed validation no longer destroys the
  durable checkpoint or overwrites verified deployment metadata.
- Corrected automatic media semantics: the authoritative Amidental manifest has
  11 preview-only business images, with four rendered; metadata-only video is
  separate provenance and cannot satisfy Studio readiness. Corrected the queue
  checkpoint from 12 to 11.
- Final customer copy now deterministically blocks inflation of exact 20-year
  evidence. Preview publishing requires the dedicated Cloudflare Pages account
  contract and no longer falls back to temporary Workers hosting.
- Fresh independent review checksum-bound the current site tree, final and live
  screenshots and deployed staging bytes. Idempotent resume of the exact existing
  job reused the verified public preview without upload, production, custom-domain
  or Telegram action.
- Final recovery-branch regression passed: 177 tests, with only the explicit
  credential-gated Cloudflare production smoke skipped. `compileall`, `pip check`,
  the local smoke build, diff validation and the patch secret-pattern scan passed.

## Preview-default and brand-fidelity implementation (2026-07-19)

- Replaced the implicit production `go` path with an isolated preview lane:
  `production=False, preview=True`. Preview completion writes only preview
  metadata and cannot notify Telegram, set production URLs or mark a job done.
- Added an explicit `production-promote --job-id ... --authorize-production`
  command. It fails closed unless an exact job/run-bound authorization artifact
  confirms production approval, media rights, contact/CTA copy, preflight and
  live-QA readiness.
- Added durable preview recovery metadata plus a no-upload reconciliation path
  for legacy `preview_ready` jobs. The current insufficient-content failure is
  classified as recoverable in the same job/run.
- Added a mandatory deterministic Brand Identity Analyzer before Design
  Director, exact official-avatar logo preservation, cross-media palette
  analysis, target-bound brand provenance and a checksum-bound independent
  Brand Fidelity Auditor before acceptance.
- Added same-run intake migration that removes Meta platform decoration while
  retaining the 11 already-isolated Amidental Cloudinary assets. This avoids a
  second scrape/upload and gives the preserved profile avatar the explicit
  `official_profile_avatar` role.
- Regression evidence so far: all 196 discovered tests resolve across bounded
  groups (195 passed, one credential-gated Cloudflare production smoke skipped).
  Focused recovery/brand tests, `compileall`, `pip check`, smoke build and diff
  validation pass. Live same-run recovery and the new isolated preview remain
  the next incomplete checkpoint; production and Telegram delivery remain off.
- Independent adversarial review initially found six high-severity bypasses.
  All were corrected and reproduced again: ordinary portraits are not logos;
  no-logo sites cannot invent a visual mark; inline/CSS-hidden logo tokens and
  tiny colour specks fail; exact-logo screenshot presence is spatially checked;
  Instagram media needs account-scoped DOM ownership or a checksum match to a
  prior accepted preview; brand cache checksums bind ownership provenance; and
  production rights materialize into a separate exact-ID manifest. Final
  independent verdict: no critical/high defect remains.
