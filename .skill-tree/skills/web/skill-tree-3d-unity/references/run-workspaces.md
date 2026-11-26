# Run Workspaces and Shared Queue

## Identity and compatible setup

A Git controller starts only after explicit `workspace-setup` establishes the canonical queue locator. Schema 2 retains the standalone/single-run checkpoint contract. Explicit setup writes index schema 3 with a schema-1 `run_registry`, a stable queue ID, multiple complete run checkpoints, task claims and exclusive resource claims. Persisted `active_run` remains null when the extension owns runs; the helper projects the explicitly selected run into the existing controller interface. A schema-2 checkpoint without the extension remains readable. An existing checkpoint requires explicit `adopt_run_id`, inspected branch/worktree/base identities and preserved original scope, admission, evidence, counters, stops and budgets. Unsupported/corrupt state requires explicit recovery. No silent conversion, reset or checkpoint deletion occurs.

Machine-local absolute checkout locators reside in the shared Git directory as `skill-tree-runtime.json`; portable metadata stores queue/run/repository IDs, remote identity, base branch/commit, working branch and worktree ID. The locator never enters scoped commits. A missing locator requires `recover-locator` with the exact queue ID and every unfinished retained worktree mapping. Completed delivery mappings can be omitted without changing historical checkpoints; unavailable historical source/evidence remains unavailable. Unknown run IDs and missing unfinished mappings reject recovery. Missing unfinished worktrees or mismatched branches require explicit reconstruction with preserved dirty-work evidence before locator recovery. A reserved run after interrupted creation retains claims and the original run ID; recovery creates the recorded branch/path from the recorded base or inspects an already-created branch rather than starting another run.

## Start and resume

`start --mode next` freezes one selected prioritized root and required dependency closure. `start --mode all` freezes the full initial prioritized snapshot or an explicit `snapshot_ids` group, together with required dependencies. One branch/worktree serves the entire admitted scope, including fixes and review iterations. A new run can coexist with unfinished runs. New standalone Work Through Next and Implement All runs capture the checked-out local launch branch and tip before reserving the run worktree. Pass `--standalone` and the corresponding `implementation_operation` value `work-through-next` or `implement-all` to `start`. The captured local tip includes local commits and excludes working-tree edits. Existing recorded operations and explicitly requested remote delivery retain the recorded base and publication routing. The owner can specify `base_branch`, working `branch`, `branch_prefix` and machine-local `worktree`. The default branch prefix is `codex/`; explicit host/project prefixes override the default. Remote/base access failures and absent `develop` stop before source edits. An explicitly authorized local-only base records `local_base` and the owner rationale; local-only base use supplies no remote/publication authorization.

An installed project reserves an initial profile hold before Git creates the linked checkout. `start` and `advance` return the exact `prepare-worktree-profile` command for a ready worktree with a pending profile. Run the command for the recorded checkout and run ID before beginning source work. The command verifies the canonical generation and installs the owned flavor and operation destinations in the linked checkout. The command verifies an already-installed exact generation during retry. Final admission occurs under the canonical writer after installation releases the installer lock.

A fresh reserved checkout can prepare the original owned profile while a sibling run implements work. The setup writes only the reserved checkout under the existing installer locks. Ordinary installation and refresh continue to require a stopped handoff.

New Web runs place the default checkout beside the canonical project under `.skill-tree-worktrees/<queue-id>/<run-id>`. The queue and run directory names use lowercase IDs. Web reservations retain the exact machine-local destination before Git creation, including an explicitly selected path. An interrupted reservation can recover that destination before or after the active locator is written. A pending local path without the matching canonical run supplies no execution authority.

`environment --run-id <id>` reports the selected Web checkout and any Git storage prerequisite. Runtime preflight requires a checkout outside Git administrative storage. An explicitly retained checkout inside Git storage remains available for static work. Use an approved outside checkout for browser or development-server execution and retain the recorded source and runtime isolation requirements.

The handoff uses the original branch, base, locator and claims. If Git creation stops, recover the recorded workspace before repeating the handoff. An ownership conflict, a different canonical profile, a missing configured plugin generation or an interrupted installation journal keeps the run stopped with the corresponding prerequisite. The initial profile command preserves product bridge files, project inputs and local credentials.

