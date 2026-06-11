# Pending Processing Checklist

## Locate

- Find the applicable `FUTURE.md`.
- Confirm it contains `Pending Queue`, `Prioritized Next Changes`, and `Backlog`.
- MUST read repository `AGENTS.md`, `RULES.md`, or equivalent rules before editing.
- MUST read repository/document map if one exists.
- MUST read current `FEATURES.md`, active `FUTURE.md`, and task-relevant architecture/domain docs.

## Read Pending

- Read the complete Pending Queue.
- Preserve source context, evidence, reproduction, constraints, and requested priority.

## Research

- Search affected code, assets, scenes, prefabs, settings, tests, and docs.
- Check related items in all three queues.
- Verify referenced paths and symbols still exist.
- Determine implementation status: implemented, stale, duplicate, contradictory, blocked, or valid.

## Expand

- Identify ownership and likely paths.
- Add current behavior, desired behavior, touch list, discovery allowance, out of scope, implementation constraints, validation, acceptance, docs updates, and risks.
- Add task-specific questions covering UX, architecture, files, state, persistence, serialization, platform behavior, compatibility, migration, recovery, diagnostics, testing, rollout, and non-goals.

## Resolve Questions

- Use repository evidence where possible.
- Mark answers as resolved by evidence, resolved by owner decision, recommended default, unresolved blocking, or unresolved non-blocking.

## Promote or Retain

- Promote only implementation-ready work.
- Retain blocked or insufficiently understood items in Pending Queue.
- Merge overlapping entries only when no intent is lost.
- Remove original pending entries only after preserving their information.

## Stop Conditions

- Required owner decision blocks implementation.
- A request conflicts with current architecture or platform constraints and no safe resolution exists.
- Evidence is insufficient to identify affected ownership.
- Required repository rules or task-relevant documents are missing or contradictory.
- The user asked to implement rather than process; route to `skill-tree-implement-next-future-task` only for prioritized tasks.
- Never process from `FUTURE.md` alone.
