<!-- GENERATED FILE; Source: skill-tree/common/references/future-workflow.md; generator: skill-tree/scripts/sync-skill-references.py -->

# Future Task Workflow

## Queue responsibilities

Pending Queue contains understood intake awaiting research. Prioritized Next Changes contains researched executable tasks. Backlog contains deferred issues and investigations. The agent never selects implementation work from Pending Queue or Backlog.

## Process Pending

Resolve optional Pending IDs or exact normalized names before mutation; no input selects the Pending Queue. Absent/ambiguous selections stop without fallback. Read repository rules, document map, relevant current documentation, implementation, configuration, assets/data, tests and source history when needed. Never process from future.md alone.

Verify scope, duplicates, existing behavior, dependencies, observable outcomes, failure paths and validation availability. Split excessive tasks into independently executable units; retain every originating Pending ID. Merge only compatible intent and relationship context. Clarify product choices with contextual options and recommendations. Missing mandatory context remains Pending with an explicit blocker. Promote only Ready work; record created/reused/retained/resolved identities. No implementation is implied.

## Processing Result and Next Action

After researched dispositions, read the refreshed index and report created/reused/retained/resolved IDs. Print the current Prioritized Next Changes in descending integer priority, preserving document order for ties. Each row includes ID, title, priority, a brief intended result and Ready/Blocked state; identify unmet dependencies and material decisions. Retained Pending blockers remain a separate concise summary. Empty or unchanged queues require explicit reporting, not invented implementation work.

Standalone Process Pending stops after research and reporting. Present available next actions, including implementation of a selected task, research/clarification of retained work, another requested action or stopping. Place exactly one recommended action last, below the prioritized list and other action choices. Recommend the highest-ranked executable scoped task through Work Through Next with an exact ID and an evidence-based reason. A higher-ranked blocked task remains visible with the reason for the recommendation; no task is silently skipped or reprioritized. If no executable task exists, recommend the concrete missing decision/dependency research instead of implementation.

Ask the developer to choose a task ID or another action. Wait for an actual answer before implementation or root-run creation; silence, preselection, readiness and the recommendation establish no implementation instruction. Use a structured next-action question when available, preserving the recommendation as the final presented action; a free-text-only question avoids a UI-required option order. The question includes concise processing results, available task context and the recommendation. The task-choice handoff grants no execution or commit permission.

Process Pending invoked by an explicitly launched or explicitly resumed Work Through Next/Implement All controller returns the scoped processing receipt to the controller. The controller automatically chooses the recommended eligible next unit through checkpointed advance/next selection, without a routine next-action question. Eligible work remains restricted to the selected root's required closure or the frozen Implement All snapshot plus required descendants. Global queue recommendations cannot replace the root, expand the snapshot or implement deferred findings. Captured nonblocking findings process once at flow completion and remain deferred.

An active checkpoint alone supplies no instruction to resume implementation after a standalone Process Pending request. Explicit controller invocation determines automatic-continuation context. Material clarification questions, unsafe isolation, mandatory validation failures without a repair path, an exhausted optional task-specific budget, repeated unchanged failures and no-progress/dependency-cycle stops remain binding in every mode. Completed flows report outcomes and deferred next choices; completed flows never automatically start another root or snapshot.

## Implement Next

Select the highest integer priority in Prioritized Next Changes; document order breaks ties. Explicit task ID/name selects only an exact prioritized match. Absent/ambiguous or blocked selections stop; no fallback. Read applicable rules, selected task questions, relevant docs, source/config/assets and tests before implementation. Never implement from future.md alone.

Use minimal task-scoped changes and existing infrastructure. Clarify material product/acceptance uncertainty before editing. Capture understood durable implementation/validation findings through Add Pending: required blockers/subtasks receive highest-open-plus-one priority; nonblocking findings receive root-minus-one priority unless explicitly overridden. Preserve identities and observations separately from inferred causes. Keep alternate controls, prerequisite waits, transport probes and targeted repairs in the current checkpoint unless an independently actionable deliverable or source/harness change survives the operation. Never create one dependency task per attempt.

Perform authorized validation and review; record individual acceptance results, limitations and matching source/evidence. Required unrun checks prevent completion. Update current documentation. Persist a terminal outcome before removing the task. Commit only under explicit developer authorization or an approved scoped commit policy; record optional commit references after the commit exists. No push, publication or scheduling is implied.

## Prioritized body

Each prioritized body contains standalone sections with nested observable requirements:

```text
Goal:
Current behavior:
Desired behavior:
Touch:
Discovery allowance:
Out of scope:
Implementation constraints:
Questions and required clarifications:
- [Resolved - repository evidence] Confirmed decision with source.
- [Unresolved - blocks implementation] Missing decision and required context.
Validation:
Acceptance:
Documentation updates:
Risks:
```

Optional dependencies, data/persistence, platform, diagnostics, failure handling and implementation approaches belong only when task-relevant. Avoid boilerplate and empty sections. Blocked status requires a blocking question; Ready requires no blocking questions. Readiness never grants validation or commit permission.