`runs` and `index` expose the registry without selecting an implementation. Resume commands accept `--run-id`; calls from a recorded worktree can resolve the unique matching run. Ambiguous canonical-checkout commands require an explicit run. Resume verifies the actual worktree, branch, repository, remote and unfinished Git operations. Dirty owned work remains progress to inspect and checkpoint; dirty publication preflight stops until scoped changes are committed safely. Different identities never trigger a silent restart.

Controller helpers called from any bound worktree route queue/index/history mutations through the canonical owner and writer lock. Branch copies of `future.md` and `future.json` supply no queue authority. Source fingerprints, recipes and runtime paths resolve the selected execution worktree, while task selection and terminal records resolve the canonical queue. A stale queue-copy edit never becomes an independent task source.

## Concurrency and publication

The canonical exclusive writer lock and recoverable hash-guarded transaction journal serialize task/progress/checkpoint/outcome mutations. Every run atomically reserves the unfinished admitted task closure. Conflicting claims reject the entire operation; a shared completed dependency uses the immutable completion outcome. A consumer verifies completed dependency integration before implementation and completion. A new Core controller records required predecessors from live definitions and exact accepted completion outcomes. Recorded predecessors and validation group members stay within the original authority of a retained controller. Modern completion receipts require current check keys, definitions and evidence alongside source fingerprints. Legacy source-only outcomes use exact available source fingerprints. A changed prerequisite requires accepted current verification and complete recorded-source coverage before the consumer advances. Missing coverage remains an explicit source review prerequisite. Required descendants discovered through processing acquire claims before save. The helper rejects overlapping implementation without a separately specified cooperative protocol; no cooperative mode is enabled implicitly. A cycle, missing dependency evidence or conflicting dependency claim stops the affected run while preserving other runs.

`resource` acquires an exclusive stable resource key with a run/token receipt. Release requires the owning run and token after actual cleanup. Persistent resource claims never expire merely because a helper process exits; PID/host data supports inspection and explicit recovery. Keys cover mutable shared services, ports, Editors, fixtures, profile maintenance and publication resources. Shared env/credentials are read only inside existing authorization and never copied automatically. Resource names identify the actual shared resource, rather than the worktree label.

Publication/merge locks reside in the shared Git directory and serialize conflicting remote/target operations across worktrees. After acquiring the lock, re-fetch the target and re-read provider state. Foreign merges invalidate stale base review/checks. Worktree isolation alone never establishes independent runtime isolation.

## Environment profiles

Read the selected flavor profile before dependency setup or runtime launch. Preserve pinned runtime/tool/dependency versions and use reproducible declared installation recipes. Missing secrets, env files, credentials or local settings become concrete prerequisites. Never copy or commit secrets, infer production configuration or print credential contents. Generated files, caches, outputs, logs and artifacts remain worktree-specific unless concurrent sharing has verified support. Inspect absolute paths in tools/MCP settings; address the exact checkout. Record process ownership, ports, deadlines and cleanup. New worktrees grant no upgrades, production service access, player builds, devices, save resets, paid models or cloud operations.

General profiles identify repository-specific dependency, env, generated-directory and runtime-resource requirements. Web profiles isolate dependency/output directories, server ports, browser storage/data and worker lifecycles. Unity profiles preserve exact Editor/package pins, independent `Library`, `Temp` and `Logs`, exact project path, owned Editor/process, save/service isolation and fixture identity. A single-Editor MCP/service uses an exclusive resource claim or verified supported isolation. Parallel Git worktrees never authorize competing Editors or shared save state.

## Scoped evidence and commits

Canonical mutations produce immutable per-run semantic events under `.skill-tree/history/run-events/`. Each event contains exact before/after task definitions, append-only completion outcomes, before/after checkpoint records and only the selected run's task-progress/check-attempt deltas. `export-run --run-id` creates a portable `.skill-tree/run-evidence/<run-id>/events.json` envelope in the source worktree for an authorized scoped commit. The envelope carries the queue/run IDs and operation history. Machine paths become logical run/canonical roots or opaque local-path references. Transport settings retained in adopted checkpoints become opaque local-value references rather than published machine configuration. Replay of an execution receipt with an external path requires an explicitly reviewed local mapping; unavailable runtime evidence remains unavailable until recovery and revalidation. Include task-owned implementation and referenced portable validation artifacts; omit machine-local locators, secrets and unrelated canonical updates. Refresh export after final checkpoint/completion. The envelope supplements canonical state and never replaces the canonical queue.

