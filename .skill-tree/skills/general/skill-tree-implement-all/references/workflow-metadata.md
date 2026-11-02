# Workflow Metadata

## Ownership and locations

`.skill-tree/skill-tree.json` indexes current repository paths, ownership, catalog, generation relationships, validation commands, policy references and audit freshness. Portable paths are repository-relative. Policy references never grant authorization.

`.skill-tree/documents/future.md` owns task definitions. Queue order: Pending Queue, Prioritized Next Changes, Backlog. Each task uses a level-three heading followed immediately by a fenced yaml block containing the fixed fields below. JSON-compatible scalar/list values keep parsing deterministic.

```yaml
id: T-<uuid>
priority: 100
status: Ready
parent_pending_ids: ["P-<uuid>"]
processing_run_id: PR-<uuid>
root_task_id: T-<uuid>
related_task_id: null
relation: main
depends_on: []
```

Pending identities use P- and status Pending; Prioritized identities use T- and status Ready or Blocked pending answers; Backlog identities use B- and status Backlog. UUID values remain stable. Promotion creates T- identities with originating Pending IDs. Relations: main, blocker, subtask, followup. Related work records root and direct-parent T- identities. Required dependencies reside in depends_on.

Higher integer priority wins; ties follow document order. No fixed maximum. Intake defaults to 100; explicitly low defaults to 25; required work defaults to highest open priority plus one; nonblocking findings default to root priority minus one. Explicit developer priority wins. Relative placement requests become a suitable numeric priority; clarify competing placement instructions. Insert before equal-priority peers without reordering existing tasks.

## Current index and run

`future.json` separates generated tasks/source_hash from authoritative active_run. The checkpoint contains identities, initial snapshot, required/deferred work, captured Pending IDs, processing results, phase, partial work, completion evidence, stop reason and next action. Refresh preserves checkpoints. Successful task mutations also refresh the derived navigation manifest. Operation deadlines, active controller time, tool wall time, prerequisite waiting and retry/repair/reload counters remain evidence during resumption. Classify operations as executed controls, prerequisite waits, transport uncertainties or host-policy rejections; only executed controls contribute to an unchanged-failure circuit breaker. Recorded counters do not expire standing authorization. A cumulative root time pool is not part of workflow state. An optional total budget belongs only to the selected task when the task contract supplies a concrete cost or irreversible-risk rationale and defines charged time.

Atomic transactions, source-hash guards and an exclusive writer lock protect mutation. An interrupted transaction replays only when every source matches the recorded old or new hash. Verify PID/host before explicit stale-lock removal; never remove an active lock. Corrupt or unsupported state stops execution. Reinstallation/setup is explicit; no automatic conversion is supported.

## Helper interface

Run `python3 scripts/workflow-state.py <command> <repository>`. Read-only commands: index, read --id, select --id, pending --names, next, history --id/--component, manifest, prune. Modifying commands: refresh, intake, process, start, advance, checkpoint, complete, finish, audit, cycle; manifest/prune modify only with --apply. Structured payloads use --input <file>. Mutations accept --expected-source-hash where applicable.

Intake payload: title, description, expected_behavior; optional source/context/priority/low_priority/priority_reason/root_task_id/related_task_id/relation. Clarify understanding and duplicates before invocation.

Process payload: selectors; dispositions keyed by every selected P- ID with status promoted/retained/resolved and reason; tasks containing title/body/parent_pending_ids and optional key/priority/depends_on/reuse_id. Research precedes payload construction. Split outputs share Pending provenance; merges preserve every parent. Conflicting roots require clarification. A reuse_id explicitly extends provenance of a compatible existing task. Payload-local lowercase kebab-case keys identify new or reused tasks; depends_on accepts existing T- IDs and `@key` references, including forward references. Processing allocates all IDs before resolving references, adds required dependency edges, then rejects unknown keys, duplicate keys/dependencies, missing required tasks and dependency cycles before any queue/index/checkpoint write. Completed dependencies require recorded completed outcomes; cancelled outcomes never satisfy requirements. The processing receipt returns task_keys; persisted metadata contains T- IDs only.

