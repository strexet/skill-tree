# Skill Tree

Skill Tree provides eight portable operations for repository documentation, intake, research, implementation and resumable orchestration. One project-scoped installation selects general, web or unity. Common contracts and concrete project capabilities compose into standalone packages with stable `skill-tree-*` names.

[Installation](.skill-tree/documents/install.md) · [Validation](.skill-tree/common/references/validation-policy.md) · [Workflow](.skill-tree/common/references/future-workflow.md) · [Metadata](.skill-tree/common/references/workflow-metadata.md) · [Source manifest](.skill-tree/skill-tree.json) · [Conformance audit](.skill-tree/documents/workflow-redesign-conformance.md)

```sh
node .skill-tree/bin/install.js --list
node .skill-tree/bin/install.js --target <project-root> --only codex --flavor general --copy --dry-run
npm run sync:check
npm run validate
npm run test:py
npm run test:node
```

Project-scoped copy installation includes owned receipts and a self-contained local profile manager. Static discovery never starts an Editor, server, browser or test suite. Missing test infrastructure remains a deduplicated setup finding. Installation and documentation initialization are separate operations; unknown or modified packages conflict even with `--force`.

Target documentation and task progress reside in `.skill-tree/documents/`. Schema 2 retains standalone single-run checkpoints; explicit workspace setup creates a schema-3 registry for isolated controllers sharing one canonical queue. Structured outcomes and bounded audit/run evidence reside in `.skill-tree/history/`. Focused Red/Green feedback remains immediate; compatible additional boundary checks can share a scoped group. Completion requires current passed check receipts.

Standalone Process Pending reports the prioritized list and waits for developer selection, with one recommendation last. Explicit Work Through Next and Implement All controllers continue through eligible required work inside the recorded scope. A checkpoint, profile or installed flavor supplies no independent execution, continuation, commit or publication permission.

Source fixtures qualify deterministic helper/composer/installer behavior. Unity, browser, hosted/provider, device and actual agent-behavior qualification remain separate evidence boundaries. [Manual target update](.skill-tree/documents/manual-target-update.md) preserves the existing repository's identities and history without an automatic converter.
