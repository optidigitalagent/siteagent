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
