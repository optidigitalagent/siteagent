# Design-quality architecture implementation plan

## Audit snapshot — 2026-07-15

Current executable flow is `site_agent.cli.run_pending_job` →
`SiteAgentOrchestrator.run` → agents (`ResearchAgent`, `StrategyAgent`,
`SiteSpecAgent`) → `SiteBuilder` → `CriticAgent` → `AcceptanceAuditor` →
`Publisher` → Telegram receipt/queue completion. Existing durable artifacts
live in `runs/<job>/generation_reports`, `critique_reports`, and
`deployment.json`; resume is based on valid serialized artifacts plus
`generation_reports/checkpoints.json`.

The current quality decision is a single `CritiqueReport` with technical,
visual and business booleans plus a total score. It can approve sparse pages
that are technically valid but commercially empty. The queue, publisher,
live verifier and Telegram receipt flow are a non-regression boundary.

## Delivery phases

1. **Skills and schemas** — vendor three reviewed, pinned external skill
   references under `.agents/skills/`; add lock validation; add versioned
   artifact models and local role contracts.
2. **Artifacts and recovery** — persist evidence, media, business, UX, story,
   copy, visual direction, design-system, responsive and builder-context
   artifacts; extend (never replace) checkpoints and make legacy runs valid.
3. **Generation** — assess evidence before strategy/build; derive structured
   contracts from research and generated copy; make the builder consume the
   selected context and explicit tokens.
4. **Quality council** — add deterministic unsupported-claim, placeholder,
   phrase-overlap, accessibility/responsive, and anti-template checks; keep
   browser technical inspection as an independent required input.
5. **Acceptance and fixtures** — aggregate category floors and blockers before
   the existing publisher; add deterministic fixtures proving niche variation
   and regression rejection.
6. **Regression and docs** — run all project checks, document the architecture
   and record precise remaining environment-limited evidence.

## Compatibility rules

- `pipeline_schema_version` is written only for new runs. Completed legacy
  jobs and legacy artifact names remain readable.
- A new pipeline failure is explicit (`insufficient_evidence` or blocked
  quality); it never silently chooses the old generator in production.
- `Publisher`, `LiveSiteVerifier`, queue state transitions and Telegram send
  ordering remain unchanged. Publishing is merely called later.
- Tests and fixtures run with local publishing and never claim Telegram work
  or use Cloudflare credentials.

## Initial acceptance evidence

- Unit: evidence levels, artifact validation, gate aggregation, fingerprint
  stability/similarity, sparse intentional design, and legacy compatibility.
- Integration: restaurant, dental clinic, decorator portfolio, online school,
  sparse usable business and the rejected yacht placeholder.
- Browser: existing Playwright desktop/mobile technical inspector plus new DOM
  contracts for viewport, semantic structure and targets.
- Regression: existing unit suite, `compileall`, `pip check`, smoke build and
  `git diff --check`.
