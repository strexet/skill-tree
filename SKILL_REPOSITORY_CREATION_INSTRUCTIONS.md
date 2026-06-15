# Skill Repository Creation Instructions

Last updated: 2026-06-10
Primary audience: AI coding agents creating the repository
Repository type: vendor-neutral, cross-agent Agent Skills source repository
Required source document: `REPO_INIT_INSTRUCTIONS.md`
Output language: English

## 1. Objective

Create a production-quality Git repository containing reusable, vendor-neutral Agent Skills derived from `REPO_INIT_INSTRUCTIONS.md`.

The repository starts with only:

```text
REPO_INIT_INSTRUCTIONS.md
SKILL_REPOSITORY_CREATION_INSTRUCTIONS.md
.git/
```

The completed repository must provide ten focused skills: five general skills and five Unity-specific skills.

General skills:

1. `skill-tree-repo-documentation`
2. `skill-tree-repo-documentation-audit`
3. `skill-tree-process-future-pending`
4. `skill-tree-implement-next-future-task`
5. `skill-tree-create-documents-snapshot`

Unity-specific skills:

1. `skill-tree-unity-repo-documentation`
2. `skill-tree-unity-repo-documentation-audit`
3. `skill-tree-unity-process-future-pending`
4. `skill-tree-unity-implement-next-future-task`
5. `skill-tree-unity-create-documents-snapshot`

The canonical skills must follow the open Agent Skills specification and remain portable across AI coding agents that support `SKILL.md`.

The repository must support, at minimum:

- Claude Code;
- OpenAI Codex;
- Gemini CLI;
- Cursor;
- Windsurf;
- Cline;
- GitHub Copilot;
- OpenCode;
- Roo Code;
- Kilo Code;
- Continue;
- JetBrains Junie;
- Kiro CLI;
- OpenHands;
- Qwen Code;
- Goose;
- AiderDesk;
- Sourcegraph Amp;
- Warp;
- Replit Agent;
- other current agents supported by the open `skills` CLI.

Do not create divergent skill content for every agent.

Use:

- one canonical `skills/` tree;
- optional vendor-specific metadata and adapters;
- one declarative provider matrix;
- one unified cross-platform installer;
- thin shell and PowerShell launchers;
- deterministic validation and tests.

The skills must preserve the behavior and constraints established by `REPO_INIT_INSTRUCTIONS.md` while using progressive disclosure:

- short, focused `SKILL.md` files;
- detailed behavior in local `references/`;
- deterministic operations in local `scripts/`;
- optional metadata such as `agents/openai.yaml`;
- optional agent-specific installation adapters;
- tests and repository-level validation;
- installation tooling for global and repository-local use across supported agents.

The repository must be usable as:

- a source repository for maintaining the skills;
- a local installation source;
- a Git source consumable by open Agent Skills installers;
- a project-scoped skill source for multiple agent hosts;
- a user-scoped skill source for multiple agent hosts;
- a foundation for future native plugin or extension packaging.

Do not convert the complete source instruction into one monolithic skill.

Do not make Codex, Claude Code, or another single agent the canonical representation.

## 2. Authoritative Inputs and Precedence

Use this precedence order:

1. Explicit owner instructions in the current task.
2. This file: `SKILL_REPOSITORY_CREATION_INSTRUCTIONS.md`.
3. The live root `REPO_INIT_INSTRUCTIONS.md`.
4. The current open Agent Skills specification.
5. Current documentation for the open `skills` CLI and its supported agent profiles.
6. Current official documentation for each directly supported AI agent.
7. The current architecture of `JuliusBrussee/caveman`, used as a reference for cross-agent distribution patterns.
8. Repository implementation and tests created during this task.

If these sources conflict:

- do not silently choose;
- verify that the relevant documentation is current;
- distinguish the portable Agent Skills contract from agent-specific extensions;
- preserve the user-required workflow unless technically invalid;
- record the conflict in the final report;
- ask only when the conflict blocks safe implementation.

Before implementing metadata, discovery, installation paths, or adapter behavior, verify:

- required `SKILL.md` frontmatter fields;
- current Agent Skills directory structure;
- current `skills` CLI profile names;
- project and global install paths;
- non-interactive installation flags;
- optional vendor fields such as `allowed-tools`, `context`, hooks, and `agents/openai.yaml`;
- whether each agent supports direct skills, rule files, or native plugins/extensions;
- update and uninstall behavior.

Use official vendor sources for vendor-specific behavior.

Use the open Agent Skills specification for the portable core.

Use `caveman` only as an architectural reference. Do not copy its branding, product behavior, or product-specific hooks.

Reference sources to verify:

```text
Open standard:
https://agentskills.io/
https://agentskills.io/specification

Universal installer/profile registry:
https://github.com/vercel-labs/skills

Cross-agent reference implementation:
https://github.com/juliusbrussee/caveman
https://github.com/juliusbrussee/caveman/blob/main/INSTALL.md
https://github.com/juliusbrussee/caveman/blob/main/bin/install.js

OpenAI Codex:
https://developers.openai.com/codex/skills
https://developers.openai.com/codex/guides/agents-md

Claude Code:
https://docs.anthropic.com/en/docs/claude-code/skills
https://docs.anthropic.com/en/docs/claude-code/memory

Gemini CLI:
https://geminicli.com/docs/extensions/
https://geminicli.com/docs/extensions/writing-extensions/

GitHub Copilot:
https://docs.github.com/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot
https://docs.github.com/copilot/reference/custom-instructions-support
```

For other supported agents, use the official links maintained by the current open `skills` CLI compatibility documentation.

Record:

- verification date;
- checked versions when available;
- current profile names;
- soft-probe limitations;
- unsupported optional fields;
- changes from the expected matrix.

Store this information in `INSTALL.md` and `docs/AGENT_COMPATIBILITY.md`.

## 3. Non-Negotiable Design Decisions

### 3.1 Ten focused skills

Create ten separate skills rather than one large skill. The five general skills own portable repository workflows. The five Unity-specific skills extend those workflows with Unity evidence, safety, and terminology.

The responsibilities must not overlap unnecessarily:

```text
skill-tree-repo-documentation
  Deeply analyzes an existing software repository and creates or repairs
  its AI-oriented repository documentation.

skill-tree-repo-documentation-audit
  Audits existing repository documentation against current code, tests,
  configuration, repository structure, and workflow rules.

skill-tree-process-future-pending
  Processes only the Pending Queue in FUTURE.md and promotes sufficiently
  researched entries into maximally detailed Prioritized Next Changes.

skill-tree-implement-next-future-task
  Selects and implements exactly one task from Prioritized Next Changes,
  following the name-selection and clarification-gate rules.

skill-tree-create-documents-snapshot
  Creates explicit-request-only Markdown documentation snapshot archives
  without modifying live source documents.

skill-tree-unity-repo-documentation
  Deeply analyzes an existing Unity repository and creates or repairs
  its AI-oriented repository documentation.

skill-tree-unity-repo-documentation-audit
  Audits existing repository documentation against current code, tests,
  configuration, repository structure, and workflow rules. It repairs
  documentation drift and adds meaningful discovered issues to FUTURE.md.

skill-tree-unity-process-future-pending
  Applies pending processing to Unity repository work using Unity-specific
  evidence such as assemblies, assets, settings, scenes, prefabs, and tests.

skill-tree-unity-implement-next-future-task
  Implements exactly one prioritized Unity repository task after Unity-specific
  orientation and clarification checks.

skill-tree-unity-create-documents-snapshot
  Creates explicit-request-only Unity Markdown documentation snapshot archives
  without modifying live source documents or Unity project state.
```

Every repository-owned skill directory and `SKILL.md` frontmatter name must start with `skill-tree-`.
Unity-specific skill directory and frontmatter names must start with `skill-tree-unity-`, and visible display names must start with `Skill-Tree-Unity:`.

### 3.2 Vendor-neutral canonical skills

Canonical content lives only under:

```text
skills/skill-tree-<skill-name>/
```

Every canonical skill must use the common Agent Skills structure:

```text
SKILL.md
references/
scripts/
assets/       # only when needed
```

Vendor-specific metadata may coexist when ignored safely by other agents, for example:

```text
agents/openai.yaml
```

Portable behavior must not depend on that metadata.

Do not create separately edited copies such as:

```text
skills-codex/
skills-claude/
skills-cursor/
```

Agent-specific installations must copy or link the canonical skill.

### 3.3 Self-contained installed skills

Every installed skill must remain usable after its folder is copied outside this source repository.

A skill must not depend at runtime on:

- the source repository root;
- sibling skill folders;
- root-only scripts;
- undocumented environment variables;
- machine-specific absolute paths;
- one vendor’s proprietary metadata;
- the installer remaining present after installation.

Repository-level scripts may maintain and validate the source tree, but each skill must contain the references and scripts it needs when installed alone.

### 3.4 One canonical source for the long instruction

The root `REPO_INIT_INSTRUCTIONS.md` is the canonical source.

Shared general workflow references live under:

```text
common/references/
```

The synchronization script must copy shared references into every installed skill folder that needs them so each installed skill remains self-contained. Unity skills should read copied common references first, then Unity-specific references.

The documentation skill must contain a synchronized copy at:

```text
skills/skill-tree-unity-repo-documentation/references/REPO_INIT_INSTRUCTIONS.md
```

The copy must be byte-for-byte identical to the root file unless a generated provenance header is explicitly adopted. Prefer byte-for-byte identity.

