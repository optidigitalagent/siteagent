# Next Action

Checkpoint: `FULL_SITE_PRODUCT_CONTRACT_REBUILD_IN_PROGRESS`.

The former Orange Beauty Studio and Bella Dent Clinic acceptance is invalid for
product quality. Their historical calibration artifacts remain preserved with
`technical_status=accepted`, `product_status=rejected_by_human_audit` and
`rejection_reason=incomplete_commercial_website`. Do not publish or cosmetically
repair either run.

The full-site product contract is implemented locally: normal business input
defaults to `full_commercial_site`; sparse evidence produces
`BLOCKED_INSUFFICIENT_BUSINESS_CONTENT`, not an inferred micro-site; acceptance
requires a blind `ProductDirectorAuditor`; and a full commercial site requires
explicit identity, services, proof, about, process/trust, commercial-decision,
objection-handling and final-conversion coverage.

Eliz de Fleur golden calibration is recoverable at
`runs/eliz-de-fleur-golden-calibration/`. Its blind 24-photo/2-video input,
research, authorised-media manifest, Design Director brief, three concepts,
native desktop/tablet/mobile concept screenshots and selection are complete.
Concept C was selected. The full build remains retryable: initial technical
validation found four unavailable rendered Cloudinary images and undersized
navigation targets. A recovery fix ensures any retryable full build invokes a
material rebuild rather than looping on the failed staging output.

Exact next action: resume only `runs/eliz-de-fleur-golden-calibration` from
`studio/task_state.json`, complete the material full-build revision, then run
fresh desktop/tablet/mobile inspection, independent Product Director audit,
blind baseline comparison, full tests and final handoff. Do not run `go`,
Telegram, Cloudflare or customer publishing. Keep
`CREATIVE_STUDIO_HUMAN_CALIBRATION_REQUIRED=true`.
