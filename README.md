# Skill Tree

Skill Tree provides eleven portable operations for repository documentation, intake, research, implementation, resumable orchestration and plugin management. One project-scoped installation selects general, web or unity. Common contracts and concrete project capabilities compose into standalone packages with stable `skill-tree-*` names.

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

Invoke `skill-tree-plugins` to browse known sources, inspect installed packages and configure ordered bindings. Complete core installation starts with zero external plugins. The [management contract](.skill-tree/documents/plugin-management-contract.md) describes source intake, parameter values and exact confirmation.

Target documentation and task progress reside in `.skill-tree/documents/`. Schema 2 retains standalone single-run checkpoints; explicit workspace setup creates a schema-3 registry for isolated controllers sharing one canonical queue. Structured outcomes and bounded audit/run evidence reside in `.skill-tree/history/`. Focused Red/Green feedback remains immediate; compatible additional boundary checks can share a scoped group. Completion requires current passed check receipts.

Standalone Process Pending reports the prioritized list and waits for developer selection, with one recommendation last. Explicit Work Through Next and Implement All controllers continue through eligible required work inside the recorded scope. A checkpoint, profile or installed flavor supplies no independent execution, continuation, commit or publication permission.

`skill-tree-clarify-tasks` supports explicit task/group interviews through source research, actual owner answers and guarded revisions. Separate session records preserve the selected scope across interruption. Current semantic confirmation completes clarification; implementation remains a separate instruction. The [clarification contract](.skill-tree/documents/task-clarification-contract.md) defines task-local holds and confirmation freshness.

Source fixtures qualify deterministic helper/composer/installer behavior. Unity, browser, hosted/provider, device and actual agent-behavior qualification remain separate evidence boundaries. [Manual target update](.skill-tree/documents/manual-target-update.md) preserves the existing repository's identities and history without an automatic converter.

The [PR review cycle](.skill-tree/common/references/pr-review-cycle.md) supports a current source branch, a default develop target and merge disabled unless explicitly authorized. [Run workspaces](.skill-tree/common/references/run-workspaces.md) bind concurrent controller runs to isolated branches/worktrees and one canonical task queue. Explicit setup/adoption preserves supported checkpoints; semantic run-event envelopes carry scoped queue and completion changes without overwriting concurrent updates.

Relocated byte-matching installations support explicit local-manager `--rebind`; queue locator recovery remains separate and preserves retained checkpoints. Source recipes retain stable installed identities. Manager dry-run flags reject unsupported operations, merge examples grant no authorization, and snapshots exclude generated packages and maintenance copies. The [quality audit](.skill-tree/documents/skill-quality-audit.md) records repair evidence and eight bounded independent Codex observations.
