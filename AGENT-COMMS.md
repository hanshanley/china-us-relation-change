# Agent communication and handoffs

Updated: October 24, 2026.

Use this file to coordinate agents and separate CLI sessions sharing this
repository. `TASKS.md` remains the single authoritative user-request checklist.
This file is for ownership, messages, blockers and handoffs, not duplicate
completion checkboxes.

## Coordination protocol

1. Read the active claims and recent messages before editing or publishing.
2. Register a short, stable agent/workstream name, task IDs and exact paths.
   Claim only the work you are actually doing. Unknown ownership is not
   permission to overwrite existing changes.
3. If a path overlaps another claim, post a message specifying the proposed
   section/change and agree on an integration order. Work in an isolated
   candidate while coordination is pending.
4. Preserve other agents' staged and unstaged changes. Stage exact owned paths
   or use an isolated index; do not commit the entire shared worktree.
5. Record meaningful progress, a blocker, a proposed integration or a handoff.
   Include the base commit, actual validation results and remaining failures.
   Do not describe implemented code as deployed or verified.
6. Before committing, recheck HEAD and overlapping files. Before deploying,
   check the release owner and active workflow so agents do not publish
   competing snapshots.
7. After completion, record the commit/deployment/verification evidence, release
   your claims and update the matching IDs in `TASKS.md`.

A file is durable communication, not a locking service. Recheck it and Git
immediately before touching an overlapping path. Add new messages below; do not
silently rewrite another agent's message or mark its work finished.

## Active claims

| Agent / workstream | Task IDs | State | Claimed scope |
|---|---|---|---|
| `chart-repair` (current CLI session) | UI-01, UI-04, UI-05, UI-06; related VERIFY gates | Final validation in progress; not released | Bilateral route-state renderer, direction colours, missing-year interactions, COVID label/geometry and their checks; exact paths below |
| Other agents | Register actual IDs here | Not registered in this file | Add your own scope before editing; do not infer ownership from this placeholder |

### `chart-repair`: exact paths and handoff

Shared code hotspots:

- `src/us_china_exchange/theme.py`
- `src/us_china_exchange/render.py`
- `src/us_china_exchange/static/app.js`
- `src/us_china_exchange/static/publication.js`
- `src/us_china_exchange/covid_context.py`
- `scripts/build_exchange_publication.py`
- `scripts/audit_exchange_plots.py`
- `scripts/check_exchange_publication.py`
- `scripts/check_public_freshness.py`
- `tests/test_exchange_site.py`
- Snapshot-bar assertions in `tests/test_exchange_tourism_backfill.py`
- Direction/style documentation in `docs/EXCHANGE.md`

These claims cover the described sections, not unrelated language, Business or
source-recovery edits in the same files. Coordinate overlapping sections.

Candidate and evidence:

- Frozen candidate: `data/local/bilateral-repair/release-source/`.
- Candidate base: `b168790`.
- Candidate public build: `data/local/bilateral-repair/release-publication/`.
- Final test log: `data/local/bilateral-repair/release-tests.log`.
- Earlier integration evidence: `data/local/bilateral-repair/integrated-screens/`
  and `integrated-tests.log` in the same directory.
- Private index: `data/local/bilateral-repair/release.index`.
- Full regression and final public audit are still pending final reconciliation;
  do not treat an earlier passing candidate as the final live release.
- Latest frozen-candidate suite: **322 passed, 2 failed**. Remaining failures
  are snapshot-rendering assumptions in
  `test_figure_background_variants_preserve_data_and_foreground` and
  `test_archival_services_are_not_compared_with_a_newer_revision_vintage`.
  The candidate intentionally removes empty line paths from snapshot bars;
  update assertions to inspect the actual bars without weakening value checks.
- Earlier integrated checks passed repeated toggles, reverse navigation,
  missing-year tooltips and COVID-band alignment at 1360px, 390px and 320px.
- The final freshness checker initially expected the old COVID label exactly.
  Its assertion has been updated to include the explicit `2020-22` period;
  the final checker/audit must be rerun.
- **Latest request to integrate:** UI-11 removes the redundant reverse button.
  Keep both directions in the dropdown. The existing repair candidate's
  button-click regression must be updated before integration; do not restore
  the rejected button merely to make that test pass.

The local runtime shell IDs are session-specific. Other sessions should inspect
the durable logs and candidate files rather than assume those shell IDs are
available to them.

## Messages

### MSG-001 | 2026-10-24 | `chart-repair` -> renderer/publication agents

The repair publishes one authoritative selection from `app.js` using
`chart.exchangeState` and the `exchange:render` event. `publication.js` consumes
that state rather than refiltering the raw dataset or inferring bar style from
the previously rendered SVG. Preserve this wiring when integrating UI changes.

`FLOW_COLORS` distinguishes China-to-U.S. maroon from U.S.-to-China blue in
interactive charts and both export themes. Preserve the same mapping in the
regional plots and their independent audit.

Status: in progress; release evidence must still be recorded.

### MSG-002 | 2026-10-24 | `chart-repair` -> UI-11 owner / all agents

The current user-request ledger explicitly rejects the additional reverse
button. Remove that button, not the direction dropdown or reverse data.
Coordinate edits to `app.js`, the public builder and toggle checks with MSG-001.
The repaired dropdown state handling must remain intact.

Status: integration required.

### MSG-003 | 2026-10-24 | `chart-repair` -> data-recovery agents

Keep independently recovered language/immigration observations and their
provenance separate from this presentation repair. The repair must not replace
unavailable U.S.-to-mainland annual immigration with resident stocks, nor replace
old mainland enrollment with newer credit-study-abroad counts. Those are distinct
open or separately completed entries in `TASKS.md`.

Known committed context: annual admissions in `0c8cf49`, freshness/basic COVID
presentation in `2a4c646`, and separate MLA/HESA evidence in `1cad87d`.
Their later integration and live verification must be recorded by the actual
workstream owner.

Status: preserve during integration; not a blanket completion claim.

## Add a claim or handoff

Copy this template, replace the placeholders, and keep it concise:

```text
Agent:
Date:
Task IDs:
State: planned / editing / validating / ready-to-integrate / blocked / released
Exact paths and sections:
Base commit:
Changes:
Validation actually run:
Remaining failures or unavailable data:
Message/request for another agent:
Commit / deployment / live verification, if available:
Next owner/action:
Claims released:
```
