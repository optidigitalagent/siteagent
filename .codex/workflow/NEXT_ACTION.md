# Next Action

Checkpoint: `TELEGRAM_GO_PREVIEW_DEFAULT_READY`.

The preview-default and brand-fidelity recovery is complete for the exact job
and run `053656c35b5d4ef58221c5be7171b625`. No automatic next action remains in
the preview lane.

Accepted isolated preview:
`https://227fe3c8.siteagent-preview-amidental-kiev-3a8654d4fd.pages.dev`.

The queue is `preview_ready`; production URL fields are empty, Telegram remains
`not_started`, and production authorization is absent. Do not promote, attach a
custom domain, or send Telegram delivery unless a later user explicitly invokes
the separate `production-promote --job-id 053656c35b5d4ef58221c5be7171b625
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
- 200 tests passed with one credential-gated production smoke skipped;
- compileall, pip check, smoke build, diff validation and secret scan passed.

Production, custom-domain changes and Telegram delivery remain forbidden for
this completed preview recovery.

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
