# Installation Architecture

Last verified: 2026-06-10.

## Canonical Ownership

Canonical behavior lives under `skills/skill-tree-<skill-name>/`. Agent adapters describe installation behavior and optional bridges, but do not redefine skill content.

## Provider Matrix

`config/providers.json` is the single source of truth for:

- provider ids and labels;
- upstream `skills` CLI profile names;
- tier;
- detection probes;
- soft-provider status;
- project and global skill paths;
- optional bridge destinations;
- official references.

No shell, PowerShell, README, or test file may maintain a separate provider list.

## Installer Flow

1. Load provider matrix.
2. Parse selected providers from `--only`, `--all`, automatic detection, and explicit upstream `--agent`.
3. Exclude soft providers from automatic detection.
4. Resolve source: explicit `--source`, current repository root, or stop with a clear error.
5. Resolve selected skills.
6. Print planned paths.
7. In `--dry-run`, stop before writes or network commands.
8. Install by copy or symlink for local sources, or delegate to `npx skills add` for Git/unknown upstream profiles.
9. Write optional marker-fenced bridges only when `--with-init` is set.
10. Verify installed skill self-containment when requested.
11. Print a final result table and return non-zero on partial failure.

## Detection

Detection favors false negatives. Probe priority:

1. command on `PATH`;
2. IDE extension or plugin;
3. macOS application bundle;
4. reliable file;
5. directory-only soft probe.

Directory-only probes are soft and do not trigger default installation.

## Source Selection

Local source is preferred when running from a clone. A Git source is used only when explicitly configured with `--source`. The installer never invents a remote slug.

## Bridges

Bridge content comes from `src/init-rules/unity-repository-skills.md`. The installer inserts it between stable markers:

```text
<!-- BEGIN unity-repository-skills -->
...
<!-- END unity-repository-skills -->
```

Existing files are backed up before modification. Uninstall removes only the marked block.

## Uninstall Boundaries

Uninstall removes selected canonical skill directories or symlinks and optional bridge blocks. It does not delete shared instruction files or unrelated skills.

Legacy unprefixed skill folders are not aliases. They must be removed explicitly during migration, then prefixed skills installed.

## Test Strategy

Tests use temporary directories and mocked provider detection. They cover local copy, symlink where supported, dry-run, bridge idempotency, soft-provider exclusion, upstream passthrough planning, provider matrix integrity, and self-containment.
