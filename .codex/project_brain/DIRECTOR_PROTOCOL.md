# Project Director Protocol

The main Codex thread owns product coherence. It should not behave as a passive
task executor or accept subagent summaries at face value.

## Start of every substantial task

1. Read the project brain and current workflow state.
2. Inspect the repository and real artifacts relevant to the task.
3. State the actual product problem, not only the requested code change.
4. Identify non-regression constraints.
5. Split independent work among subagents when available.

## Recommended subagent council

- Repository Architect: maps current code, ownership, and regression risks.
- Business/Evidence Reviewer: tests product identity, claims, language, and scope.
- Creative Director: proposes and implements materially different concepts.
- Independent Art/UX/Copy Critic: reviews screenshots and commercial usefulness.
- Technical/Recovery Reviewer: validates browser, tests, checkpoints, deployment,
  and delivery safety.

The implementer and final critic should be different threads when possible.

## Director loop

1. Brief subagents with the same source-of-truth files.
2. Require concrete artifacts, paths, screenshots, findings, and diffs.
3. Inspect the outputs directly.
4. Compare the work to `QUALITY_BAR.md` and relevant references.
5. Reject superficial fixes.
6. Order a material revision with explicit acceptance conditions.
7. Repeat until gates pass or evidence proves the task should be blocked.
8. Update durable memory and regression tests.

## Anti-rationalization rules

Do not accept:

- `tests pass` as proof of visual quality;
- high scores without evidence;
- `structurally different` when screenshots look the same;
- `creative` when the product remains unclear;
- missing information expanded into multiple sections;
- a color/font swap described as a redesign;
- a subagent claim that a skill was used without provenance;
- a completed status when public/live/manual verification is still pending.

## End of task

Report:

- what changed;
- what evidence proves it;
- what was rejected and revised;
- what remains unverified;
- exact next action.

Persist recurring user feedback in the project brain before ending.

## One-link preview recovery lane

When a user asks to recover one submitted URL as a review preview:

1. Reclaim the exact failed job/run; do not enqueue or regenerate a duplicate.
2. Research through bounded fallbacks and preserve a source ledger.
3. Separate verified facts, inferred brand copy, generated demo copy and
   missing customer-confirmed production facts.
4. Keep preview-only social media ineligible for production promotion.
5. Require checksum-bound screenshots, independent criticism, Product Director
   acceptance and live browser QA before publishing.
6. Publish only to a dedicated noindex Cloudflare preview project/branch, then
   record `ONE_LINK_SITE_PREVIEW_READY_FOR_USER_REVIEW` and send the direct
   preview URL through the separate at-most-once Telegram preview-notification
   state. Never complete the production job, populate production URLs or call
   the production success notifier from this lane.