The general FUTURE-related skills must use generated focused references from `common/references/FUTURE_WORKFLOW.md`:

```text
skills/skill-tree-process-future-pending/references/FUTURE_TASK_STANDARD.md
skills/skill-tree-implement-next-future-task/references/FUTURE_EXECUTION_RULES.md
```

The Unity FUTURE-related skills must include both copied common references and Unity-specific generated references:

```text
skills/skill-tree-unity-process-future-pending/references/COMMON_FUTURE_WORKFLOW.md
skills/skill-tree-unity-process-future-pending/references/FUTURE_TASK_STANDARD.md
skills/skill-tree-unity-implement-next-future-task/references/COMMON_FUTURE_WORKFLOW.md
skills/skill-tree-unity-implement-next-future-task/references/FUTURE_EXECUTION_RULES.md
```

Do not manually maintain divergent copies.

Provide a deterministic synchronization script.

### 3.5 Progressive disclosure

Keep `SKILL.md` focused on:

- when the skill should activate;
- when it must not activate;
- required workflow;
- critical safety constraints;
- which local references and scripts to read;
- completion and reporting requirements.

Move long templates, detailed checklists, command semantics, and edge cases into `references/`.

Do not copy all of `REPO_INIT_INSTRUCTIONS.md` into `SKILL.md`.

### 3.6 Instruction-first, script-backed only where deterministic

Use natural-language skill instructions for repository analysis, architectural reasoning, task refinement, and implementation decisions.

Use scripts for deterministic operations such as:

- read-only repository inventory;
- reference synchronization;
- structure validation;
- Markdown contract validation;
- cross-agent installation;
- provider detection;
- documentation snapshot creation;
- fixture generation.

Scripts must not replace the agent’s responsibility to understand the repository.

### 3.7 Cross-agent installer architecture

Follow the useful architectural patterns demonstrated by `caveman`:

- one canonical skill source;
- one provider matrix;
- one cross-platform installer implementation;
- thin `install.sh` and `install.ps1` launchers;
- reliable probes for automatic detection;
- soft probes excluded from automatic installation;
- explicit `--only` selection for uncertain agents;
- idempotent re-runs;
- `--dry-run`;
- `--list`;
- `--force`;
- clear per-agent results;
- optional repository instruction bridges;
- safe uninstall;
- no first-party telemetry.

Do not copy product-specific behavior such as hooks, status lines, MCP middleware, or always-on response modification. These Unity workflow skills do not need those features.

### 3.8 Compatibility tiers

Define and document three support tiers.

**Tier 1 — verified popular agents**

The repository must have explicit detection, installation tests, and documented behavior for:

```text
Claude Code
OpenAI Codex
Gemini CLI
Cursor
Windsurf
Cline
GitHub Copilot
OpenCode
Roo Code
Kilo Code
Continue
JetBrains Junie
Kiro CLI
OpenHands
Qwen Code
Goose
AiderDesk
Sourcegraph Amp
Warp
Replit Agent
```

**Tier 2 — upstream `skills` CLI profiles**

Support all additional current profiles exposed by the open `skills` CLI through explicit `--only` or `--agent` passthrough.

Tier 2 agents do not require custom local detection when no reliable signal exists.

**Tier 3 — generic/manual fallback**

Provide:

- installation to an explicit destination path;
- direct use through `npx skills use` when supported;
- manual copy instructions;
- optional generation of a short repository instruction bridge.

Do not claim native support when only a generic fallback is verified.

### 3.9 Detection quality

Provider detection must favor false negatives over false positives.

Preferred probes:

1. executable on `PATH`;
2. installed IDE extension;
3. installed application bundle;
4. vendor plugin directory with a reliable identifier;
5. config directory only when no better signal exists.

A config-directory-only probe is soft and must not trigger default auto-installation.

A soft provider installs only when explicitly selected.

### 3.10 Safe defaults

All provided scripts must default to non-destructive behavior.

They must:

- avoid network access unless installation or update is explicitly requested;
- avoid changing Unity project files during inspection;
- avoid opening Unity;
- avoid running package resolution;
- avoid overwriting existing skills without an explicit flag;
- avoid overwriting agent instruction files;
- avoid committing or pushing automatically;
- avoid writing outside the requested destination;
- return non-zero exit codes for validation failures;
- produce actionable error messages;
- display every destination before writing;
- make optional bridge-file changes idempotent and reversible.

## 4. Required Final Repository Layout

Create this structure:

```text
.
├── .editorconfig
├── .gitignore
├── AGENTS.md
├── CLAUDE.md
├── GEMINI.md
├── INSTALL.md
├── README.md
├── REPO_INIT_INSTRUCTIONS.md
├── SKILL_REPOSITORY_CREATION_INSTRUCTIONS.md
├── install.sh
├── install.ps1
├── package.json
├── bin/
│   └── install.js
├── config/
│   └── providers.json
├── docs/
│   ├── AGENT_COMPATIBILITY.md
│   ├── INSTALLATION_ARCHITECTURE.md
│   └── SECURITY.md
├── adapters/
│   ├── README.md
│   ├── codex/
│   │   └── README.md
│   ├── claude-code/
│   │   └── README.md
│   ├── gemini-cli/
│   │   └── README.md
│   ├── github-copilot/
│   │   └── README.md
│   ├── cursor/
│   │   └── README.md
│   ├── windsurf/
│   │   └── README.md
│   ├── cline/
│   │   └── README.md
│   └── generic/
│       └── README.md
├── src/
│   └── init-rules/
│       └── skill-tree-skills.md
├── common/
│   └── references/
│       ├── DOCUMENTATION_OUTPUT_CONTRACT.md
│       ├── FUTURE_WORKFLOW.md
│       ├── PENDING_TASK_FORMAT.md
│       ├── REPOSITORY_DISCOVERY_CHECKLIST.md
│       └── SNAPSHOT_RULES.md
├── skills/
│   ├── skill-tree-repo-documentation/
│   ├── skill-tree-repo-documentation-audit/
│   ├── skill-tree-process-future-pending/
│   ├── skill-tree-implement-next-future-task/
│   ├── skill-tree-create-documents-snapshot/
│   ├── skill-tree-unity-repo-documentation/
│   ├── skill-tree-unity-repo-documentation-audit/
│   ├── skill-tree-unity-process-future-pending/
│   ├── skill-tree-unity-implement-next-future-task/
│   └── skill-tree-unity-create-documents-snapshot/
├── scripts/
│   ├── sync_skill_references.py
│   └── validate_skill_repository.py
└── tests/
    ├── README.md
    ├── fixtures/
    │   ├── future/
    │   │   ├── valid.md
    │   │   ├── missing-questions.md
    │   │   ├── duplicate-prioritized-names.md
    │   │   ├── empty-prioritized.md
    │   │   └── named-task-only-in-backlog.md
    │   ├── providers/
    │   │   ├── valid.json
    │   │   ├── duplicate-id.json
    │   │   └── invalid-soft-probe.json
    │   └── unity-repository/
    │       └── README.md
    ├── test_installer.js
    ├── test_provider_matrix.js
    ├── test_reference_sync.py
    ├── test_select_prioritized_task.py
    ├── test_skill_repository_validation.py
    └── test_validate_future_document.py
```

Additional adapter documentation may be created when justified.

Do not duplicate canonical skills under agent-specific directories.

Do not create native plugin manifests during initial implementation unless required by an explicitly selected mechanism and verified against current official documentation.

Do not create a `LICENSE` file unless the owner has selected a license.

## 5. Initial Repository Safety and Git Baseline

Before editing:

1. Confirm the working directory is the intended repository root.
2. Confirm `REPO_INIT_INSTRUCTIONS.md` exists and is non-empty.
3. Confirm this instruction exists and is non-empty.
4. Check Git status.
5. Determine whether Git is already initialized.
6. Preserve all existing files.
7. Do not modify the source instruction except to fix an explicit owner-requested issue.
8. Do not configure Git user identity globally or locally without instruction.
9. Do not add a remote without a supplied remote URL.
10. Do not push.

Recommended commands:

```bash
pwd
git rev-parse --show-toplevel
git status --short
ls -la
wc -c REPO_INIT_INSTRUCTIONS.md
wc -c SKILL_REPOSITORY_CREATION_INSTRUCTIONS.md
```

If `.git/` does not exist, initialize Git:

```bash
git init
```

Use the repository’s existing default branch. If Git creates a new branch and the owner has not specified a branch name, use `main` only when changing it does not conflict with existing configuration:

```bash
git branch -M main
```

Do not rewrite existing history.

## 6. Implementation Phases

Perform the work in this order:

1. Verify the open Agent Skills specification.
2. Verify the current `skills` CLI provider matrix.
3. Review the current `caveman` installer architecture.
4. Verify official documentation for Tier 1 agents.
5. Analyze the source instruction.
6. Create repository conventions and cross-agent documentation.
7. Implement reference synchronization.
8. Create the ten canonical skills.
9. Implement deterministic skill-local scripts.
10. Create the provider matrix.
11. Implement the unified installer and thin launchers.
12. Implement adapters and optional instruction bridges.
13. Implement repository validators.
14. Create fixtures and tests.
15. Run synchronization.
16. Run static validation and all tests.
17. Perform explicit cross-agent and skill-behavior review.
18. Review the Git diff.
19. Commit only when validation passes and committing is within scope.

Do not start by writing all `SKILL.md` files from memory. Build a source-to-skill responsibility map first.

## 7. Analyze `REPO_INIT_INSTRUCTIONS.md`

