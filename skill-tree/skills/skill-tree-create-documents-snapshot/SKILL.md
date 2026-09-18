---
name: skill-tree-create-documents-snapshot
description: "Create an explicitly requested Markdown documentation snapshot archive without editing live documents."
license: MIT
---

# Skill-Tree: Create Snapshot

Read repository rules and [snapshot scope](references/snapshot-rules.md). Inspect candidate relevance, then run scripts/create-documentation-snapshot.py <repository> --dry-run. Create the requested archive only after scope is understood. Preserve live sources, exclude private/generated/vendor content and verify member names/notices. Return archive path and scope; commit only under explicit authorization.

Generated prose follows [document rules](references/document-rules.md). No unrelated changes, implicit permission or source/sibling dependency.
