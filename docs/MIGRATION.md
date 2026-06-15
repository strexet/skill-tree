# Migration

## Skill Name Prefix

Repository-owned skills use the `skill-tree-` prefix. Unity-specific skills additionally use the `skill-tree-unity-` prefix and `Skill-Tree-Unity:` display names.

Skill folder names and `SKILL.md` frontmatter names are discovery keys, so renames are breaking for installed skill folders.

## Current Canonical Skills

General skills:

- `skill-tree-repo-documentation`
- `skill-tree-repo-documentation-audit`
- `skill-tree-process-future-pending`
- `skill-tree-implement-next-future-task`
- `skill-tree-create-documents-snapshot`

Unity-specific skills:

- `skill-tree-unity-repo-documentation`
- `skill-tree-unity-repo-documentation-audit`
- `skill-tree-unity-process-future-pending`
- `skill-tree-unity-implement-next-future-task`
- `skill-tree-unity-create-documents-snapshot`

Legacy installed folders should be removed, then canonical skills should be installed.

Project-scope Codex cleanup example:

```bash
rm -rf /path/to/repo/.agents/skills/unity-repo-documentation
rm -rf /path/to/repo/.agents/skills/process-future-pending
rm -rf /path/to/repo/.agents/skills/implement-next-future-task
rm -rf /path/to/repo/.agents/skills/skill-tree-process-future-pending
rm -rf /path/to/repo/.agents/skills/skill-tree-implement-next-future-task
rm -rf /path/to/repo/.agents/skills/skill-tree-create-documents-snapshot
node bin/install.js --only codex --project --target /path/to/repo --copy --with-init
```

Global Claude Code cleanup example:

```bash
rm -rf ~/.claude/skills/unity-repo-documentation
rm -rf ~/.claude/skills/process-future-pending
rm -rf ~/.claude/skills/implement-next-future-task
rm -rf ~/.claude/skills/skill-tree-process-future-pending
rm -rf ~/.claude/skills/skill-tree-implement-next-future-task
rm -rf ~/.claude/skills/skill-tree-create-documents-snapshot
node bin/install.js --only claude-code --global --copy --with-init
```

No duplicate active alias skills are provided. Use canonical names in all new install, verify, uninstall, and upstream CLI commands.
