# Changelog

## 0.4.0 (2026-11-09)

### Added

- `skill-tree-plugins` manages project-scoped external skills from the catalog, URLs and local sources. Configuration previews show the exact installation, update, binding or removal before confirmation.
- Workflows support ordered plugin bindings before, during and after operations. Repeated occurrences retain independent parameters and instructions. Optional integrations cover a Ponytail review pass and post-Processing editorial and interview passes.
- `skill-tree-clarify-tasks` supports resumable interviews, guarded revisions and current confirmation for individual tasks and groups. Auto delegates bounded decisions to agents and records the rationale. Manual sends decision questions to the owner.
- Owned profiles expose the built-in `static-inspection` recipe. Explicit declarations take precedence.

### Changed

- The installer defaults to core skills and offers optional plugin setup in interactive sessions. The catalog groups candidates by workflow integration point and records the evidence and prerequisites for each candidate.
- Local delivery binds the reviewed source and target refs to a verified merge receipt. PR merge consent names the target, and changes to the review scope require current evidence. Legacy consent without a recorded target requires fresh owner authorization.

### Fixed

- Plugin imports resolve Markdown reference links and balanced paths and ignore apparent links inside fenced examples and HTML comments.
- Core refresh and rollback preserve binary plugin resources. Relocation preserves the retained package generation, and plugin transactions protect unrelated staging and backup files.
- Interrupted stale validation attempts can be reconciled after verifying that the original bound local process group has ended. Earlier checks and task history remain available.