`replay-events --input <envelope>` uses semantic compare-and-swap under the canonical lock. Replayed event IDs deduplicate application; matching after-state also deduplicates a lost response. Conflicting task, validation-progress or checkpoint changes stop atomically. Unrelated tasks and outcomes remain intact. A reviewer integrates the event envelope with the canonical owner; ordinary copying of queue/checkpoint files between branches is unsupported. Identical terminal evidence remains immutable. Unavailable worktree artifacts are reported honestly rather than treated as fresh evidence.

## Completion and handoff

`finish` preserves implementation acceptance and the run checkpoint. For runs with recorded `reviewed_local_delivery`, use `controller-review` with the exact run ID after all scoped task commits pass. Review the whole committed diff against the returned base, using the returned identity and the exact controller decision-frame scope. Resolve findings, make scoped fix commits, revalidate affected checks and review the new head. Pass the current clean controller decision frame ID as `review_id` to `finish`.

Implement All merges locally into the exact recorded launch branch after current full-run review. Work Through Next retains a review-ready branch by default. To merge at launch, record `delivery_authorization` with `pr: false`, `merge: true` and the explicit owner instruction. To merge after review, run `merge-reviewed` with the exact run ID and `owner_instruction`. The local merge uses the recorded launch checkout and exact reviewed head. Moved refs or overlapping local edits preserve the reviewed branch and block integration. Runs without `reviewed_local_delivery` use the recorded finish route. Explicit remote orders continue through the PR review cycle. A recorded full-path instruction keeps delivery open as implementation completed, then PR/review in progress, PR ready or merged. Publication blockers preserve implementation completion. Resume reconciles existing PRs, operation keys and merged status before another write. Never announce the full order complete while a promised PR or merge remains unfulfilled.

## Current-target integration

For an explicitly authorized local integration after the target advances, use `current-target-prepare` with the exact run ID, current target head and integration owner. The original reviewed result remains available. A separate integration worktree records the current target as the first parent and the original reviewed source as the second parent. Resolve only identified generated outputs by regenerating the combined source. An authored conflict holds delivery with the exact paths.

Use `current-target-seal` for the exact attempt. The seal regenerates the declared owned package files from the combined source. Use `current-target-checks` to execute the affected supported Core recipes and inspect the receipts. Obtain an independent review of the sealed tree on the current target. Use `current-target-merge` with the exact attempt, integration owner and review receipt. The local ref guard verifies the prepared target before updating the branch. An already confirmed update returns the original result on exact retry.

Use the exact `review_reference` for each executed check in the independent review. A rerun produces a new execution identity and requires current review evidence.

## Partial completion of Implement All

From the canonical checkout, run `workflow-state.py partial-finish-preview <root> --run-id WR-<uuid>` after the exact Core Implement All run stops. The preview binds the queue, recorded checkout, accepted outcome events and commits, remaining task order, unfinished progress, in-flight checks, and owned resource claims. Reconcile original checks, hooks, workers and leases before applying the preview. Preserve unaccepted work in the original checkout.

Run `partial-finish` with the same run ID and a JSON input containing `expected_preview_sha256` and `owner_instruction`. Supply `preserve_unaccepted: true` when the preview identifies an unaccepted commit, dirty path or unfinished progress to preserve. An exact retry returns the original receipt. A different preview or an unresolved attempt preserves the stopped run.

Partial completion retires the live Git locator under the exact owner-bound transaction journal and archives the original checkpoint and progress. The original accepted outcomes, Git branch and worktree remain available. The terminal receipt frees the remaining task claims without changing queue entries. Ordinary resume, new resource acquisition and portable replay cannot reactivate archived runs. A pending profile refresh is preserved in the archived checkpoint and does not require executing the stopped scope.

### Optional reviewed local delivery

Use `partial-delivery-preview` with the archived run ID and an exact `target_branch`. The optional `target_worktree` selects the linked checkout for the authorized target. If the current target already contains the accepted range, the preview reports verified ancestry. Explicit delivery recording requires `owner_instruction` and `expected_preview_sha256`; the already-integrated route writes an observation without a new Git merge.

For new delivery, supply an exact clean `candidate_worktree`. The candidate must contain the sealed accepted tip and current target. A divergent target requires the ordinary conflict-free integration tree with exact target and accepted parents. Review fixes remain scoped to the accepted diff. Execute `partial-delivery-checks` with the same target, candidate, owner instruction and preview SHA. The command runs the original supported local recipes and stores candidate-bound check references. Missing executables, unsupported runtime lanes, failed checks and target drift remain delivery blockers.

