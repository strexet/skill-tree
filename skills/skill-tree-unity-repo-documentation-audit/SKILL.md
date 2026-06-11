---
name: skill-tree-unity-repo-documentation-audit
description: Audit existing Unity repository documentation against the current codebase, tests, configuration, repository structure, and skill/workflow rules. Use after documentation already exists, after major changes or repository restructures, before releases, or when documentation drift is suspected. Fix stale documentation in place, enforce FEATURES.md and FUTURE.md responsibilities, recreate missing baseline documents from current evidence, and add meaningful discovered issues to FUTURE.md without changing unrelated product code.
license: MIT
---

# Skill-Tree: Audit Documents

Use this skill for ongoing audit and maintenance of existing Unity repository documentation. For first-time documentation initialization, use `skill-tree-unity-repo-documentation`.

Do not use this skill to implement product features, refactor code, upgrade Unity, or process/implement `FUTURE.md` tasks.

## Mandatory Orientation

Before editing, MUST inspect:

1. Repository root and worktree state.
2. `AGENTS.md`, `RULES.md`, or equivalent repository rules.
3. Repository/document map if one exists.
4. Existing `PROJECT.md`, `TECHNICAL.md`, `FEATURES.md`, `FUTURE.md`, `RULES.md`, `AGENTS.md`, `REPOSITORY_MAP.md`, and other live docs.
5. Key code, tests, build configuration, package manifests, settings, and agent workflow files relevant to documented claims.
6. Current `skill-tree-unity-repo-documentation` specification when baseline document expectations are unclear.

MUST NOT audit docs by comparing documents only. Verify substantial claims against code and tests.

## Required Workflow

1. Inventory all repository documentation and classify each document role.
2. Verify the expected baseline document set exists. Recreate missing required docs from current repository evidence, not memory.
3. Validate documented features against entry points, main classes/modules, data flow, persistence, external integrations, tests, known constraints, and current settings.
4. Enforce document responsibilities:
   - `FEATURES.md`: current implemented, partial, configured, disabled, or deprecated behavior only.
   - `FUTURE.md`: planned work, backlog, known bugs awaiting fixes, deferred investigations, documentation improvements, and proposed features.
   - `AGENTS.md` / `RULES.md`: repository workflow rules and source-of-truth hierarchy.
   - Architecture docs: current architecture only.
   - Historical docs: clearly marked as historical.
5. Fix stale paths, renamed symbols, outdated behavior, contradictions, duplicate guidance, obsolete future sections in current-state docs, and unsupported claims.
6. While inspecting code, identify meaningful issues: confirmed bugs, likely bugs, risky logic, documentation/code drift, missing validation, missing tests, error-handling gaps, security/data-safety concerns, maintainability problems, performance risks, and dead or misleading code.
7. Add meaningful findings to active `FUTURE.md` Backlog using repository task structure. Do not add documentation/audit findings to Pending Queue. Merge with existing tasks when same issue exists. Do not duplicate tasks.
8. Distinguish finding type: confirmed bug, strongly suspected issue, documentation inconsistency, or improvement opportunity. Include evidence, affected paths/symbols, impact, suggested direction, acceptance criteria, and focused tests where relevant.
9. Do not change product code unless user explicitly requested implementation or a documentation-specific defect cannot be repaired otherwise.
10. Run documentation validators when owner policy allows validation.
11. Review final diff for secrets, personal data, absolute local paths, stale references, unsupported compatibility claims, malformed Markdown/frontmatter, placeholders, and accidental generated-file edits.

## FEATURES.md / FUTURE.md Rule

`FEATURES.md` may mention current limitations only as present behavior. Plans to resolve limitations must live in `FUTURE.md`.

When implementation is already complete, update or remove the matching `FUTURE.md` task instead of leaving implemented work in active backlog.

## Audit Summary

Final response MUST report:

- Documents inspected.
- Missing documents created.
- Documents removed, merged, or role-corrected.
- Drift corrected.
- Paths/symbols updated.
- Contradictions resolved.
- Backlog items added or merged.
- Confirmation that documentation/audit findings were not added to Pending Queue.
- Potential issues not added because evidence was insufficient.
- Checks run and checks not run.
- Required context inspected.

## Completion

Complete only when straightforward documentation drift is fixed in place, meaningful discovered issues are represented in `FUTURE.md` Backlog, duplicate backlog entries are avoided, and remaining unverified claims are explicitly reported.
