# SITE_REFINEMENT technical contract

This document describes the implemented `site_refinement` mode for maintainers.
The source of truth remains `site_agent/refinement.py`, `site_agent/cli.py`,
`site_agent/config.py`, `site_agent/critic.py`, and the refinement tests. Any
future change must preserve the isolation and checksum contracts below.

## Boundary and ownership

The refinement lane edits one resolved existing project. It is intentionally
separate from `SiteAgentOrchestrator.run`, the Telegram queue/notifier, preview
publisher, production publisher, Cloudflare, and custom domains.

```text
CLI refinement-start / refinement-continue
                 |
                 v
      SiteRefinementOrchestrator
        | baseline + snapshot
        | executor (workspace-write)
        | local commands (sandboxed)
        | browser QA (five widths)
        | reviewer (read-only)
        v
 CANDIDATE_READY --explicit accept--> USER_ACCEPTED
```

Neither state is a deployment state. A later preview or production
action requires a separately designed and authorised workflow.

## CLI integration

`site_agent.cli` routes four commands to `SiteRefinementOrchestrator`:

| Command | Orchestrator method | Mutation |
| --- | --- | --- |
| `refinement-start` | `start()` | Creates a session, merges intake, and normally runs iteration 0. |
| `refinement-continue` | `continue_session()` | Appends/supersedes inputs and normally runs the next iteration. |
| `refinement-status` | `load()` | Read-only session summary. |
| `refinement-accept` | `accept()` | Revalidates a ready candidate and records explicit acceptance. |

`--no-execute` applies to start/continue and persists intake without invoking
the iteration. Existing `go`, direct URL, preview notification, and production
promotion routing is unchanged.

The request model is `RefinementRequest`. CLI flags overlay the JSON request:
scalar values use the CLI value when present, while feedback, supersession IDs,
scope, constraints, blocker resolutions, test commands, and attachments append.

## Project and session containment

`resolve_project()` accepts:

- an explicit project directory;
- `runs/<value>/site`;
- `runs/<value>` when it contains a supported project marker;
- `<resolved>/site` when that child contains `index.html`.

The current process working directory, runs root, refinement root, and any
directory nested under `runs/refinement` cannot be selected as the edited
project. This is a runtime-CWD check, not a stable repository-root identity
check. A project must contain `index.html`, `package.json`, or `pyproject.toml`.

Sessions are rooted at `runs/refinement/<session-id>`. IDs are validated before
path construction, and the resolved session directory must be a direct child of
the refinement root. A project-scoped non-blocking file lock prevents concurrent
refinement iterations from editing the same project.

Project manifests exclude generated dependency/cache directories during normal
integrity checks and reject links/junctions. Snapshots additionally exclude
secrets and common generated output directories. Attachments are copied into
`inputs/`, named by content digest, and rehashed before use.

## Persistent data model

`session.json` is a `RefinementSession` with:

- immutable identity: schema version, session ID, project ID/path, active mode;
- live brief: user goal, requirements, constraints, scope, confirmed business
  data, business-data history, and attachments;
- execution configuration: entry path, localhost preview URL, build/start/test
  commands;
- workflow state: current status, iteration, open/completed/rejected tasks,
  blockers, resolved blockers, and transition history;
- candidate binding: project, brief, baseline, snapshot, screenshot, and
  supporting-artifact checksums.

Requirements are append-only records with `active`, `completed`, `superseded`,
or `rejected` state. Supersession requires explicit known IDs. A new request
after `CANDIDATE_READY` transitions the same session to `IMPLEMENTING`; a
`USER_ACCEPTED` session is immutable.

Atomic JSON writes protect the session and orchestrator-owned JSON checkpoints.
Browser-inspector artifacts use their own writes and are subsequently validated
fail-closed for completeness, schema, dimensions, checksums, session, iteration,
and source-tree binding.

## Iteration lifecycle

Each iteration performs the following bounded sequence:

1. Capture or validate the pre-edit baseline.
2. Validate stored attachments and analyze incomplete visual-reference mappings
   without widening explicit scope.
3. Write `change_plan.json` and bind it to the active requirement authority.
4. Capture a checksum-complete `pre_change_snapshot` and pre-change manifest.
5. Run the implementation role with workspace-write access to the selected
   project.
6. Compute the actual project diff; do not trust the model's changed-file list.
7. Run configured local build/tests through the native Codex workspace sandbox.
8. Start and own an optional managed localhost preview server.
9. Inspect every discovered route at 1440, 1024, 768, 390, and 360 CSS pixels,
   plus reduced-motion and interaction states.
