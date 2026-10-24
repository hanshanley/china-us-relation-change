# Working in this repository

Read `TASKS.md` for the authoritative user-request checklist and
`AGENT-COMMS.md` for active file claims, messages and handoffs before editing.

## Keep working through the full checklist

Work with the other agents toward **all outstanding user requests**, not just
the current subtask. Continue targeting actionable unchecked tasks until their
required outcomes are verified. A source discovery, passing test, commit, push
or handoff is a progress checkpoint, not a reason to stop while actionable work
remains.

After each checkpoint, reread `TASKS.md` and the latest `AGENT-COMMS.md` messages.
Continue the highest-priority unclaimed work, resolve an integration dependency,
or agree the next handoff. Do not duplicate another agent's active work or sit
idle on one blocked item when other tasks can advance.

If a task is blocked, record the concrete blocker, alternatives tried and the
next action/owner; move to another actionable task. Never mark an unavailable
measurement recovered, invent data, bypass an access restriction, or claim the
whole project finished while unresolved tasks remain. Stop only when the user
pauses/redirects work, the requested work is verified complete, or all remaining
work has documented blockers requiring outside input.

## Coordinate through the local communication file

Register your workstream and paths in `AGENT-COMMS.md`. Coordinate overlapping
edits before touching shared files; this checkout is not exclusive to one agent.
Preserve other agents' staged and unstaged work.

Record progress, blockers and integration instructions in `AGENT-COMMS.md`.
Read and respond to other agents' messages; explicitly agree ownership and
integration order, identify the next owner, and release claims when handed off.
Before a release, reconcile all relevant data/code checkpoints with the release
owner rather than deploying competing snapshots.

`AGENT-COMMS.md` is local-only and git-ignored. Create a local coordination file
if absent; never force-add it, publish its contents or include private work
artifacts in a public commit.

## Keep every user request in TASKS.md

Record every new request, correction and screenshot follow-up in `TASKS.md`
before implementation. Use stable IDs, consolidate duplicates and explicitly
note superseding instructions without silently dropping earlier requirements.
Do not keep requests only in chat, agent messages or a competing checklist.

Record verified completion in `TASKS.md`, not in a competing checklist.
Implemented, committed, deployed and live-verified are different states.

## Keep working through the complete request

Work with the other active agents until all requested tasks are completed and
verified. Do not stop merely because a checklist was written, one component
passed tests, a commit was pushed, or a handoff was posted. After a milestone,
update its evidence and move to the next actionable unfinished task.

Read and use `AGENT-COMMS.md` throughout execution, not only at startup. Claim
exact paths, communicate overlapping changes and integration order, post
blockers and results, and coordinate with the release owner before publishing.
Use an isolated candidate while an overlapping edit or release is pending.
Do not duplicate another agent's claimed work or launch competing deployments.
The communication file is local/ignored; do not commit or push it.

Every user request and screenshot follow-up must be represented in `TASKS.md`.
Add a distinct task when it adds scope; otherwise update or reference the
existing task without losing the new requirement. Keep `TASKS.md` as the only
completion checklist, with stable IDs, acceptance conditions, and evidence.

If a task is blocked, record the exact missing permission, unavailable source,
or external dependency, try legitimate alternatives, and continue independent
actionable tasks. Do not fabricate data, silently abandon gaps, or check off a
blocked task. Ask for user input only when it is genuinely required. Stop only
when the user pauses the work, all tasks are verified complete, or no actionable
work remains without a clearly reported external blocker.

For public changes, completion requires the intended commit, deployment and
actual live verification, not just a successful build or workflow. Commit/push
coherent milestones as Hans Hanley without Copilot attribution and preserve
other agents' staged and unstaged changes.
Public-facing tasks need the actual deployed checks before completion; source
recovery and a substitute chart do not close an unresolved data gap.
