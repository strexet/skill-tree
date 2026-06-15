<!--
GENERATED FILE
Source: common/references/DOCUMENTATION_OUTPUT_CONTRACT.md
Generator: scripts/sync_skill_references.py
Do not edit manually. Update the source document and rerun the generator.
-->

# Documentation Output Contract

This shared contract is the general parent contract for repository documentation.

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
- `FEATURES.md`: implemented, partial, configured, disabled, or deprecated behavior only.
- `FUTURE.md`: Pending Task Format, Pending Queue, Prioritized Next Changes, Backlog, planned improvements, known bugs awaiting fixes, documentation improvements, proposed features, refactoring plans, and deferred investigations.
- `RULES.md`: AI-agent workflow and repository editing rules.
- `REPOSITORY_MAP.md`: physical layout and ownership.
- `BUILD_AND_RELEASE.md`: local builds, CI, release flow.
- `TESTING.md`: test topology and validation matrix.
- `DEPENDENCIES.md`: dependencies, SDKs, sources, update constraints.

Snapshot archive creation is handled by the snapshot skill, not by generated live documentation.

## State Rules

- Implemented behavior belongs in current-state docs.
- Planned behavior belongs in `FUTURE.md`.
- Current limitations may be documented in `FEATURES.md`; plans to resolve them belong in `FUTURE.md`.
- Assumptions and open questions must be marked.
- Repository evidence outranks existing docs for current behavior.

## Issue Discovery

Documentation work must inspect key implementation paths, tests, error handling, state transitions, persistence, mutation logic, and existing `FUTURE.md` entries. Add meaningful discovered issues to active `FUTURE.md` Backlog, not Pending Queue, with evidence, affected paths/symbols, impact, suggested direction, acceptance criteria, and focused tests when relevant.

## Final Handoff

Report created and updated files, optional documents and why, major verified findings, drift corrected, issues added to Backlog, potential issues excluded for insufficient evidence, open questions, checks run, checks not run, risks, and a suggested commit message.