Read the complete source document.

Create a temporary analysis table with:

```text
Source section
Responsibility
Target skill
Target file
Must be copied exactly
Can be summarized
Requires deterministic script
Requires test
```

At minimum, map:

- repository documentation initialization;
- Unity repository discovery;
- evidence hierarchy;
- document specifications;
- `FUTURE.md` queue semantics;
- `Process pending` command semantics;
- required implementation questions;
- clarification gate;
- `Implement next` command semantics;
- task selection boundaries;
- documentation snapshot procedure;
- completion checks.

Do not infer the source document from its title or selected excerpts. Read it fully.

After mapping, verify:

- every material workflow has one owning skill;
- cross-cutting safety constraints are present where needed;
- no command behavior has been weakened;
- no task queue is silently treated as implementation-ready;
- `Backlog` remains inaccessible to `Implement next`;
- unresolved blocking questions stop implementation.

## 8. Root Repository Files

### 8.1 `.gitignore`

Create a minimal repository-specific `.gitignore`.

Include at least:

```gitignore
.DS_Store
Thumbs.db
__pycache__/
*.py[cod]
.pytest_cache/
.coverage
htmlcov/
.venv/
venv/
node_modules/
dist/
build/
*.zip
.tmp/
tmp/
```

Do not ignore:

- `skills/`;
- `tests/fixtures/`;
- `config/providers.json`;
- Markdown references;
- generated focused references that are intentionally committed.

### 8.2 `.editorconfig`

Use conservative cross-platform defaults:

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true

[*.md]
trim_trailing_whitespace = false

[*.py]
indent_style = space
indent_size = 4

[*.{js,json}]
indent_style = space
indent_size = 2

[*.{yaml,yml}]
indent_style = space
indent_size = 2
```

### 8.3 Root `AGENTS.md`

Keep this file concise and vendor-neutral.

It must tell agents:

- this repository maintains reusable cross-agent Agent Skills;
- `REPO_INIT_INSTRUCTIONS.md` is canonical for Unity documentation behavior;
- generated references must be updated through `scripts/sync_skill_references.py`;
- `config/providers.json` is canonical for installer provider definitions;
- every skill change requires validation and tests;
- skill folders must remain self-contained;
- vendor behavior belongs in adapters or optional metadata;
- external agent behavior must be verified against official docs;
- no automatic remote, push, release, or marketplace publication;
- no license selection without owner input.

Suggested structure:

```markdown
# Repository Agent Instructions

## Required reading
## Source-of-truth rules
## Portable skill rules
## Provider and adapter rules
## Validation commands
## Git and release safety
```

### 8.4 Root `CLAUDE.md`

Create a short Claude Code maintainer entry point.

It must:

- instruct Claude Code to read `AGENTS.md`;
- identify `skills/` as canonical;
- clarify that `.claude/skills/` is an installation destination, not a second source;
- point to `adapters/claude-code/README.md`;
- prohibit editing generated references manually.

Do not duplicate all repository rules.

### 8.5 Root `GEMINI.md`

Create a short Gemini CLI maintainer entry point.

It must:

- instruct Gemini CLI to read `AGENTS.md`;
- point to the canonical skills and Gemini adapter docs;
- clarify that Gemini extensions are optional and not required for basic skill installation;
- prohibit divergent Gemini-specific copies.

### 8.6 Root `README.md`

Create a human-facing repository overview.

Include:

- repository purpose;
- vendor-neutral Agent Skills statement;
- skill list;
- trigger examples;
- source-of-truth model;
- repository layout;
- prerequisites;
- quick installation;
- per-agent overview;
- supported-agent tiers;
- validation commands;
- update workflow;
- Git contribution workflow;
- limitations;
- optional future native packaging;
- official references and verification date.

README must distinguish:

```text
Canonical source:
  skills/skill-tree-<skill-name>/

Project installation:
  Determined by the selected agent profile.

Global installation:
  Determined by the selected agent profile.

Vendor metadata:
  Optional and non-canonical.
```

Do not hard-code a remote one-liner until a real Git remote/repository slug exists.

### 8.7 Root `INSTALL.md`

Create a detailed installation guide organized similarly to the useful parts of `caveman/INSTALL.md`, but specific to these skills.

Include:

- local-clone installation;
- unified installer examples;
- `--list`;
- `--dry-run`;
- automatic detection;
- explicit `--only`;
- project versus global scope;
- one or several skills;
- copy versus symlink;
- optional `--with-init`;
- uninstall;
- update;
- per-agent matrix;
- soft-probe explanation;
- troubleshooting;
- privacy and network behavior;
- exact files touched.

Clearly distinguish direct skill installation, optional instruction bridges, and future native packaging.

### 8.8 `docs/AGENT_COMPATIBILITY.md`

Maintain a compatibility table with:

```text
Agent
Provider id
Upstream profile
Tier
Detection method
Soft probe
Project path
Global path
Install mechanism
Invocation behavior
Automatic discovery expectation
Optional init bridge
Official reference
Last verified
Known limitations
```

Do not claim that every agent interprets optional frontmatter identically.

### 8.9 `docs/INSTALLATION_ARCHITECTURE.md`

Document:

- canonical skill ownership;
- provider matrix ownership;
- installer flow;
- detection precedence;
- soft providers;
- local versus remote source selection;
- delegation to the open `skills` CLI;
- optional bridge generation;
- uninstall boundaries;
- test strategy.

### 8.10 `docs/SECURITY.md`

Document:

- no first-party telemetry;
- commands that may access the network;
- external tools invoked;
- dry-run behavior;
- path validation;
- overwrite policy;
- marker-fenced bridge modifications;
- backup behavior;
- symlink behavior;
- no secret collection;
- no execution of installed skill scripts during installation.

## 9. Repository-Level Reference Synchronization

Create:

```text
scripts/sync_skill_references.py
```

Use Python standard library only.

### 9.1 Responsibilities

The script must:

1. Locate the repository root reliably from its own path.
2. Read root `REPO_INIT_INSTRUCTIONS.md` and `common/references/`.
3. Copy `REPO_INIT_INSTRUCTIONS.md` byte-for-byte to:
   `skills/skill-tree-unity-repo-documentation/references/REPO_INIT_INSTRUCTIONS.md`.
4. Copy common documentation, discovery, pending-format, future-workflow, and snapshot references into every general and Unity skill folder that needs them.
5. Extract Unity-specific `FUTURE.md` and execution sections into:
   `skills/skill-tree-unity-process-future-pending/references/FUTURE_TASK_STANDARD.md`
   and `skills/skill-tree-unity-implement-next-future-task/references/FUTURE_EXECUTION_RULES.md`.
6. Extract the Unity pending template into:
   `skills/skill-tree-unity-repo-documentation-audit/references/PENDING_TASK_FORMAT.md`.
7. Add a concise generated-file notice to generated references.
8. Fail if required source headings are missing or ambiguous.
9. Support a check-only mode that makes no changes.
10. Use deterministic output.
11. Preserve UTF-8 and LF line endings.

Recommended interface:

```bash
python3 scripts/sync_skill_references.py
python3 scripts/sync_skill_references.py --check
```

### 9.2 Heading-based extraction

Do not use fragile fixed line numbers.

Find source ranges by exact Markdown headings.

Expected source boundaries should be validated against the actual source document. Likely anchors include:

```text
## 14. Document Specification — `Documents/FUTURE.md`
## 15. Document Specification — `Documents/RULES.md`
```

For the execution reference, extract the relevant subsections by heading, including:

- command semantics;
- mandatory implementation questions;
- clarification gate;
- `Implement next` behavior;
- selection boundaries;
- implementor rules;
- prioritized-task completeness;
- task template;
- task lifecycle.

If source headings differ, adapt to the actual document and document the anchors in code constants.

### 9.3 Generated-file notice

For focused derived references, prepend:

```markdown
<!--
GENERATED FILE
Source: REPO_INIT_INSTRUCTIONS.md
Generator: scripts/sync_skill_references.py
Do not edit manually. Update the source document and rerun the generator.
-->
```

Do not prepend this notice to the byte-for-byte documentation-skill copy.

### 9.4 Check mode

`--check` must fail when:

- the full copy differs;
- a generated reference is missing;
- generated content differs;
- required headings cannot be found.

It must print the affected paths.

## 10. Skill 1 — `skill-tree-unity-repo-documentation`

Create:

```text
skills/skill-tree-unity-repo-documentation/
```

## 10.1 Purpose

This skill deeply analyzes an existing Unity repository and creates or repairs an AI-oriented documentation system.

It must not implement product features or upgrade the Unity project.

## 10.2 `SKILL.md` frontmatter

Use current officially supported frontmatter.

At minimum:

```yaml
---
name: skill-tree-unity-repo-documentation
description: Deeply analyze an existing Unity repository and create, initialize, audit, or repair its AI-oriented repository documentation. Use for requests to document an unfamiliar Unity project, create PROJECT.md, TECHNICAL.md, FEATURES.md, FUTURE.md, RULES.md, AGENTS.md, or establish repository documentation. Do not use for ordinary feature implementation, isolated copy edits, or Unity/package upgrades.
---
```

Keep the description concise enough for discovery while explicitly including positive and negative triggers.

Do not add unsupported frontmatter fields.

## 10.3 Required `SKILL.md` behavior

The skill must instruct the agent to:

1. Confirm repository root and worktree state.
2. Find every Unity project root.
3. Read local `references/REPO_INIT_INSTRUCTIONS.md`.
4. Read the local discovery checklist.
5. Build an evidence inventory.
6. Inspect code, assemblies, scenes, prefabs, assets, packages, settings, build tooling, platform integrations, tests, and existing docs.
7. Create the required live document set.
8. Keep planned and implemented behavior separate.
9. Keep `FEATURES.md` limited to current implemented or partial behavior.
10. Put planned work, known bugs awaiting fixes, deferred investigations, and proposed improvements in `FUTURE.md`.
11. Inspect key implementation paths, tests, error handling, state transitions, persistence, mutation logic, and existing `FUTURE.md` entries before finalizing documentation.
12. Add meaningful discovered issues to the active `FUTURE.md` Backlog, not Pending Queue, with evidence, affected paths/symbols, impact, suggested direction, acceptance criteria, and focused tests.
13. Distinguish confirmed bugs, strongly suspected issues, documentation inconsistencies, and improvement opportunities.
14. Avoid modifying Unity behavior during documentation initialization.
15. Run local documentation validation.
16. Review the final diff.
17. Report evidence gaps, drift corrected, issues added to Backlog, potential issues excluded for insufficient evidence, checks run, and risks.

It must instruct the agent to use the skill-local script by path relative to the skill directory, not by assuming the source repository layout.

### 10.3.1 Activation examples

Include examples in `SKILL.md` or a reference:

```text
Initialize repository documentation for this Unity project.
Document this existing Unity repository.
Audit and repair the project documentation.
Create AI-oriented documentation for this Unity package.
```

### 10.3.2 Negative examples

Include:

```text
Fix this gameplay bug.
Update one README sentence.
Upgrade Unity.
Implement the next FUTURE.md task.
Process pending tasks.
```

## 10.4 `agents/openai.yaml`

This file is optional Codex-specific metadata. It must not contain behavior required by the portable skill, and other agents must be able to ignore it safely.

Create optional UI metadata only after verifying the current schema.

Use fields supported by current official documentation.

Recommended intent:

```yaml
interface:
  display_name: "Skill-Tree-Unity: Initialize Documents"
  short_description: "Analyze and document an existing Unity repository"
  default_prompt: "Analyze this existing Unity repository and create or repair its AI-oriented documentation."

