# Next Action

Checkpoint: `READY_FOR_CREDENTIALLED_REFERENCE_IMPORT`.

Configure local OpenAI and Cloudinary credentials without recording them, then run
`python -m site_agent.reference_import`. The importer will capture desktop/mobile
screenshots and invoke the configured screenshot-led Reference Analyst; failures
remain per-reference and are resumable. Prepare authorised real-user media manifests
for Orange Beauty Studio and Bella Dent Clinic. Existing Cloudinary assets require
explicit business ID, origin, `user_authorized=true`, and
`allowed_for_public_site=true`; local inputs preserve originals and flag ambiguous
Instagram crops for manual review. If either asset set cannot prove authorisation,
stop at media-input and report the exact missing assets. Keep
`CREATIVE_STUDIO_HUMAN_CALIBRATION_REQUIRED=true`; do not run `go`, Telegram,
Cloudflare, publishing, or delivery.
