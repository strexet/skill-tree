# Skill Tree

Skill Tree provides portable repository documentation, task intake, research, implementation and resumable orchestration skills. Thirteen skills include five Unity-specific variants.

[Installation](skill-tree/documents/install.md) · [Workflow](skill-tree/common/references/future-workflow.md) · [Metadata](skill-tree/common/references/workflow-metadata.md) · [Source manifest](skill-tree/skill-tree.json)

```sh
node skill-tree/bin/install.js --list
node skill-tree/bin/install.js --dry-run --all
npm run validate
npm run test:py
npm run test:node
```

Install individual skills by copy or symlink using the local installer. Optional provider bridges preserve unowned instruction content. Installed skills carry required resources; source repository access is unnecessary during execution.

Target documentation and task state reside in `skill-tree/documents/`. Structured task outcomes and bounded audit/run records reside in `skill-tree/history/`. Developer authorization governs validation, commits and external operations.

## Processing Handoff

Standalone Process Pending reports the refreshed prioritized list and asks for the next action, with one recommended action last. Work Through Next and Implement All automatically select the next eligible scoped unit after processing while preserving material questions, validation limits and deferred work. An active checkpoint alone supplies no implementation instruction.
