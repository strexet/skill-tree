---
name: skill-tree-unity-process-future-pending
description: >
  Process the Pending Queue in a Unity repository FUTURE.md. Use when asked to
  "Process pending" or "Process pending tasks" in a Unity project: research each
  pending request, validate it against code, assets, settings, docs, and tests,
  add implementation questions, and promote only implementation-ready work into
  Prioritized Next Changes. Do not implement tasks or promote Backlog work unless
  explicitly requested.
license: MIT
---

# Skill-Tree-Unity: Process Pending Tasks

Use this skill only for `Process pending` and `Process pending tasks`.

Processing pending work is research and documentation work. Do not implement features unless the user explicitly combines the commands.

## Required Workflow

1. Locate the applicable `FUTURE.md`.
2. MUST read repository `AGENTS.md`, `Documents/RULES.md`, and equivalent repository rules.
3. Read `references/COMMON_FUTURE_WORKFLOW.md`, `references/FUTURE_TASK_STANDARD.md`, `references/PENDING_TASK_FORMAT.md`, and `references/PENDING_PROCESSING_CHECKLIST.md`.
4. MUST read repository/document map if one exists.
5. MUST read current `FEATURES.md`, active `FUTURE.md`, and task-relevant architecture/domain docs.
6. Read the complete Pending Queue.
7. MUST inspect affected implementation, serialized assets, settings, tests, and docs before changing tasks.
8. MUST verify whether each item is already implemented, stale, duplicate, contradictory, blocked, or valid.
9. MUST verify referenced paths and symbols still exist.
10. Check existing `FUTURE.md` tasks for overlap and merge only when requests describe the same coherent change.
11. Expand valid items to the full prioritized-task standard with current code/test paths.
12. Add `Questions and required clarifications:` to every promoted task.
13. Resolve questions from evidence where possible and mark the answer state.
14. Mark blocking unresolved questions explicitly.
15. Move only sufficiently researched, implementation-ready tasks.
16. Preserve priority placement.
17. Leave insufficiently understood items in Pending Queue with missing information.
18. Run `scripts/validate_future_document.py` when validation is allowed.
19. Report required context inspected plus promoted, retained, merged, removed, and blocked items.

MUST NOT process pending work from `FUTURE.md` alone. Stop or mark the item blocked when required repository context is missing or contradictory.

## Boundaries

- Do not process Backlog unless explicitly requested.
- Do not write product code.
- Do not promote lightly expanded bullets.
- Do not omit task-specific implementation questions.
- Do not silently guess architecture, ownership, tests, or conventions.

## Local Validator

```bash
python3 scripts/validate_future_document.py /path/to/Documents/FUTURE.md
python3 scripts/validate_future_document.py /path/to/Documents/FUTURE.md --strict --format json
```

## Completion

Complete when every Pending Queue item has been researched and either promoted with a full task contract or retained with a clear blocker.
