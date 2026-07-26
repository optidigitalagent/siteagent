# SITE_REFINEMENT operator guide

`site_refinement` changes an existing local website project without entering
SiteAgent's new-site build, Telegram, Cloudflare, custom-domain, or production
delivery workflows. It keeps one durable session, accumulates feedback, edits
the selected project in place, and requires rendered QA before a candidate can
be accepted.

Acceptance records a decision only. It does not publish a preview or production
site.

## Before you start

You need:

- an existing project directory, or a SiteAgent run ID that resolves to an
  existing site;
- an `index.html`, `package.json`, or `pyproject.toml` project marker;
- a clear change request;
- a local Codex installation for implementation and independent review;
- Playwright Chromium and the repository dependencies already installed.

For a static HTML/CSS/JavaScript bundle, SiteAgent can discover `index.html`
without build commands. A source project must provide its own local build and
test commands. If browser QA needs a development server, provide a start
command and a `localhost` preview URL together.

## Start a session

Static site:

```powershell
python -m site_agent.cli refinement-start `
  --project "C:\work\existing-site" `
  --request "Keep the current identity, rebuild the hero, and tighten the service cards" `
  --entry-path index.html
```

Source project with a managed local server:

```powershell
python -m site_agent.cli refinement-start `
  --project "C:\work\existing-app" `
  --request "Improve the booking flow without changing the brand system" `
  --build-command "npm run build" `
  --test-command "npm test" `
  --start-command "npm run preview" `
  --preview-url "http://127.0.0.1:4173/"
```

The command prints a compact JSON result containing `session_id`, `mode`,
`status`, `open_tasks`, and `blockers`. Save the session ID; all later feedback
and acceptance refer to it.

Use `--session-id` on `refinement-start` only when a stable, unique ID is
needed. Otherwise SiteAgent creates one. Session IDs may contain letters,
numbers, `_`, `-`, and bounded dot-separated segments.

Use `--no-execute` to create or update durable session state without starting
the implementation and QA cycle:

```powershell
python -m site_agent.cli refinement-start `
  --project "C:\work\existing-site" `
  --request "Prepare the hero refinement brief" `
  --no-execute
```

## Continue with more feedback

New feedback is additive. Earlier active requirements remain part of the live
brief:

```powershell
python -m site_agent.cli refinement-continue `
  --session-id existing-site-a1b2c3d4e5 `
  --request "Also reduce the card radius and keep the footer unchanged"
```

Use `--constraint` for a durable restriction and `--scope` to name a page or
route affected by the request. Both options can be repeated.

To replace an earlier requirement, copy its stable ID from `session.json` and
supersede it explicitly:

```powershell
python -m site_agent.cli refinement-continue `
  --session-id existing-site-a1b2c3d4e5 `
  --request "Replace the light hero requirement with a dark hero" `
  --supersede req-0123456789
```

The earlier requirement remains auditable with state `superseded`; it is not
deleted from history.

## Supply files and visual references

Use `--attachment` for a general task file. Use `--reference` for a visual
reference and bound it to the intended part of the site:

```powershell
python -m site_agent.cli refinement-continue `
  --session-id existing-site-a1b2c3d4e5 `
  --request "Use this composition for the home hero" `
  --reference "C:\brief\hero-reference.png" `
  --reference-page home `
  --reference-section hero `
  --reference-interpretation "Transfer only the split composition and spacing" `
  --reference-transfer composition `
  --reference-transfer spacing
```

`--reference-match` accepts `visual_direction` (default) or `exact`. A reference
cannot silently expand from its recorded component to other sections. When the
mapping is incomplete, SiteAgent performs a persisted read-only analysis and
blocks if it cannot establish a safe, specific scope.

Attachments are copied into the session and checksum-bound. Later changes to a
stored attachment invalidate its use.

## Use a structured input file

`--input-json` is useful for several files, confirmed business data, immutable
elements, or multiple test commands. The file is validated as
`RefinementRequest`.

```json
{
  "project": "C:\\work\\existing-app",
  "goal": "Improve the booking journey without changing the accepted identity",
  "feedback": [
    "Make the primary booking action visible in the first mobile viewport"
  ],
  "business_data": {
    "contacts": ["+000 000 000"],
    "address": "",
    "hours": [],
    "prices": [],
    "services": ["Consultation"],
    "texts": [],
    "other": {}
  },
  "constraints": ["Keep the existing logo and footer navigation"],
  "immutable_elements": ["Existing analytics markup"],
  "scope": ["/", "/booking"],
  "preview_url": "http://127.0.0.1:4173/",
  "build_command": "npm run build",
  "start_command": "npm run preview",
  "test_commands": ["npm test"],
  "attachments": [
    {
      "path": "C:\\brief\\booking-reference.png",
      "kind": "reference",
      "target_page": "booking",
      "target_section": "booking form",
      "target_component": "form shell",
      "target_locator": "main form",
      "target_properties": ["composition", "spacing"],
      "target_properties_explicit": true,
      "match_kind": "visual_direction",
      "interpretation": "Use only the grouping and spacing rhythm",
      "transfer": ["composition", "spacing"]
    }
  ]
}
```

Start or continue with the file:

```powershell
python -m site_agent.cli refinement-start --input-json "C:\brief\request.json"
python -m site_agent.cli refinement-continue `
  --session-id existing-site-a1b2c3d4e5 `
  --input-json "C:\brief\follow-up.json"
