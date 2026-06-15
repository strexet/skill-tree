# Test and Evaluation Scenarios

Run automated tests:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/test_installer.js tests/test_provider_matrix.js
```

## General Documentation Skills

Prompt: `Initialize AI-oriented documentation for this existing repository.`

Expected activation: `skill-tree-repo-documentation`.

Prompt: `Audit and repair existing repository documentation.`

Expected activation: `skill-tree-repo-documentation-audit`.

Scoring checks: evidence-backed docs, no planned behavior in `FEATURES.md`, `FUTURE.md` queues and `Pending Task Format` present, stale claims repaired, meaningful discovered issues added or merged in `FUTURE.md` Backlog.

## Unity Documentation Skills

Prompt: `Initialize AI-oriented documentation for this existing Unity project.`

Expected activation: `skill-tree-unity-repo-documentation`.

Prompt: `Audit and repair existing Unity repository documentation.`

Expected activation: `skill-tree-unity-repo-documentation-audit`.

Expected files read: common documentation references, `references/REPO_INIT_INSTRUCTIONS.md`, `references/DOCUMENTATION_OUTPUT_CONTRACT.md`, `references/UNITY_DISCOVERY_CHECKLIST.md`, repository code/settings/assets/docs.

Forbidden behavior: Unity launch, package upgrade, product feature implementation, snapshot generation.

Fixtures: `tests/fixtures/documentation-audit/`.

## Snapshot Skills

Prompt: `Create a documentation snapshot archive.`

Expected activation: `skill-tree-create-documents-snapshot`.

Prompt: `Create a Unity documentation snapshot archive.`

Expected activation: `skill-tree-unity-create-documents-snapshot`.

Forbidden behavior: live document edits, ignored/transient file inclusion, secret inclusion, committing archives without explicit request. Unity snapshot additionally forbids Unity launch, package resolution, and asset reserialization.

Scoring checks: archive members are at zip root, snapshot notices are prepended, live source files are unchanged, included docs are repository-relevant, exclusions are reported.

## Pending Processing Skills

Prompt: `Process pending tasks in FUTURE.md.`

Expected activation: `skill-tree-process-future-pending`.

Prompt: `Process pending tasks for this Unity repository.`

Expected activation: `skill-tree-unity-process-future-pending`.

Forbidden behavior: product code changes, Backlog selection, unresearched promotion, missing questions.

Scoring checks: every pending item researched, promoted tasks are complete, blockers retained pending, validator passes.

## Implement Next Skills

Prompt: `Implement next.`

Expected activation: `skill-tree-implement-next-future-task`.

Prompt: `Implement next Unity task.`

Expected activation: `skill-tree-unity-implement-next-future-task`.

Forbidden behavior: Backlog fallback, Pending implementation, skipping blocked first task, fuzzy matching missing names, implementing multiple tasks.

Scoring checks: prioritized-only selection, clarification gate, one task implemented, docs/tests updated, completed task removed.

## Cross-Agent Activation

Simulate prompts against Tier 1 providers by installing canonical skills into temporary provider paths. Verify the same `SKILL.md` is used and adapter bridges remain short pointers.
