# Repository Agent Instructions

## Required Reading

- Read `SKILL_REPOSITORY_CREATION_INSTRUCTIONS.md` before changing repository structure, installer behavior, provider metadata, tests, or skill contracts.
- Read `common/references/` before changing general documentation, snapshot, or `FUTURE.md` workflow behavior.
- Read `REPO_INIT_INSTRUCTIONS.md` before changing Unity documentation workflow behavior.
- Read `docs/INSTALLATION_ARCHITECTURE.md` before changing the installer or provider matrix.
- Read `docs/AGENT_COMPATIBILITY.md` before changing agent support claims.
- Read `docs/MIGRATION.md` before changing skill names or installation compatibility.

## Repository Map

- Canonical skills: `skills/skill-tree-*/`.
- Skill installer: `bin/install.js`; shell wrappers: `install.sh`, `install.ps1`.
- Provider matrix: `config/providers.json`.
- Agent adapters and bridge notes: `adapters/`.
- Shared bridge text: `src/init-rules/skill-tree-skills.md`.
- Repository validators and generators: `scripts/`.
- Python and Node tests: `tests/`.
- Compatibility/security/installation docs: `docs/`.

## Source-of-Truth Rules

- `common/references/` is canonical for general documentation, snapshot, and `FUTURE.md` workflow behavior.
- `REPO_INIT_INSTRUCTIONS.md` is canonical for Unity repository analysis and Unity-specific documentation workflow behavior.
- `scripts/sync_skill_references.py` owns generated references. Do not edit generated references manually.
- `config/providers.json` is canonical for provider ids, paths, detection metadata, upstream profiles, and adapter bridges.
- `LICENSE` is the existing repository license. The SPDX identifier is `MIT`.
- `docs/AGENT_COMPATIBILITY.md` is canonical for support tier limits and official reference dates.
- `docs/INSTALLATION_ARCHITECTURE.md` is canonical for installer behavior.
- `docs/MIGRATION.md` is canonical for breaking skill-name migration notes.
- `FEATURES.md`, when generated in target repositories by these skills, describes current implemented or partial behavior only.
- `FUTURE.md`, when generated in target repositories by these skills, is the single source of truth for planned work, backlog items, known bugs awaiting fixes, and deferred investigations.

## Portable Skill Rules

- Canonical skills live only in `skills/skill-tree-<skill-name>/`.
- Every repository-owned skill directory and `SKILL.md` frontmatter name must start with `skill-tree-`.
- Installed skills must remain self-contained after copying.
- `SKILL.md` files must follow the open Agent Skills format: YAML frontmatter with `name` and `description`, then focused Markdown instructions.
- Keep detailed behavior in `references/` and deterministic helpers in `scripts/`.
- Do not create divergent skill implementations for specific agents.

## FUTURE.md Workflow Orientation

Before processing or implementing `FUTURE.md` work, agents MUST read this file, then inspect any target repository `AGENTS.md`, `RULES.md`, repository/document map if present, relevant current-state docs, relevant code, and relevant tests.

Agents MUST NOT implement from `FUTURE.md` alone. They MUST verify paths, symbols, task assumptions, duplicate work, and current implementation state before editing. If required context is missing or contradictory, stop and report the blocker instead of guessing architecture.

## Provider and Adapter Rules

- Vendor behavior belongs in `adapters/`, optional `agents/openai.yaml`, or `config/providers.json`.
- Verify version-sensitive agent claims against official docs or the current open `skills` CLI.
- Directory-only probes are soft and must not trigger automatic installation.
- Soft providers install only when explicitly selected.

## Validation Commands

Run these before staging, when owner policy permits tests:

```bash
python3 scripts/sync_skill_references.py
python3 scripts/sync_skill_references.py --check
python3 scripts/validate_skill_repository.py --strict
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/test_installer.js tests/test_provider_matrix.js
node bin/install.js --list
node bin/install.js --dry-run --all
git diff --check
git status --short
```

## Git and Release Safety

- Do not add a remote, push, publish, tag, or create marketplace packages without owner instruction.
- Do not commit unless explicitly asked.
- Do not select or change the repository license without owner input.
- Do not overwrite unrelated user files or complete instruction files.
