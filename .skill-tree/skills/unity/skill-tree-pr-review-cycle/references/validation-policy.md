# Validation Policy

Web source directory checks can include packages with materialized pnpm dependencies. With matching owned Web pnpm profile files and the ordinary pnpm store, source traversal skips wholly Git-ignored, unversioned `node_modules` directories in the selected checkout. Nested packages require the same package name and path in pnpm's materialized workspace state and a match in the current workspace declaration. The source checker recognizes block lists of literal paths, simple wildcards and recursive directory wildcards. Unsupported declarations and explicitly named dependency inputs retain the normal source checks.

## Check ownership

The task Validation section owns required check IDs, criterion mapping and task parameters. A fenced JSON object contains `checks`, with entries containing `id`, `recipe_id`, `criteria`, `sources`, `parameters` and `timing`. Timing is `immediate`, `group-end` or `before-dependent-work`. The profile owns concrete recipes and environment facts. Task headers own optional `validation_group_id` and `boundary_validation`; group membership never expands controller scope.

Owned profiles list the built-in `static-inspection` fallback when no explicit recipe owns the ID. The built-in recipe uses the static lane for explicit source and artifact assertions and has no executable argument vector. An explicit recipe retains precedence. Older profiles may resolve the same fallback without a discovery entry.

Small task bodies require Goal, Touch, Validation and Acceptance. Optional sections contain substantive constraints only. Every acceptance bullet requires a mapped check. Default strategy is test-first for meaningful behavior changes; characterization, exploratory or not-applicable requires a concise task-specific reason when suitable. Existing adequate matching evidence remains reusable.

## Focused feedback

Establish intended behavior, relevant baseline and boundary/failure cases. Execute the smallest meaningful test before implementation. Red requires the intended runnable behavioral failure: zero tests, infrastructure failure or unrelated compilation errors cannot establish Red. Implement Green without weakening the oracle. Review legitimate test corrections. Refactor under matching regressions and static checks. Retain Red/Green reports, source/test fingerprints and failure category inside task progress; no additional TDD ledger exists.

Focused behavioral checks remain immediate. Grouping delays only compatible additional integration, rendering or platform qualification. Dependencies retain verified completion semantics through the single `depends_on` graph. Check grouping feasibility before execution; validate upstream work early when a verified dependency requires the result.

## Full Cycle worker briefs

Give the executor the current `worker_brief` from the implementation handoff. The brief binds the selected run, task fingerprints, checkout and admitted profile. The coordinator prepares the exact attempt before the worker executes an entry marked `focused-command`. Compare the prepared argument vector and checkout with the brief. Return the check evidence to the coordinator for recording. A `pending-attempt` entry directs the coordinator to reconcile the original attempt before any new execution. The brief supplies no execution-session, resource or acceptance receipt.

The coordinator owns checks deferred by timing, checks without an executable command and product lanes with execution-session and resource requirements. Keep required immediate and dependency-bound checks at the existing validation boundaries. Resolve a reported prerequisite before executing the affected check.

A project recipe in `.skill-tree/validation-recipes.json` can declare `"delivery_validation": {"path": "final-suite.json", "check_id": "full-suite"}`. The tagged recipe uses the same literal `argv` as the named check in the declared PR suite. The owned profile fingerprints the suite file. Keep delivery-only recipes outside leaf Acceptance mappings. The leaf preflight reports the required phase and the leaf writer refuses preparation. Pass the linked path as the publication's final suite declaration and prepare the named suite through `final-validation` on the current reviewed PR candidate.

## Shared policy evidence

Implementation and current review handoffs include the shared invariants relevant to the selected task or check. Inspect both allowed and forbidden cases for each named transition against the stated rule. Relevant check keys bind the invariant, case mappings and source or owner evidence. A changed policy definition requires current evidence even when the check IDs stay the same.

Task revisions preserve required invariant identities and mappings. A change to the rule requires current policy evidence and ordinary clarification before implementation continues. Editorial changes preserve the policy contract. Completion retains the rule, transition mappings and evidence with the accepted check results after removing the task from the queue.

## Launch and evidence

