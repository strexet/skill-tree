# Installation

Verified on: 2026-06-10.

This repository installs canonical Agent Skills from `skills/`. It does not publish a package or create native agent plugins during initial setup.

## Requirements

- Node.js 18+
- Python 3 for validation and skill-local helpers
- Git for local source detection and snapshot tooling
- Network only when delegating to `npx skills` or installing from a Git URL

## Local Clone

```bash
node bin/install.js --list
node bin/install.js --dry-run --all
node bin/install.js --only claude-code --global --copy
node bin/install.js --only codex --project --target /path/to/repo --symlink
```

## Selecting Agents

```bash
node bin/install.js --only claude-code
node bin/install.js --only codex --only cursor
node bin/install.js --all
node bin/install.js --agent qwen-code
```

`--only` selects provider ids from `config/providers.json`. `--agent` passes an upstream open `skills` CLI profile through explicitly.

Soft providers are listed but not selected by automatic detection. Select them with `--only`.

## Selecting Skills

```bash
node bin/install.js --skills skill-tree-repo-documentation
node bin/install.js --skills skill-tree-repo-documentation-audit
node bin/install.js --skills skill-tree-process-future-pending skill-tree-implement-next-future-task
node bin/install.js --skills skill-tree-create-documents-snapshot
node bin/install.js --skills skill-tree-unity-repo-documentation
node bin/install.js --skills skill-tree-unity-repo-documentation-audit
node bin/install.js --skills skill-tree-unity-process-future-pending skill-tree-unity-implement-next-future-task
node bin/install.js --skills skill-tree-unity-create-documents-snapshot
```

Without `--skills`, all canonical skills are selected.

## Scope

Project scope writes under the selected target repository:

```bash
node bin/install.js --project --target /path/to/repo --only codex
```

Global scope writes under the provider global path:

```bash
node bin/install.js --global --only claude-code
```

`config/providers.json` is the source for exact paths.

## Copy and Symlink

```bash
node bin/install.js --copy --only claude-code
node bin/install.js --symlink --only codex
```

Copy mode stages replacement and refuses overwrite unless `--force` is passed. Symlink mode prints the resolved target and links each selected skill folder when supported.

## Optional Init Bridges

```bash
node bin/install.js --only claude-code --with-init --target /path/to/repo
```

Bridges are short instruction blocks generated from `src/init-rules/skill-tree-skills.md`. They use explicit begin/end markers, preserve existing content, and create backups before modifying existing files.

## Uninstall

```bash
node bin/install.js --uninstall --only windsurf --target /path/to/repo
node bin/install.js --uninstall --only claude-code --with-init --target /path/to/repo
```

Uninstall removes only selected skill folders and marker-fenced bridge blocks owned by this installer. It does not delete unrelated instruction files or unrelated skills.

## Migration From Unprefixed Skill Names

The installer does not provide active alias skill folders for legacy unprefixed names. Remove old installed folders, then reinstall the prefixed skills. See `docs/MIGRATION.md` for project and global cleanup examples.

## Verify

```bash
node bin/install.js --verify --only codex --target /path/to/repo
```

Verify checks installed `SKILL.md` files, local references, scripts, symlinks, and optional bridge markers. It writes nothing.

## Dry Run

```bash
node bin/install.js --dry-run --all --with-init
```

Dry run prints the final result table and all touched paths. It does not invoke network commands or write files.

## Upstream `skills` CLI

For Git URLs or unknown upstream profiles, the installer delegates to the current open `skills` CLI command shape verified on 2026-06-10:

```bash
npx -y skills add <source> --agent <profile> --skill '*' --yes
```

The upstream CLI supports local paths, GitHub shorthand, full Git URLs, `--global`, `--agent`, `--skill`, `--list`, `--copy`, `--yes`, and `--all`.

## Privacy

This installer has no first-party telemetry. Network access may occur indirectly through `npx`, Git source resolution, or the upstream `skills` CLI when not in `--dry-run` or `--list` mode.

## Files Touched

- Provider skill paths from `config/providers.json`.
- Optional bridge destinations declared by selected providers.
- No target project source files, builds, tests, dependency resolution, or editor state unless optional bridge files are explicitly requested with `--with-init`.

## Troubleshooting

- Use `--list` to confirm provider ids.
- Use `--dry-run --only <provider>` to see destination paths.
- Use `--force` only when replacing installer-owned skill folders.
- Use `--copy` when symlinks are not supported.
- For soft providers, pass `--only`; automatic detection excludes them.
