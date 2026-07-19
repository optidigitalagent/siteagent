# Risk Register

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Railway filesystem is not shared with local Codex | Telegram URL is not visible locally | Enable `TELEGRAM_INBOX_GIT_SYNC=true` and use repo-backed inbox |
| Railway cannot push to GitHub | Inbox sync fails | Configure GitHub integration or tokenized remote URL |
| OpenAI key missing | Generation cannot run | `.env`/Railway vars must include `OPENAI_API_KEY` |
| Playwright browser missing | Critic gate fails | Dockerfile installs Chromium with Playwright deps |
| Cloudflare credentials missing locally | Production job cannot publish | Fail closed with setup guidance; never return `file://` |
| Wrangler output/schema changes | Deployment metadata parsing fails | Pin Wrangler major version and cover representative JSON in tests |
| Local system disk is full | npm cannot install Wrangler or Wrangler cannot write local state | Free disk space or configure npm cache on a disk with capacity before real deployment |
| Cloudflare deployment propagation delay | Immediate live check fails | Bounded retry with backoff before declaring failure |
| Oversized or sensitive file in site output | Broken upload or data exposure | Preflight every file, reject traversal, secrets, reports, and files over 25 MiB |
| Deterministic Pages name collides | Another project could be overwritten | Stable URL marker ownership check and bounded hash-suffix retry |
| Public queue exposes client links | Privacy risk | Use private repo for `website-agent` inbox |
| Studio child invocation can hang after partial artifacts | A stale `running` task state can mask an incomplete build | Preserve concepts/selection, stop only the known child process, require a separate staged build plus fresh technical and independent visual review before promotion |
| Fixture/stock imagery is mistaken for business portfolio proof | False commercial claims or unlicensed production media | Record per-asset source classification, final-use report and visible fixture disclosure; block production until authorised business media and rights provenance exist |
| Fixture-only disclosure is stripped while fixture media remains | A calibration artifact can masquerade as a production portfolio site | Promotion validates selected media provenance before stripping calibration markers; fixture/stock media fails closed, while valid production rejects calibration-only text |
| Cloudinary or authorised media is unavailable | A builder could substitute stock, fixture, or fragile scrape URLs | Block at media-input before Design Director/Codex and list missing authorised assets |
| Reference library is absent or incomplete | Design direction can revert to generic/category patterns | Require three captured trait references before design; importer is resumable and records failures |
| Screenshot analysis is unavailable or incomplete | Weak DOM-only reference notes could masquerade as art direction | Keep a per-reference analysis failure state, block selection until three screenshot-analysed records exist, and resume after credentials are available |
| Instagram UI crop is uncertain | Automatic crop could delete business content or publish social chrome | Preserve source files, record crop coordinates/confidence, require manual review below the high-confidence threshold, and expose a contact sheet |
| Award gallery links resolve to agency/footer destinations rather than an original work | A gallery can contaminate the trait library with an unrelated site | Preserve discovery provenance, resolve the original live URL separately, reject unrelated redirects, and retain failed candidates as excluded raw evidence |
| Autonomous curation wrongly admits an incomplete or duplicate reference | The design plane can regress to a thin, copied or category-driven composition | Require Curator/Auditor agreement, screenshot completeness/mobile checks, bounded scope, perceptual near-duplicate suppression and active-only selection |
| Evidence automatically shrinks a normal business request into a micro-site | A technically valid redirect/three-section page is accepted as a commercial site | Keep `requested_product_type` immutable; default normal jobs to `full_commercial_site`; emit `BLOCKED_INSUFFICIENT_BUSINESS_CONTENT` with a manifest instead of scope shrink |
| Internal visual/technical scores mask incomplete commercial coverage | A polished concept passes without services, proof, decision support or conversion | Require DOM coverage roles, a blind ProductDirectorAuditor, score caps and acceptance evidence independent of internal critic scores |
| Golden calibration media has weak or unavailable individual frames | One failed asset blocks the whole research/design package or is silently replaced | Preserve media diagnostics, reject individual weak frames, retain usable authorized assets, and fail the final render if any selected URL is unavailable |
| Human-audit preview mutates customer production or becomes indexable | An unapproved site can replace the customer site or appear in search | Use a dedicated preview project and non-production branch, HTML robots meta plus `X-Robots-Tag`, no custom domain, separate preview metadata, and explicit production-isolation checks |
| Existing-site revision is routed through new-site generation | Accepted design/business context is lost and unrelated sections are regenerated | Keep the future `SiteRevisionAgent` as a separate workflow with persistent project context, scoped impact analysis, QA, preview, and explicit production approval |
| A visually polished build ships with scrolling navigation, a metadata-only footer, or collapsed CTA text | Visitors lose orientation or cannot convert despite passing basic technical checks | Require checksum-bound browser shell checks on every declared page and viewport; block non-persistent headers, incomplete footers and clipped primary CTA labels |
| A one-link retry creates a second job, site or customer notification | Duplicate work or delivery reaches the customer | Reclaim only the exact failed job/run, keep Telegram `not_started`, and stop at `preview_ready` |
| Exact evidence is inflated during strategy or copy generation | Preview publishes an unsupported numeric claim | Normalize exact-duration claims before Studio input and regression-test plus/over variants |
| A business ID appears in an image URL but not the required meta | Wrong or unbound preview can pass a substring check | Parse DOM and require exact `siteagent-business-id` meta locally and live |
| Wrangler changes deployment-list field capitalization | A successful upload is mistaken for a missing preview and is duplicated | Parse both API-style and humanized JSON keys and test representative Wrangler output |