Select the smallest sufficient lane from the unverified assertion. Documentation and metadata use static/temporary-fixture checks. Pure logic uses focused unit checks. Rendering, input, accessibility, lifecycle, native and device assertions require the matching lane. A launch records exact task/check IDs, assertion, cheaper-evidence insufficiency, source/test/environment identity, authorization, hard deadline and cleanup reserve. Reuse compatible owned processes when scope permits; process availability never proves current acceptance.

Reports record actual assertions/artifacts or nonzero expected/discovered test counts, required skips, failures, environment identity and cleanup. Missing, stale, skipped or unavailable mandatory evidence blocks completion. Expected behavioral Red establishes test validity without counting as an unresolved failure. Executed-control, prerequisite-wait, transport-uncertainty and host-policy-rejection classifications preserve the existing circuit breaker.

## Progress and groups

`future.json.task_progress` owns standalone and controller implementation/check progress. Stages are implementing, awaiting-validation and blocked; absence means not-started. Only matching passing required results permit terminal completion. Awaiting-validation preserves the specification and prevents repeated implementation. Refresh preserves progress. Terminal receipts precede queue/progress removal through recoverable writes.

Controllers freeze admitted in-scope group members. Work Through Next admits only the selected root and required descendants; Implement All admits only the frozen initial roots and required descendants. Another root can join an unresolved batch only as an eligible declared member of the same group. Standalone implementation never executes another member. Shared check reuse requires identical recipe, parameters, relevant source/tests and environment while preserving criterion coverage. Missing out-of-scope prerequisites block the exact check; artificial subgroups cannot weaken acceptance.

Source/check-set changes invalidate affected results. Unaffected passes remain available. Progress detection counts stage transitions and newly resolved obligations, excluding timestamps and repeated logs. Finish refuses pending, failed, stale or unavailable required checks. Required validation never becomes optional during completion.

A pending attempt blocks acceptance even when an earlier result passes or the current task removes the check. For local runner recovery, bind the live original process group to the prepared attempt before drift. After cleanup, `reconcile-check` verifies current drift and absence of the bound group and records a cancellation receipt. Earlier results, recorded stops and admission remain separate. The workflow metadata contract defines the exact request and evidence fields.

An owned static or unit runner can retain the finished result before leaving the original native process group. After coordinator interruption, `reconcile-check` can recover the result using the exact receipt digest, the current check and evidence, and verified absence of the original group. Verified cleanup can close a native local attempt with an unavailable result so the current check can retry.

## Final run evidence

A declared local delivery suite belongs to the PR final validation phase. Leaf task completion requires all mapped immediate and dependency-bound checks. Run focused regressions during review fixes. Bind final suite results to the reviewed candidate and preserve required provider checks at readiness and merge.

Review can reuse an executed check receipt when the current check contract, relevant source and test inputs, recipe, execution environment and evidence remain verified for the exact review candidate. Reviewers retain independent responsibility for the candidate and current findings. An unavailable artifact, changed input, outstanding execution or a fresh-check requirement retains the corresponding validation obligation. After reuse becomes invalid, execute the required check and use a current review frame for the new evidence.

Finish checks the current sources, recipe/environment, group contract and artifacts of required completed checks. Ordinary and maintenance finish also verify the recorded completion fingerprints for every required completed contract, including roots and dependencies. Changed evidence returns a validate handoff for the immutable completed contract. `prepare-check` and `record-check` perform the due verification; `accept-revalidation` retains the new receipts in the existing run and removes temporary revalidation progress. The queue and original terminal outcome remain unchanged. Revalidation never reimplements a completed unit or creates another task/dependency graph. A pending revalidation attempt prevents finish even when an earlier matching pass exists.

A changed completed dependency returns a validate handoff before consumer implementation. Advance selects the immutable contract and establishes revalidation progress without preparing an attempt or launching a runtime. Prepare-check, record-check and accept-revalidation remain mandatory. Accepted results establish integration only while every recorded source fingerprint is covered and current, the check set and environment match, evidence remains available and no new attempt is pending. A separate source review may cover completion paths outside the accepted checks. Review evidence and fingerprints must remain current. Original outcomes, task identities, execution stops and snapshot membership remain unchanged.

## Validation evidence preflight

Read the current evidence contract with `validation-preflight` before preparing a selected check. Product lanes describe the owned execution-session identity, deadline and cleanup reserve. Browser passes carry actual counts with nonzero discovery. Server passes carry matching executed assertions. A task boundary prerequisite must be resolved before preparing an affected attempt.