10. Run a separate read-only screenshot critic.
11. Materialize review issues as requirements for a bounded fixer iteration, or
    bind all evidence and transition to `CANDIDATE_READY`.

The loop runs through `MAX_FIX_ITERATIONS + 1` attempts. Exhaustion records a
blocker and transitions to `BLOCKED`; it does not waive the candidate gate.

## Runtime isolation

The executor and reviewer use different Codex roles and schemas:

- executor: `workspace-write` in the selected project;
- reviewer: `read-only`, with before/after project manifests proving it did not
  mutate the project.

Both roles run with `shell=False`, a restricted environment, bounded stdout and
stderr capture, timeouts, process-tree termination, structured result parsing,
and durable redacted `runtime.json` evidence. Network access is disabled in the
workspace-write sandbox. Runtime setup, timeout, cleanup, schema, or reviewer
mutation failure is fail-closed.

Relevant settings:

| Variable | Default | Purpose |
| --- | ---: | --- |
| `REFINEMENT_EXECUTOR_TIMEOUT_SECONDS` | 900 | Executor deadline. |
| `REFINEMENT_REVIEWER_TIMEOUT_SECONDS` | 600 | Independent reviewer deadline. |
| `REFINEMENT_GRACEFUL_TERMINATION_TIMEOUT_SECONDS` | 10 | Process-tree shutdown window. |
| `REFINEMENT_MAX_STDOUT_BYTES` | 1000000 | Bounded executor/reviewer stdout evidence. |
| `REFINEMENT_MAX_STDERR_BYTES` | 1000000 | Bounded executor/reviewer stderr evidence. |
| `REFINEMENT_CODEX_EXECUTABLE` | empty | Optional compatible native executable override. |
| `REFINEMENT_CODEX_MODEL` | empty | Optional refinement-specific model override. |
| `MAX_FIX_ITERATIONS` | 5 | Material fixer retry bound shared with the configured quality loop. |

When no refinement executable override is set, runtime resolution requires the
native Codex binary. Shell wrappers are not accepted as the sandbox boundary.

The child environment allowlist carries only basic OS/runtime path variables,
sets `PUBLISH_REQUIRED=false` and `HOSTING_PROVIDER=local`, and omits Telegram,
Cloudflare, OpenAI, Cloudinary, and other credential-bearing variables.

## Local command contract

Build, test, and start commands are parsed to a top-level argv and executed
through:

```text
codex sandbox -P :workspace -C <project> -- <resolved executable> <args>
```

SiteAgent does not invoke a shell for that top-level process. Package-manager
commands such as `npm run` may execute declared lifecycle scripts through the
package manager's normal shell, but remain inside the restricted Codex sandbox.
The lexical validator is defense in depth, not a general script analyzer. Its
bounded token and regular-expression lists reject forms including:

- deployment, publishing, Cloudflare/Wrangler, release, and infrastructure
  commands;
- named VCS/network clients such as `git`, `gh`, `curl`, `wget`, `ssh`, `scp`,
  `sftp`, `ftp`, and `rsync`;
- named shell executables such as PowerShell, `cmd`, Bash, `sh`, `zsh`, `fish`,
  and WSL;
- named destructive commands including `rm`, `rmdir`, and `del`;
- inline Python and JavaScript evaluation;
- package lifecycle scripts containing forbidden external actions.

A static bundle can record build/tests as not applicable. A source project must
provide a passing build and at least one passing test command before candidate
readiness.

## Managed preview-server lifecycle

A `start_command` requires a `preview_url` on `localhost` or `127.0.0.1`.
Before launch, endpoint ownership probes must prove the port is free across
explicit IPv4, wildcard IPv4, and IPv6/dual-stack bindings. SiteAgent starts the
server in the command sandbox, writes lifecycle evidence, waits up to 45 seconds
for a same-origin response, and rejects an external redirect.

After QA or any startup failure, the complete process tree is terminated. A
bounded connect plus exclusive bind probes must prove that no child or listener
survived. Unverified cleanup blocks candidate certification.

If `preview_url` is supplied without `start_command`, SiteAgent inspects that
already-running localhost origin but does not establish process ownership,
write managed lifecycle evidence, or stop the server. This unmanaged mode has a
weaker ownership guarantee even though browser evidence and side-effect guards
still apply.

## Browser evidence contract

For file-mode projects, every discovered project-local HTML page is inspected.
For localhost projects, the primary URL plus declared route-like scope entries
are inspected and must remain on the exact configured localhost origin.

The technical inspector installs its safety guard before navigation and retains
it through real unload. It restricts reads to the project root or exact local
origin and neutralizes external HTTP writes, beacons, popups, and WebSockets.
Form evidence requires either a newly visible changed outcome or an honest safe
contact fallback.

