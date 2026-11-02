---
name: skill-tree-implement-all
description: "Implement an initial prioritized snapshot and required dependencies with resumable checkpoints; defer new nonblocking work."
license: MIT
---

# Skill-Tree: Implement All

Read applicable rules, [orchestration](references/orchestration.md) and [metadata](references/workflow-metadata.md). Query the index/checkpoint first. Start mode all only when no active run exists; otherwise resume. Use scripts/workflow-state.py advance before handoffs. After scoped processing, automatically choose the recommended eligible unit inside the recorded root/snapshot boundary; routine next-action questions apply only to standalone processing. Material questions and execution stops remain binding. Follow bundled [intake](references/pending-task-intake.md) and [processing/implementation](references/future-workflow.md) contracts; read [Unity safety](references/unity-safety.md) only for Unity work. Query compact history only when relevant. Return completed/deferred/blocked IDs, checks and next action. No scheduler or blanket execution permission is implied.

Generated prose follows [document rules](references/document-rules.md). No unrelated changes, implicit permission or source/sibling dependency.
