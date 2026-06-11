# Migration

## Skill Name Prefix

This repository now uses the `skill-tree-` prefix for every repository-owned skill. The rename is breaking for installed skill folder names because Agent Skills discovery uses folder names and `SKILL.md` metadata.

Current canonical skills:

- `skill-tree-unity-repo-documentation`
- `skill-tree-process-future-pending`
- `skill-tree-implement-next-future-task`
- `skill-tree-unity-repo-documentation-audit`

Legacy installed folders should be removed, then the prefixed skills should be installed.

Project-scope Codex cleanup example:

```bash
rm -rf /path/to/repo/.agents/skills/unity-repo-documentation
rm -rf /path/to/repo/.agents/skills/process-future-pending
rm -rf /path/to/repo/.agents/skills/implement-next-future-task
node bin/install.js --only codex --project --target /path/to/repo --copy --with-init
```

Global Claude Code cleanup example:

```bash
rm -rf ~/.claude/skills/unity-repo-documentation
rm -rf ~/.claude/skills/process-future-pending
rm -rf ~/.claude/skills/implement-next-future-task
node bin/install.js --only claude-code --global --copy --with-init
```

No duplicate active alias skills are provided. Use the prefixed names in all new install, verify, uninstall, and upstream CLI commands.
