<!--
GENERATED FILE
Source: common/references/SNAPSHOT_RULES.md
Generator: scripts/sync_skill_references.py
Do not edit manually. Update the source document and rerun the generator.
-->

# Snapshot Rules

Create a dated Markdown documentation snapshot archive only when explicitly requested by the user.

## Source Scope

Default source set:

- root `README.md`;
- root `AGENTS.md`;
- tracked repository-owned Markdown under `Documents/`;
- other tracked project-owned Markdown only when it contains material repository-specific information.

Use Git when available:

```bash
git ls-files '*.md'
```

Exclude by default:

- package/vendor documentation;
- dependency and package caches;
- generated API docs;
- build output;
- imported SDK changelogs unless explicitly requested;
- dependency licenses unless explicitly requested;
- transient reports;
- ignored files;
- secrets, credentials, real user data, signing material, local endpoints, and private logs.

Explicit user scope overrides the default when it is safe.

## Relevance Check

Inspect each candidate enough to confirm that it contains project-specific information.

Relevant categories include:

- project purpose;
- architecture;
- implemented features;
- build/release;
- testing;
- packages and SDKs;
- platform integrations;
- persistence/networking;
- AI-agent rules;
- implementation plans and backlog.

Do not claim a file is relevant without checking it.

## Naming

Generate the current local timestamp at snapshot creation:

```text
YYYY-MM-DD-HH-MM
```

Default archive name:

```text
<repository-name>-documents-snapshot-YYYY-MM-DD-HH-MM.zip
```

Keep archive members at zip root. Convert:

```text
Documents/FUTURE.md
```

to:

```text
FUTURE.snapshot-YYYY-MM-DD-HH-MM.md
```

If two source files have same basename, flatten relative paths deterministically:

```text
Packages__com.company.tool__README.snapshot-YYYY-MM-DD-HH-MM.md
```

Never overwrite a collision.

## Snapshot Notice

Prepend every copied Markdown file with:

```markdown
<!--
SNAPSHOT DOCUMENT
Snapshot date: YYYY-MM-DD
Snapshot time: HH-MM
Original source path: path/from/repository/root.md
Archive file name: NAME.snapshot-YYYY-MM-DD-HH-MM.md
Relevance check: Included after confirming that the source contains repository-specific project, architecture, feature, build, test, dependency, platform, implementation-plan, or AI-agent workflow information.
Snapshot warning: This is a dated copy for AI-agent context. The live repository document, project state, dependencies, generated files, and implementation may drift after this snapshot. Check the live source path and current repository before changing behavior.
-->
```

Keep one blank line before original content.

## Safety

- Do not edit live source documents.
- Stage copies outside the repository.
- Do not run build tools, dependency resolution, project generators, or editor tooling.
- Do not include secrets, local reports, ignored files, or transient files.
- Do not commit the archive unless requested.
- Keep live document names free of snapshot suffixes.

## Verification

Verify:

- archive exists;
- requested scope is correct;
- entries are at zip root;
- every member has the timestamped snapshot name;
- every member begins with `SNAPSHOT DOCUMENT`;
- no source document changed due to snapshot generation;
- no secrets or transient files were included;
- collisions were handled;
- single-file requests contain exactly one Markdown member when single-file scope was requested.

Report included count, scope, exclusions, archive path, and source-file status.
