# Creative Studio migration implementation plan

## Audit snapshot — 2026-07-15

Current flow is `site_agent.cli.run_pending_job` → `SiteAgentOrchestrator.run`
→ research/strategy/SiteSpec structured calls → `build_context()` →
`compose_page()` → `SiteBuilder` → `templates/site.html.j2` → critic →
acceptance → publisher → verified Telegram receipt/queue completion.

The precise template boundary is `site_agent/design_quality.py:compose_page()`:
its pattern table selects hero, section order, grid/layout family, closing and CTA logic before
HTML exists. `SiteBuilder` serializes that `PageComposition` into Jinja payloads. A generated
visual direction is therefore reduced to tokens/labels and cannot own composition. The queue,
publisher, live verifier and Telegram receipt flow remain a non-regression boundary.

## Delivery phases

1. **Creative contracts** — create the repository-owned Web Studio skill, lock its checksum,
   create the optional plugin distribution bundle, and validate that runtime resolves only
   `.agents/skills`, never a manually installed/global copy.
2. **Studio runner and artifacts** — add `SITE_BUILDER=codex_studio` (default) and explicit
   `legacy_template`, isolated `runs/<job>/studio/` inputs/concepts/reviews/provenance,
   staged atomic promotion, and resumable studio checkpoints.
3. **Creative generation** — invoke local Codex with `$siteagent-web-studio`; it writes three
   materially different HTML concepts, captures real desktop/mobile screenshots, records
   comparison/selection evidence, and expands the selected concept instead of rendering Jinja.
4. **Quality gates** — extract (rather than select) composition/fingerprints after builds;
   block near-identical concepts, missing screenshots, Jinja use in the new path, unsupported
   claims, incomplete provenance, and unreviewed full builds. Keep existing technical checks.
5. **Compatibility and recovery** — preserve legacy reads and explicit legacy builder behavior;
   Level C bypasses the creative runner; no silent fallback exists. Publisher/Telegram remain
   downstream of the new acceptance result.
6. **Fixture calibration** — add deterministic studio coverage plus opt-in real Codex fixtures,
   comparison page and evidence. Do not publish or send Telegram; halt rollout while
   `CREATIVE_STUDIO_HUMAN_CALIBRATION_REQUIRED=true`.

## Compatibility rules

- `pipeline_schema_version` is written only for new runs. Completed legacy jobs and artifact
  names remain readable.
- A Studio failure leaves a retryable run and is explicit; it never silently selects Jinja.
- `Publisher`, `LiveSiteVerifier`, queue transitions and Telegram ordering are unchanged.
- Tests/fixtures run locally and never claim Telegram jobs or use Cloudflare credentials.
- The calibration flag blocks production rollout only until a user has reviewed fixture evidence.

## Acceptance evidence

- Unit: skill/plugin integrity, workspace isolation, concept persistence/similarity, screenshot
  precondition, selection provenance, atomic promotion, recovery, calibration, legacy behavior,
  no category-template maps, and secrets exclusion.
- Integration: four distinct controlled businesses plus Level C/no-evidence behavior.
- Browser: desktop/tablet/mobile screenshots, console/network/overflow checks and screenshot-led
  art-direction critique.
- Regression: current suite, `compileall`, `pip check`, smoke build and `git diff --check`.