```

Direct CLI values are merged into the loaded request. For example, an extra
`--request` becomes another feedback item.

## Understand the result

The durable state is stored in:

```text
runs/refinement/<session-id>/
```

Important files are:

- `session.json` — live brief, requirements, status, blockers, configuration,
  and candidate bindings;
- `inputs/` — copied and checksum-bound user files;
- `baseline/` — pre-edit project inventory and rendered baseline;
- `iterations/<NNN>/pre_change_snapshot/` — recovery copy for that iteration;
- `iterations/<NNN>/change_plan.json` — requirements and reference scope;
- `iterations/<NNN>/computed_diff.json` — actual authored file changes;
- `iterations/<NNN>/implementation_result.json` — structured implementation
  result;
- `iterations/<NNN>/browser_qa/` — route and five-width screenshots plus
  technical evidence;
- `iterations/<NNN>/independent_review.json` — read-only critic decision;
- `iterations/<NNN>/candidate_report.md` and `.json` — human-readable and
  machine-readable readiness reports.

Check the current state at any time:

```powershell
python -m site_agent.cli refinement-status `
  --session-id existing-site-a1b2c3d4e5
```

Common statuses:

| Status | Meaning |
| --- | --- |
| `INTAKE_INCOMPLETE` | Session exists but has not completed baseline and execution. |
| `IMPLEMENTING` | The current brief needs implementation or another fixer pass. |
| `BLOCKED` | A fail-closed requirement, runtime, evidence, or external-data blocker remains. |
| `CANDIDATE_READY` | The current project and QA evidence are checksum-bound and pass all candidate gates. |
| `USER_ACCEPTED` | The user explicitly accepted the unchanged candidate. The session is immutable. |

Intermediate baseline and QA statuses are also preserved in `status_history`.

## Accept a candidate

Review the site and the current checksum-bound `candidate_report.json`. The
adjacent `candidate_report.md` is a readable convenience summary, but it is not
an acceptance-authority artifact. Then run:

```powershell
python -m site_agent.cli refinement-accept `
  --session-id existing-site-a1b2c3d4e5
```

Acceptance succeeds only from `CANDIDATE_READY`. It revalidates the project
tree, live brief, baseline, recovery snapshot, screenshots, and bound QA
artifacts. A project-tree or browser-evidence mismatch, including a bound
browser screenshot mismatch, invalidates the candidate and requires a new
refinement/QA iteration. A mismatch in another bound baseline, snapshot,
attachment, or artifact also refuses acceptance; inspect the error before
recovery. A changed stored attachment must be restored to its recorded bytes or
replaced through a new session because the current session revalidates every
stored attachment before continuing.

`USER_ACCEPTED` does not deploy or notify anyone. Publishing remains a separate,
explicitly authorised action outside `site_refinement`.

## Recover from a blocker

1. Run `refinement-status` and inspect `blockers`.
2. Open the latest authoritative `candidate_report.json`, its readable
   `candidate_report.md` companion, and the referenced runtime/browser evidence.
3. Correct the missing local input, project problem, or command configuration.
4. Continue the same session with new feedback. If a recorded blocker is now
   resolved, pass its exact text with `--resolve-blocker`.
5. Let SiteAgent run a fresh implementation and QA cycle.

Do not delete the session or its snapshots to clear a blocker. If an interrupted
iteration left unknown project edits that match neither the saved pre-change nor
post-change manifest, preserve the artifacts and resolve that divergence before
running another implementation pass.

## Troubleshooting

`Existing site project was not found`

- Pass a project directory or run ID that resolves to a directory with
  `index.html`, `package.json`, or `pyproject.toml`.

`Source project requires an explicit build command`

- Add `--build-command` and at least one `--test-command`. Static bundles do not
  need them.

`No browser target found`

- Add `--entry-path` for a static file, or use `--start-command` with a
  `localhost` `--preview-url`.

`Managed preview port already has a listener`

- Stop the existing process or choose an unused localhost port. SiteAgent will
  not start and lifecycle-certify its managed server over an existing listener.
  If only `--preview-url` is supplied without `--start-command`, SiteAgent can
  inspect an already-running localhost server, but it does not prove ownership
  or clean up that process. Use a managed start command when server ownership is
  part of the evidence you require.

`Refinement commands require the native Codex sandbox executable`

- Install a compatible Codex CLI or configure the supported native executable.
  The workflow fails closed when command isolation is unavailable.

`Candidate project changed after QA`

- Keep the manual edit, add it as feedback if appropriate, and run another
  refinement cycle. Acceptance cannot reuse stale screenshots.

`An accepted session is immutable`

- Start a new session for subsequent work on the accepted project.

## Safety boundaries

- Only a local file inside the selected project or a
  `localhost`/`127.0.0.1` origin can be browser-tested. Localhost may be managed
  by `start-command` or supplied as an already-running unmanaged preview.
- SiteAgent parses and starts the top-level build, test, and start argv without
  a shell. Package-manager scripts may use their normal lifecycle shell inside
  the restricted Codex sandbox. A lexical defense-in-depth guard rejects the
  enumerated deployment, publishing, network, VCS, infrastructure, and
  destructive command forms; it is not a general script analyzer.
- Refinement child environments omit deployment and Telegram credentials and
  force local, non-publishing hosting settings.
- Browser QA blocks external writes, beacons, popups, and WebSockets while it
  inspects load, interactions, and unload.
- Project links, resources, attachments, snapshots, and evidence must remain
  inside their declared roots; symlinks and junctions fail closed.

For the state machine, integrity model, runtime evidence, and acceptance
algorithm, see [SITE_REFINEMENT_TECHNICAL.md](SITE_REFINEMENT_TECHNICAL.md).
