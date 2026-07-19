# Next Action

Checkpoint: `TELEGRAM_GO_PREVIEW_DEFAULT_AND_BRAND_FIDELITY_REBUILD_REQUIRED`.

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