policy:
  allow_implicit_invocation: true
```

Do not add icons unless actual repository-owned icon assets are created.

Do not add tool dependencies unless required.

## 10.5 `references/DOCUMENTATION_OUTPUT_CONTRACT.md`

Create a concise output contract extracted from the source instruction.

Include:

- required root and `Documents/` files;
- document ownership map;
- live filename rules;
- required `FUTURE.md` queues;
- required repo-local Pending Queue entry format guidance;
- current-state versus planned-state rule;
- cross-document validation;
- final handoff requirements.

Do not duplicate the full source document.

## 10.6 `references/UNITY_DISCOVERY_CHECKLIST.md`

Create an operational checklist covering:

- Unity roots;
- exact Unity version;
- packages and lock files;
- assemblies;
- startup;
- scenes;
- prefabs;
- ScriptableObjects;
- Addressables/Resources/StreamingAssets;
- persistence;
- networking;
- platform plugins;
- build/CI;
- tests;
- observability;
- security/privacy;
- generated files;
- existing documentation drift.

Each checklist item should identify likely evidence paths.

## 10.7 `scripts/inspect_unity_repository.py`

Create a read-only inventory tool.

### Required properties

- Python standard library only.
- Accept target repository path.
- Default to current directory only when explicit.
- Never open Unity.
- Never modify target files.
- Never run package resolution.
- Never follow unbounded symlink traversal.
- Exclude transient Unity directories.
- Produce human-readable Markdown or JSON.
- Support `--format markdown|json`.
- Support `--output PATH`; otherwise print to stdout.
- Return non-zero for invalid target paths.

Recommended interface:

```bash
python3 inspect_unity_repository.py /path/to/unity-repo
python3 inspect_unity_repository.py /path/to/unity-repo --format json
```

Collect:

- Git root/status when available;
- Unity project roots;
- `ProjectVersion.txt`;
- `manifest.json` and `packages-lock.json`;
- `.asmdef`/`.asmref`;
- scenes and likely build-scene settings;
- common serialized asset types;
- test assemblies;
- native plugin directories;
- build scripts;
- CI files;
- Markdown documents;
- common generated/transient directories present;
- TODO/FIXME counts without dumping sensitive file contents.

Do not parse arbitrary binary assets.

## 10.8 `scripts/validate_unity_documentation.py`

Validate a target Unity repository’s documentation contract.

Required checks:

- root `README.md`;
- root `AGENTS.md`;
- required `Documents/` files;
- no snapshot markers in live filenames;
- required top-level sections in core documents;
- three required `FUTURE.md` queues;
- every prioritized task has required sections;
- every prioritized task has `Questions and required clarifications`;
- no duplicate normalized prioritized task names;
- relative Markdown links resolve where practical;
- no obvious unresolved scaffold placeholders;
- no source path claims that point outside the target repository;
- optional strict mode.

Recommended interface:

```bash
python3 validate_unity_documentation.py /path/to/unity-repo
python3 validate_unity_documentation.py /path/to/unity-repo --strict
```

Validation must not claim semantic correctness. It validates structure and detectable contracts.

## 10.9 Snapshot boundary

Documentation initialization must not create `Documents/DOCUMENTS_SNAPSHOT.md` and must not own snapshot archive creation. Unity snapshot archive creation belongs to `skill-tree-unity-create-documents-snapshot`.

The documentation skill may still reject snapshot-named live files.

## 10A. Skill 4 — `skill-tree-unity-repo-documentation-audit`

Create:

```text
skills/skill-tree-unity-repo-documentation-audit/
```

### 10A.1 Purpose

This skill audits existing repository documentation against current code, tests, configuration, repository structure, build metadata, agent workflows, and skill definitions.

It performs the same depth of code and architecture inspection as `skill-tree-unity-repo-documentation`, but its primary purpose is ongoing documentation maintenance after baseline docs already exist.

It must not automatically implement unrelated product code changes.

### 10A.2 Required behavior

The skill must:

1. MUST read repository `AGENTS.md`, `RULES.md`, or equivalent rules before auditing.
2. MUST read the repository/document map if one exists.
3. Inventory all documentation and classify each document role.
4. Verify the baseline document set expected by `skill-tree-unity-repo-documentation`.
5. Recreate missing required documents from current repository evidence.
6. Validate documented claims against current code, tests, repository structure, build configuration, and agent workflows.
7. Fix stale paths, renamed symbols, outdated behavior descriptions, contradictions, duplicate guidance, incorrect implementation status, and obsolete future sections in current-state documents.
8. Enforce that `FEATURES.md` describes current implemented or partial behavior only.
9. Enforce that `FUTURE.md` contains planned work, backlog, known bugs awaiting fixes, documentation improvements, proposed skills, refactoring plans, and deferred investigations.
10. Enforce that `FUTURE.md` contains repo-local `## Pending Task Format` guidance before `## Pending Queue`; add or repair the nested Markdown template when absent or incomplete.
11. Mark historical documents clearly when they remain useful.
12. While inspecting code, identify meaningful bugs, risky logic, missing tests, documentation/code drift, maintainability issues, and security/data-safety risks.
13. Add meaningful findings to the active `FUTURE.md` Backlog, not Pending Queue, using the same task-quality requirements as the documentation skill.
14. Merge with existing backlog entries and avoid duplicate tasks.
15. Distinguish confirmed bugs, strongly suspected issues, documentation inconsistencies, and improvement opportunities.
16. Produce an audit summary covering documents inspected, missing documents created, documents merged or role-corrected, drift corrected, paths/symbols updated, contradictions resolved, Pending Task Format repair, backlog items added, and unverified claims.

The audit skill must include a generated `references/PENDING_TASK_FORMAT.md` extracted from `REPO_INIT_INSTRUCTIONS.md` section 14.8 and use it when repairing missing repo-local Pending Queue guidance.

### 10A.3 `SKILL.md` frontmatter

Use:

```yaml
---
name: skill-tree-unity-repo-documentation-audit
description: Audit existing Unity repository documentation against the current codebase, tests, configuration, repository structure, and skill/workflow rules. Use after documentation already exists, after major changes or repository restructures, before releases, or when documentation drift is suspected. Fix stale documentation in place, enforce FEATURES.md and FUTURE.md responsibilities, recreate missing baseline documents from current evidence, and add meaningful discovered issues to FUTURE.md without changing unrelated product code.
---
```

### 10A.4 `agents/openai.yaml`

Recommended intent:

```yaml
interface:
  display_name: "Skill-Tree-Unity: Audit Documents"
  short_description: "Audit existing Unity docs against code"
  default_prompt: "Audit existing Unity repository documentation against the current codebase and repair drift."

policy:
  allow_implicit_invocation: true
```

## 10B. Unity Skill — `skill-tree-unity-create-documents-snapshot`

Create:

```text
skills/skill-tree-unity-create-documents-snapshot/
```

### 10B.1 Purpose

This skill creates explicit-request-only Markdown documentation snapshot archives for Unity repositories.

It must not run during normal documentation initialization, documentation audit, feature implementation, pending processing, or implement-next workflows.

### 10B.2 Required behavior

The skill must:

1. Confirm repository root and worktree state.
2. Read local `references/SNAPSHOT_RULES.md`.
3. Determine requested scope.
4. Inspect candidate Markdown enough to confirm repository-specific relevance.
5. Exclude vendor, generated, ignored, transient, secret, and local-only files by default.
6. Stage copies outside the repository.
7. Prepend snapshot notices.
8. Create a timestamped ZIP archive with members at zip root.
9. Avoid modifying live source documents.
10. Avoid opening Unity, package resolution, asset reserialization, or generated project changes.
11. Verify archive existence, member names, snapshot notices, scope, collision handling, and source-file preservation.
12. Report archive path, included count, included files, exclusions, checks run, and checks not run.

### 10B.3 `SKILL.md` frontmatter

Use:

```yaml
---
name: skill-tree-unity-create-documents-snapshot
description: Create explicit-request-only Markdown documentation snapshot archives for Unity repositories without modifying live source documents. Use when asked to create a documentation snapshot, documents snapshot, Markdown snapshot, .md snapshot archive, or AI-context docs archive. Do not use during normal documentation initialization, documentation audit, feature implementation, Process pending, or Implement next.
---
```

### 10B.4 `agents/openai.yaml`

Recommended intent:

```yaml
interface:
  display_name: "Skill-Tree-Unity: Create Snapshot"
  short_description: "Create explicit docs snapshots"
  default_prompt: "Create an explicit-request-only Markdown documentation snapshot archive."

policy:
  allow_implicit_invocation: true
```

### 10B.5 `scripts/create_documentation_snapshot.py`

Required behavior:

- explicit target repository;
- tracked Markdown discovery using Git when available;
- include only requested/default repository-owned files;
- exclude vendor/generated/transient docs;
- stage copies in a temporary directory;
- prepend snapshot notice;
- deterministic collision handling;
- timestamped ZIP;
- no modification of live files;
- `--dry-run`;
- post-generation archive verification;
- explicit inclusion/exclusion report.

## 11. Skill 2 — `skill-tree-process-future-pending`

Create:

```text
skills/skill-tree-process-future-pending/
```

## 11.1 Purpose

This skill handles only:

```text
Process pending
Process pending tasks
```

It researches and refines pending work. It does not implement features.

## 11.2 `SKILL.md` frontmatter

Use:

```yaml
---
name: skill-tree-process-future-pending
description: Process the Pending Queue in a repository FUTURE.md. Use when asked to "Process pending" or "Process pending tasks": research each pending request, validate it against the repository, add implementation questions, and promote only implementation-ready work into Prioritized Next Changes. Do not implement the tasks and do not promote Backlog work unless explicitly requested.
---
```

Adjust only if required by the current official format.

## 11.3 Required workflow

The skill must:

1. Locate the applicable `FUTURE.md`.
2. MUST read repository `AGENTS.md`, `RULES.md`, or equivalent rules.
3. MUST read repository/document map if one exists.
4. MUST read current `FEATURES.md`, active `FUTURE.md`, and task-relevant architecture/domain docs.
5. Read local `references/FUTURE_TASK_STANDARD.md`.
6. Read the complete Pending Queue.
7. MUST inspect affected implementation, tests, settings, serialized assets, and documents.
8. MUST verify whether each item is implemented, stale, duplicate, contradictory, or blocked.
9. MUST verify referenced paths and symbols still exist.
10. Check existing `FUTURE.md` tasks for overlap.
11. Merge overlapping requests when justified.
12. Expand valid items to the complete prioritized-task standard with current code/test paths.
13. Add task-specific implementation questions.
14. Resolve questions from evidence where possible.
15. Mark blocking unresolved questions explicitly.
16. Move only sufficiently researched tasks.
17. Preserve priority placement.
18. Leave insufficiently understood items pending.
19. Run FUTURE validation.
20. Report required context inspected plus promoted, retained, merged, and removed items.

It must explicitly state:

- MUST NOT process pending work from `FUTURE.md` alone;
- stop or mark the item blocked when required repository context is missing or contradictory;
- do not silently guess architecture, ownership, tests, or conventions;
- processing is research and documentation work;
- no feature implementation occurs;
- Backlog is not processed unless the user explicitly includes it;
- a promoted task must be detailed enough to minimize unrelated modifications.
- if an AI agent adds a new item to Pending Queue, it must use the nested Markdown pending task format from `REPO_INIT_INSTRUCTIONS.md`;
- documentation or audit findings belong in Backlog, not Pending Queue.

## 11.4 Questions rule

Every promoted task must contain:

```text
Questions and required clarifications:
```

Questions must be task-specific and cover material uncertainty in:

- UX/product behavior;
- architecture;
- affected files;
- state and persistence;
- serialization;
- platform behavior;
- compatibility;
- migration;
- failure/recovery;
- diagnostics;
- testing;
- rollout;
- non-goals.

Do not add generic filler.

A task may state that no unresolved questions remain, but the section must exist.

## 11.5 `agents/openai.yaml`

This file is optional Codex-specific metadata. It must not contain behavior required by the portable skill, and other agents must be able to ignore it safely.

Recommended intent:

```yaml
interface:
  display_name: "Skill-Tree: Process Pending Tasks"
  short_description: "Research and promote pending repository tasks"
  default_prompt: "Process pending tasks in FUTURE.md without implementing them."

policy:
  allow_implicit_invocation: true
```

Verify current schema before committing.

## 11.6 `references/PENDING_PROCESSING_CHECKLIST.md`

Create a concise operational checklist:

```text
Locate
Read rules
Read pending
Search implementation
Check duplicates
Check implementation status
Determine ownership
Identify questions
Resolve evidence-backed questions
Mark blockers
Expand full task
Validate
Report
```

Include stop conditions.

## 11.7 Reuse of validator

Installed skills must be self-contained.

Therefore either:

- include a local copy of `validate_future_document.py`, or
- generate/copy it through synchronization and validate that the copy is current.

Do not require the skill to call a root repository script after installation.

## 12. Skill 3 — `skill-tree-implement-next-future-task`

Create:

```text
skills/skill-tree-implement-next-future-task/
```

## 12.1 Purpose

This skill implements exactly one eligible task from `Prioritized Next Changes`.

It must never select from Pending Queue or Backlog.

## 12.2 `SKILL.md` frontmatter

Use:

```yaml
---
name: skill-tree-implement-next-future-task
description: Implement exactly one task from the Prioritized Next Changes section of FUTURE.md. Use for "Implement next", "Implement next feature", "Implement next: <task name>", or "Implement next feature: <task name>". Never select from Pending Queue or Backlog, and stop for blocking unresolved questions or when a named prioritized task is absent.
---
```

## 12.3 Required selection behavior

Without a task name:

```text
Implement next
Implement next feature
```

The skill must:

1. Select the first task in `Prioritized Next Changes`.
2. Stop if that section is empty.
3. Do not skip a blocked first task automatically.
4. Perform the clarification gate.
5. Implement only that task.

With a task name:

```text
Implement next: Task Name
Implement next feature: Task Name
```

The skill must:

1. Search only prioritized headings.
2. Normalize heading comparison in the documented way.
3. Require one unambiguous match.
4. Stop if absent.
5. Stop if duplicate normalized matches exist.
6. Never fall back to a similarly named pending or backlog item.
7. Perform the clarification gate.
8. Implement only the matching task.

## 12.4 Clarification gate

Before editing:

1. Read the complete task.
2. MUST read repository `AGENTS.md`, `RULES.md`, or equivalent repository rules.
3. MUST read repository/document map if one exists.
4. MUST inspect all documents referenced by the task.
5. MUST read current-state docs such as `FEATURES.md` and task-relevant architecture/domain docs.
6. MUST inspect current code and tests for affected paths and symbols.
7. MUST check for recent changes that invalidate task assumptions or make the work already complete.
8. MUST check existing `FUTURE.md` tasks for duplicate or overlapping work.
9. Read `Questions and required clarifications`.
10. Identify unresolved blocking questions.
11. Ask the owner those questions.
12. Stop implementation until answers exist.
13. Update the task with answers or stale assumptions before implementation.

Do not guess to avoid the stop.
MUST NOT implement from `FUTURE.md` alone.

## 12.5 Scope behavior

The skill must:

- honor `Touch`;
- honor `Discovery allowance`;
- honor `Out of scope`;
- update the task before justified scope expansion;
- avoid opportunistic refactors;
- add or update tests;
- update current-state documentation;
- keep `FEATURES.md` current-state only and move plans, deferred work, or known bugs awaiting fixes to `FUTURE.md`;
- remove the completed task from `FUTURE.md`;
- not mark it completed indefinitely;
- report required context inspected and checks actually run.

## 12.6 `agents/openai.yaml`

This file is optional Codex-specific metadata. It must not contain behavior required by the portable skill, and other agents must be able to ignore it safely.

Recommended intent:

```yaml
interface:
  display_name: "Skill-Tree: Implement Next Task"
  short_description: "Implement one prioritized FUTURE.md task"
  default_prompt: "Implement the next eligible task from Prioritized Next Changes."

policy:
  allow_implicit_invocation: true
```

Use a precise description to avoid accidental activation.

## 12.7 `references/IMPLEMENTATION_HANDOFF_CHECKLIST.md`

Include:

- selected task and selection reason;
- blocking questions checked;
- scope boundaries;
- files changed;
- tests run;
- docs updated;
- task removed;
- remaining risks;
- unrelated issues not changed.

## 12.8 `scripts/select_prioritized_task.py`

Create a deterministic selector/parser.

Required interface:

```bash
python3 select_prioritized_task.py /path/to/FUTURE.md
python3 select_prioritized_task.py /path/to/FUTURE.md --name "Task Name"
python3 select_prioritized_task.py /path/to/FUTURE.md --format json
```

