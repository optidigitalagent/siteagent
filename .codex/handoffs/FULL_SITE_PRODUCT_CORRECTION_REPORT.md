# Full-site product correction — human-audit handoff

## Status

`AUTONOMOUS_FULL_SITE_AGENT_READY_FOR_HUMAN_AUDIT`

The autonomous product and QA pass is complete. This is not production approval:
`CREATIVE_STUDIO_HUMAN_CALIBRATION_REQUIRED=true` remains blocking, and no
publishing or customer delivery ran.

One calibration-integrity disclosure remains material. The manual Eliz baseline
was present in the selected reference/design inputs, so the strict blind-input
claim cannot be proven for this recovered run. The recovery contract required
preserving Concept C and forbade regenerating research/references/concepts. The
final product can therefore be audited for quality, but this run cannot be used
as clean evidence of a blind benchmark without explicit human acceptance.

## Root cause and invalidated acceptance

The former system could silently reduce an ordinary business request to a
micro-site and then judge that smaller output against its self-selected scope.
Orange Beauty Studio and Bella Dent Clinic remain technically accepted
historical artifacts but product-rejected with
`rejection_reason=incomplete_commercial_website`. Neither was repaired,
published, or delivered during this work.

The Eliz recovery exposed three additional causes:

- the technical inspector classified pending lazy images as broken;
- controls hidden by an ancestor were classified as 0×0 tap targets;
- stale critic output was reusable after the authored site changed, and the
  Product Director only inspected `index.html` for a multi-page request.

## Implemented product and recovery contracts

- Normal business intake defaults to `full_commercial_site`; sparse evidence
  blocks rather than silently shrinking scope.
- Full-site acceptance requires identity/value, offer/services, proof,
  brand/about, trust/process, commercial decision, objection handling, and
  final conversion.
- Retryable/timed-out Studio staging can be revalidated only with bounded,
  checksum-clean provenance; validator/source changes are explicit.
- Canonical final screenshots are rerendered instead of accepted by existence.
- Lazy images are activated and decoded before inspection; only completed
  zero-width images fail. Hidden-ancestor controls are excluded from tap checks.
- Critic reuse is bound to the complete HTML/CSS/JS tree, not only `index.html`.
- Multi-page Product Director acceptance now requires Home, Services,
  Portfolio, About, and Contact, complete cross-page navigation, PL/EN controls,
  portfolio filters, and a contact form.

## Eliz de Fleur final product

Concept C remains the selected direction. The final information architecture is:

1. `index.html` — identity, verified offer, service overview, proof, brand,
   process, FAQ, and enquiry entry.
2. `services.html` — four evidence-backed service situations with media.
3. `portfolio.html` — 24-item filtered portfolio: commercial 3, corporate 7,
   private 12, photo zones 2; 22 photographs and 2 films.
4. `about.html` — brand position, proof range, process, and next step.
5. `contact.html` — project guidance, accessible validated form, prepared
   enquiry, copy/manual fallback, and verified Instagram route.

The first desktop and mobile viewport states the event-scenography/floral-
installation offer and exposes enquiry and portfolio actions. PL/EN switching,
mobile navigation, portfolio filtering, invalid-form focus/error handling, and
valid-form fallback were exercised in Chromium.

## Media recovery

The four assets originally reported as unavailable were false positives caused
by the lazy-image race. Fresh GET and checksum verification proves all four are
`200 image/jpeg`, business-origin, user-authorised, allowed for public-site use,
and byte-identical to their prepared files:

- `siteagent/e170ce25575f0e2b60e7c305`
- `siteagent/f9a6c04ece0b0f3330a92861`
- `siteagent/f3182f6c49fdb530b950af7c`
- `siteagent/b47099f93aa7a98b9858c1af`

No reupload was needed. Evidence is recorded in
`studio/cloudinary_media_reverification.json` inside the Eliz run.

## Independent decisions and baseline comparison

- Fresh critic: 89, visual approved, business approved, technical pass; no
  critical/high issue. Remaining findings are medium/low CTA/copy specificity
  and editorial-rhythm refinements.
- Fresh Art Director: 89, approved, hard gate passed, no high issue.
- Fresh multi-page Product Director: 100, accepted, all five pages/navigation,
  PL/EN, filters, form, screenshots, identity, and media checks passed.
- Acceptance audit: approved at 89 with no blocking reason.
- Independent screenshot comparison found the final five-page product materially
  stronger than the manual one-page baseline in completeness, IA, media
  coverage, service clarity, portfolio depth, mobile journey, and conversion.
  The baseline evidence contains many visibly blank portfolio tiles. A high
  tablet-width Services defect found during that comparison was fixed and
  independently re-reviewed; no critical/high issue remains.
- The live manual baseline returned HTTP 200 during comparison. Comparison was
  after-build visual review only and does not repair the disclosed blind-input
  contamination.

## Verification evidence

- Focused recovery/product suite: 47/47 passed.
- Full suite: 141 passed; 1 credential-gated Cloudflare production smoke skipped.
- `python -m compileall -q site_agent scripts tests`: passed.
- `python -m pip check`: passed, no broken requirements.
- `python scripts/smoke_build.py`: passed.
- All five pages passed desktop 1440×1100, tablet 768×1024, and mobile
  390×844 inspection with no overflow, missing images, failed requests, console
  errors, broken links, or sub-44px visible targets.
- Accessibility interaction audit v2 passed: semantic landmarks/headings,
  `lang`, labels/alts, skip-link/focus, keyboard menu, PL/EN, reduced motion,
  form focus/error/result, and AA-oriented core color contrast.
- Portfolio filters returned 24/3/7/12/2 items as specified.
- The final authored tree checksum bound to critic/accessibility evidence is
  `e02cc6a865eb8d076293073dc078d001167f893ea1abd59988203e1676f22af2`.
- Final `git diff --check`, tracked-diff secret scan, and customer-site
  secret/internal-path scan passed; no secrets or private run provenance are
  published in the site or reports.

## External actions, blockers, and next action

No `go`, Telegram notification/delivery, Cloudflare action, or customer
deployment ran. The live baseline was read-only HTTP comparison only.

Product QA has no remaining critical/high issue. Production remains blocked by
the human calibration gate. The human auditor must also decide whether the
disclosed baseline/reference contamination invalidates this golden run as a
strict blind benchmark. If strict blindness is mandatory, a new clean run is
required; this recovered Concept C run must not be relabelled blind.

Checkpoint commit: `5041a730eae79e837539ae6fd3a17ecb4a21a573`.
Final implementation/report commits are resolved through the pushed `main` HEAD
and will be recorded in the final response.

Exact next action: human visual/product audit of the Eliz screenshots and the
blind-integrity disclosure. Do not publish before explicit approval.
