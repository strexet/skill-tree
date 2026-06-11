# Documentation Output Contract

This contract summarizes the deliverables owned by `REPO_INIT_INSTRUCTIONS.md`. The full source remains `references/REPO_INIT_INSTRUCTIONS.md`.

## Required Root Files

- `README.md`: human entry point and setup summary.
- `AGENTS.md`: concise AI-agent handoff and mandatory reading.

## Required `Documents/` Files

- `PROJECT.md`
- `TECHNICAL.md`
- `FEATURES.md`
- `FUTURE.md`
- `RULES.md`
- `REPOSITORY_MAP.md`
- `BUILD_AND_RELEASE.md`
- `TESTING.md`
- `DEPENDENCIES.md`

## Optional Documents

Create optional specialized documents only when repository evidence justifies them:

- `UX_UI_MANIFEST.md`
- `PLATFORM_INTEGRATIONS.md`
- `BACKEND_AND_NETWORKING.md`
- `DATA_AND_PERSISTENCE.md`
- `ANALYTICS_AND_MONETIZATION.md`
- `LOCALIZATION.md`
- `SECURITY.md`
- `TROUBLESHOOTING.md`
- `REFERENCES.md`
- `DECISIONS.md`
- `GLOSSARY.md`

## Ownership Map

- `PROJECT.md`: product purpose, scope, users, non-goals.
- `TECHNICAL.md`: stack, architecture, data flow, constraints.
- `FEATURES.md`: implemented, partial, configured, disabled, or deprecated feature behavior only. No future-work, roadmap, next-step, pending, or implementation-plan sections.
- `FUTURE.md`: Pending Queue, Prioritized Next Changes, Backlog, planned improvements, known bugs awaiting fixes, documentation improvements, proposed features, refactoring plans, and deferred investigations.
- `RULES.md`: AI-agent workflow and repository editing rules.
- `REPOSITORY_MAP.md`: physical layout and ownership.
- `BUILD_AND_RELEASE.md`: local builds, CI, signing, release flow.
- `TESTING.md`: test topology and validation matrix.
- `DEPENDENCIES.md`: packages, SDKs, sources, update constraints.
Snapshot archive creation is handled by `skill-tree-create-documents-snapshot`, not by generated live documentation.

## Live Filename Rules

Live documents use stable names without timestamps or snapshot markers. Snapshot copies belong only inside explicit snapshot archives.

## State Rules

- Implemented behavior belongs in current-state docs.
- Planned behavior belongs in `FUTURE.md`.
- Current limitations may be documented in `FEATURES.md`; plans to resolve them belong in `FUTURE.md`.
- Assumptions and open questions must be marked.
- Repository evidence outranks existing docs for current behavior.

## Issue Discovery

Documentation work must inspect key implementation paths, tests, error handling, state transitions, persistence, mutation logic, and existing `FUTURE.md` entries. Add meaningful discovered issues to the active `FUTURE.md` Backlog, not Pending Queue, with evidence, affected paths/symbols, impact, suggested direction, acceptance criteria, and focused tests. Distinguish confirmed bugs, strongly suspected issues, documentation inconsistencies, and improvement opportunities.

## `FUTURE.md` Queues

`FUTURE.md` must contain:

```text
## Pending Queue
## Prioritized Next Changes
## Backlog
```

`Implement next` uses only `Prioritized Next Changes`. `Process pending` researches Pending Queue entries and promotes only implementation-ready tasks.

## Final Handoff

Report created and updated files, optional documents and why, major verified findings, drift corrected, issues added to Backlog, potential issues excluded for insufficient evidence, open questions, checks run, checks not run, risks, and a suggested commit message.
