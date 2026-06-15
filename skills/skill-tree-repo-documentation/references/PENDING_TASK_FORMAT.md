<!--
GENERATED FILE
Source: common/references/PENDING_TASK_FORMAT.md
Generator: scripts/sync_skill_references.py
Do not edit manually. Update the source document and rerun the generator.
-->

# Pending Task Format

Use this format when an AI agent adds an item to `Pending Queue`. Keep the entry concise, preserve source context, and use nested Markdown lists only. Include only relevant sections.

When initializing or repairing repository documentation, copy this template into the target repository's `Documents/FUTURE.md` under `## Pending Task Format`.

```text
- Task title
  - Description
    - State what should change, why, where it applies, and what problem it solves.
  - Current context
    - Summarize known current behavior, relevant modules, entry points, configuration, data, tests, docs, tooling, or integrations.
  - Source verification requirements
    - MUST inspect current project code, configuration, data files, docs, and tests before promotion when assumptions may be stale.
    - MUST verify official package, platform, SDK, backend, service, store, or other external behavior before relying on it.
    - MUST update the task if source inspection contradicts the current assumptions.
  - Requirements
    - List concrete, testable requirements.
  - Runtime/product behavior
    - Describe user-visible, CLI, service, job, package, workflow, UI, API, operational, or content behavior when relevant.
  - Data/model behavior
    - Describe state, persistence, serialization, migration, storage, networking, cache, backend, analytics, or mutation behavior when relevant.
  - Edge cases
    - Include missing data, stale data, disabled states, duplicate entries, partial failure, cancellation, concurrency, offline behavior, platform differences, or old data/config compatibility when relevant.
  - Expected behavior
    - Describe the final observable outcome.
  - Suggested implementation
    - Name likely files, symbols, tests, helpers, docs, and reuse points without over-constraining the developer.
  - Acceptance criteria
    - List concrete checks that can be verified manually, by tests, or by code review.
  - Tests
    - List focused test scenarios or validation steps when logic, state, serialization, platform behavior, tooling, or important UI behavior changes.
  - Documentation updates
    - Name docs that likely need updates, especially `FEATURES.md`, `FUTURE.md`, `TECHNICAL.md`, `REPOSITORY_MAP.md`, `TESTING.md`, or specialized integration docs.
```

Pending entries do not need the full questions section. The mandatory questions section is created during `Process pending tasks` or `Process pending`.

Do not use vague titles such as `Fix UI`, `Improve things`, `Update page`, or `Bug`. Use short action-oriented titles. Do not add empty sections. Do not put future work in `FEATURES.md` while drafting pending items.
