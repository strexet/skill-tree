---
name: skill-tree-unity-create-documents-snapshot
description: "Create an explicitly requested Markdown documentation snapshot archive without editing live documents. Use for Unity repositories."
license: MIT
---

# Skill-Tree-Unity: Create Snapshot

Read repository rules and [snapshot scope](references/snapshot-rules.md). Inspect candidate relevance, then run scripts/create-documentation-snapshot.py <repository> --dry-run. Create the requested archive only after scope is understood. Preserve live sources, exclude private/generated/vendor content and verify member names/notices. Return archive path and scope; commit only under explicit authorization.

Read [Unity safety](references/unity-safety.md). Inspect relevant serialized state, pinned versions and lifecycle. Separate static, Editor, Play Mode/UI, player and device evidence; authorization remains scoped.

Generated prose follows [document rules](references/document-rules.md). No unrelated changes, implicit permission or source/sibling dependency.
