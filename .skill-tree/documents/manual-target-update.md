# Manual Target Update

The existing target repository requires an explicit owner-selected update after source qualification. Explicit run-registry setup/adoption supports schema-2 checkpoints and writes schema 3 while preserving task progress and complete run records. No automatic migration, legacy path alias or general format converter exists.

1. Inspect status, owned Skill Tree files/packages, repository rules, queue, checkpoint and history. Stop the controller and preserve a reviewable backup.
2. Move the owned directory to `.skill-tree/` and update root pointers, commands and narrow ignore entries while preserving unrelated content.
3. Review exact superseded packages and marker blocks. Packages without receipts require manual ownership review; `--force` never adopts legacy content. Install the selected project-scoped flavor and verify the receipt and output inventories.
4. Verify the schema-2 structured check contract. Use explicit workspace-setup to create schema 3 for Git controllers; an existing active checkpoint requires exact adopt_run_id and inspected branch/worktree/base identities. Adapt unsupported queue/index/checkpoint formats manually before setup. Preserve task/run IDs, required/deferred scope, outstanding acceptance, stop reasons and next action. Reconcile unsupported state explicitly; never reset progress merely to pass validation.
5. Preserve original history receipts/evidence bytes. Record relocated-reference mapping and honest stale/unavailable evidence in an update note; rebuild derived navigation/index data.
6. Run metadata/package/source checks, review the diff and report the preserved next action. Product execution and controller continuation require applicable owner scope.

The current source release performs no existing-target update, live provider installation or product execution.