Required behavior:

- parse only `Prioritized Next Changes`;
- stop at the next peer queue heading;
- identify task headings at the documented level;
- normalize names using:
  - Unicode normalization;
  - trim;
  - collapse whitespace;
  - case folding;
- without `--name`, select first task;
- with `--name`, require exactly one normalized match;
- return distinct non-zero exit codes for:
  - file missing;
  - prioritized section missing;
  - no prioritized tasks;
  - named task absent;
  - duplicate normalized match;
  - malformed task;
  - blocking unresolved questions;
- never search Pending or Backlog;
- print selected task body;
- support JSON with stable fields;
- never modify the file.

Do not implement fuzzy matching.

## 13. FUTURE Validator Contract

Create the canonical implementation at:

```text
skills/skill-tree-process-future-pending/scripts/validate_future_document.py
```

Copy or generate the same implementation for any skill that requires standalone use, or design the implementation skill to use its own selector for relevant checks.

Checks must include:

- required queue headings;
- queue ordering;
- prioritized task heading extraction;
- duplicate normalized task names;
- required task sections;
- mandatory questions section;
- valid status values where present;
- blocking question/status consistency;
- no task accidentally nested under the wrong queue;
- no `Implement next` instruction that refers to Backlog;
- optional strict checks for placeholders.

Support:

```bash
python3 validate_future_document.py /path/to/FUTURE.md
python3 validate_future_document.py /path/to/FUTURE.md --format json
python3 validate_future_document.py /path/to/FUTURE.md --strict
```

The parser must be tested against fixtures.

## 14. Cross-Agent Distribution and Unified Installation

Create one cross-platform installer implementation:

```text
bin/install.js
```

Create thin launchers:

```text
install.sh
install.ps1
```

Create package metadata:

```text
package.json
```

The installer architecture should follow the useful cross-agent patterns demonstrated by `caveman`, while remaining simpler because these skills do not need hooks, status lines, MCP middleware, or persistent response modes.

### 14.1 Runtime and dependency policy

Use Node.js 18 or newer for the unified installer.

The installer must use Node standard library only at runtime.

Python remains appropriate for:

- Unity repository inspection;
- reference synchronization;
- Markdown validation;
- snapshot creation;
- skill-local deterministic tools.

`package.json` must:

- declare the minimum Node version;
- expose a CLI entry pointing to `bin/install.js`;
- avoid runtime dependencies;
- include repository metadata only when a real remote is known;
- never publish automatically.

### 14.2 Canonical provider matrix

Create:

```text
config/providers.json
```

This is the single source of truth for supported-agent metadata.

Each provider entry should contain fields equivalent to:

```json
{
  "id": "claude-code",
  "label": "Claude Code",
  "tier": 1,
  "skillsProfile": "claude-code",
  "detect": [
    { "kind": "command", "value": "claude" }
  ],
  "soft": false,
  "projectPath": ".claude/skills",
  "globalPath": "~/.claude/skills",
  "initBridge": "claude",
  "officialDocs": [
    "https://docs.anthropic.com/en/docs/claude-code/skills"
  ]
}
```

Exact field names may differ, but the matrix must remain declarative and testable.

Do not maintain parallel provider lists in JavaScript, shell, PowerShell, README, and tests.

Generate documentation tables from the provider matrix where practical.

### 14.3 Required provider coverage

At implementation time, compare the matrix with the current supported-agent table from `vercel-labs/skills`.

The matrix must include all Tier 1 agents and support current Tier 2 profiles through explicit passthrough.

Tier 1 must include:

```text
claude-code
codex
gemini-cli
cursor
windsurf
cline
github-copilot
opencode
roo
kilo
continue
junie
kiro-cli
openhands
qwen-code
goose
aider-desk
amp
warp
replit
```

Also verify current upstream profiles such as:

```text
antigravity
augment
bob
crush
devin
droid
forgecode
iflow-cli
rovodev
tabnine-cli
trae
```

Do not freeze this example list without checking current upstream documentation.

Support unknown future upstream profiles with:

```text
--agent <upstream-profile>
```

when explicitly selected.

### 14.4 Detection strategies

Support declarative probe kinds:

```text
command
vscode-extension
cursor-extension
jetbrains-plugin
mac-application
directory
file
environment
```

Rules:

- command detection is preferred;
- IDE extension identifiers are strong signals;
- application bundle detection may supplement CLI detection;
- stale config directories must not trigger automatic installation;
- directory-only providers must be marked soft;
- soft providers are listed but excluded from default auto-detection;
- explicit `--only` overrides detection;
- detection failures are not installation failures;
- never launch an agent merely to detect it.

### 14.5 Installation engine

Use the open `skills` CLI as the primary multi-agent installation engine.

For each selected provider, invoke the current verified equivalent of:

```bash
npx -y skills add <source> \
  --agent <profile> \
  --skill '*' \
  --yes
```

Use exact flags verified at implementation time.

Source selection order:

1. Explicit `--source`.
2. Local repository path when running from a clone.
3. Configured Git remote/repository slug only when verified.
4. Otherwise stop with a clear error.

Do not invent `<owner>/<repo>`.

Do not silently install from an unrelated working directory.

### 14.6 Native mechanisms

Native packaging may be added only when it materially improves behavior and is explicitly implemented.

Possible future mechanisms:

- Claude Code plugin;
- Gemini CLI extension;
- OpenCode plugin;
- OpenClaw workspace package;
- vendor-specific marketplaces.

For initial creation, canonical Agent Skills installation is sufficient.

If native packaging is added later:

- it must consume canonical `skills/`;
- it must not fork skill content;
- it needs separate tests;
- installer output must identify the mechanism used.

### 14.7 Optional repository instruction bridges

Implement optional:

```text
--with-init
```

It may write short repository-level bridges for agents where discovery or routing benefits from explicit instructions.

Possible destinations include:

```text
AGENTS.md
CLAUDE.md
GEMINI.md
.github/copilot-instructions.md
.cursor/rules/skill-tree-skills.mdc
.windsurf/rules/skill-tree-skills.md
.clinerules/skill-tree-skills.md
.opencode/AGENTS.md
```

Do not write every destination blindly.

Use the selected provider’s adapter definition.

Bridge content must be generated from:

```text
src/init-rules/skill-tree-skills.md
```

The bridge must only explain:

- which skill handles repository documentation;
- which skill handles `Process pending`;
- which skill handles `Implement next`;
- that `Implement next` never reads Backlog;
- that blocking questions stop implementation.

Do not inline complete skills.

Every bridge write must:

- preserve existing user content;
- use explicit begin/end markers;
- be idempotent;
- create a backup before modifying an existing file;
- support clean removal;
- refuse ambiguous legacy content unless `--force` is used.

`--with-init` defaults to false.

### 14.8 Required CLI interface

Support:

```text
--all
--only <provider-id>          repeatable
--agent <upstream-profile>   repeatable
--skills <skill-name...>
--global
--project
--target <path>
--source <git-or-local-source>
--copy
--symlink
--with-init
--dry-run
--list
--force
--uninstall
--verify
--non-interactive
--no-color
--help
```

Resolve mutually exclusive combinations explicitly.

Recommended usage:

```bash
node bin/install.js --list
node bin/install.js --dry-run --all
node bin/install.js --only claude-code --global
node bin/install.js --only codex --only cursor --project --target /path/to/repo
node bin/install.js --agent qwen-code --skills skill-tree-process-future-pending
node bin/install.js --all --with-init
node bin/install.js --uninstall --only windsurf
```

### 14.9 Automatic selection

Default behavior:

1. Detect reliable providers.
2. Exclude soft providers.
3. Show the planned selection.
4. Prompt when interactive.
5. Require explicit defaults in non-interactive mode.
6. Skip agents not detected.
7. Continue installing other agents when one fails.
8. Return non-zero on partial failure.
9. Print a final result table.

`--all` means all selected or reliably detected supported providers unless explicitly documented otherwise.

### 14.10 Thin launchers

`install.sh` and `install.ps1` must not contain provider logic.

They should:

- locate a local clone and run `node bin/install.js`; or
- when remote distribution is configured, delegate to the packaged CLI;
- forward all arguments;
- fail clearly when Node is missing or too old;
- avoid duplicated option parsing.

### 14.11 Idempotency and overwrite policy

Re-running the installer must be safe.

Rules:

- existing installations are skipped unless update or force is requested;
- copy mode stages before replacement;
- symlink mode displays resolved targets;
- unrelated skills remain untouched;
- unrelated instruction content remains untouched;
- provider failures are isolated;
- dry-run writes nothing;
- verify writes nothing.

### 14.12 Uninstall

Uninstall removes only installer-owned state.

Use the upstream skill manager when it owns the installation.

Remove bridge blocks only between repository-specific markers.

Do not delete entire shared instruction files.

Do not delete unrelated skills.

Report items requiring manual cleanup.

### 14.13 Privacy and network behavior

The installer must have no first-party telemetry.

Document that network access may occur indirectly through:

- `npx`;
- the open `skills` CLI;
- Git source resolution;
- optional native installers added later.

`--dry-run` must not invoke network installation commands.

`--list` should not require network access unless an explicit refresh option is used.

### 14.14 Adapter documentation

Each adapter README must document:

- provider id;
- upstream profile;
- detection;
- install paths;
- invocation examples;
- known frontmatter support;
- bridge behavior;
- uninstall behavior;
- official documentation;
- last verification date.

