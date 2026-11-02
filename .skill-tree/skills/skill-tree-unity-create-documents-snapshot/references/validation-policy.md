<!-- GENERATED FILE; Source: .skill-tree/common/references/validation-policy.md; generator: .skill-tree/scripts/sync-skill-references.py -->

# Validation Policy

## Check ownership

The task Validation section owns required check IDs, criterion mapping and task parameters. A fenced JSON object contains `checks`, with entries containing `id`, `recipe_id`, `criteria`, `sources`, `parameters` and `timing`. Timing is `immediate`, `group-end` or `before-dependent-work`. The profile owns concrete recipes and environment facts. Task headers own optional `validation_group_id` and `boundary_validation`; group membership never expands controller scope.

Small task bodies require Goal, Touch, Validation and Acceptance. Optional sections contain substantive constraints only. Every acceptance bullet requires a mapped check. Default strategy is test-first for meaningful behavior changes; characterization, exploratory or not-applicable requires a concise task-specific reason when suitable. Existing adequate matching evidence remains reusable.

## Focused feedback

Establish intended behavior, relevant baseline and boundary/failure cases. Execute the smallest meaningful test before implementation. Red requires the intended runnable behavioral failure: zero tests, infrastructure failure or unrelated compilation errors cannot establish Red. Implement Green without weakening the oracle. Review legitimate test corrections. Refactor under matching regressions and static checks. Retain Red/Green reports, source/test fingerprints and failure category inside task progress; no additional TDD ledger exists.

Focused behavioral checks remain immediate. Grouping delays only compatible additional integration, rendering or platform qualification. Dependencies retain verified completion semantics through the single `depends_on` graph. Check grouping feasibility before execution; validate upstream work early when a verified dependency requires the result.

## Launch and evidence

Select the smallest sufficient lane from the unverified assertion. Documentation and metadata use static/temporary-fixture checks. Pure logic uses focused unit checks. Rendering, input, accessibility, lifecycle, native and device assertions require the matching lane. A launch records exact task/check IDs, assertion, cheaper-evidence insufficiency, source/test/environment identity, authorization, hard deadline and cleanup reserve. Reuse compatible owned processes when scope permits; process availability never proves current acceptance.

Reports record actual assertions/artifacts or nonzero expected/discovered test counts, required skips, failures, environment identity and cleanup. Missing, stale, skipped or unavailable mandatory evidence blocks completion. Expected behavioral Red establishes test validity without counting as an unresolved failure. Executed-control, prerequisite-wait, transport-uncertainty and host-policy-rejection classifications preserve the existing circuit breaker.

## Progress and groups

`future.json.task_progress` owns standalone and controller implementation/check progress. Stages are implementing, awaiting-validation and blocked; absence means not-started. Only matching passing required results permit terminal completion. Awaiting-validation preserves the specification and prevents repeated implementation. Refresh preserves progress. Terminal receipts precede queue/progress removal through recoverable writes.

Controllers freeze admitted in-scope group members. Work Through Next admits only the selected root and required descendants; Implement All admits only the frozen initial roots and required descendants. Another root can join an unresolved batch only as an eligible declared member of the same group. Standalone implementation never executes another member. Shared check reuse requires identical recipe, parameters, relevant source/tests and environment while preserving criterion coverage. Missing out-of-scope prerequisites block the exact check; artificial subgroups cannot weaken acceptance.

Source/check-set changes invalidate affected results. Unaffected passes remain available. Progress detection counts stage transitions and newly resolved obligations, excluding timestamps and repeated logs. Finish refuses pending, failed, stale or unavailable required checks. Required validation never becomes optional during completion.
