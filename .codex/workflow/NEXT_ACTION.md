# Next Action

Active checkpoint: `SITE_REFINEMENT_VERIFIED_NO_PUBLISH`.

The separate persistent existing-site refinement workflow is implemented and
verified. Focused/full regressions, compileall, dependency validation, smoke
build, diff validation, real strict Chromium lifecycle checks and two independent
final audits pass with no critical/high issue. No automatic next action remains.
Do not publish, touch Telegram state, or change any existing deployment without
a separate explicit user request.

Previous checkpoint: `AMIDENTAL_EXTERNAL_AUDIT_VERIFIED_AWAITING_AUTHORIZATION`.

The current 18-issue external audit has been verified and converted into a
system-level change plan in
`.codex/handoffs/AMIDENTAL_PRODUCTION_AUDIT_VERIFICATION_18_ISSUES.md`. The
older `AMIDENTAL_EXTERNAL_AUDIT_VERIFICATION.md` covers an earlier partial
input and is retained only as historical evidence. Do not edit
the Amidental site or implement the proposed generator gates until the user
explicitly authorizes implementation. The recommended first implementation
slice is evidence/cache regression plus computed business-data completeness,
real first-viewport validation and conversion-outcome tests.

The preview-ready Telegram delivery boundary is complete for exact job/run
`053656c35b5d4ef58221c5be7171b625`. No automatic next action remains in the
preview lane.

The preview-default and brand-fidelity recovery is complete for the exact job
and run `053656c35b5d4ef58221c5be7171b625`. No automatic next action remains in
the preview lane.

Accepted isolated preview:
`https://227fe3c8.siteagent-preview-amidental-kiev-3a8654d4fd.pages.dev`.

The queue is `preview_ready`; preview notification is `sent` with a safe
Telegram-accepted receipt. Production URL fields and production authorization
are empty. Do not promote, attach a custom domain, or send the production
success notification unless a later user explicitly invokes the separate
`production-promote --job-id 053656c35b5d4ef58221c5be7171b625
--authorize-production` lane and all production rights/contact/copy/preflight
gates pass.

Completed evidence:

- normal `go` is exactly `production=False, preview=True`;
- legacy preview metadata was reconciled without another upload;
- Brand Identity ran before Design Director and Brand Fidelity passed;
- exact same-run recovery produced critic approval 90/100 with no critical/high
  issue and acceptance bound to the current site checksum;
- live desktop/tablet/mobile browser QA and an independent published-preview
  audit passed;
- 219 tests passed with one credential-gated production smoke skipped;
- compileall, pip check, smoke build, diff validation and secret scan passed.
- independent code and adversarial safety reviewers accepted the final state
  with no critical/high issue;
- `preview-notify` freshly live-verified and sent the existing direct deployment
  URL once; the receipt contains no Telegram chat/message identifier.

Production, custom-domain changes and production Telegram delivery remain
forbidden for this completed preview recovery.

## Superseded recovery instructions

The fresh Telegram job `053656c35b5d4ef58221c5be7171b625` was incorrectly
routed through the production lane by `run_pending_job(... production=True)`.
Its exact run directory is already durable and must be resumed in place. Do not
create a new queue item, request the Instagram URL again, or derive a new run.

The existing Amidental preview is technically accepted but does not yet prove
fidelity to the business's actual logo and recurring visual identity. Preserve
it as historical evidence only. The source profile avatar contains the official
Amidental tooth/wordmark, and preview media rights remain distinct from customer
production rights.

Exact next action:

1. make `go` claim/resume preview by default with `production=False, preview=True`;
2. add a separately authorised `production-promote` lane;
3. repair durable preview queue metadata and legacy recovery fields without a
   duplicate upload;
4. create and validate `brand_identity.md`, `brand_identity.json`,
   `brand_assets_manifest.json` before Design Director;
5. pass the brand package losslessly to Design Director and Studio;
6. require an independent `BrandFidelityAuditor` before preview acceptance;
7. resume the exact current run from its first invalid/incomplete checkpoint;
8. materially align logo, palette, typography accents, controls and graphic
   language with verified Amidental brand evidence while retaining useful site
   structure;
9. run desktop/tablet/mobile QA and publish only a new isolated noindex preview;
10. commit and push only after focused/full tests, compileall, pip check, smoke,
    browser QA, diff validation and secret scan pass.

Production, custom domain changes and customer Telegram delivery are forbidden
for this recovery.
