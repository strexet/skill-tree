# Unity Skill Tree

Vendor-neutral Agent Skills for Unity repository documentation and `FUTURE.md` task workflows.

## Skills

- `skill-tree-unity-repo-documentation`: analyze an existing Unity repository and create or repair AI-oriented documentation.
- `skill-tree-process-future-pending`: research `FUTURE.md` Pending Queue entries and promote only implementation-ready work.
- `skill-tree-implement-next-future-task`: implement exactly one task from `Prioritized Next Changes`.
- `skill-tree-unity-repo-documentation-audit`: audit existing repository documentation against current code and repair drift.

## Trigger Examples

```text
Initialize AI-oriented documentation for this Unity project.
Audit and repair existing Unity repository documentation.
Process pending.
Implement next.
Implement next: Add save migration validation.
```

## Source Model

Canonical source:

```text
skills/skill-tree-<skill-name>/
```

Project installation and global installation paths are determined by the selected agent profile in `config/providers.json`. Optional vendor metadata is non-canonical and may be ignored by other agents.

`REPO_INIT_INSTRUCTIONS.md` remains canonical for Unity documentation behavior and `FUTURE.md` workflow semantics. Generated references are refreshed by:

```bash
python3 scripts/sync_skill_references.py
```

## Quick Install

From a local clone:

```bash
node bin/install.js --list
node bin/install.js --dry-run --all
node bin/install.js --only claude-code --global --copy
node bin/install.js --only codex --project --target /path/to/repo --symlink
```

Direct upstream passthrough for current `skills` CLI profiles:

```bash
node bin/install.js --agent qwen-code --skills skill-tree-process-future-pending --source /path/to/this/repo
```

Do not use a remote one-liner until a real repository URL is intentionally selected.

## Migration

All repository-owned skills use the `skill-tree-` prefix. Legacy installed folders are not active aliases and should be removed before reinstalling. See `docs/MIGRATION.md`.

## Supported Tiers

- Tier 1: explicit provider entries, docs, mocked compatibility tests, and install paths for the requested popular agents.
- Tier 2: current upstream `skills` CLI profiles through explicit `--agent`.
- Tier 3: generic/manual fallback with explicit destination paths.

The provider matrix was checked against the open `skills` CLI README on 2026-06-10. Open Agent Skills specification was checked on 2026-06-10. Vendor docs were checked on 2026-06-10 and known limits are recorded in `docs/AGENT_COMPATIBILITY.md`.

## Validation

When owner policy permits tests:

```bash
python3 scripts/sync_skill_references.py --check
python3 scripts/validate_skill_repository.py --strict
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/test_installer.js tests/test_provider_matrix.js
node bin/install.js --list
node bin/install.js --dry-run --all
git diff --check
```

## Repository Layout

```text
skills/      canonical Agent Skills
config/      provider matrix
bin/         unified installer
adapters/    agent-specific documentation only
scripts/     repository maintenance tools
tests/       Python and Node test coverage
docs/        compatibility, installation, and security notes
```

## Updating Skills

1. Update `REPO_INIT_INSTRUCTIONS.md` only when the canonical workflow changes.
2. Run `python3 scripts/sync_skill_references.py`.
3. Update concise references, validators, fixtures, and docs when behavior changes.
4. Run validation and tests.
5. Review generated diffs before staging.

## Limitations

- Native agent plugin or marketplace packaging is intentionally deferred.
- Some agents rely on the generic Agent Skills paths exposed by the open `skills` CLI rather than verified native skill semantics.
- The Codex upstream `skills` CLI profile path differs from OpenAI's direct user-scope skill path; see compatibility notes.