Candidate evidence requires, for every route:

- valid screenshots and observations at 1440, 1024, 768, 390, and 360 widths;
- reduced-motion evidence;
- interaction-state screenshots;
- source-tree/session/iteration binding in the browser evidence manifest;
- a passing merged technical gate with no blocking reason.

Baseline or previous-iteration screenshots cannot satisfy current candidate
evidence.

## Reference scope and business-data integrity

A visual reference must resolve to a specific page, section, component, locator,
interpretation, and property allowlist. Automatic analysis may fill missing
fields but cannot replace or broaden a user-supplied boundary. The executor must
provide per-property source evidence and attribute every changed file to an
active requirement. The independent reviewer must confirm property-scope
isolation.

Confirmed contacts, addresses, hours, prices, services, and texts accumulate in
business-data history. Candidate readiness checks their rendered presence when
business data was supplied. New numeric claims must already exist in the
baseline or be supported by the live requirements/business data.

## Candidate gate

`_candidate_allowed()` rejects readiness unless all applicable checks pass,
including:

- no active, open, rejected, or blocked requirement;
- no runtime failure or unresolved implementation/review difference;
- checksum-valid pre-change recovery snapshot;
- passing build/tests and actual authored project changes;
- complete current-route browser and screenshot matrices;
- passing technical, functional, content, animation, responsive, visual, and
  reference-comparison evidence;
- complete functional scenarios;
- applied and rendered confirmed business data;
- no unsupported new numeric claim or placeholder;
- independent `accept` decision with no P0/P1 issue;
- requirement/file attribution and reference-scope/source verification.

When allowed, the session stores checksums for the project tree, live brief,
baseline file and artifact tree, pre-change snapshot marker, every screenshot,
and all required candidate artifacts.

## Explicit acceptance

`accept()` is permitted only from `CANDIDATE_READY`. Before transitioning to
`USER_ACCEPTED`, it revalidates:

- current project tree;
- current live brief;
- baseline file and baseline artifact tree;
- recovery snapshot marker;
- attachment paths and content;
- browser evidence manifest;
- every bound screenshot and candidate artifact.

A project-tree or browser-evidence mismatch, including a bound browser
screenshot mismatch, invalidates the candidate, records the reasons in the
report, clears candidate bindings, and requires new browser QA. A mismatch in
another bound baseline, snapshot, attachment, or artifact refuses acceptance
without promoting the session. Corrupted stored attachments must be restored to
their recorded bytes or replaced through a new session because continuation
revalidates every stored attachment. Acceptance never deploys.

## Crash recovery

The iteration records a pre-change manifest and checksum-complete snapshot
before editing, then a post-change manifest and typed implementation result.
On restart:

- unchanged pre-edit bytes allow the implementation to run;
- bytes matching a complete post-change checkpoint allow QA to resume without
  repeating implementation;
- bytes matching neither checkpoint cause a fail-closed error so unknown edits
  are not overwritten;
- an incomplete baseline may be archived and recaptured only when the project
  still matches its recorded tree.

Do not delete or rewrite recovery evidence to force a status transition.

## Artifact layout

```text
runs/refinement/<session-id>/
  session.json
  inputs/
  baseline/
    baseline.json
    browser/
  baseline_attempts/
  iterations/<NNN>/
    change_plan.json
    pre_change_manifest.json
    pre_change_snapshot/
    implementation/
      schema.json
      result.json
      stdout.log
      stderr.log
      runtime.json
    implementation_result.json
    computed_diff.json
    post_change_manifest.json
    command_evidence.json
    server_lifecycle.json              # when a managed server is used
    browser_qa/
    independent_review/
      schema.json
      result.json
      stdout.log
      stderr.log
      runtime.json
    independent_review.json
    candidate_report.json
    candidate_report.md
```

Some artifacts appear only when their stage is reached. Their absence must be
interpreted through `session.json`, `candidate_report.json`, and runtime
evidence, not silently treated as success.

## Regression boundaries

Changes to this mode must retain tests for:

- CLI routing and configuration isolation;
- append/supersede semantics and immutable acceptance;
- project/attachment/snapshot containment;
- process-level/CWD operation;
- executor/reviewer lifecycle, timeout, redaction, and cleanup;
- five-width route/browser evidence and stale-source rejection;
- localhost/file resource and side-effect isolation;
- endpoint ownership and managed-server cleanup;
- functional outcomes and numeric/business-data claims;
- visual-reference scope/property attribution;
- existing BUILD mode compatibility.

The completion bar remains evidence-based: a build or unit-test pass alone does
not make a refinement candidate ready.
