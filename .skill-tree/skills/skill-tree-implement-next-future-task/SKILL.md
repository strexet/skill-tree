---
name: skill-tree-implement-next-future-task
description: "Implement the highest-priority Prioritized task or an exact task ID/name; capture findings and record acceptance evidence before completion."
license: MIT
---

# Skill-Tree: Implement Next Task

Read repository rules, [workflow](references/future-workflow.md), [metadata](references/workflow-metadata.md), selected task questions, current documentation and task-relevant source/tests. Use scripts/workflow-state.py select: highest priority wins, ties follow document order; exact IDs/names never fall back. A blocked selection stops. Implement minimal scoped changes and capture findings through intake with root/direct-parent context. Perform authorized validation and review, update current documentation, then complete with individual acceptance/source evidence. Required unrun checks prevent completion. Record authorized commits only after commit creation. Return completed/needs-dependencies/needs-clarification/validation-blocked outcome and captured IDs. Never implement from the queue alone.

Generated prose follows [document rules](references/document-rules.md). No unrelated changes, implicit permission or source/sibling dependency.
