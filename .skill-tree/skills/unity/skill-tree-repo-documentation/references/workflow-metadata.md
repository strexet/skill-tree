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

Higher integer priority wins; ties follow document order. No fixed maximum. Ordinary intake defaults to 100; explicitly low defaults to 25; required work defaults to highest open priority plus one; nonblocking findings default to root priority minus one. Semantically classified defect intake defaults to the highest open Pending/Prioritized/Backlog priority plus one, with an empty-queue baseline of 100. Explicit owner numeric, relative or low priority wins over the defect default. The [intake contract](pending-task-intake.md) owns classification and override details. Relative placement requests become a suitable numeric priority; clarify competing placement instructions. Insert before equal-priority peers without reordering existing tasks.

## Current index and run

`future.json` separates generated tasks/source_hash from authoritative controller checkpoints. Explicit workspace setup creates index schema 3 with a schema-1 run_registry. The registry owns multiple runs, claims and resources; persisted active_run remains null while helpers project the selected registry entry. The [run workspace contract](run-workspaces.md) defines explicit adoption, canonical queue routing, portable events and recovery. Schema-2 checkpoints retain the single-run interface. Older helpers reject schema 3 before mutation. The checkpoint contains identities, initial snapshot, required/deferred work, captured Pending IDs, processing results, phase, partial work, completion evidence, stop reason and next action. Refresh preserves checkpoints. Successful task mutations also refresh the derived navigation manifest. Operation deadlines, active controller time, tool wall time, prerequisite waiting and retry/repair/reload counters remain evidence during resumption. Classify operations as executed controls, prerequisite waits, transport uncertainties or host-policy rejections; only executed controls contribute to an unchanged-failure circuit breaker. Recorded counters do not expire standing authorization. A cumulative root time pool is not part of workflow state. An optional total budget belongs only to the selected task when the task contract supplies a concrete cost or irreversible-risk rationale and defines charged time.

Atomic transactions, source-hash guards and an exclusive writer lock protect mutation. An interrupted transaction replays only when every source matches the recorded old or new hash. Verify PID/host before explicit stale-lock removal; never remove an active lock. Corrupt or unsupported state stops execution. Reinstallation/setup is explicit; no automatic conversion is supported.

## Helper interface

Run `python3 scripts/workflow-state.py <command> <repository>`. Read-only commands: index, read --id, select --id, pending --names, next, history --id/--component, manifest, prune. Modifying commands: refresh, intake, process, start, advance, checkpoint, complete, finish, audit, cycle; manifest/prune modify only with --apply. Structured payloads use --input <file>. Mutations accept --expected-source-hash where applicable.

Intake payload: title, description, expected_behavior; optional source/context/priority/low_priority/priority_reason/root_task_id/related_task_id/relation. Owner-request intake supplies `classification: {"kind":"defect"|"other","reason":"English semantic rationale"}`. Existing programmatic callers can omit classification and retain previous defaults. `relative_priority: {"direction":"above"|"below","task_id":"P-/T-/B-uuid"}` resolves an exact open anchor to an integer and conflicts with numeric priority. Classification remains in the Pending body; the fixed metadata header remains unchanged. Clarify understanding and duplicates before invocation.

Process payload: selectors; dispositions keyed by every selected P- ID with status promoted/retained/resolved and reason; tasks containing title/body/parent_pending_ids and optional key/priority/depends_on/reuse_id. Research precedes payload construction. Split outputs share Pending provenance; merges preserve every parent. Conflicting roots require clarification. A reuse_id explicitly extends provenance of a compatible existing task. Payload-local lowercase kebab-case keys identify new or reused tasks; depends_on accepts existing T- IDs and `@key` references, including forward references. Processing allocates all IDs before resolving references, adds required dependency edges, then rejects unknown keys, duplicate keys/dependencies, missing required tasks and dependency cycles before any queue/index/checkpoint write. Completed dependencies require recorded completed outcomes; cancelled outcomes never satisfy requirements. The processing receipt returns task_keys; persisted metadata contains T- IDs only.

