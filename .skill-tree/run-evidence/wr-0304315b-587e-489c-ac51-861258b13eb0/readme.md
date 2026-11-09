# Plugin System Run Evidence

The canonical registry records `WR-0304315b-587e-489c-ac51-861258b13eb0` as completed and locally merged into `codex/next-version`. The immutable run history contains contiguous sequences 1 through 792. Sequence 792 records the terminal checkpoint. [Canonical registry](../../documents/future.json) · [Run events](../../history/run-events/wr-0304315b-587e-489c-ac51-861258b13eb0/) · [Terminal event](../../history/run-events/wr-0304315b-587e-489c-ac51-861258b13eb0/e-5ee62222-0896-40c8-81e7-f616dbf6efb6.json)

The earlier portable envelope in commit `2a6d240bf6f844d339d246bea57a437e9e3eb7fd` stops at sequence 445 with delivery in progress. Git retains that intermediate snapshot under the original path. The terminal event history remains the source for a current portable export.

To regenerate the export, run the export command from the canonical checkout after verifying the Git-local locator and the retained `codex/plugin-system` worktree. The helper writes the envelope under `.skill-tree/run-evidence/` in the recorded run worktree. Keep the full generated envelope local. The [run workspace contract](../../common/references/run-workspaces.md) defines locator recovery and reviewed local-path mappings.

```sh
python3 .skill-tree/common/scripts/workflow-state.py export-run . \
  --run-id WR-0304315b-587e-489c-ac51-861258b13eb0
```