Start uses --mode next or all and optional --id; payload limits records optional task-specific budgets, operation deadlines and observed counters. Advance checkpoints the next dependency/root handoff. Checkpoint accepts phase/partial_work/stop_reason/next_action/history_refs, validation_consumed and task_budget_used_seconds. Observed retry/repair/reload counters and optional selected-task budget usage only increase. Elapsed-time and recovery-counter records provide evidence rather than authorization expiry; an explicitly justified selected-task budget remains an enforceable stop. Helpers select work and persist state; agents perform implementation and authorized validation.

Complete payload: task_id, outcome, acceptance entries with criterion/result/required/evidence, source_fingerprints, limitations, followup_ids, commits and evidence. Every recorded acceptance criterion requires pass with available matching repository-relative evidence and current stored check receipts; optional validation gaps belong in limitations. Complete records the terminal outcome before task removal. Finish requires roots/dependencies complete and one processing pass for captured followups. Missing tasks without completion records stop execution.

Audit payload: scope, sources, findings with stable id/observation/status, checks and coverage_gaps; optional corrections/task links. Refresh manifest after metadata/audit changes. Use history queries by task identity/component; query views mark expired or changed evidence unavailable without rewriting recorded verdicts. Run cycle only after a completed orchestration iteration; unchanged task/dependency state stops further handoffs.

## Metadata consistency checks

The repository documentation validator reads persisted manifests and indexes without refresh or checkpoint replacement. Validation checks JSON structure, repository-relative paths, canonical source-digest coverage/freshness, installed skill entrypoints/resources, task-index equality, source hashes, required dependency closure/cycles and active-run identity consistency. Invalid state requires a concrete repair; validation never resets state. A stale audit supplies a warning and never changes the recorded verdict.

Target manifests catalog repository-local installed Skill Tree packages, including provider-specific entrypoints, without consulting the source repository. Explicit manifest/queue refresh updates derived navigation while preserving active_run.

## Validation progress interface

Queue/index schema 2 stores `task_progress` independently of `active_run`. Optional header fields are `validation_group_id: VG-<uuid>` and `boundary_validation: not-required|group-end|before-dependent-work`. The [validation policy](validation-policy.md) defines check ownership and timing. Minimal tasks require Goal, Touch, Validation and Acceptance; additional sections contain substantive constraints only. Validation contains one fenced JSON checks object with stable IDs and criterion mapping.

`begin` admits standalone implementation or reuses controller admission; `implemented` preserves the task and marks awaiting-validation. `prepare-check` freezes source/test, recipe, environment and group/check-set fingerprints before execution. `record-check` requires the original attempt ID, actual lane/environment, classification, matching artifacts and actual cleanup. Test lanes require nonzero expected discovery and no required skips. Static/visual lanes require matching assertions. Expected behavioral Red remains separate from a final pass. `reuse-check` deduplicates only identical compatible checks inside an admitted group. `complete` verifies stored results and matching acceptance artifacts before terminal queue/progress removal.

`admit` explicitly rechecks profile freshness on controller resume; nested focused checks reuse the pin. `resume-task` records a resolved blocking condition and re-admits the profile without recreating the task/checkpoint or erasing observed failures. A resolution record grants no new execution authorization. `capture-foundation` retains a finding without a queue or captures/reuses one highest-open-plus-one Pending after setup. Helpers never launch a product during intake, composition or admission.

Check receipts are immutable per attempt ID. Repeated delivery recovers the original receipt; conflicting replay fails. An unresolved prepared attempt requires recovery before another control. A new Red invalidates final Green eligibility while retaining the useful Red/Green artifacts. Shared evidence validates the selected check independently of other pending obligations. Scheduler decisions require current matching immediate evidence.

Product lanes require an owned execution session even when no new process launch occurs. The session supplies exact checkout, tool/build/fixture identity, identity artifacts, verified authorization/profile, operation deadline and cleanup reserve; Unity adds the pinned Editor and save/service isolation. Focused iterations reuse matching session context. Expired execution deadlines prevent new controls without invalidating already completed matching evidence. Separate observed controller, tool-wall and prerequisite-wait timings remain inside the check receipt.

`accept-revalidation` accepts current passing checks for a required completed contract selected by advance. Temporary `task_progress` entries carry `revalidation: true`; immutable terminal history owns the completed check definitions. The active run retains accepted `revalidated_checks`, without another outcome ledger or rewritten terminal record. Finish rejects stale/missing required completed evidence and unresolved revalidation attempts. A blocked-task resume can clear only the execution stop owned by the same admitted task; unrelated stops remain binding. History views refresh artifact availability and source matching without changing recorded verdicts.
