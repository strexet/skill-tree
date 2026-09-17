These Skill Tree repository skills may be installed:

- `skill-tree-repo-documentation` handles general repository documentation initialization, audit, and repair.
- `skill-tree-repo-documentation-audit` handles general documentation audit against current code, tests, configuration, and docs.
- `skill-tree-add-pending-task` handles lightweight informal-request intake into Pending Queue, with clarification and priority/placement; it also works in Unity repositories.
- `skill-tree-process-future-pending` handles general `Process pending` and `Process pending tasks` workflows.
- `skill-tree-implement-next-future-task` handles general `Implement next` and `Implement next: <task name>` workflows.
- `skill-tree-create-documents-snapshot` handles general explicit-request-only Markdown documentation snapshots.
- `skill-tree-unity-repo-documentation` handles Unity repository documentation initialization, audit, and repair.
- `skill-tree-unity-repo-documentation-audit` handles Unity documentation audit against current Unity code, assets, settings, tests, and docs.
- `skill-tree-unity-process-future-pending` handles Unity `Process pending` workflows.
- `skill-tree-unity-implement-next-future-task` handles Unity `Implement next` workflows.
- `skill-tree-unity-create-documents-snapshot` handles explicit-request-only Unity Markdown documentation snapshots.

Prefer Unity-prefixed skills for Unity-specific workflows. Use portable `skill-tree-add-pending-task` for intake in either repository type; prefer the other non-Unity skills for general repositories.

`Add pending: <idea>` adds one understood, concise request. Default priority is Highest and first in Pending Queue; explicit priority/placement overrides it. Clarify missing intent before writing. Intake does not run `Process pending` or implement features.

`Implement next` never selects from `Pending Queue` or `Backlog`. It never falls back to Backlog when a named prioritized task is absent.

Blocking unresolved questions in a prioritized task stop implementation until the owner answers them.

For `Process pending` or `Implement next`, read repository rules, current docs, task-relevant code, and tests before editing. Never use `FUTURE.md` as the sole implementation source.