Start uses --mode next with optional --id, or --mode all. An all-mode payload can supply `snapshot_ids`, a nonempty unique list of exact prioritized T- IDs; omission freezes the full initial Prioritized queue. Every selected root must be Ready. Selection preserves numeric priority and document tie order, includes required dependency closure and excludes unrelated roots. Invalid groups fail before state/claim/workspace creation. Mode next and --id cannot combine with `snapshot_ids`. The [run workspace contract](run-workspaces.md) supplies a start payload example. Git controllers require explicit workspace-setup and one dedicated workspace for the admitted scope. Registry commands accept --run-id for unambiguous selection; payload limits records optional task-specific budgets, operation deadlines and observed counters. Advance checkpoints the next dependency/root handoff. Checkpoint accepts phase/partial_work/stop_reason/next_action/history_refs, validation_consumed and task_budget_used_seconds. Observed retry/repair/reload counters and optional selected-task budget usage only increase. Elapsed-time and recovery-counter records provide evidence rather than authorization expiry; an explicitly justified selected-task budget remains an enforceable stop. Helpers select work and persist state; agents perform implementation and authorized validation.

Complete payload: task_id, outcome, acceptance entries with criterion/result/required/evidence, source_fingerprints, limitations, followup_ids, commits and evidence. Every recorded acceptance criterion requires pass with available matching repository-relative evidence and current stored check receipts; optional validation gaps belong in limitations. Complete records the terminal outcome before task removal. Finish requires roots/dependencies complete and one processing pass for captured followups. Missing tasks without completion records stop execution.

Audit payload: scope, sources, findings with stable id/observation/status, checks and coverage_gaps; optional corrections/task links. Refresh manifest after metadata/audit changes. Use history queries by task identity/component; query views mark expired or changed evidence unavailable without rewriting recorded verdicts. Run cycle only after a completed orchestration iteration; unchanged task/dependency state stops further handoffs.

## Plugin invocation metadata

