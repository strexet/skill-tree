These repository skills are installed:

- `skill-tree-unity-repo-documentation` handles Unity repository documentation initialization, audit, and repair.
- `skill-tree-process-future-pending` handles `Process pending` and `Process pending tasks` by researching the Pending Queue and promoting only implementation-ready work.
- `skill-tree-implement-next-future-task` handles `Implement next` and `Implement next: <task name>` by selecting exactly one task from `Prioritized Next Changes`.
- `skill-tree-unity-repo-documentation-audit` handles ongoing documentation audit against current code and tests.
- `skill-tree-create-documents-snapshot` handles explicit-request-only Markdown documentation snapshot archives.

`Implement next` never selects from `Pending Queue` or `Backlog`. It never falls back to Backlog when a named prioritized task is absent.

Blocking unresolved questions in a prioritized task stop implementation until the owner answers them.

For `Process pending` or `Implement next`, read repository rules, current docs, task-relevant code, and tests before editing. Never use `FUTURE.md` as the sole implementation source.
