---
name: skill-tree-create-documents-snapshot
description: Create explicit-request-only Markdown documentation snapshot archives for Unity repositories without modifying live source documents. Use when asked to create a documentation snapshot, documents snapshot, Markdown snapshot, .md snapshot archive, or AI-context docs archive. Do not use during normal documentation initialization, documentation audit, feature implementation, Process pending, or Implement next.
license: MIT
---

# Skill-Tree: Create Snapshot

Use this skill only when the user explicitly asks for a documentation, Markdown, `.md`, or AI-context document snapshot archive.

Do not create snapshots during normal code edits, documentation initialization, documentation audit, pending processing, or task implementation.

## Required Workflow

1. Confirm repository root and worktree state.
2. Read `references/SNAPSHOT_RULES.md`.
3. Determine requested scope: default repository docs, a specific Markdown file, or an explicit document set.
4. Inspect candidate Markdown files enough to confirm repository-specific relevance.
5. Exclude vendor docs, package cache, generated API docs, build output, ignored files, transient reports, secrets, and local-only files unless the user explicitly requests a safe subset.
6. Create staged copies outside the repository, prepend snapshot notices, and archive them at zip root.
7. Do not edit live source documents.
8. Do not open Unity, run package resolution, or cause asset reserialization.
9. Verify archive existence, member names, snapshot notices, requested scope, collision handling, and source-file preservation.
10. Report archive path, included count, included files, exclusions, checks run, and checks not run.

Run the helper by path relative to this skill directory:

```bash
python3 scripts/create_documentation_snapshot.py /path/to/unity-repo --dry-run
python3 scripts/create_documentation_snapshot.py /path/to/unity-repo
python3 scripts/create_documentation_snapshot.py /path/to/unity-repo --output /path/to/archive.zip
```

## Boundaries

- Do not create or update `Documents/DOCUMENTS_SNAPSHOT.md`.
- Do not add snapshot files to live repository docs.
- Do not commit the archive unless explicitly requested.
- Do not include secrets or real user data.
- Do not claim the snapshot is current after creation time.

## Completion

Complete only when the archive is created or the dry-run plan is reported, live source documents are unchanged, and remaining exclusions or risks are explicit.
