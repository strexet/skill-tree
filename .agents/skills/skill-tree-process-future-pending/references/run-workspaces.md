# Run Workspaces and Shared Queue

## Identity and compatible setup

A Git controller starts only after explicit `workspace-setup` establishes the canonical queue locator. Schema 2 retains the standalone/single-run checkpoint contract. Explicit setup writes index schema 3 with a schema-1 `run_registry`, a stable queue ID, multiple complete run checkpoints, task claims and exclusive resource claims. Persisted `active_run` remains null when the extension owns runs; the helper projects the explicitly selected run into the existing controller interface. A schema-2 checkpoint without the extension remains readable. An existing checkpoint requires explicit `adopt_run_id`, inspected branch/worktree/base identities and preserved original scope, admission, evidence, counters, stops and budgets. Unsupported/corrupt state requires explicit recovery. No silent conversion, reset or checkpoint deletion occurs.

Machine-local absolute checkout locators reside in the shared Git directory as `skill-tree-runtime.json`; portable metadata stores queue/run/repository IDs, remote identity, base branch/commit, working branch and worktree ID. The locator never enters scoped commits. A missing locator requires `recover-locator` with the exact queue ID and every unfinished retained worktree mapping. Completed delivery mappings can be omitted without changing historical checkpoints; unavailable historical source/evidence remains unavailable. Unknown run IDs and missing unfinished mappings reject recovery. Missing unfinished worktrees or mismatched branches require explicit reconstruction with preserved dirty-work evidence before locator recovery. A reserved run after interrupted creation retains claims and the original run ID; recovery creates the recorded branch/path from the recorded base or inspects an already-created branch rather than starting another run.

## Start and resume

`start --mode next` freezes one selected prioritized root and required dependency closure. `start --mode all` freezes the full initial prioritized snapshot or an explicit `snapshot_ids` group, together with required dependencies. One branch/worktree serves the entire admitted scope, including fixes and review iterations. A new run can coexist with unfinished runs; the new run defaults to the current remote `develop`, never the old run branch or dirty changes. The owner can specify `base_branch`, working `branch`, `branch_prefix` and machine-local `worktree`. The default branch prefix is `codex/`; explicit host/project prefixes override the default. Remote/base access failures and absent `develop` stop before source edits. An explicitly authorized local-only base records `local_base` and the owner rationale; local-only base use supplies no remote/publication authorization.

`runs` and `index` expose the registry without selecting an implementation. Resume commands accept `--run-id`; calls from a recorded worktree can resolve the unique matching run. Ambiguous canonical-checkout commands require an explicit run. Resume verifies the actual worktree, branch, repository, remote and unfinished Git operations. Dirty owned work remains progress to inspect and checkpoint; dirty publication preflight stops until scoped changes are committed safely. Different identities never trigger a silent restart.

Controller helpers called from any bound worktree route queue/index/history mutations through the canonical owner and writer lock. Branch copies of `future.md` and `future.json` supply no queue authority. Source fingerprints, recipes and runtime paths resolve the selected execution worktree, while task selection and terminal records resolve the canonical queue. A stale queue-copy edit never becomes an independent task source.

## Concurrency and publication

The canonical exclusive writer lock and recoverable hash-guarded transaction journal serialize task/progress/checkpoint/outcome mutations. Every run atomically reserves the unfinished admitted task closure. Conflicting claims reject the entire operation; a shared completed dependency uses the immutable completion outcome. A consumer verifies completed dependency integration before implementation. Exact original source fingerprints retain the direct integration path. Changed sources require accepted current revalidation of the immutable completed contract, complete recorded-source coverage and available matching evidence. The controller selects required completed-contract validation before the consumer; missing source coverage remains an explicit review prerequisite. Required descendants discovered through processing acquire claims before save. The helper rejects overlapping implementation without a separately specified cooperative protocol; no cooperative mode is enabled implicitly. A cycle, missing dependency evidence or conflicting dependency claim stops the affected run while preserving other runs.

`resource` acquires an exclusive stable resource key with a run/token receipt. Release requires the owning run and token after actual cleanup. Persistent resource claims never expire merely because a helper process exits; PID/host data supports inspection and explicit recovery. Keys cover mutable shared services, ports, Editors, fixtures, profile maintenance and publication resources. Shared env/credentials are read only inside existing authorization and never copied automatically. Resource names identify the actual shared resource, rather than the worktree label.

Publication/merge locks reside in the shared Git directory and serialize conflicting remote/target operations across worktrees. After acquiring the lock, re-fetch the target and re-read provider state. Foreign merges invalidate stale base review/checks. Worktree isolation alone never establishes independent runtime isolation.

## Environment profiles