Adapter README files describe behavior. They do not contain separate skill implementations.

### 14.15 Generic fallback

The generic adapter must support:

- explicit destination path;
- copy or symlink;
- direct prompt generation through `npx skills use` where available;
- manual installation instructions;
- no claim of automatic discovery.

### 14.16 Installation verification

After installation, verify:

- target skill directory exists;
- `SKILL.md` parses;
- referenced local resources exist;
- copied content matches the source manifest;
- symlink resolves;
- optional bridge marker exists exactly once;
- unrelated files were not modified.

Provide an installation report, but do not commit private absolute paths.

## 15. Repository-Level Validator

Create:

```text
scripts/validate_skill_repository.py
```

This is the main deterministic gate.

Recommended interface:

```bash
python3 scripts/validate_skill_repository.py
python3 scripts/validate_skill_repository.py --strict
python3 scripts/validate_skill_repository.py --format json
```

Required checks:

### 15.1 Repository structure

- required root files exist;
- expected skill folders exist;
- no unexpected snapshot-named live source files;
- no committed Python cache or temporary output;
- tests and fixtures exist;
- unified installer files exist;
- provider matrix exists;
- adapter documentation exists;
- root cross-agent entry files exist.

### 15.2 Skill structure

For each skill:

- folder name is kebab-case;
- `SKILL.md` exists;
- YAML frontmatter is present;
- `name` exists and equals folder name;
- `description` exists and is non-empty;
- required local references exist;
- required local scripts exist;
- references mentioned in `SKILL.md` resolve;
- scripts mentioned in `SKILL.md` resolve;
- no absolute machine-local paths;
- no dependency on sibling skill paths;
- optional metadata parses at least structurally;
- portable behavior does not depend on vendor metadata;
- no agent-specific divergent copy of the canonical skill exists.

Use a minimal safe parser. Do not add a YAML dependency solely for validation unless approved.

### 15.3 Source synchronization

- full source copy is identical;
- generated references are current;
- generated notices exist;
- generator check mode passes.

### 15.4 Behavioral contract

Search or parse enough to ensure:

- documentation skill reads the full source reference;
- process skill explicitly does not implement;
- process skill requires questions;
- implement skill selects only prioritized work;
- implement skill forbids Backlog fallback;
- named task absence stops;
- blocking questions stop;
- first blocked task is not skipped automatically.

Do not rely only on substring checks. Combine deterministic checks with tests and a manual review checklist.

### 15.5 Cross-agent compatibility

Validate:

- provider ids are unique;
- upstream profile names are non-empty;
- Tier 1 providers have official references;
- hard probes use reliable signals;
- directory-only probes are marked soft;
- soft providers are not auto-selected;
- documented paths match the provider matrix;
- adapter docs reference existing provider ids;
- `install.sh` and `install.ps1` contain no provider matrix;
- bridge destinations use safe markers;
- canonical skills are the only skill source;
- all Tier 1 providers have fixtures or mocked detection tests;
- explicit unknown upstream profiles are handled safely;
- installer has no first-party telemetry.

### 15.6 Script quality

- Python files compile;
- scripts have `main()` and guarded entry points;
- no third-party imports;
- no obvious hard-coded repository path;
- `--help` succeeds;
- dry-run/check modes do not modify files.

### 15.7 Documentation quality

- README references valid paths;
- installation commands match script interface;
- official source verification date exists;
- no unsupported product claims;
- no unresolved scaffold placeholders.

## 16. Tests

Use Python’s built-in `unittest` unless a test framework already exists.

Do not introduce a package dependency merely for tests.

