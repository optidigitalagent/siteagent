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
