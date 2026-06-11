# Test and Evaluation Scenarios

Run automated tests:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/test_installer.js tests/test_provider_matrix.js
```

## Documentation Skill

Prompt: `Initialize AI-oriented documentation for this existing Unity project.`

Expected activation: `skill-tree-unity-repo-documentation`.

Expected files read: `references/REPO_INIT_INSTRUCTIONS.md`, `references/DOCUMENTATION_OUTPUT_CONTRACT.md`, `references/UNITY_DISCOVERY_CHECKLIST.md`, repository code/settings/assets/docs.

Forbidden behavior: Unity launch, package upgrade, product feature implementation, snapshot generation.

Scoring checks: evidence-backed docs, no planned behavior in `FEATURES.md`, `FUTURE.md` queues present, validation reported.

Negative prompts:

- `Fix a NullReferenceException in PlayerController.`
- `Translate this changelog.`
- `Update one sentence in README.`
- `Implement next.`

## Documentation Audit Skill

Prompt: `Audit and repair existing Unity repository documentation.`

Expected activation: `skill-tree-unity-repo-documentation-audit`.

Fixtures: `tests/fixtures/documentation-audit/`.

Forbidden behavior: product code refactors, docs-only comparison without code inspection, duplicate backlog issue creation, future-work sections in `FEATURES.md`.

Scoring checks: baseline docs verified, stale claims repaired, missing docs recreated from evidence, meaningful discovered issues added or merged in `FUTURE.md` Backlog, audit summary reports inspected context.

## Snapshot Skill

Prompt: `Create a documentation snapshot archive.`

Expected activation: `skill-tree-create-documents-snapshot`.

Forbidden behavior: live document edits, Unity launch, asset reserialization, ignored/transient file inclusion, secret inclusion, committing archives without explicit request.

Scoring checks: archive members are at zip root, snapshot notices are prepended, live source files are unchanged, included docs are repository-relevant, exclusions are reported.

## Pending Processing Skill

Prompt: `Process pending tasks in FUTURE.md.`

Expected activation: `skill-tree-process-future-pending`.

Forbidden behavior: product code changes, Backlog selection, unresearched promotion, missing questions.

Scoring checks: every pending item researched, promoted tasks are complete, blockers retained pending, validator passes.

## Implement Next Skill

Prompt: `Implement next.`

Expected activation: `skill-tree-implement-next-future-task`.

Forbidden behavior: Backlog fallback, Pending implementation, skipping blocked first task, fuzzy matching missing names, implementing multiple tasks.

Scoring checks: prioritized-only selection, clarification gate, one task implemented, docs/tests updated, completed task removed.

## Cross-Agent Activation

Simulate prompts against Tier 1 providers by installing canonical skills into temporary provider paths. Verify the same `SKILL.md` is used and adapter bridges remain short pointers.
