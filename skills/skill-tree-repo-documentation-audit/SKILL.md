---
name: skill-tree-repo-documentation-audit
description: >
  Audit existing software repository documentation against the current codebase,
  tests, configuration, repository structure, and workflow rules. Use after
  documentation already exists, after major changes or repository restructures,
  before releases, or when documentation drift is suspected. Fix stale
  documentation in place, enforce FEATURES.md and FUTURE.md responsibilities,
  recreate missing baseline documents from current evidence, and add meaningful
  discovered issues to FUTURE.md without changing unrelated product code.
license: MIT
---

# Skill-Tree: Audit Documents

Use this skill for ongoing audit and maintenance of existing repository documentation.

Use a domain-specific audit skill instead when one is available and the request needs domain-specific evidence.

## Mandatory Orientation

Before editing, MUST inspect:

1. Repository root and worktree state.
2. `AGENTS.md`, `RULES.md`, or equivalent repository rules.
3. Repository/document map if one exists.
4. Existing `PROJECT.md`, `TECHNICAL.md`, `FEATURES.md`, `FUTURE.md`, `RULES.md`, `AGENTS.md`, `REPOSITORY_MAP.md`, and other live docs.
5. Key code, tests, build configuration, dependency manifests, configuration, and agent workflow files relevant to documented claims.
6. Local `references/DOCUMENTATION_OUTPUT_CONTRACT.md`, `references/REPOSITORY_DISCOVERY_CHECKLIST.md`, and `references/PENDING_TASK_FORMAT.md`.
7. `skill-tree-repo-documentation` expectations when other baseline document expectations are unclear.

MUST NOT audit docs by comparing documents only. Verify substantial claims against code and tests.

## Required Workflow

1. Inventory all repository documentation and classify each document role.
2. Verify expected baseline documents exist. Recreate missing required docs from current repository evidence, not memory.
3. Validate documented features against entry points, main modules, data flow, persistence, external integrations, tests, known constraints, and current configuration.
4. Enforce document responsibilities:
   - `FEATURES.md`: current implemented, partial, configured, disabled, or deprecated behavior only.
   - `FUTURE.md`: planned work, backlog, known bugs awaiting fixes, deferred investigations, documentation improvements, and proposed features.
   - `AGENTS.md` / `RULES.md`: repository workflow rules and source-of-truth hierarchy.
   - Architecture docs: current architecture only.
   - Historical docs: clearly marked as historical.
5. Ensure `FUTURE.md` contains `## Pending Task Format` before `## Pending Queue`. If absent or incomplete, add or repair the repo-local nested Markdown template from `references/PENDING_TASK_FORMAT.md`.
6. Fix stale paths, renamed symbols, outdated behavior, contradictions, duplicate guidance, obsolete future sections in current-state docs, and unsupported claims.
7. While inspecting code, identify meaningful issues: confirmed bugs, likely bugs, risky logic, documentation/code drift, missing validation, missing tests, error-handling gaps, security/data-safety concerns, maintainability problems, performance risks, and dead or misleading code.
8. Add meaningful findings to active `FUTURE.md` Backlog using repository task structure. Do not add documentation/audit findings to Pending Queue. Merge with existing tasks when same issue exists.
9. Do not change product code unless user explicitly requested implementation or a documentation-specific defect cannot be repaired otherwise.
10. Run documentation validators when owner policy allows validation.
11. Review final diff for secrets, personal data, absolute local paths, stale references, unsupported compatibility claims, malformed Markdown/frontmatter, placeholders, and accidental generated-file edits.

## Audit Summary

Final response MUST report documents inspected, missing documents created, documents removed or role-corrected, drift corrected, paths/symbols updated, contradictions resolved, Pending Task Format added or confirmed, Backlog items added or merged, checks run, checks not run, and required context inspected.

## Completion

Complete only when straightforward documentation drift is fixed in place, meaningful discovered issues are represented in `FUTURE.md` Backlog, duplicate backlog entries are avoided, Pending Task Format is present when `FUTURE.md` exists, and remaining unverified claims are explicitly reported.
