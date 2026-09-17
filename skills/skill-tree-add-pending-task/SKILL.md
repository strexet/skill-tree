---
name: skill-tree-add-pending-task
description: >
  Turn a vague or informal user request into one concise, context-grounded task
  in FUTURE.md Pending Queue, clarifying missing intent before writing and
  recording priority and queue placement. Use for "Add pending: <idea>",
  "Add this to the pending queue", or "Capture this feature request".
  Do not use for Process pending, implementation, documentation audits, or
  casual brainstorming without a request to record a task.
license: MIT
---

# Skill-Tree: Add Pending Task

Capture understood intent, not an implementation plan. This general skill also works in Unity repositories; obey their local rules without launching Unity.

## Lightweight intake

1. Confirm the target repository and locate its live `FUTURE.md` using its entry point or document map. Ask if the repository/document is ambiguous or missing; do not initialize a documentation system as part of intake.
2. Read applicable repository rules, the local `Pending Task Format`, and [intake rules](references/PENDING_TASK_INTAKE.md). Use [the shared format](references/PENDING_TASK_FORMAT.md) only as a fallback or for fields the local template does not define.
3. Read only relevant portions of current-state docs, such as `PROJECT.md`, `FEATURES.md`, the repository map or one specialized doc. Check the queues for obvious duplicates and overlap. Inspect a narrow source location only when needed to identify the subject; leave deep code/asset/test/external research to `Process pending`.
4. Establish what should change, where it applies and the intended observable outcome. Ask focused questions if missing or conflicting intent would produce different tasks. Wait for required answers; do not insert a guessed task while waiting. Technical choices may remain deferred when the goal is clear.
5. Determine priority and placement from the user's wording and local conventions. Default to Highest and first in Pending Queue. Honor explicit lower priority or relative placement. Ask only if conflicting instructions or an unclear queue convention leave placement ambiguous.
6. Write one concise nested-list entry in Pending Queue using the local format and the intake reference. Record priority/placement, a clear description and expected behavior, plus relevant context and the original request. Add only useful optional sections. Mark documentation-based assumptions and technical questions to verify later.
7. Review the diff: only the intended Pending Queue entry changed, other entries retain their relative order, and no prioritized or backlog task moved. Report the title, priority, placement and any deferred detail; show the resulting entry when helpful.

## Boundaries

- Do not implement, promote tasks, mark intake `Ready`, reorder existing tasks, or process the rest of the queue.
- Do not silently duplicate or merge an existing task. If an obvious match exists, show it and ask whether to update it, create a distinct task, or leave it unchanged; an explicit update request permits only that entry's change.
- Do not invent architecture, API names, asset paths, numeric priority scales, acceptance rules or product behavior. Preserve the user's exact constraints and supplied examples.
- One coherent request becomes one entry. Ask how to split independent requests if the intended grouping is unclear.
- No builds, tests, Unity launch, commits or publishing are implied by intake. No source repository or sibling skill is required after installation.

## Completion

Complete when understood intent is recorded once in the correct Pending Queue, with explicit priority and explained placement, without expanding into prioritized-task research. If required intent or placement is still unresolved, ask the specific question and leave the queue unchanged.
