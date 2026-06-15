@AGENTS.md

## Claude Code Maintainer Notes

- `skills/` is the canonical source tree.
- `.claude/skills/` is an installation destination, not a second source.
- Read `adapters/claude-code/README.md` before changing Claude-specific guidance.
- Do not edit generated references manually. Update `common/references/` or `REPO_INIT_INSTRUCTIONS.md`, then run `scripts/sync_skill_references.py`.
