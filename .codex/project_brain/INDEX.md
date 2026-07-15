# SiteAgent Project Brain

This directory is the durable product memory for every Codex session in this
repository.

## Mandatory reading order

1. `VISION.md`
2. `QUALITY_BAR.md`
3. `HUMAN_FEEDBACK.md`
4. `DIRECTOR_PROTOCOL.md`
5. `REFERENCE_LIBRARY.md`
6. Current `.codex/workflow/` state

## Instruction precedence

1. Current explicit user request.
2. Root `AGENTS.md`.
3. This project brain.
4. Current workflow decisions.
5. Individual skills.
6. Legacy documentation and completed-run artifacts.

Legacy documents may describe the old deterministic/Jinja builder. They are
historical unless an explicit legacy compatibility task is being performed.

## Persistence rule

When the user rejects a result or clarifies the product goal, store the reusable
lesson in `HUMAN_FEEDBACK.md` and strengthen the appropriate contract, skill,
critic, or regression test before closing the task. Important product knowledge
must not live only in chat history.
