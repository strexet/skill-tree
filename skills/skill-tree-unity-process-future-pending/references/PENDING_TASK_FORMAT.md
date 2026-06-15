<!--
GENERATED FILE
Source: REPO_INIT_INSTRUCTIONS.md
Generator: scripts/sync_skill_references.py
Do not edit manually. Update the source document and rerun the generator.
-->

### 14.8 Pending item template

Use this format when an AI agent adds an item to `Pending Queue`. Keep the entry concise, preserve source context, and use nested Markdown lists only. Include only relevant sections.

When initializing or repairing repository documentation, copy this template into the target repository's `Documents/FUTURE.md` under `## Pending Task Format`.

```text
- Task title
  - Description
    - State what should change, why, where it applies, and what problem it solves.
  - Current context
    - Summarize known current behavior, relevant Unity systems, assemblies, scenes, prefabs, ScriptableObjects, settings, tests, docs, or tooling.
  - Source verification requirements
    - MUST inspect current project code, assets, settings, and tests before promotion when assumptions may be stale.
    - MUST verify official Unity, package, platform, SDK, backend, store, or other external behavior before relying on it.
    - MUST update the task if source inspection contradicts the current assumptions.
  - Requirements
    - List concrete, testable requirements.
  - Unity/game behavior
    - Describe runtime, Editor, build, platform, scene/prefab, input, UI, gameplay, content, or tool behavior when relevant.
  - Data/model behavior
    - Describe state, persistence, serialization, save migration, Addressables/Resources, networking, cache, backend, analytics, or mutation behavior when relevant.
  - Edge cases
    - Include missing data, stale data, disabled states, duplicate entries, partial failure, cancellation, concurrency, offline behavior, platform differences, or old save/config compatibility when relevant.
  - Expected behavior
    - Describe the final observable outcome.
  - Suggested implementation
    - Name likely files, symbols, assets, tests, helpers, docs, and reuse points without over-constraining the developer.
  - Acceptance criteria
    - List concrete checks that can be verified manually, by tests, or by code review.
  - Tests
    - List focused test scenarios or validation steps when logic, state, serialization, platform behavior, tooling, or important UI behavior changes.
  - Documentation updates
    - Name docs that likely need updates, especially `FEATURES.md`, `FUTURE.md`, `TECHNICAL.md`, `REPOSITORY_MAP.md`, `TESTING.md`, or specialized integration docs.
```

Pending entries do not need the full questions section. The mandatory questions section is created during `Process pending tasks` or `Process pending`.

Do not use vague titles such as `Fix UI`, `Improve things`, `Update page`, or `Bug`. Use short action-oriented titles. Do not add empty sections. Do not put future work in `FEATURES.md` while drafting pending items.
