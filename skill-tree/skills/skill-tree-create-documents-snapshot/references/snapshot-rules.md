<!-- GENERATED FILE; Source: skill-tree/common/references/snapshot-rules.md; generator: skill-tree/scripts/sync-skill-references.py -->

# Documentation Snapshots

Create Markdown snapshot archives only upon explicit developer request. Default candidates: root README.md/AGENTS.md and tracked repository-owned Markdown under skill-tree/documents/. Include other project-owned Markdown only with material context. Exclude vendor/package documentation, caches, generated output, ignored artifacts, credentials, private reports and unrequested licenses/changelogs.

Default archive: skill-tree/artifacts/<repository>-documents-snapshot-<timestamp>.zip. Member filenames use lowercase kebab-case and remain at archive root; flatten path collisions with hyphens and deterministic suffixes. Prefix each copy with source path, snapshot timestamp and an explicit live-source verification warning. Preserve live files. Dry-run performs no writes. Archive creation does not launch tools or imply commits.

Explicit scope uses `--include <file-or-directory> ...`, with repeated options combined and overlapping sources deduplicated. Directory selection uses relevant tracked Markdown; an explicitly selected new Markdown file may be untracked. Missing, excluded or out-of-repository selections reject the whole request before archive creation. Vendor/generated/private evidence remains excluded; symlinks never capture external documents.

Repository-owned naming/output contracts select `--member-style dotted` for `<source-stem>.snapshot-<timestamp>.md` members and `--output-dir root` for a root archive. Defaults remain kebab-case members and ignored artifacts. `--output <archive.zip>` sets an explicit destination; `--timestamp YYYY-MM-DD-HH-MM` supplies an explicit creation timestamp when required. Naming collisions flatten relative paths and receive deterministic suffixes. Existing archives require another output path; live Markdown files remain untouched. Pass the same scope and policy options to dry-run and creation.
