# Scenario Matrix

| Scenario | Expected Result | Evidence |
| --- | --- | --- |
| Telegram receives Instagram URL | Queue file gets a pending job and bot replies with Codex `го` instruction | Queue JSON + bot log |
| Codex `go` with pending job | Job becomes running, pipeline starts from stored URL | CLI output + queue JSON |
| Codex `go` with no jobs | CLI says no pending jobs and exits cleanly | CLI output |
| Generation passes QA | Acceptance audit runs before publisher | `acceptance_audit.json` |
| Critic blocks site | Fixer loop runs up to max iterations | critique reports |
| Telegram production publishing env missing | Job fails; no `file://`, done status, or success Telegram message | queue JSON + `deployment.json` |
| Cloudflare project already exists for business | Deterministic project is reused and updated | mocked Wrangler calls + `deployment.json` |
| Cloudflare project is new | Project is created non-interactively, then deployed | mocked Wrangler calls + `deployment.json` |
| Direct Upload succeeds but live page fails | Job remains failed and success Telegram message is not sent | queue JSON + verification failure metadata |
| Explicit local development | `HOSTING_PROVIDER=local` and `PUBLISH_REQUIRED=false` returns a preview URI | unit test |
| Cloudflare credentials available | Opt-in smoke publishes static fixture and verifies stable HTTPS URL | smoke test output |
| Railway deploy | Bot starts with `python -m site_agent.telegram_bot` | Railway logs |
| Git inbox sync enabled | Bot commits queue change, Codex pulls before claim | git history |
| Selected Studio media includes fixture/stock provenance | Production promotion fails deterministically; no publisher call | focused provenance-promotion test |
| Selected Studio media is verified business media | Promotion remains eligible, subject to other gates | focused provenance-promotion test |
| Fixture media remains but its provenance disclosure is removed | Production validation fails; warning cannot be silently stripped | focused provenance-integrity test |
| Production build is otherwise valid | Calibration-only fixture footer/disclosure is absent | focused production-output test |
| Award source lists a candidate | Original live URL is resolved, captured and stored with source/award provenance; gallery itself is never selected | discovery candidates + raw record |
| Candidate is blank, 404, parked, mismatched, incomplete without scope, or near-duplicate | It remains raw/excluded and cannot enter selection | reference_decisions.json + focused test |
| Curator and Auditor disagree at low confidence | Candidate is excluded without routine user intervention | reference_decisions.json |
| Human-audit preview is requested | A separate preview project is deployed with an isolated run URL; customer production, custom domains, queue and Telegram stay unchanged | preview deployment metadata + Cloudflare environment + live checks |
| Preview crawler protection is inspected | Every HTML page contains `noindex,nofollow` and every response includes `X-Robots-Tag: noindex, nofollow` | five live responses + browser DOM checks |
| Preview form has no backend | The site reports its fallback mode and never claims a server-side submission | interaction report + final handoff `form_mode` |
| A generated page is long enough to scroll | Header/navigation remains usable at the top, midpoint and near-bottom; sticky controls remain below it | desktop/tablet/mobile browser shell report |
| Final page reaches its footer | Footer exposes declared-IA navigation, a primary CTA and only verified social/contact routes | DOM plus footer screenshots on every page |
| Primary CTA contains nested decorative elements or translated text | Label stays fully visible inside a ≥44×44 clickable box in default/hover/focus/active states | CTA geometry/state assertions plus screenshots |
| One-link static fetch lacks usable evidence or media | Rendered browser, public search and discovered official-site providers continue; every attempt is ledgered | `00_one_link_intake.json` + source ledger |
| Source says exactly `20 років` | Research and copy retain exact 20; no `20+`, `over 20` or `понад 20` appears | provenance regression test + final HTML |
| Profile media is authorised only for preview | Preview accepts business-social Cloudinary assets; production acceptance rejects them | media manifest + focused acceptance tests |
| Preview HTML contains the business ID only in an asset path | Publisher injects/verifies an exact business-id meta; incidental substring cannot pass | preview publisher regression test + live DOM |
| Preview upload succeeds but deployment-list JSON uses capitalized Wrangler keys | Existing non-production deployment is parsed and verified without creating a duplicate job | publisher tests + deployment metadata |
| Live page uses lazy media | Browser scroll-through loads every image before missing-media judgment | live browser QA report |
| CSS/JS or a final screenshot changes after critic approval | Cached critic/acceptance is rejected and the normal review path resumes | full-tree and screenshot provenance regression tests |
| A verified preview exists and a later retry fails locally | Verified deployment metadata and `preview_ready` remain intact; failure is recorded separately | preview publisher and CLI recovery tests |
| Intake discovers four images plus only video metadata | Video remains provenance-only; fallback continues and Studio sufficiency stays false | one-link media intake tests |
| Preview Pages credentials are missing or partial | No Wrangler/toolchain/deployment command runs and no temporary Workers fallback occurs | preview publisher credential tests |
| Exact source says 20 years but final HTML says 20+ | Acceptance/recovery fails closed before reporting or publishing the preview | final-copy exact-duration regression test |
| A new Telegram business job runs through `go` | The exact job/run is claimed or resumed with `production=False, preview=True`, ends `preview_ready`, records the direct preview URL and never touches production URL fields or Telegram production delivery | CLI call assertions + queue JSON + preview deployment metadata |
| A user explicitly requests production promotion | Promotion is rejected unless the command carries explicit authorisation and the saved job has approval, confirmed contacts/copy/CTA, production media rights, preflight and live QA | production-promotion CLI and contract tests |
| Preview media is authorised but production rights are false | Brand analysis and isolated preview continue; the same assets remain deterministic production blockers | brand asset/media manifests + preview/production acceptance tests |
| Profile avatar contains the official business logo | Original and deterministic processed logo files, source, checksums, dimensions, extraction method, confidence and rights are stored before design | brand assets manifest + logo extraction test |
| Photos contain frequent incidental colours | Repeated logo/template/highlight/signage colours outrank object and environment colours; low confidence produces a conservative neutral fallback | brand identity evidence counts + palette tests |
| Design Director or Studio input omits the brand package | Generation or acceptance fails before publication | implementation-package integrity + Brand Fidelity tests |
| Final screenshots conflict with a high-confidence brand package | BrandFidelityAuditor blocks acceptance and triggers a material fixer cycle | auditor report + before/after screenshots + acceptance test |
| A normal `go` reaches a verified isolated preview | The exact direct preview URL is sent once to the originating Telegram chat; the job stays `preview_ready` and production fields stay empty | preview receipt + queue state + notifier regression |
| Telegram may have accepted a preview message but its response is lost | Preview notification becomes `unknown`, the verified URL remains, and no automatic run/upload/resend occurs | queue state + transport-failure regression |
| Existing `preview_ready/not_started` needs recovery delivery | `preview-notify` freshly verifies the existing live preview and sends without invoking generation or Cloudflare upload | CLI mocks + live verifier + unchanged deployment ID |
| Preview notification is `sent`, `sending` or `unknown` for the same key | Repeated `go`, live audit and `preview-notify` do not send; explicit `preview-resend` is the only authorised retry path | idempotency and concurrency regressions |
| A refinement session receives hero feedback and later card feedback | Both requirements remain active in the live brief | refinement state/history regression |
| A refinement user explicitly replaces the light hero requirement with a dark hero requirement | The old item remains auditable as `superseded`; only the dark requirement is active | explicit supersession regression |
| A refinement build passes without browser QA | `CANDIDATE_READY` is rejected | refinement readiness regression |
| New feedback arrives after `CANDIDATE_READY` | The session returns to `IMPLEMENTING` and keeps prior history | refinement transition regression |
| Contacts are missing but the requested card-design task is actionable | The design task runs and the contact blocker remains explicit | partial-progress regression |
| A reference is scoped only to the hero | Its mapping cannot be widened to unrelated pages/components | reference-scope regression |
| Existing BUILD MODE is invoked after refinement support is installed | The original `go`/URL orchestration contract remains unchanged | CLI/build-mode regression |
| A refinement page attempts POST, beacon, popup or WebSocket work during load/unload | Every side effect is neutralized before external connection and appears in browser evidence | lifecycle Chromium regressions + interaction screenshots |
| A file-based project links to or loads an existing file outside its root | The resource/link is rejected even when the destination exists or resolves through a link | project-root resource and relative/absolute href regressions |
| A localhost port is owned by explicit IPv4, `0.0.0.0`, non-HTTP or IPv6 dual-stack listener | Start refuses the owner and cleanup cannot certify the port free | endpoint ownership regressions + lifecycle JSON |
| A handled form leaves only hidden or stale feedback, or points at an unverified endpoint | Functional QA fails; only a changed visible outcome or safe contact fallback passes | form interaction regressions |
| Bounded one-link intake finds zero provable business photos but generated media is available and real-media-only was not requested | The same run creates a truthful generated-media plan and may continue to isolated preview; evidence-only sections stay omitted or missing | media plan, generated provenance, same-run recovery and preview acceptance regressions |
| A generated portrait/interior/before-after is presented as a real employee, business location or case | Preview and candidate acceptance fail before publishing | generated-media truthfulness regression plus rendered-use audit |
| A `reference_only` asset is rendered in the site | Preview and candidate acceptance fail before publishing | provenance/output regression |