Read the selected flavor profile before dependency setup or runtime launch. Preserve pinned runtime/tool/dependency versions and use reproducible declared installation recipes. Missing secrets, env files, credentials or local settings become concrete prerequisites. Never copy or commit secrets, infer production configuration or print credential contents. Generated files, caches, outputs, logs and artifacts remain worktree-specific unless concurrent sharing has verified support. Inspect absolute paths in tools/MCP settings; address the exact checkout. Record process ownership, ports, deadlines and cleanup. New worktrees grant no upgrades, production service access, player builds, devices, save resets, paid models or cloud operations.

General profiles identify repository-specific dependency, env, generated-directory and runtime-resource requirements. Web profiles isolate dependency/output directories, server ports, browser storage/data and worker lifecycles. Unity profiles preserve exact Editor/package pins, independent `Library`, `Temp` and `Logs`, exact project path, owned Editor/process, save/service isolation and fixture identity. A single-Editor MCP/service uses an exclusive resource claim or verified supported isolation. Parallel Git worktrees never authorize competing Editors or shared save state.

## Scoped evidence and commits

Canonical mutations produce immutable per-run semantic events under `.skill-tree/history/run-events/`. Each event contains exact before/after task definitions, append-only completion outcomes, before/after checkpoint records and only the selected run's task-progress/check-attempt deltas. `export-run --run-id` creates a portable `.skill-tree/run-evidence/<run-id>/events.json` envelope in the source worktree for an authorized scoped commit. The envelope carries the queue/run IDs and operation history. Machine paths become logical run/canonical roots or opaque local-path references. Transport settings retained in adopted checkpoints become opaque local-value references rather than published machine configuration. Replay of an execution receipt with an external path requires an explicitly reviewed local mapping; unavailable runtime evidence remains unavailable until recovery and revalidation. Include task-owned implementation and referenced portable validation artifacts; omit machine-local locators, secrets and unrelated canonical updates. Refresh export after final checkpoint/completion. The envelope supplements canonical state and never replaces the canonical queue.

`replay-events --input <envelope>` uses semantic compare-and-swap under the canonical lock. Replayed event IDs deduplicate application; matching after-state also deduplicates a lost response. Conflicting task, validation-progress or checkpoint changes stop atomically. Unrelated tasks and outcomes remain intact. A reviewer integrates the event envelope with the canonical owner; ordinary copying of queue/checkpoint files between branches is unsupported. Identical terminal evidence remains immutable. Unavailable worktree artifacts are reported honestly rather than treated as fresh evidence.

## Completion and handoff

`finish` preserves implementation acceptance and the run checkpoint. With no publication instruction, delivery ends as `local-result` and offers local result, PR review/fix, or PR review/fix with merge into an explicit target. An offer grants no permission. A recorded full-path instruction keeps delivery open as implementation completed, then PR/review in progress, PR ready or merged. Publication blockers preserve implementation completion. Resume reconciles existing PRs, operation keys and merged status before another write. Never announce the full order complete while a promised PR or merge remains unfulfilled.

```sh
python3 scripts/workflow-state.py workspace-setup <canonical-root> --input <setup.json>
python3 scripts/workflow-state.py start <canonical-root> --mode next --id T-<uuid> --input <workspace.json>
python3 scripts/workflow-state.py start <canonical-root> --mode all --input <workspace.json>
python3 scripts/workflow-state.py advance <worktree> --run-id WR-<uuid>
python3 scripts/workflow-state.py export-run <worktree> --run-id WR-<uuid>
```

Setup JSON is empty for a new registry. Adoption JSON specifies `adopt_run_id`, `base_branch`, `branch`, `worktree` and any explicit local-base rationale. Start JSON supports `remote`, `base_branch`, `branch`, `branch_prefix`, `worktree`, `limits` and `delivery_authorization`. Optional `snapshot_ids` selects a nonempty unique list of exact prioritized `T-` roots for mode all. Omission selects the full initial prioritized queue. Selected roots retain queue priority and document tie order; required dependencies join admission without adding unrelated roots. Invalid, duplicate, blocked or non-prioritized selections fail before claims or workspace creation. Mode next rejects `snapshot_ids`. Resume preserves every recorded ID, scope, counter, budget and stop condition. Fixture qualification covers local Git and controlled providers; live Git hosting and actual runtime isolation require matching evidence.

For an owner request such as “Implement All for these two tasks”, `workspace.json` supplies the selected identities:

```json
{
  "base_branch": "develop",
  "snapshot_ids": [
    "T-11111111-1111-4111-8111-111111111111",
    "T-22222222-2222-4222-8222-222222222222"
  ]
}
```

Replace the example identities with existing Ready task IDs, then use the mode-all start command. Later queue additions remain outside the frozen snapshot unless scoped processing admits required descendants. A root group supplies execution scope; `validation_group_id` supplies validation batching and never selects extra roots.
