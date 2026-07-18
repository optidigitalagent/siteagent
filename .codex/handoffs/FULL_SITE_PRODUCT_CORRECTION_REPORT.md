# Full-site product correction — in-progress handoff

## Status

`FULL_SITE_PRODUCT_CONTRACT_REBUILD_IN_PROGRESS` — not ready for human audit.

## Root cause and invalidated acceptance

The old system allowed evidence readiness to select `micro_site`, then judged
the resulting short page against that reduced scope. Orange and Bella therefore
remain technically accepted historical artifacts but are product-rejected for
`incomplete_commercial_website`; neither was published or cosmetically changed.

## Implemented contract changes

- Normal business intake defaults to `full_commercial_site`; only explicit
  campaign/micro requests may use a micro-site.
- Sparse full-site evidence now fails closed as
  `BLOCKED_INSUFFICIENT_BUSINESS_CONTENT` with a missing-content manifest.
- Full-site checks require explicit coverage of identity, offer/services,
  proof, brand/about, trust/process, commercial decision, objection handling
  and final conversion; a redirect or three sections cannot pass.
- Acceptance requires a blind `ProductDirectorAuditor`, separate from internal
  critic scores and scope rationale.
- Media preparation retains rejected-frame diagnostics while preserving the
  usable authorised set; documented video media is now supported.

## Eliz de Fleur golden calibration

- Blind media recovery completed from the published catalog: 24 images and 2
  videos; baseline HTML/copy/layout/screenshots were excluded from the
  research, Design Director and Builder inputs.
- Rich research, media manifest, reference selection, Design Director brief,
  immutable package, three concepts and desktop/tablet/mobile concept captures
  are complete under `runs/eliz-de-fleur-golden-calibration/`.
- Concept C was selected from screenshots. Its first full build is rejected by
  the local technical gate: four rendered Cloudinary images are unavailable and
  several navigation targets are below 44px. The build is retryable; a recovery
  bug that revalidated failed staging without invoking a material rebuild was
  fixed.
- Final build, independent Product Director report, blind baseline comparison,
  final screenshots and human gate have not completed. The autonomous result
  must not be represented as equal to the manual baseline yet.

## Verification

Focused regression suite: 53 passed (`test_full_site_product_contract`,
`test_design_quality`, `test_commercial_usefulness`, `test_creative_studio`,
`test_calibration_contract`). `git diff --check` passed.

The broad unittest discovery command exceeded the shell timeout, so full-suite,
smoke and final browser QA remain unverified.

## External actions and next action

No `go`, Telegram delivery, Cloudflare publishing or customer deployment ran.
`CREATIVE_STUDIO_HUMAN_CALIBRATION_REQUIRED` remains true.

Resume only the Eliz `full_creative_build` checkpoint, complete material fixes,
then run final visual/product/baseline audits and full verification before any
commit or readiness claim.
