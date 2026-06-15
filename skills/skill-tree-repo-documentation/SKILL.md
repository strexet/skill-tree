---
name: skill-tree-repo-documentation
description: >
  Deeply analyze an existing software repository and create, initialize, audit,
  or repair its AI-oriented repository documentation. Use for requests to
  document an unfamiliar project, create PROJECT.md, TECHNICAL.md,
  FEATURES.md, FUTURE.md, RULES.md, AGENTS.md, or establish repository
  documentation. Do not use for ordinary feature implementation, isolated copy
  edits, domain-specific documentation variants, Process pending, or Implement next.
license: MIT
---

# Skill-Tree: Initialize Documents

Use this skill for documentation initialization, audit, or repair in an existing software repository.

Use a domain-specific documentation skill instead when one is available and the request needs domain-specific evidence.

## Required Workflow

1. Confirm repository root and worktree state.
2. Read `references/DOCUMENTATION_OUTPUT_CONTRACT.md`, `references/REPOSITORY_DISCOVERY_CHECKLIST.md`, and `references/PENDING_TASK_FORMAT.md`.
3. Build an evidence inventory before writing narrative documentation.
4. Inspect source code, entry points, package manifests, configuration, build tooling, CI, tests, data/storage boundaries, external integrations, generated files, and existing docs.
5. Create or repair required live documents.
6. Keep implemented, configured, partial, disabled, deprecated, planned, assumption, and open-question states distinct.
7. Keep `FEATURES.md` limited to current implemented or partial behavior. Put future work, plans, backlog, known bugs awaiting fixes, and deferred investigations in `FUTURE.md`.
8. Ensure `FUTURE.md` contains `## Pending Task Format` before `## Pending Queue`.
9. Add meaningful discovered issues to active `FUTURE.md` Backlog, not Pending Queue. Merge with existing entries when same issue exists.
10. Label findings as confirmed bug, strongly suspected issue, documentation inconsistency, or improvement opportunity. Include evidence, affected paths/symbols, impact, suggested direction, acceptance criteria, and focused tests where relevant.
11. Do not present speculation as a confirmed bug.
12. Do not modify product behavior, generated files, dependency versions, build settings, or source code as part of documentation initialization.
13. Run `scripts/validate_repository_documentation.py` against the target repository when validation is allowed.
14. Review final diff for unsupported claims, secrets, personal data, broken links, snapshot-named live files, stale placeholders, and planned work in `FEATURES.md`.
15. Report created/updated docs, drift corrected, issues added to Backlog, potential issues excluded for insufficient evidence, evidence gaps, checks run, checks not run, and remaining risks.

Run skill-local helper by path relative to this skill directory:

```bash
python3 scripts/validate_repository_documentation.py /path/to/repo
```

## Activation Examples

- Initialize repository documentation for this project.
- Document this existing repository.
- Audit and repair project documentation.
- Create AI-oriented documentation for this package or service.

## Negative Examples

- Fix this production bug.
- Update one README sentence.
- Document this domain-specific project with a specialized skill.
- Implement the next `FUTURE.md` task.
- Process pending tasks.

## Completion

Complete only when documentation contract is satisfied, `FEATURES.md` and `FUTURE.md` responsibilities are preserved, meaningful discovered issues are represented in `FUTURE.md` Backlog, and unresolved evidence gaps are explicitly reported.
