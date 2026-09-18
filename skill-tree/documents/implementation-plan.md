# Approved Skill Tree Implementation Plan

## Authorization and boundaries

The developer approved implementation and scoped local commits. Source repository: `/Users/petr/Projects/_skills/_my/skill-tree`. No push, publication, skill reinstallation, live Yahtzee setup, Unity execution or scheduling. Preserve unrelated work.

## Layout and document rules

Move source skills, common resources, scripts, installer, provider configuration, adapters and tests beneath `skill-tree/`. Place substantive documentation under `skill-tree/documents/`. Use lowercase kebab-case filenames and directories. Preserve required external filenames: `SKILL.md`, root/provider discovery documents, package manifests and `LICENSE`. Update every path, generator, validator, installer and test runner. Remove migration machinery, legacy aliases and format converters; existing projects require explicit setup after reinstallation.

All skill instructions, references, templates, examples and generated prose use English, declarative current-state descriptions and explicit entities instead of pronouns. Structured historical evidence remains permitted. Entry points remain concise and supporting resources load progressively. Installed skills remain self-contained.

## Metadata and priorities

`skill-tree.json` indexes repository-relative documentation, queues, skill catalog, file ownership, generator relationships, validators, source digests and latest audit pointers. Policy references never grant authorization. No automatic full documentation initialization during intake.

`documents/future.md` owns editable task definitions. Task headers contain id, priority, status, parent_pending_ids, processing_run_id, root_task_id, related_task_id, relation and depends_on. Stable UUID identities use P-/T-/B- prefixes. Promotion creates a T- identity and retains Pending provenance. Relations: main, blocker, subtask, followup. Higher integer priority wins; ties follow document order. Explicit developer priority overrides defaults. Intake=100; low=25; required dependency=highest open priority+1; nonblocking finding=root priority-1. No fixed maximum.

`documents/future.json` contains a generated task index and authoritative active-run checkpoint: run/root/current IDs, phase, required/deferred tasks, initial snapshot, processing results, acceptance evidence, partial work, stop reason and next action. Refresh preserves active state and original validation deadlines/retry counters. Source-hash checks, exclusive locks, atomic writes and temporary transaction recovery protect metadata. Corrupt/unsupported state causes an actionable error rather than silent reset.

## History

`history/task-outcomes.jsonl` retains compact terminal records: identities/provenance, disposition, delivered outcome/reason, acceptance checks, limitations/followups, source fingerprints, optional commits, evidence availability and timestamp. Record completion before queue removal. Queue absence never proves completion.

`history/audits/audit-<id>.json` retains scope, source fingerprints, stable findings, corrections, task links, performed checks and coverage gaps. `history/runs/run-<id>.json` retains initial roots, outcomes, unresolved dependencies, consumed limits and next action. Keep latest 10 audits and 10 finished runs; protect records referenced by unresolved findings, active runs or explicit pins. Keep compact task outcomes without count-based expiry. Large evidence resides in ignored artifacts. Mark expired evidence unavailable. Source changes make audit coverage stale. Historical passes never establish current validation or authorization. Exclude transcripts, reasoning, routine tool events, repeated snapshots, secrets and unmeasured token claims.

## Leaf contracts and orchestration

Add Pending: clarify material ambiguity; brief understood English intake; duplicate checks; stable ID and dependency context; return Pending ID.

Process Pending: optional IDs/exact normalized names, otherwise whole Pending queue. Resolve complete selection before mutation; reject absent/ambiguous targets without fallback. Deep repository research; split/merge support; preserve parent IDs; structured created/reused/retained/resolved results.

Implement Next: highest-priority Prioritized task, ties by order; optional explicit ID/name. Never Pending/Backlog fallback; blocked selection stops. Structured completed/dependency/clarification/validation-blocked outcomes, changed files, findings, review and validation evidence, authorized commits.

Work through next: checkpoint one main; implement; intake findings; process exact required Pending IDs; recursively execute required dependency closure; resume/validate parent; process nonblocking findings and defer implementation. Finish only when main and required descendants complete.

Implement All: freeze initial Prioritized identities; execute Work through next cycle in priority order; include required discovered dependencies; exclude new nonblocking work; deduplicate completed dependencies. Stop on cycles, unresolved decisions, failed mandatory validation or a full cycle without task/dependency progress. Preserve authorization, deadlines and consumed limits. Both orchestrators install independently with applicable generated contracts/helpers.

## Verification and delivery

Behavioral tests: naming and discovery exceptions; document rules; IDs/priorities and targeted split/merge; checkpoint preservation and interruption; concurrent/corrupt state; dependency recursion/parent resumption/deferred findings/snapshot boundaries; completion before removal; audit freshness/retention pins/evidence expiry; standalone install/provider discovery; absence of legacy conversion machinery.

Run generated resource checks, strict validators, Python/Node tests, installer list/dry-run and git diff --check. Scoped commits: layout/document rules; metadata/history/leaf contracts; orchestration/integration.

## Current checkpoint

Phase: final source review and scoped commits. Layout, thirteen skill entry points, canonical contracts, state/history helpers and standalone orchestration are implemented. Behavioral qualification: 49 Python checks and 24 Node checks pass. Source synchronization, document rules, installer list and installer dry-run pass. The ancillary bundled quick validator cannot run because available Python runtimes lack PyYAML; strict repository validation checks current frontmatter and resource integrity. Remaining work: final staged review, scoped commits, qualification evidence and manifest refresh.
