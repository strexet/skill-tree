---
name: skill-tree-implement-next-future-task
description: Implement exactly one task from the Prioritized Next Changes section of FUTURE.md. Use for "Implement next", "Implement next feature", "Implement next: <task name>", or "Implement next feature: <task name>". Never select from Pending Queue or Backlog, and stop for blocking unresolved questions or when a named prioritized task is absent.
license: MIT
---

# Skill-Tree: Implement Next Task

Use this skill to implement exactly one eligible task from `Prioritized Next Changes`.

Never select from Pending Queue or Backlog. Never use Backlog as hidden implementation context for a missing named task.

## Selection

Without a task name:

1. Open `FUTURE.md`.
2. Select the first task in `Prioritized Next Changes`.
3. Stop if that section is empty.
4. Do not skip a blocked first task automatically.
5. Perform the clarification gate before editing.

With a task name:

1. Search only prioritized headings.
2. Normalize heading comparison by Unicode normalization, trim, whitespace collapse, and case folding.
3. Require one unambiguous match.
4. Stop if absent.
5. Stop if duplicate normalized matches exist.
6. Never fall back to a similarly named pending or backlog item.
7. Perform the clarification gate before editing.

Use the local selector when helpful:

```bash
python3 scripts/select_prioritized_task.py /path/to/Documents/FUTURE.md
python3 scripts/select_prioritized_task.py /path/to/Documents/FUTURE.md --name "Task Name" --format json
```

## Clarification Gate

Before editing:

1. Read the complete selected task.
2. MUST read repository `AGENTS.md`, `Documents/RULES.md`, or equivalent repository rules.
3. MUST read repository/document map if one exists.
4. MUST inspect all documents referenced by the task.
5. MUST read current-state docs such as `FEATURES.md` and task-relevant architecture/domain docs.
6. MUST inspect current code and tests for affected paths and symbols.
7. MUST check for recent changes that invalidate task assumptions or make the work already complete.
8. MUST check existing `FUTURE.md` tasks for duplicate or overlapping work.
9. Read `Questions and required clarifications`.
10. Identify unresolved blocking questions.
11. Ask the owner those questions.
12. Stop implementation until answers exist.
13. Update the task with answers or stale assumptions before implementation.

Do not guess to keep moving.
MUST NOT implement from `FUTURE.md` alone.

## Scope

- Honor `Touch`.
- Honor `Discovery allowance`.
- Honor `Out of scope`.
- Update the task before justified scope expansion.
- Avoid opportunistic refactors.
- Add or update tests appropriate to the task.
- Update current-state documentation when behavior ships.
- Keep `FEATURES.md` current-state only. Move new plans, deferred work, or known bugs awaiting fixes to `FUTURE.md`.
- Remove the completed task from `FUTURE.md` instead of keeping completed entries indefinitely.
- Report required context inspected and checks actually run.

## Completion

Complete only after one selected task is implemented, relevant docs are updated, validations are reported, and the task is removed from `FUTURE.md`.
