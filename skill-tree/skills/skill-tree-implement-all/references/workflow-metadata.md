<!-- GENERATED FILE; Source: skill-tree/common/references/workflow-metadata.md; generator: skill-tree/scripts/sync-skill-references.py -->

# Workflow Metadata

## Ownership and locations

`skill-tree/skill-tree.json` indexes current repository paths, ownership, catalog, generation relationships, validation commands, policy references and audit freshness. Portable paths are repository-relative. Policy references never grant authorization.

`skill-tree/documents/future.md` owns task definitions. Queue order: Pending Queue, Prioritized Next Changes, Backlog. Each task uses a level-three heading followed immediately by a fenced yaml block containing the fixed fields below. JSON-compatible scalar/list values keep parsing deterministic.

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

Process payload: selectors; dispositions keyed by every selected P- ID with status promoted/retained/resolved and reason; tasks containing title/body/parent_pending_ids and optional priority/depends_on/reuse_id. Research precedes payload construction. Split outputs share Pending provenance; merges preserve every parent. Conflicting roots require clarification. A reuse_id explicitly extends provenance of a compatible existing task.

Start uses --mode next or all and optional --id; payload limits records optional task-specific budgets, operation deadlines and observed counters. Advance checkpoints the next dependency/root handoff. Checkpoint accepts phase/partial_work/stop_reason/next_action/history_refs, validation_consumed and task_budget_used_seconds. Observed retry/repair/reload counters and optional selected-task budget usage only increase. Elapsed-time and recovery-counter records provide evidence rather than authorization expiry; an explicitly justified selected-task budget remains an enforceable stop. Helpers select work and persist state; agents perform implementation and authorized validation.

Complete payload: task_id, outcome, acceptance entries with criterion/result/required/evidence, source_fingerprints, limitations, followup_ids, commits and evidence. Every recorded acceptance criterion requires pass with available matching repository-relative evidence; optional validation gaps belong in limitations. Complete records the terminal outcome before task removal. Finish requires roots/dependencies complete and one processing pass for captured followups. Missing tasks without completion records stop execution.

Audit payload: scope, sources, findings with stable id/observation/status, checks and coverage_gaps; optional corrections/task links. Refresh manifest after metadata/audit changes. Use history queries by task identity/component; query views mark expired or changed evidence unavailable without rewriting recorded verdicts. Run cycle only after a completed orchestration iteration; unchanged task/dependency state stops further handoffs.
