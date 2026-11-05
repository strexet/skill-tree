# Skill Tree Repository Instructions

Repository development uses the installed general Skill Tree operations under `.agents/skills/`. Read the matching operation's `SKILL.md` and applicable bundled references before documentation, task intake, prioritization, implementation or PR review work. The installed packages form the execution snapshot; authored templates, domain slots and common resources remain the source of future versions. Refresh the installed snapshot through the owned installer after reviewed source changes; never edit installed packages independently.

Read [maintainer instructions](.skill-tree/documents/skill-repository-creation-instructions.md) before source changes. Read applicable contracts under `.skill-tree/common/references/`; Unity contracts reside in `.skill-tree/documents/repo-init-instructions.md`.

Authored operations: `.skill-tree/templates/`; domain slots: `.skill-tree/domains/`; generated representative skills: `.skill-tree/skills/<flavor>/`. Shared behavior: `.skill-tree/common/`. Provider metadata: `.skill-tree/config/providers.json`. Generated resources: `.skill-tree/config/resource-map.json`. Generate copies with `python3 .skill-tree/scripts/sync-skill-references.py`; never edit generated resources independently.

Documents use English, declarative current-state prose and explicit entities instead of pronouns. Owned filenames use lowercase kebab-case; external discovery filenames retain required spelling. Installed skills remain self-contained. Repository-relative paths are mandatory in portable metadata. Explicit developer instructions take precedence.

Process Pending requires repository/source research. Standalone processing reports the prioritized list and waits for developer next-action selection, with one recommendation last. Explicit Work Through Next/Implement All controllers automatically select eligible units inside recorded scope; active state alone grants no continuation. Implement Next selects only Prioritized tasks by highest integer priority or exact ID/name; blocked selection stops. Never implement from the queue alone. Authorization policies remain binding. Commit only when explicitly authorized, after review and relevant validation; stage task-owned files only. No push, publish, tags, history rewriting or license changes without explicit authorization.

Validation: `npm run sync:check`, `npm run validate`, `npm run test:py`, `npm run test:node`, `node .skill-tree/bin/install.js --list`, `node .skill-tree/bin/install.js --dry-run --all --target <temporary-project-root> --flavor general`, `git diff --check`.

Approved implementation scope and current checkpoint: [implementation plan](.skill-tree/documents/implementation-plan.md).

<!-- BEGIN skill-tree-skills -->
Skill Tree navigation resides in .skill-tree/skill-tree.json. Applicable repository rules remain mandatory. Task definitions reside in .skill-tree/documents/future.md; active state resides in future.json. Add Pending captures brief understood requests; Process Pending accepts IDs/names and produces researched tasks; standalone processing prints the prioritized list, presents one recommended next action last and waits for developer selection; explicitly launched Work Through Next/Implement All controllers continue automatically within root/snapshot boundaries; Implement Next selects the highest numeric priority or an exact prioritized ID/name. Work Through Next resolves one main and required dependencies. Implement All freezes an initial prioritized snapshot. Required clarifications stop execution. History provides evidence without granting authorization. Installed packages contain standalone contracts/helpers. No queue-only implementation or implicit publication/scheduling permission.
Flavor: general. Profile: `.skill-tree/installation/profile.json`.
<!-- END skill-tree-skills -->