Review the complete final candidate with the returned `identity`, `review_scope` and `required_checks`. Cite the exact execution references in the current clean review. Apply `partial-delivery` with the same preview and the current `review_id`. The protected local merge reconciles exact lost acknowledgements and preserves unrelated target content. A delivery block leaves the historical partial result and the released task scope intact.

## Post-merge worktree cleanup

Verified local and controller-linked provider delivery evaluate cleanup after saving the merge result. New controller provisioning records a creation token in the linked Git administrative directory and the run checkpoint. Cleanup requires the matching token, run locator, source branch and head, and current target reachability. Existing or recovered worktrees without qualifying creation evidence are retained.

Cleanup retains check and acceptance artifacts verified at the source commit. Historical queries expose the matching `git_commit` for artifacts after cleanup. Git references and canonical outcome and run records remain available.

The controller records the original cleanup attempt, moves the checkout to a private temporary Git worktree path, and rechecks the delivery target, identity and untracked, ignored and tracked content. A clean checkout is removed with ordinary Git worktree removal. A failed safety check restores the original location when available. A conflicting original location preserves the staged worktree for inspection in `git worktree list`.

The delivery record exposes `worktree_cleanup` with `removed` or `deferred` status and a reason for deferral. A prepared attempt remains recoverable after interruption. From the canonical checkout, run `workflow-state.py cleanup-worktree <canonical-root> --run-id WR-<uuid>` to reconcile or retry the exact attempt.

A verified move keeps the native Git administrative registration, original controller marker and branch. Use `recover-workspace` for the exact run with the current moved directory and a recovery reference. Core retains the original owned location digest and the verified move before activating the locator. Retry an interrupted activation with the same moved directory. After a generic locator replacement, supply the exact previously verified directory as `previous_worktree` with the same moved directory to verify the relocation before cleanup.

A prior external removal can be acknowledged through `cleanup-worktree` with `--run-id` and an input object containing `external_removal.worktree` and `external_removal.reference`. Core verifies actual worktree and administrative absence, the delivered source and target, and committed evidence. The receipt records `removal: "external"` alongside the original cleanup scope. Exact retries return the retained receipt.

```sh
python3 scripts/workflow-state.py workspace-setup <canonical-root> --input <setup.json>
python3 scripts/workflow-state.py start <launch-worktree> --standalone --mode next --id T-<uuid> --input <workspace.json>
python3 scripts/workflow-state.py start <launch-worktree> --standalone --mode all --input <workspace.json>
python3 scripts/workflow-state.py advance <worktree> --run-id WR-<uuid>
python3 scripts/workflow-state.py export-run <worktree> --run-id WR-<uuid>
```

Setup JSON is empty for a new registry. Adoption JSON specifies `adopt_run_id`, `base_branch`, `branch`, `worktree` and any explicit local-base rationale. Start JSON supports `remote`, `base_branch`, `branch`, `branch_prefix`, `worktree`, `limits` and `delivery_authorization`. Use `implementation_operation` with `work-through-next` for mode next and `implement-all` for mode all in the standalone commands above. Optional `snapshot_ids` selects a nonempty unique list of exact prioritized `T-` roots for mode all. Omission selects the full initial prioritized queue. Selected roots retain queue priority and document tie order; required dependencies join admission without adding unrelated roots. Invalid, duplicate, blocked or non-prioritized selections fail before claims or workspace creation. Mode next rejects `snapshot_ids`. Resume preserves every recorded ID, scope, counter, budget and stop condition. Fixture qualification covers local Git and controlled providers; live Git hosting and actual runtime isolation require matching evidence.

For an owner request such as “Implement All for these two tasks”, `workspace.json` supplies the selected identities:

```json
{
  "implementation_operation": "implement-all",
  "expected_source_hash": "<inspected canonical future.md SHA-256>",
  "snapshot_ids": [
    "T-11111111-1111-4111-8111-111111111111",
    "T-22222222-2222-4222-8222-222222222222"
  ]
}
```

Replace the example identities with existing Ready task IDs and supply the SHA-256 of the inspected canonical queue. Run the mode-all command from the worktree on the branch selected to receive the reviewed merge. Later queue additions remain outside the frozen snapshot unless scoped processing admits required descendants. A root group supplies execution scope; `validation_group_id` supplies validation batching and never selects extra roots.
