# Skill Tree

Vendor-neutral Agent Skills for repository documentation, `FUTURE.md` task workflows, and optional Unity-specific repository workflows.

## Skills

General skills:

- `skill-tree-repo-documentation` — Skill-Tree: Initialize Documents: analyze an existing repository and create or repair AI-oriented documentation.
- `skill-tree-repo-documentation-audit` — Skill-Tree: Audit Documents: audit existing repository documentation against current code and repair drift.
- `skill-tree-add-pending-task` — Skill-Tree: Add Pending Task: clarify an informal request and capture a concise task with priority in Pending Queue; also works in Unity repositories.
- `skill-tree-process-future-pending` — Skill-Tree: Process Pending Tasks: research `FUTURE.md` Pending Queue entries and promote only implementation-ready work.
- `skill-tree-implement-next-future-task` — Skill-Tree: Implement Next Task: implement exactly one task from `Prioritized Next Changes`.
- `skill-tree-create-documents-snapshot` — Skill-Tree: Create Snapshot: create explicit-request-only Markdown documentation snapshot archives.

Unity-specific skills:

- `skill-tree-unity-repo-documentation` — Skill-Tree-Unity: Initialize Documents: analyze an existing Unity repository and create or repair AI-oriented documentation.
- `skill-tree-unity-repo-documentation-audit` — Skill-Tree-Unity: Audit Documents: audit existing Unity documentation against code, assets, settings, tests, and docs.
- `skill-tree-unity-process-future-pending` — Skill-Tree-Unity: Process Pending Tasks: process Unity repository pending tasks with Unity-specific evidence.
- `skill-tree-unity-implement-next-future-task` — Skill-Tree-Unity: Implement Next Task: implement one prioritized Unity repository task.
- `skill-tree-unity-create-documents-snapshot` — Skill-Tree-Unity: Create Snapshot: create explicit Unity documentation snapshot archives.

## Trigger Examples

```text
Initialize AI-oriented documentation for this repository.
Audit and repair existing repository documentation.
Create a documentation snapshot archive.
Add pending: not urgent, let me turn off the dice shake in settings.
Add this feature idea to the pending queue: add replay on the loss screen.
Process pending.
Implement next.
Implement next: Add save migration validation.

Initialize AI-oriented documentation for this Unity project.
Audit and repair existing Unity repository documentation.
```

## Recommended task flow

Use `Add pending: <informal request>` to capture one idea, then `Process pending` to research and promote ready work, then `Implement next` to implement exactly one prioritized task. Intake is deliberately shallow: read relevant docs, clarify missing intent, preserve source wording, and leave architecture/code/test discovery for processing.

Intake defaults to Highest priority and first in Pending Queue. Explicit low/later priority defaults to last; other stated priorities follow local conventions. A requested relative position wins over default ordering. The skill asks about conflicting priority, unclear placement or missing subject/outcome before writing. It preserves existing task order and never promotes a task during intake.

### Intake output

Entries use the repository's nested Markdown format. Minimum fields are title, Priority, Description, Expected behavior and Source; include Current context and other sections only when useful. Do not create a full prioritized specification or mark the entry Ready.

```markdown
- Add replay from the loss screen
  - Priority
    - Highest — default; first in Pending Queue.
  - Description
    - Let the player start another game directly from the loss screen.
  - Expected behavior
    - A replay action on the loss screen starts another game.
  - Source
    - User request: “add replay on the loss screen so I can start another game there”.
```

See [intake decisions and examples](common/references/PENDING_TASK_INTAKE.md) and [the shared pending template](common/references/PENDING_TASK_FORMAT.md). Unknown implementation details may be deferred; unclear intent must be answered before adding the entry.

## Source Model

Canonical source:

```text
skills/skill-tree-<skill-name>/
```

Shared parent references live in `common/references/`. Shared helper scripts live in `common/scripts/`. Installed skills remain self-contained because `scripts/sync_skill_references.py` copies generated common references and generated helper-script copies into each skill folder that needs them.

Unity documentation behavior remains canonical in `REPO_INIT_INSTRUCTIONS.md`. General workflow behavior lives in `common/references/`.

Refresh generated files with:

```bash
python3 scripts/sync_skill_references.py
```

Project installation and global installation paths are determined by `config/providers.json`. Optional vendor metadata is non-canonical and may be ignored by other agents.

## Quick Install

From a local clone:

```bash
node bin/install.js --list
node bin/install.js --dry-run --all
node bin/install.js --only claude-code --global --copy
node bin/install.js --only codex --project --target /path/to/repo --symlink
```

Install only general workflow skills:

```bash
node bin/install.js --only codex --project --target /path/to/repo --copy --skills skill-tree-repo-documentation skill-tree-add-pending-task skill-tree-process-future-pending skill-tree-implement-next-future-task
```

Install the Unity workflow plus portable task intake:

```bash
node bin/install.js --only codex --project --target /path/to/unity-repo --copy --skills skill-tree-unity-repo-documentation skill-tree-add-pending-task skill-tree-unity-process-future-pending skill-tree-unity-implement-next-future-task
```

Direct upstream passthrough for current `skills` CLI profiles:

```bash
node bin/install.js --agent qwen-code --skills skill-tree-process-future-pending --source /path/to/this/repo
```

Do not use a remote one-liner until a real repository URL is intentionally selected.

## Migration

All repository-owned skills use the `skill-tree-` prefix. Unity-specific skills additionally use `skill-tree-unity-` in folder/frontmatter names and `Skill-Tree-Unity:` in display names. Legacy installed folders are not active aliases and should be removed before reinstalling. See `docs/MIGRATION.md`.

## Supported Tiers

- Tier 1: explicit provider entries, docs, mocked compatibility tests, and install paths for requested popular agents.
- Tier 2: current upstream `skills` CLI profiles through explicit `--agent`.
- Tier 3: generic/manual fallback with explicit destination paths.

Provider matrix was checked against the open `skills` CLI README on 2026-06-10. Open Agent Skills specification was checked on 2026-06-10. Vendor docs were checked on 2026-06-10 and known limits are recorded in `docs/AGENT_COMPATIBILITY.md`.

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
common/      shared parent references and scripts copied into self-contained skills
skills/      canonical Agent Skills
config/      provider matrix
bin/         unified installer
adapters/    agent-specific documentation only
scripts/     repository maintenance tools
tests/       Python and Node test coverage
docs/        compatibility, installation, and security notes
```

## Updating Skills

1. Update `common/references/` for general workflow behavior.
2. Update `common/scripts/` for shared helper behavior.
3. Update `REPO_INIT_INSTRUCTIONS.md` only when Unity-specific workflow changes.
4. Run `python3 scripts/sync_skill_references.py`.
5. Update concise references, validators, fixtures, and docs when behavior changes.
6. Run validation and tests when owner policy allows.
7. Review generated diffs before staging.

## Limitations

- Native agent plugin or marketplace packaging is intentionally deferred.
- Some agents rely on generic Agent Skills paths exposed by open `skills` CLI rather than verified native skill semantics.
- Codex upstream `skills` CLI profile path differs from OpenAI direct user-scope skill path; see compatibility notes.
