# Gemini CLI Maintainer Notes

Read `AGENTS.md` first.

- Canonical skills live in `skills/`.
- Gemini extensions are optional distribution bridges, not required for basic Agent Skills installation.
- Read `adapters/gemini-cli/README.md` before changing Gemini-specific guidance.
- Do not create divergent Gemini-specific skill copies.
- Do not edit generated files manually. Update `common/references/`, `common/scripts/`, or `REPO_INIT_INSTRUCTIONS.md`, then run `scripts/sync_skill_references.py`.
