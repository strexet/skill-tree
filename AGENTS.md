# Skill Tree Repository Instructions

Read [maintainer instructions](.skill-tree/documents/skill-repository-creation-instructions.md) before source changes. Read applicable contracts under `.skill-tree/common/references/`; Unity contracts reside in `.skill-tree/documents/repo-init-instructions.md`.

Authored operations: `.skill-tree/templates/`; domain slots: `.skill-tree/domains/`; generated representative skills: `.skill-tree/skills/<flavor>/`. Shared behavior: `.skill-tree/common/`. Provider metadata: `.skill-tree/config/providers.json`. Generated resources: `.skill-tree/config/resource-map.json`. Generate copies with `python3 .skill-tree/scripts/sync-skill-references.py`; never edit generated resources independently.

Documents use English, declarative current-state prose and explicit entities instead of pronouns. Owned filenames use lowercase kebab-case; external discovery filenames retain required spelling. Installed skills remain self-contained. Repository-relative paths are mandatory in portable metadata. Explicit developer instructions take precedence.

Process Pending requires repository/source research. Standalone processing reports the prioritized list and waits for developer next-action selection, with one recommendation last. Explicit Work Through Next/Implement All controllers automatically select eligible units inside recorded scope; active state alone grants no continuation. Implement Next selects only Prioritized tasks by highest integer priority or exact ID/name; blocked selection stops. Never implement from the queue alone. Authorization policies remain binding. Commit only when explicitly authorized, after review and relevant validation; stage task-owned files only. No push, publish, tags, history rewriting or license changes without explicit authorization.

Validation: `npm run sync:check`, `npm run validate`, `npm run test:py`, `npm run test:node`, `node .skill-tree/bin/install.js --list`, `node .skill-tree/bin/install.js --dry-run --all --target <temporary-project-root> --flavor general`, `git diff --check`.

Approved implementation scope and current checkpoint: [implementation plan](.skill-tree/documents/implementation-plan.md).
