<!-- GENERATED FILE; Source: skill-tree/common/references/snapshot-rules.md; generator: skill-tree/scripts/sync-skill-references.py -->

# Documentation Snapshots

Create Markdown snapshot archives only upon explicit developer request. Default candidates: root README.md/AGENTS.md and tracked repository-owned Markdown under skill-tree/documents/. Include other project-owned Markdown only with material context. Exclude vendor/package documentation, caches, generated output, ignored artifacts, credentials, private reports and unrequested licenses/changelogs.

Default archive: skill-tree/artifacts/<repository>-documents-snapshot-<timestamp>.zip. Member filenames use lowercase kebab-case and remain at archive root; flatten path collisions with hyphens and deterministic suffixes. Prefix each copy with source path, snapshot timestamp and an explicit live-source verification warning. Preserve live files. Dry-run performs no writes. Archive creation does not launch tools or imply commits.
