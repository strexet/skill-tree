# Agent Compatibility

Verification date: 2026-06-10.

Primary sources checked:

- Open Agent Skills specification: <https://agentskills.io/specification>
- Open `skills` CLI README and provider table: <https://github.com/vercel-labs/skills>
- OpenAI Codex skills docs: <https://developers.openai.com/codex/skills>
- OpenAI `AGENTS.md` docs: <https://developers.openai.com/codex/guides/agents-md>
- Claude Code skills and memory docs: <https://code.claude.com/docs/en/skills>, <https://code.claude.com/docs/en/memory>
- Gemini CLI extensions docs: <https://geminicli.com/docs/extensions/>
- GitHub Copilot repository instructions docs: <https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions>
- Vendor docs linked by the open `skills` CLI for remaining Tier 1 profiles.

## Compatibility Notes

- Basic `SKILL.md` folders are the canonical portable format.
- Repository-owned skill names intentionally use the `skill-tree-` prefix for cross-source discovery clarity.
- Unity-specific repository-owned skill names use `skill-tree-unity-` and `Skill-Tree-Unity:` display names. General skills keep `Skill-Tree:` display names.
- Optional fields such as `allowed-tools`, hooks, or product-specific metadata are not interpreted uniformly.
- `agents/openai.yaml` is optional Codex metadata and is not required for portable behavior.
- Some Tier 1 providers rely on the open `skills` CLI path convention instead of verified native skill-discovery semantics.
- Codex direct docs list user-scope skills under `$HOME/.agents/skills`, while the current `skills` CLI profile lists `~/.codex/skills`. This repository records both and installs according to `config/providers.json`.

## Tier 1 Matrix

| Agent | Provider id | Upstream profile | Tier | Detection | Soft | Project path | Global path | Init bridge | Known limitation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Claude Code | `claude-code` | `claude-code` | 1 | `claude` command | No | `.claude/skills` | `~/.claude/skills` | `CLAUDE.md` | Claude reads `CLAUDE.md`, not `AGENTS.md`, without bridge/import. |
| OpenAI Codex | `codex` | `codex` | 1 | `codex` command | No | `.agents/skills` | `~/.codex/skills` | `AGENTS.md` | Upstream CLI and OpenAI docs differ for user-scope direct path. |
| Gemini CLI | `gemini-cli` | `gemini-cli` | 1 | `gemini` command | No | `.agents/skills` | `~/.gemini/skills` | `GEMINI.md` | Gemini extensions are optional; basic skills use CLI profile paths. |
| Cursor | `cursor` | `cursor` | 1 | command/app/extension | No | `.agents/skills` | `~/.cursor/skills` | `.cursor/rules/skill-tree-skills.mdc` | Rule bridge is optional. |
| Windsurf | `windsurf` | `windsurf` | 1 | command/app/rule dir | No | `.windsurf/skills` | `~/.codeium/windsurf/skills` | `.windsurf/rules/skill-tree-skills.md` | Current docs redirect to Devin Desktop naming for Cascade rules. |
| Cline | `cline` | `cline` | 1 | VS Code extension | No | `.agents/skills` | `~/.agents/skills` | `.clinerules/skill-tree-skills.md` | Native behavior depends on extension version. |
| GitHub Copilot | `github-copilot` | `github-copilot` | 1 | VS Code extension | No | `.agents/skills` | `~/.copilot/skills` | `.github/copilot-instructions.md` | Repository instructions are not equivalent to skill execution. |
| OpenCode | `opencode` | `opencode` | 1 | `opencode` command | No | `.agents/skills` | `~/.config/opencode/skills` | `.opencode/AGENTS.md` | Optional fields vary by client. |
| Roo Code | `roo` | `roo` | 1 | VS Code extension | No | `.roo/skills` | `~/.roo/skills` | `.roo/rules/skill-tree-skills.md` | Extension-specific discovery may vary. |
| Kilo Code | `kilo` | `kilo` | 1 | VS Code extension | No | `.kilocode/skills` | `~/.kilocode/skills` | `.kilocode/rules/skill-tree-skills.md` | Extension-specific discovery may vary. |
| Continue | `continue` | `continue` | 1 | VS Code extension | No | `.continue/skills` | `~/.continue/skills` | `.continue/rules/skill-tree-skills.md` | Continue rules are related but not identical to Agent Skills. |
| JetBrains Junie | `junie` | `junie` | 1 | JetBrains plugin probe | Yes | `.junie/skills` | `~/.junie/skills` | `.junie/rules/skill-tree-skills.md` | Soft until a reliable local plugin id is verified. |
| Kiro CLI | `kiro-cli` | `kiro-cli` | 1 | `kiro` command | No | `.kiro/skills` | `~/.kiro/skills` | `.kiro/steering/skill-tree-skills.md` | Custom Kiro agents may need resource configuration. |
| OpenHands | `openhands` | `openhands` | 1 | command/file probe | Yes | `.openhands/skills` | `~/.openhands/skills` | `.openhands/microagents/repo.md` | Soft unless local install signal is present. |
| Qwen Code | `qwen-code` | `qwen-code` | 1 | `qwen` or `qwen-code` command | No | `.qwen/skills` | `~/.qwen/skills` | `.qwen/AGENTS.md` | CLI command names differ by installation. |
| Goose | `goose` | `goose` | 1 | `goose` command | No | `.goose/skills` | `~/.config/goose/skills` | `.goosehints` | Skill interpretation depends on Goose release. |
| AiderDesk | `aider-desk` | `aider-desk` | 1 | app/command probe | Yes | `.aider-desk/skills` | `~/.aider-desk/skills` | `AGENTS.md` | Soft until reliable installed-app detection is verified. |
| Sourcegraph Amp | `amp` | `amp` | 1 | `amp` command | No | `.agents/skills` | `~/.config/agents/skills` | `AGENTS.md` | Shares universal path with Replit profile. |
| Warp | `warp` | `warp` | 1 | app/command probe | Yes | `.agents/skills` | `~/.agents/skills` | `AGENTS.md` | Soft because terminal app detection alone is weak. |
| Replit Agent | `replit` | `replit` | 1 | `replit` command/env | Yes | `.agents/skills` | `~/.config/agents/skills` | `AGENTS.md` | Soft outside Replit environment. |

## Tier 2 Passthrough

The installer supports explicit upstream profiles with:

```bash
node bin/install.js --agent <upstream-profile>
```

Current upstream examples checked on 2026-06-10 include `antigravity`, `augment`, `bob`, `crush`, `devin`, `droid`, `forgecode`, `iflow-cli`, `rovodev`, `tabnine-cli`, and `trae`.

## Tier 3 Generic Fallback

Use `--only generic --target <path>` or manual copy when an agent has no verified profile. Generic fallback does not claim automatic discovery.