Run:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/test_installer.js tests/test_provider_matrix.js
```

## 16.1 Required test groups

### Reference synchronization

Test:

- byte-identical source copy;
- deterministic generation;
- check mode passes when current;
- check mode fails after intentional fixture drift;
- missing heading fails safely;
- duplicate heading fails safely.

### Skill repository validation

Test:

- valid repository passes;
- missing SKILL.md fails;
- name/folder mismatch fails;
- missing description fails;
- missing reference fails;
- stale generated reference fails;
- absolute path dependency fails when detectable.

### FUTURE validation

Fixtures must test:

- fully valid prioritized task;
- missing questions section;
- duplicate normalized names;
- empty prioritized section;
- named task only in Backlog;
- blocking unresolved question;
- no unresolved questions form;
- malformed queue ordering.

### Prioritized task selection

Test:

- first task selection;
- exact normalized named selection;
- case-insensitive match;
- whitespace normalization;
- Unicode normalization;
- absent named task;
- duplicate name;
- empty prioritized list;
- blocked first task;
- similarly named Backlog item not selected.

### Installation

Use temporary directories.

Test:

- user-like destination;
- repository destination;
- one-skill install;
- all-skills install;
- overwrite refusal;
- force replacement;
- dry run;
- symlink mode where supported;
- installed skill self-containment;
- unrelated destination skill preserved.

### Unity inventory and documentation validation

At minimum test:

- invalid target;
- minimal Unity root detection;
- transient directory exclusion;
- documentation required-file detection;
- snapshot-named live file rejection;
- FUTURE contract delegation.

## 16.2 Cross-agent installer tests

Use mocked process execution and temporary directories.

Test:

- reliable command detection;
- VS Code extension detection;
- Cursor extension detection;
- JetBrains plugin detection;
- macOS application detection where simulation is practical;
- soft directory-only detection excluded by default;
- explicit `--only` installs a soft provider;
- unknown provider id fails;
- explicit upstream `--agent` passthrough;
- project scope;
- global scope;
- local source selection;
- missing source failure;
- dry-run performs no writes or installation calls;
- list mode performs no writes;
- partial provider failure;
- final non-zero status on partial failure;
- idempotent re-run;
- force behavior;
- copy mode;
- symlink mode where supported;
- bridge insertion;
- bridge re-run without duplication;
- bridge uninstall preserving surrounding content;
- backup creation;
- unrelated skills preserved;
- provider matrix and documentation synchronization.

## 16.3 Cross-agent compatibility fixtures

Fixtures must cover at minimum:

```text
claude-code
codex
gemini-cli
cursor
windsurf
cline
github-copilot
opencode
roo
kilo
continue
junie
kiro-cli
openhands
qwen-code
goose
aider-desk
amp
warp
replit
```

A fixture does not need the real agent installed. Mock detection and expected upstream command generation.

## 16.4 Fixture policy

Fixtures must not contain:

- real credentials;
- proprietary project code;
- large Unity binary assets;
- copied third-party packages.

The Unity fixture may be a documented minimal synthetic tree containing text files only.

## 17. Skill Evaluation Scenarios

In addition to deterministic unit tests, create `tests/README.md` with manual/eval scenarios.

For each skill define:

```text
Prompt
Expected skill activation
Expected files read
Expected process
Forbidden behavior
Expected output
Scoring checks
```

### 17.1 Documentation skill scenarios

Positive prompts:

```text
Initialize AI-oriented documentation for this existing Unity project.
Audit this Unity repository and repair stale project documentation.
Create PROJECT.md, TECHNICAL.md, FEATURES.md, FUTURE.md, and RULES.md.
```

Negative prompts:

```text
Fix a NullReferenceException in PlayerController.
Translate this changelog.
Update one sentence in README.
Implement next.
```

### 17.2 Pending processing scenarios

Positive:

```text
Process pending.
Process pending tasks in FUTURE.md.
```

Expected:

- no implementation changes;
- repository research;
- detailed promoted tasks;
- mandatory questions.

Forbidden:

- selecting Backlog;
- writing product code;
- promoting an unresearched item as ready.

### 17.3 Implement-next scenarios

Positive:

```text
Implement next.
Implement next: Add save migration validation.
```

Expected:

- prioritized-only selection;
- stop on blocker;
- exact named behavior;
- one task only.

Forbidden:

- Backlog fallback;
- pending implementation;
- skipping blocked first task;
- fuzzy replacement for missing task.

### 17.4 Cross-agent activation scenarios

Run or simulate the same core prompts against Tier 1 agents where practical.

Verify:

- the intended skill is discoverable;
- the same canonical `SKILL.md` is used;
- agent-specific metadata is optional;
- unsupported optional fields do not break the skill;
- `Process pending` does not implement;
- `Implement next` never selects Backlog;
- blocking questions stop implementation.

Record deviations by agent rather than forking the canonical skill immediately.

The eval document should encourage trace-based evaluation when infrastructure is available, but must not require hosted eval services for repository correctness.

## 18. Git Workflow

## 18.1 Before staging

Run:

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

Review:

```bash
git diff --stat
git diff
```

Check for:

- accidental changes to root source instruction;
- generated-reference drift;
- temporary files;
- absolute paths;
- secrets;
- unsupported claims;
- unbalanced Markdown fences;
- executable-bit mistakes;
- missing tests.

## 18.2 Commit policy

Do not commit until validation passes.

Do not configure Git identity to make a commit succeed.

If the task explicitly includes committing and identity is already configured, use coherent commits.

Recommended commit sequence:

```text
chore: initialize skill repository structure
feat: add Unity repository workflow skills
test: add skill validation and installation coverage
```

A single commit is acceptable for an initial small repository:

```text
feat: add reusable Unity repository workflow skills
```

Do not push.

Do not create tags or releases.

## 18.3 Repository cleanliness

After tests:

```bash
git status --short
```

Remove untracked transient output created by tests. Do not remove the two source instruction files.

## 19. Manual Review of Each Skill

After automated checks, read each installed-form skill folder as though the source repository does not exist.

Install or simulate installation for every Tier 1 provider and at least one Tier 2 passthrough profile.

For each skill verify:

- `SKILL.md` has enough information to find its own references;
- local references contain required behavior;
- local scripts work from arbitrary working directories;
- no sibling path is required;
- no root path is required;
- trigger description is precise;
- negative activation boundary is clear;
- completion report is defined;
- destructive behavior is prohibited;
- unresolved ambiguity causes the correct stop.

## 20. Source Drift Policy

When `REPO_INIT_INSTRUCTIONS.md` changes:

1. Read the diff.
2. Determine which skill responsibilities are affected.
3. Run reference synchronization.
4. Update manually authored concise references only when their behavior changed.
5. Update `SKILL.md` only if trigger, workflow, or critical constraints changed.
6. Update validators and fixtures for contract changes.
7. Run all tests.
8. Review generated diffs.
9. Commit source and synchronized changes together.

Never manually patch generated references to hide drift.

The repository validator must fail when synchronization is stale.

## 21. Versioning and Releases

Do not introduce release automation during initial creation unless requested.

Document a future-compatible policy in README:

- use semantic version tags for repository releases when distribution begins;
- describe behavior changes in release notes;
- treat breaking trigger/command changes as major or clearly breaking;
- validate before tagging;
- consider native plugins or extensions later only when they add behavior beyond portable Agent Skills.

Do not claim that the source repository is already a Codex plugin, Claude plugin, Gemini extension, or native package for another agent.

Do not create native plugin or extension manifests in this task unless explicitly requested after the portable installer is complete.

## 22. Security and Privacy

The repository must contain no:

- API keys;
- tokens;
- credentials;
- signing material;
- personal paths;
- private Unity project code;
- private issue content;
- real production `FUTURE.md` tasks unless intentionally provided;
- logs with user data.

Scripts must avoid printing file contents unnecessarily.

Inventory scripts should report paths and metadata rather than dumping secrets.

Installation scripts must refuse suspicious destinations such as filesystem root unless explicitly supported and guarded.

Symlink mode must display the resolved target.

## 23. Error Handling Requirements

All command-line tools must:

- validate arguments before writing;
- print concise errors to stderr;
- use stable non-zero exit codes;
- support paths containing spaces;
- use UTF-8 explicitly;
- use temporary directories for staged writes;
- clean up temporary data;
- avoid destructive fallback behavior;
- document exit codes when callers depend on them.

Python tools must:

- use clear `argparse` help;
- use `pathlib`;
- avoid tracebacks for expected user errors;
- preserve tracebacks only for unexpected internal failures when useful;
- avoid `shell=True`.

The Node installer must:

- provide clear `--help`;
- validate mutually exclusive options;
- use argument arrays for child processes;
- handle Windows command shims safely;
- avoid shell execution unless required for Windows compatibility;
- quote arguments defensively when shell execution is unavoidable;
- isolate per-provider failures;
- return non-zero on partial installation failure;
- distinguish detection, installation, validation, and uninstall errors;
- never report success when an upstream command installed zero skills.

## 24. Coding Standards

Use Python 3 standard library for:

- reference synchronization;
- Unity repository inspection;
- Markdown validation;
- snapshot creation;
- skill-local deterministic tools.

Use Node.js 18+ standard library for:

- unified cross-agent installation;
- provider detection;
- process delegation;
- cross-platform installer behavior.

General rules:

- type hints for public Python functions;
- JSDoc or clear contracts for non-obvious JavaScript;
- small functions;
- data-driven provider behavior;
- deterministic ordering;
- explicit UTF-8;
- `pathlib.Path` in Python;
- `node:path` in JavaScript;
- guarded CLI entry points;
- no broad exception suppression;
- no `shell: true` unless Windows command-shim compatibility requires it and arguments are safely quoted;
- no duplicated provider logic in wrappers.

Do not add:

- Poetry;
- Python runtime dependencies;
- Node runtime dependencies;
- Makefile;
- Docker;
- CI configuration;
- pre-commit;
- formatters;
- linters;

unless explicitly requested.

Development dependencies are unnecessary for the initial repository.

The repository should work with:

```text
Python 3
Node.js 18+
Git
npx access for remote installation operations
```

Validation and local skill use must remain possible without installing npm dependencies.

## 25. Definition of Done

The repository is complete only when:

### Structure

- [ ] All ten canonical skill folders exist.
- [ ] Every skill has `SKILL.md`.
- [ ] Every skill is self-contained.
- [ ] Optional vendor metadata is non-canonical.
- [ ] Root README, INSTALL, AGENTS, CLAUDE, and GEMINI files exist.
- [ ] Provider matrix exists.
- [ ] Unified installer and thin platform launchers exist.
- [ ] Adapter documentation exists.
- [ ] Git ignore and editor settings exist.

### Portable skill contract

- [ ] Canonical skills follow the open Agent Skills specification.
- [ ] No canonical behavior is tied to one agent.
- [ ] No divergent agent-specific skill copies exist.
- [ ] Skills work after standalone copying.
- [ ] Vendor-specific optional fields are not required.

### Source synchronization

- [ ] Full instruction copy is identical.
- [ ] FUTURE references are generated.
- [ ] Check mode passes.
- [ ] Generated references say not to edit them manually.

### Behavior

- [ ] Documentation skill performs repository documentation only.
- [ ] Pending skill never implements.
- [ ] Pending skill adds task-specific questions.
- [ ] Prioritized tasks must be maximally detailed.
- [ ] Implement-next uses only Prioritized Next Changes.
- [ ] Named selection stops when absent.
- [ ] Backlog fallback is forbidden.
- [ ] Blocking questions stop implementation.
- [ ] A blocked first task is not silently skipped.

### Cross-agent support

- [ ] Tier 1 agent matrix is complete and verified.
- [ ] Tier 2 passthrough is supported.
- [ ] Generic fallback is documented.
- [ ] Reliable probes and soft probes are distinguished.
- [ ] Soft providers are not auto-installed.
- [ ] Project and global scopes are supported.
- [ ] Copy and symlink modes are supported.
- [ ] Dry-run and list modes are non-destructive.
- [ ] Optional init bridges are marker-fenced and reversible.
- [ ] Installer has no first-party telemetry.
- [ ] Installation docs state every touched location.
- [ ] Agent paths and profile names were verified against current sources.

### Scripts

- [ ] Installer is non-destructive by default.
- [ ] Provider matrix is the single source of truth.
- [ ] Shell and PowerShell launchers contain no provider logic.
- [ ] Repository validator passes.
- [ ] FUTURE validator passes fixtures.
- [ ] Selector never searches Backlog.
- [ ] Unity inventory is read-only.
- [ ] Documentation snapshot tool does not modify live files.

### Tests

- [ ] All Python unit tests pass.
- [ ] All Node installer tests pass.
- [ ] Tier 1 providers have mocked compatibility coverage.
- [ ] Invalid cases fail as expected.
- [ ] Installation self-containment is tested.
- [ ] Bridge idempotency and uninstall are tested.
- [ ] Git diff check passes.

### Documentation

- [ ] README installation commands are correct.
- [ ] INSTALL contains the compatibility matrix or a generated equivalent.
- [ ] Compatibility docs include verification dates.
- [ ] AGENTS is vendor-neutral and concise.
- [ ] CLAUDE and GEMINI point to canonical rules.
- [ ] No unsupported vendor claims remain.
- [ ] No secrets or personal paths exist.
- [ ] No placeholders remain unless explicitly documented as future work.

### Git

- [ ] Worktree contains only intended files.
- [ ] No transient output is staged.
- [ ] Commit was created only if requested and possible.
- [ ] Nothing was pushed.
- [ ] No remote was invented.

## 26. Final Handoff

Report:

```text
Created files
Skill names
Canonical source model
Source synchronization strategy
Supported-agent tiers
Provider count
Tier 1 agents
Soft providers
Unified installer commands
Adapters implemented
Tests run and results
Agent documentation verification date
Open Agent Skills specification verification date
Installation examples
Git status
Commit hash, only if a commit was created
Open questions
Known limitations
Suggested next step
```

State explicitly:

- whether Git was initialized;
- whether a commit was created;
- whether any test was not run;
- whether native plugin or extension packaging was intentionally deferred;
- whether any provider relies only on generic fallback;
- whether a license still needs owner selection.

Do not say the skills are production-ready unless all required validation and tests passed.

## 27. Suggested Execution Summary

Use this only after reading the complete instruction:

```text
1. Protect the Git worktree.
2. Verify the open Agent Skills specification.
3. Verify the current open skills CLI agent matrix.
4. Review caveman's provider-matrix and unified-installer architecture.
5. Verify official documentation for Tier 1 agents.
6. Read and map all of REPO_INIT_INSTRUCTIONS.md.
7. Create vendor-neutral root documentation and compatibility docs.
8. Implement deterministic reference synchronization.
9. Create the ten focused, self-contained canonical skills.
10. Create the declarative provider matrix.
11. Implement the unified Node installer and thin platform wrappers.
12. Add optional, reversible repository instruction bridges.
13. Add skill-local references and safe scripts.
14. Add repository validators.
15. Add fixtures, unit tests, compatibility tests, and eval scenarios.
16. Synchronize generated references.
17. Run strict validation and all Python and Node tests.
18. Review standalone installed-form skills and every Tier 1 command.
19. Review the Git diff.
20. Commit only when requested and valid.
21. Report exact outcomes and remaining limitations.
```
