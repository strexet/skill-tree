# Future Task Workflow

## Queue responsibilities

Pending Queue contains understood intake awaiting research. Prioritized Next Changes contains researched executable tasks. Backlog contains deferred issues and investigations. The agent never selects implementation work from Pending Queue or Backlog.

## Process Pending

Resolve optional Pending IDs or exact normalized names before mutation; no input selects the Pending Queue. Absent/ambiguous selections stop without fallback. Read repository rules, document map, relevant current documentation, implementation, configuration, assets/data, tests and source history when needed. Never process from future.md alone.

Verify scope, duplicates, existing behavior, dependencies, observable outcomes, failure paths and validation availability. Split excessive tasks into independently executable units; retain every originating Pending ID. Merge only compatible intent and relationship context. Clarify product choices with contextual options and recommendations. Missing mandatory context remains Pending with an explicit blocker. Promote only Ready work; record created/reused/retained/resolved identities. No implementation is implied.

## Implement Next

Select the highest integer priority in Prioritized Next Changes; document order breaks ties. Explicit task ID/name selects only an exact prioritized match. Absent/ambiguous or blocked selections stop; no fallback. Read applicable rules, selected task questions, relevant docs, source/config/assets and tests before implementation. Never implement from future.md alone.

Use minimal task-scoped changes and existing infrastructure. Clarify material product/acceptance uncertainty before editing. Capture understood implementation/validation findings through Add Pending: required blockers/subtasks receive highest-open-plus-one priority; nonblocking findings receive root-minus-one priority unless explicitly overridden. Preserve identities and observations separately from inferred causes.

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
