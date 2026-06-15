# Future Workflow Standard

This shared standard is the general parent contract for `FUTURE.md` task intake, pending processing, and implement-next execution.

## Required Sections

`FUTURE.md` must contain:

```text
## Pending Task Format
## Pending Queue
## Prioritized Next Changes
## Backlog
```

`Pending Task Format` must contain the nested Markdown template from `PENDING_TASK_FORMAT.md`.

## Queue Semantics

`Pending Queue` is raw intake. Pending entries are not implementation-ready and must be researched before implementation.

`Prioritized Next Changes` is the only implementation queue. Items higher in this section have higher priority.

`Backlog` is deferred work. Implementation commands must never select work directly from `Backlog`.

Documentation or audit findings discovered during repository documentation work belong in `Backlog`, not `Pending Queue`, unless the owner explicitly asks to capture them as pending intake.

## Process Pending

When processing pending work:

1. Read repository `AGENTS.md`, `RULES.md`, or equivalent rules.
2. Read repository/document map if one exists.
3. Read current `FEATURES.md`, active `FUTURE.md`, and task-relevant architecture/domain docs.
4. Read the complete `Pending Queue`.
5. Inspect current implementation, configuration, data files, tests, history, and docs as needed.
6. Verify referenced paths and symbols still exist.
7. Check whether each request is already implemented, obsolete, duplicated, contradictory, or blocked.
8. Check existing `FUTURE.md` tasks for overlap.
9. Merge overlapping pending entries only when no intent is lost.
10. Expand valid requests into detailed prioritized tasks using current evidence.
11. Add `Questions and required clarifications:` to every promoted task.
12. Resolve questions from repository evidence where possible.
13. Mark answers as verified, inferred, recommended, or unresolved.
14. Move only implementation-ready entries into `Prioritized Next Changes`.
15. Leave blocked or insufficiently understood entries in `Pending Queue` with missing information.
16. Remove original pending entries only after preserving their information.
17. Report rules, documents, code paths, data/config files, and tests inspected.

Processing pending work is research and documentation work. It does not implement tasks unless the user explicitly combines the commands.

MUST NOT process pending work from `FUTURE.md` alone. Stop or mark the item blocked when required repository context is missing or contradictory.

## Implement Next

Without a task name, select the first task in `Prioritized Next Changes`.

With a task name, search only `Prioritized Next Changes` headings. Use exact normalized matching unless repository rules define aliases. Stop when no match or multiple normalized matches exist.

Never fall back to:

- the first prioritized task when a named task is absent;
- a similarly named backlog task;
- a pending entry;
- repository TODOs;
- inferred work.

Before editing, read repository rules, task-relevant docs, current-state docs, code, tests, data/config files, and the selected task's complete `Questions and required clarifications` section.

MUST NOT implement from `FUTURE.md` alone.

Blocking unresolved questions stop implementation until the owner answers them.

## Prioritized Task Template

```text
### Task Title

Priority:
Status: Ready | Blocked pending answers
Origin:
Evidence:
Goal:

Current behavior:
- ...

Desired behavior:
- ...

Touch:
- ...

Discovery allowance:
- ...

Dependencies:
- ...

Out of scope:
- ...

Implementation constraints:
- ...

Possible implementation approaches:
1. ...
2. ...

Recommended approach:
- ...

Implementation notes:
- ...

Data, persistence, and migration:
- ...

Platform considerations:
- ...

Failure handling and recovery:
- ...

Diagnostics and observability:
- ...

Questions and required clarifications:
- [Resolved - repository evidence] ...
  Answer:
  Evidence:

- [Recommended default - confirmation optional] ...
  Recommendation:
  Rationale:

- [Unresolved - blocks implementation] ...
  Why it matters:
  Required answer from:

Validation:
- ...

Acceptance:
- ...

Documentation updates:
- ...

Risks:
- ...
```

Every prioritized task must include at least `Goal`, `Current behavior`, `Desired behavior`, `Touch`, `Discovery allowance`, `Out of scope`, `Implementation constraints`, `Questions and required clarifications`, `Validation`, `Acceptance`, `Documentation updates`, and `Risks`.
