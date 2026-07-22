# Current Goal

## Active goal — site refinement mode (2026-07-22)

Implement a real `site_refinement` workflow for existing site projects. The
mode must preserve an accumulating user brief and referenced files, edit the
selected project rather than enter new-site generation, capture a baseline,
run implementation plus browser/visual/responsive/functional/technical QA,
and persist a candidate report. `CANDIDATE_READY` is permitted only from
checksum-bound QA evidence; `USER_ACCEPTED` requires an explicit command.

Non-regression boundaries: the Telegram `go` build lane, queue state,
Cloudflare deployment and existing-site production remain unchanged. The
refinement lane never publishes automatically.

Acceptance evidence is focused and full tests, compile/build checks, a real
local static-site refinement integration run with five target widths, and an
independent contract review with no critical/high issue.

## Previous completed goal

Status: achieved at checkpoint `TELEGRAM_PREVIEW_NOTIFICATION_READY` on
2026-07-19 for the exact existing job/run
`053656c35b5d4ef58221c5be7171b625`.

Complete the missing preview-delivery boundary: after a verified isolated
preview reaches `preview_ready`, send its direct preview URL exactly once to
the originating Telegram chat while the job remains `preview_ready`. Preview
delivery must have its own at-most-once state, safe receipt and recovery
commands; it must never reuse production notification fields or start another
generation, run, Cloudflare upload, production promotion or custom-domain
action.

Restore the one-link Telegram contract for job
`053656c35b5d4ef58221c5be7171b625` without creating another queue item or run:

```text
Telegram business URL
→ python -m site_agent.cli go
→ autonomous evidence and preview-only media intake
→ verified brand identity package
→ brand-faithful full commercial site
→ independent critics and Brand Fidelity audit
→ isolated noindex Cloudflare Preview URL
```

Normal `go` must never enter customer production, request production rights,
populate production URL fields, or send the production Telegram success message.
Production promotion is a separate explicitly authorised command after approval,
confirmed contacts/copy/CTA, production media rights, preflight and live QA.

Completion requires the exact existing run to reach `preview_ready`, durable
queue recovery metadata, focused and full regression evidence, screenshot-led
desktop/tablet/mobile review, an independent brand-fidelity decision, a live
noindex preview URL, and no production/custom-domain/customer-delivery action.

The existing accepted isolated preview is
`https://227fe3c8.siteagent-preview-amidental-kiev-3a8654d4fd.pages.dev`.
Production promotion remains a separate blocked action until its explicit
authorization contract is satisfied.

The verified preview notification was accepted by Telegram. The queue remains
`preview_ready`, preview notification is `sent`, and production URL,
repository URL and production authorization remain empty.