The [invocation contract](plugin-invocation.md#guarded-invocation-chains) owns ordered plugin execution and acceptance. Canonical schema-1 chain records reside in `.skill-tree/invocations/hc-<uuid>.json` with stable `HC-` identities, integer revisions and chain hashes. Original `HI-` attempts retain isolated actor creation, sealed public inputs, dispatch/result evidence and accepted core transitions. Chains remain separate from task definitions, clarification sessions, decision records, check receipts and controller checkpoints. Linked controllers retain chain references without widening admitted task scope.

The workflow CLI exposes `hook-start`, `hook-read`, `hook-next`, `hook-prepare`, `hook-invoke`, `hook-record`, `hook-accept`, `hook-reconcile`, `hook-resume` and `hook-pending` through the ordinary repository and structured `--input` convention. Read accepts `--id HC-<uuid>`. Existing mutations require `chain_id`, `expected_chain_hash` and `expected_chain_revision`; an existing queue also requires the inspected `expected_source_hash`. The bridge obtains trusted current proofs from the verified owned Node closure rather than caller-provided JSON proofs.

Start freezes effective configuration, occurrence order, package identities, context, mode, bounded authority and execution inputs. Preparation seals an original isolated actor attempt; invocation binds actual producer and private delivery digests. A returned result remains unaccepted until a no-change receipt or verified ordinary core incorporation/resolution advances the cursor. Each following occurrence receives the accepted current context. Chain completion supplies one readiness obligation alongside current core acceptance, checks and authorization. Source/configuration/context/policy drift, failures and unresolved originals remain visible prerequisites rather than successful results.

Explicit resume preserves frozen configuration and accepted history. Configuration adoption creates an explicitly authorized replacement chain with a guarded predecessor reference. Reconciliation remains available for original pending attempts after scope removal or revocation without recreating tasks or asserting success. Prepared, invoking and unknown attempts participate in the owned installation barrier before Future initialization. Task-free inspection and empty core-only routing create no fabricated queue or plugin obligation.

Reference-level public parameters remain separate from private resolved delivery values. Trusted in-process private provider/sink callbacks run outside the writer lock; JSON cannot install callbacks. Machine-local package/execution locators reside under `.skill-tree/local/hook-locations/` rather than portable chain metadata. Actor execution, secret resolution and owner waits remain outside writer transactions. A host supplies actual source-backed invocation evidence and sanitizes returned capture; stored state alone supplies no native Skill call, human approval or candidate-effectiveness evidence.

Current global and current-occurrence prerequisites gate business transitions before private provider callbacks and inside the writer transaction. Other-occurrence requirements remain visible without blocking valid current incorporation or rewriting accepted prefixes. Ordinary business transitions preserve the frozen configuration/watch baseline; drift requires explicit supported recovery. Associated managed operations retain live registry authority through exact project, destination and verified receipt inventory evidence. Independent standalone copies retain standalone operation, and empty optional configurations create no new hold. Completed-chain readiness still checks applicable outstanding obligations.

Completed readiness proofs use the dedicated `completed-readiness` kind and cannot substitute for ordinary business proofs. The workflow preflights exact scoped chain references outside the writer and retains an operation-local in-memory cache of current chain, locator, admitted-context and watch identities. Pure writer/commit checks reject stale or missing matching preflight without executing Node. Completed During readiness preserves accepted planning history after the draft frontier advances. Core/PR callers preserve existing selection, authority and publication gates; empty reference sets acquire no Node dependency or persistent readiness record.

## Metadata consistency checks

The repository documentation validator reads persisted manifests and indexes without refresh or checkpoint replacement. Validation checks JSON structure, repository-relative paths, canonical source-digest coverage/freshness, installed skill entrypoints/resources, task-index equality, source hashes, required dependency closure/cycles and active-run identity consistency. Invalid state requires a concrete repair; validation never resets state. A stale audit supplies a warning and never changes the recorded verdict.

Target manifests catalog repository-local installed Skill Tree packages, including provider-specific entrypoints, without consulting the source repository. Explicit manifest/queue refresh updates derived navigation while preserving active_run.

## Validation progress interface

Queue/index schemas 2 and 3 store `task_progress` independently of the selected controller checkpoint. Optional header fields are `validation_group_id: VG-<uuid>` and `boundary_validation: not-required|group-end|before-dependent-work`. The [validation policy](validation-policy.md) defines check ownership and timing. Minimal tasks require Goal, Touch, Validation and Acceptance; additional sections contain substantive constraints only. Validation contains one fenced JSON checks object with stable IDs and criterion mapping.

`begin` admits standalone implementation or reuses controller admission; `implemented` preserves the task and marks awaiting-validation. `prepare-check` freezes source/test, recipe, environment and group/check-set fingerprints before execution. `record-check` requires the original attempt ID, actual lane/environment, classification, matching artifacts and actual cleanup. Test lanes require nonzero expected discovery and no required skips. Static/visual lanes require matching assertions. Expected behavioral Red remains separate from a final pass. `reuse-check` deduplicates only identical compatible checks inside an admitted group. `complete` verifies stored results and matching acceptance artifacts before terminal queue/progress removal.

`admit` explicitly rechecks profile freshness on controller resume; nested focused checks reuse the pin. `resume-task` records a resolved blocking condition and re-admits the profile without recreating the task/checkpoint or erasing observed failures. A resolution record grants no new execution authorization. `capture-foundation` retains a finding without a queue or captures/reuses one highest-open-plus-one Pending after setup. Helpers never launch a product during intake, composition or admission.

Check receipts are immutable per attempt ID. Repeated delivery recovers the original receipt; conflicting replay fails. An unresolved prepared attempt requires recovery before another control. A new Red invalidates final Green eligibility while retaining the useful Red/Green artifacts. Shared evidence validates the selected check independently of other pending obligations. Scheduler decisions require current matching immediate evidence.

Product lanes require an owned execution session even when no new process launch occurs. The session supplies exact checkout, tool/build/fixture identity, identity artifacts, verified authorization/profile, operation deadline and cleanup reserve; Unity adds the pinned Editor and save/service isolation. Focused iterations reuse matching session context. Expired execution deadlines prevent new controls without invalidating already completed matching evidence. Separate observed controller, tool-wall and prerequisite-wait timings remain inside the check receipt.

`focus-maintenance` accepts an exact prioritized `task_id` and the explicit owner `instruction` for bounded infrastructure work inside an already admitted required closure. The preserved controller must remain stopped. A nested `maintenance` record owns the exact selected dependency closure, separate profile admission and static/unit-only restriction; the original run/root/current task, admission, execution stop and counters remain authoritative for the parked controller. Advance, begin, check receipts and completion operate only inside the maintenance closure. Product recipes and unrelated tasks fail closed. Finish closes only the completed maintenance scope and retains the stopped original controller. The owner instruction remains necessary; a stored scope grants no additional authorization. Intake/processing preserve an existing controller stop and capture required maintenance descendants without expanding into other roots.

`accept-revalidation` accepts current passing checks for a required completed contract selected by advance. Temporary `task_progress` entries carry `revalidation: true`; immutable terminal history owns the completed check definitions. The active run retains accepted `revalidated_checks`, without another outcome ledger or rewritten terminal record. Finish rejects stale/missing required completed evidence and unresolved revalidation attempts. A blocked-task resume can clear only the execution stop owned by the same admitted task; unrelated stops remain binding. History views refresh artifact availability and source matching without changing recorded verdicts.

## Task clarification contract

The `skill-tree-clarify-tasks` operation exposes the following metadata-only interface through the bundled helper. Canonical mutable records reside in `.skill-tree/clarifications/cl-<uuid>.json` with schema 1, stable `CL-<uuid>` identity and integer revision. Records contain exact selected task IDs, source and semantic baselines, facts, rounds/questions/answers, revision evidence, confirmation, state and next action. The queue/index remain task authorities; implementation progress, run checkpoints and terminal ledgers remain separate.

Clarification commands: `clarify-start`, `clarify-read`, `clarify-round`, `clarify-answer`, `clarify-revise`, `clarify-confirm`, `clarify-resume`, `clarify-cancel` and `clarify-switch-mode`. Commands use the existing root and structured `--input` convention; read accepts `--id CL-<uuid>`. Start supplies exact unique `task_ids` and `expected_source_hash`; existing-session mutators additionally supply `session_id`, `expected_session_hash` and `expected_session_revision`. Source/session hashes are complete-content guards, not semantic identities.

Round payloads supply stable question IDs, prerequisite IDs, task/semantic-field bindings, recommendations and source facts. Answer payloads bind actual submitted Manual evidence or a validated Auto decision reference to the exact session, round, question revision and parent mode epoch. Revision payloads identify exact selected tasks, replacement content and permitted dependency changes; fixed provenance/relationship fields and optional validation metadata remain preserved. Confirmation payloads bind actual Manual owner evidence or separate Auto specification acceptance to the current exact scope and semantic fingerprints after clarity recheck. Resume reconciles drift without new selection; cancellation records the reason without asserting satisfied required interviews.

Session-only commands write only the session through the canonical writer lock. Revisions atomically update task definitions, derived index/manifest and session while preserving parked runs, claims, counters and progress. The lock snapshots session files as owned mutable inputs. Every stale/conflicting guard, invalid task/dependency or unmatched answer/confirmation rejects before mutation. Separate semantic projections cover goals, scope, exclusions, dependencies, acceptance, validation, required plugin policy and remaining substantive content; the validation signature alone supplies insufficient coverage.

## Guarded decision records

The shared `decision-governance.py` helper owns `.skill-tree/decisions/dg-<uuid>.json` records through the existing canonical writer/installation barrier. `workflow-state.py` exposes `decision-start`, `decision-read`, `decision-prepare`, `decision-record`, `decision-reconcile`, `decision-switch`, `decision-resume` and `decision-accept`. Read never creates metadata. A task-free decision creates no Future, implementation run or worktree. Existing queue mutations require the inspected `expected_source_hash`; the decision helper never loads or saves a controller.

A record freezes typed context, semantic/content identities, question/options/recommendation, mode/epoch, bounded authority, actual executor and original `DA-` attempts. Existing mutators require `decision_id`, `expected_decision_hash`, `expected_decision_revision`, `expected_mode_epoch` and `expected_context_fingerprint`. Preparation records the role and distinct actor/context. Submitted results retain actual owner or delegated origin. Significant decisions require current independent criticism; substantive disagreement retains arbitration. A new label cannot manufacture independence or erase an unsettled role.

`clarify-start` accepts separate `decision_mode`, `decision_authority` and `decision_executor` fields. Legacy sessions and the compatible state interface retain Manual defaults until separately qualified operation routing selects Auto. `clarification_decision_context` and `clarification_decision_question` derive exact parent bindings. Auto answer/confirmation payloads supply `decision_receipt: {decision_id, acceptance_digest}`. References validate live current mode, authority, purpose and semantic scope; old acceptance or a product answer cannot impersonate current specification acceptance. Explicit switching records previous policy and confirmation while preserving history. Formatting equivalence preserves semantic validity; changed semantics reopen affected acceptance.

Switching and session cancellation require original pending actors to be reconciled first. Cancelled parents reject late preparation, recording and acceptance. Original-attempt reconciliation retains exact record/attempt guards while permitting cleanup after removal of the former scope; cleanup never recreates Future or records a successful answer.

The PR adapter binds decisions to exact repository/head/base/target and review-policy identity. A decision receipt adds decision evidence without changing publication authorization, review completion, check status or external approval. State helpers validate submitted evidence; actual host delegation and automatic actor/default-mode activation require separate orchestration qualification.

## Core operation phase frames

The `decision-orchestration.py` helper owns `.skill-tree/decisions/do-<uuid>.json` frames separately from DG authority and answer records. The workflow CLI exposes `orchestration-start`, `orchestration-read`, `orchestration-next`, `orchestration-question`, actor preparation/recording/reconciliation, mode switching, decision acceptance, research, plan/accept-plan, implementation, checks, review, resolution, fixes, resume and unchanged-failure observation. The command names use the `orchestration-` prefix. Existing mutations require `orchestration_id`, `expected_orchestration_hash` and `expected_orchestration_revision`; an existing queue also requires the inspected `expected_source_hash`. Read and next-action inspection create no metadata.

Start freezes actual typed context, bounded authority, executor, mode, host capabilities and execution snapshot. New frames default to Auto; explicit Manual and stored modes remain binding. The CLI pins actual bundle/reference hashes and the owned profile digest. Changed core inputs require original-actor reconciliation and explicit resume; old plan/decision/check/review acceptance never becomes current through a source update. Phase-owned decisions bind the execution generation. Task-free frames create no queue, implementation run or worktree.

Question attachment creates one DG decision or binds an existing exact context/mode/grant/executor-owned DG identity. Actor preparation records the actual host creation event and returns `prepared_actor` with the original `attempt_id`, sealed `input`, `input_digest` and creation evidence. The host delivers the sealed input outside the writer lock, then records the matching actual returned result. A separate trusted host capture establishes actual tool observations; supplied JSON labels alone establish no native authenticity.

DG mutation and the corresponding DO frame change share one recoverable transaction. Current plans, required-check sets, source/head/base identities, review findings and individual resolutions guard phase transitions. A clean review creates no fix. A frame's ready phase never replaces actual operation validation receipts, task completion, external approval or publication authorization. Repeated unchanged obligations persist one owner question without treating new timestamps, review IDs, actor counts or repeated endorsements as progress.

## Workspace helper interface

`workspace-setup` explicitly enables the compatible run registry and optionally adopts an existing checkpoint. `runs` lists retained runs. `recover-locator` and `recover-workspace` preserve identities while resolving explicitly inspected machine-state gaps. `environment` inspects declared prerequisites without reading secrets or launching runtimes. `resource` owns exclusive runtime claims. `export-run` and `replay-events` transfer scoped semantic changes without replacing canonical queue files. The run workspace contract defines payloads and conflict behavior.


## Clarification payloads

`clarify-start` accepts the exact `task_ids`, inspected `expected_source_hash` and optional `mode: explicit|required-interview`. The returned session includes `id`, integer `revision` and computed `session_hash`. `clarify-read --id CL-<uuid>` returns the current record without mutation. Every existing-session mutation supplies the following guard fields; placeholders represent exact inspected values.

```json
{
  "session_id": "CL-<uuid>",
  "expected_source_hash": "<complete-queue-sha256>",
  "expected_session_hash": "<complete-session-sha256>",
  "expected_session_revision": 1
}
```

`clarify-round` merges stable question definitions and source facts. Question IDs use lowercase kebab-case. `bindings` maps selected task IDs to semantic fields: `title`, `goal`, `scope`, `exclusions`, `dependencies`, `acceptance`, `validation`, `required_plugin_policy` or `content`. An unchanged question retains the question revision; an edited definition advances the revision and reopens affected answers. The round returns a `CR-` identity, complete independent `question_ids` frontier and matching question revisions. Dependent questions stay registered for a later round.

```json
{
  "questions": [
    {
      "id": "storage-choice",
      "text": "Which storage boundary applies?",
      "recommendation": "Keep the selected project-local boundary.",
      "prerequisites": [],
      "bindings": {"T-<uuid>": ["scope", "dependencies"]}
    },
    {
      "id": "migration-choice",
      "text": "Which migration behavior follows the storage decision?",
      "recommendation": "Preserve existing records within the selected boundary.",
      "prerequisites": ["storage-choice"],
      "bindings": {"T-<uuid>": ["acceptance", "validation"]}
    }
  ],
  "facts": [
    {
      "id": "storage-source",
      "observation": "The inspected source defines project-local storage.",
      "sources": [{"path": "src/storage.py", "sha256": "<inspected-file-sha256>"}],
      "limitations": ["Runtime behavior remains unqualified."]
    }
  ]
}
```

Source paths resolve against the caller execution checkout, independently of canonical queue routing. Stored source-origin identity and file hashes retain the inspected checkout boundary. Changed or unavailable facts block clarity/confirmation until fresh research replaces the facts. Fact `limitations` can be an empty list when supported.

`clarify-answer` requires the displayed round/question identity, exact question revision, actual submitted answer and source evidence. Evidence kind is `owner-message` or `submitted-answer`; a nonempty `reference` identifies the actual owner submission. Recommendations, defaults and elapsed waits never qualify. An exact duplicate answer returns without another session write; conflicting replay rejects mutation.

```json
{
  "round_id": "CR-<uuid>",
  "question_id": "storage-choice",
  "question_revision": 1,
  "answer": "Keep storage within the selected project.",
  "evidence": {"kind": "owner-message", "reference": "Owner message identifying the submitted storage decision."}
}
```

`clarify-revise` accepts `tasks`, a nonempty list of objects with exact selected `task_id` and optional replacement `title`, `body` or `depends_on`. Replacement `body` contains the task sections without the task heading/metadata header. Omitted fields remain preserved. Replacement dependencies are exact `T-` IDs. Fixed provenance/relationship fields and optional validation headers remain unchanged. Open prepared implementation attempts require safe recovery before revision. Invalid acceptance/check mapping, missing dependencies, cycles and unowned tasks reject the complete transaction.

A `clarify-round` payload with an empty decision frontier records the clarity rubric below. Every rubric value requires source-backed assessment; `evidence` contains concrete recheck observations. A false assessment preserves the research prerequisite. A true complete rubric with no unresolved mandatory questions permits current shared-understanding confirmation.

```json
{
  "clarity": {
    "goals": true,
    "scope": true,
    "exclusions": true,
    "dependencies": true,
    "acceptance": true,
    "validation": true,
    "decisions": true,
    "evidence": ["The selected task, accepted decisions and inspected sources define feasible observable acceptance."]
  }
}
```

`clarify-confirm` supplies `task_ids` in the returned frozen order, the exact returned `semantic_fingerprints` mapping and actual owner `evidence` with the same evidence shape as an answer. The owner confirms the displayed current task summary after recheck; a prepared confirmation request supplies no approval. `clarify-resume` reconciles current source drift without selecting new tasks or resuming implementation. `clarify-cancel` requires a nonempty `reason`; a required-interview cancellation retains the unsatisfied admission hold. Repeated unchanged rounds persist a blocked state and concrete next action.
