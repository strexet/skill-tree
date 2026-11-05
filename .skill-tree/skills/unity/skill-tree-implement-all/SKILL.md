---
name: skill-tree-implement-all
description: "[unity] Implement all prioritized tasks or an explicitly selected group with required dependencies and resumable checkpoints; defer new nonblocking work."
license: MIT
---

# Skill-Tree: Implement All

Flavor: unity. Read the [concrete project profile](references/project-profile.md).

Read repository-owner rules before action. Exact prioritized selection, required dependency scope, checkpoint integrity, truthful evidence, owner authorization and commit/publication boundaries remain mandatory. A profile, installed flavor or stored checkpoint grants no execution or continuation permission. Read [validation policy](references/validation-policy.md) and [installation profile](references/installation-profile.md).

Read applicable rules, [orchestration](references/orchestration.md) and [metadata](references/workflow-metadata.md). Query the index/checkpoint first. Select an existing run explicitly for resume, or start mode all for a new isolated run. For an owner-selected group, pass the exact Ready T- IDs as snapshot_ids in the start JSON; omission selects the full initial prioritized queue. Report the frozen roots and required dependencies; preserve the recorded group on resume. Use scripts/workflow-state.py advance before handoffs. After scoped processing, automatically choose the recommended eligible unit inside the recorded root/snapshot boundary; routine next-action questions apply only to standalone processing. Material questions and execution stops remain binding. Follow bundled [intake](references/pending-task-intake.md) and [processing/implementation](references/future-workflow.md) contracts. Query compact history only when relevant. Return completed/deferred/blocked IDs, checks and next action. No scheduler or blanket execution permission is implied.

Generated prose follows [document rules](references/document-rules.md). No unrelated changes, implicit permission or source/sibling dependency. Read [development practices](references/development-practices.md) for test-oracle and behavior-preservation decisions.

Read [run workspaces](references/run-workspaces.md) before source changes. Use one branch/worktree for the entire admitted root/snapshot, resolve canonical queue authority and atomically claim tasks/resources. New runs default to the current remote develop and require a separate workspace. Preserve multiple runs and explicit resume selection. Implementation acceptance offers local result, [PR review/fix](references/pr-review-cycle.md), or PR review/fix with authorized merge; no offer starts publication. Execute a recorded full-path instruction without repeated permission questions and retain separate implementation/publication outcomes.

Prefer deterministic logic and UTF EditMode assertions. Focused PlayMode fixtures cover lifecycle, frames, physics and coroutines. Preserve serialized identity and pinned packages. Verify exact Editor ownership, save/service isolation, authorization, deadlines and cleanup before execution. Player builds, device runs and external services require matching scope. Read [Unity safety](references/unity-safety.md). Read [Unity development](references/unity-development.md) for test seams, lane selection and lifecycle cleanup.

Use the [uGUI checks](references/ugui-testing.md) for the admitted Canvas surfaces.
