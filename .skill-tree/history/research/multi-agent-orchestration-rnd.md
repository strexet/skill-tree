# Multi-agent orchestration research

## Research scope and recommendation

**Research date** 2026-11-24. **Source baseline** local `develop` at `02afcd2c`. The current-state findings come from source inspection and retained evidence. The candidate design and proposed checks precede the completed sandbox results and qualification gaps.

Start with two concurrent implementation attempts in separate worktrees. Reuse the Core queue and delivery gates. Classify Ready tasks using declared writes, relevant consumers and shared resources. Give Director and project coordinators the same durable dispatch, wait and recovery protocol. Test a local SQLite store for that protocol and integrate candidates one at a time against the current target. Measure time to checked integration of the whole batch.

## Current behavior

| Area | Confirmed behavior and consequence |
| --- | --- |
| Director dispatch | A run freezes an exact assignment set, plan digest and allowed effects. `run-status` derives eligibility from dependencies, questions, resource conflicts and recorded effects. `run-dispatch` performs one authorized intake, process or Core start. Core start reserves a run and worktree. The skill directs the coordinator to an independent host worker where available. Worker launch and supervision depend on the host. [Run implementation](../../common/scripts/director-run.py#L117), [Director Run skill](../../skills/director/skill-tree-director-run/SKILL.md#L17) |
| Director scope and impact | Plan preview checks declared paths and the dependency graph, including unordered write overlaps within one canonical queue. Director also checks named resource conflicts. `plan-impact` follows known source pins to declared downstream consumers. Coverage depends on the quality of the declarations. Director checks `Touch` and check sources when promoting a directed task. An existing Ready task is bound by ID and body digest. The scoped brief gives the worker a contract. [Plan compiler](../../common/scripts/director-plans.py#L118), [Dispatch scope](../../common/scripts/director-run.py#L272), [Director workflow](../../documents/director-workflow.md#objectives-plans-and-source-pins) |
| Core execution | `Work Through Next` selects a root and the root's dependency closure. `Implement All` freezes a snapshot in one worktree and selects one next unit. Multiple separate runs can coexist. Admission checks task IDs and unfinished dependencies. Different task IDs can still target the same files. Auto decision and review actors have separate roles from implementation workers. [Core selection and claims](../../common/scripts/workflow-state.py#L1122), [Implement All](../../../.agents/skills/skill-tree-implement-all/SKILL.md#L15), [Workspace tests](../../tests/test-run-workspaces.py#L76) |
| Shared state and recovery | Linked worktrees share the canonical `future.md`, `future.json`, outcomes and run events. Core serializes writes through a lock and a recoverable journal. Separate repositories retain separate queues. Director keeps separate objective, plan, run and dispatch records, linked to exact child receipts. Workers get scoped briefs, source pins and committed Git context. The audited path has no common worker lease or liveness model across delegation levels. [Core state](../../common/references/run-workspaces.md#concurrency-and-publication), [Director effects and receipts](../../documents/director-workflow.md#effects-and-decisions) |
| Resources and delivery | Source worktrees isolate Git edits. Runtime access has separate named claims. Core records scoped commits and reviews the full run diff. The local reviewed merge requires the recorded target tip. After A merges, a run B started at the same base stops even when the two diffs are disjoint. PR delivery rechecks current base, review and checks under the publication gate. Director verifies child results and cross-project handoffs. [Workspace and delivery rules](../../common/references/run-workspaces.md#completion-and-handoff), [Moved-target regression](../../tests/test-local-delivery.py#L385), [PR review](../../common/references/pr-review-cycle.md#ready-and-merge-boundaries) |

Retained Codex evidence records a worker returning a structured question, then an independent sibling reaching intake during the hold. The topology test preserves the original child run, worktree and partial edits after the answer. The available evidence covers independent progression and recovery. Concurrent implementation, nested worker failure, two checked integrations into one target and throughput remain unmeasured. [Codex observation](../validation/director/codex-host-result.json#L10), [Topology test](../../tests/test-director-topologies.py#L330)

## Candidate design

### Ready task scope and scheduling

Derive a scheduling record at Ready or first preview from the current task body and repository configuration. Start with the existing `Touch` section and validation sources. Add explicit fields only where the pilot demonstrates a gap.

| Signal | Minimum record | Admission use |
| --- | --- | --- |
| Identity and validity | Canonical queue and repository IDs, task ID and body digest, target ref, observed base SHA, scope revision | Reject stale proposals after a relevant task, source or policy revision changes. Identify linked worktrees and folder areas as the same source owner. |
| Expected writes | Repo-relative files or directory prefixes, including relevant generated outputs and rename boundaries | Detect file and ancestor/descendant overlap. Resolve path aliases using repository and filesystem semantics. Require fresh classification when writes expand. |
| Important reads and effects | Consumed pins and checks, plus named contracts where source evidence supports the declaration, such as an API, schema, serialized asset or shared package | Detect write/read conflicts and clean Git merges that break consumers. Distinguish ordinary check coverage from a dependency that must be integrated first. |
| Execution resources | Stable keys for the actual Editor, service, port, fixture or other exclusive resource, with required phase | Reserve implementation resources before editing when both tasks share writes. Acquire scarce validation resources at the validation phase when source preparation is independent. |
| Confidence and evidence | Confirmed, inferred or unknown, with the source of each material assumption | Make the reason visible in preview. Refresh uncertain scope through bounded inspection. Keep ambiguous broad writes out of automatic parallel dispatch. |

Classify each pair or active claim with both a reason and a next action.

- **Hard conflict.** An unresolved dependency, duplicate task, active exclusive resource for the same phase, or conflicting change to a high-impact contract orders or blocks the affected work.
- **Possible overlap.** Broad prefixes, edits to the same text file, related consumers or uncertain scope prompt focused inspection or an explicit risk decision. If the fixture shows that selected same-file edits routinely combine safely, allow that class to run with separate worktrees and a combined check.
- **Independent on recorded evidence.** Different write sets, compatible reads, satisfied dependencies and available resources make a task eligible. A scope prediction is an admission estimate. Review the actual diff, including deletions, renames and generated files, before acceptance.

First choose from the eligible dependency frontier using existing priorities and a stable tie-break. A bounded greedy pass fills spare slots with compatible tasks. Preserve priority across retries and surface prolonged deferrals. Consider critical-path ordering only if traces show that priority order consistently delays integration. Use one canonical task claim for each unfinished shared dependency. Park the consuming tasks and recheck source integration when the dependency completes.

On scope growth, keep partial edits in the worker worktree, publish the proposed new scope and re-run admission against active peers. Reclassify, order or hand off the conflicting work before either result is accepted. Keep task ownership with the coordinating Core run. Reserve per-task sibling runs for separable units with independent checks.

### Dispatch and waits at every level

Use the same protocol for Director, a project coordinator and any worker granted delegation authority. Each delegation carries a parent ID, exact task/assignment and expected result, authority, writable scope, base or pinned input, budget, deadline and workspace identity. A child mandate is bounded by the parent mandate. Track parentage separately from prerequisite edges. Reject cycles, including a parent waiting for a child that requires the parent's terminal result. A parent may hand off an intermediate artifact using an explicit dependency and check.

1. **Reserve and launch.** Atomically reserve the eligible unit, worker slot and required claims for the next phase. Record an operation key and attempt generation before calling Core or the host. Capture the Core run and host actor IDs. Require host capability evidence for launch, status, result delivery and cancellation at each intended depth. If direct nested spawning is unavailable, let a worker submit a bounded child request to a capable ancestor. Persist the same logical parent and mandate.
2. **Wait by dependency.** A coordinator continues eligible sibling work until a specific result, resource or decision becomes necessary, or the worker limit is reached. Persist a wait reason, awaited IDs and next deadline. Prefer host completion events and a bounded wait until the nearest deadline. Re-read durable state after a wake or reconnect. If events are unavailable, use the host's bounded wait or an operator-triggered reconciliation. Any recurring pull would require a separate demonstrated freshness need and ownership decision.
3. **Join on evidence.** An agent message proposes a result. The coordinator verifies the current attempt, scope, commit or artifact, required checks and applicable Core receipt. A parent completes after the required child results and integration checks are accepted. Optional work follows the recorded delivery scope. Active coordinator capacity is distinct from implementation slots, so a waiting parent leaves capacity for a required child.
4. **Supervise independently.** A supervisor above the worker tree can inspect every attempt, including an unresponsive project coordinator. Record latest host or tool activity and latest meaningful progress separately. Track `waiting_for_child`, `waiting_for_owner`, `waiting_for_resource` and an active tool with a tool-specific deadline explicitly. A process heartbeat indicates life. A lack of milestone progress or an exceeded tool deadline can warrant investigation even while heartbeats continue.
5. **Recover an uncertain attempt.** Treat an expired lease, missed heartbeat or missing result as a signal to inspect the host, checkout, receipts and running tools. Distinguish confirmed exit, slow work, intentional wait and unknown execution. Reconcile an already-applied effect before retry. Confirm stop and resource cleanup before reusing exclusive assets. If stop remains uncertain, quarantine the checkout, hold destructive or shared-resource effects, and use a separate checkout only when isolation and authority permit. Fence state updates and acceptance by attempt generation so late results cannot replace newer work. Reuse accepted partial work through explicit review.

The lease governs who may advance the orchestration record. Existing Core or runtime claims continue to govern resource ownership, and Git or Core operations require exact operation-specific preconditions. A worker with filesystem access can still write to the allocated checkout after losing a lease. Fencing and cleanup decisions must account for that distinction.

### Shared durable state

**First candidate** is one local SQLite database per orchestration workspace, shared by all participating workers through a scoped API or helper on the same host. All nesting levels use the same transaction rules and state view. A local service is optional if direct helper access meets privilege, concurrency and lifecycle requirements. Use a separate connection per process or thread, short transactions, a bounded busy policy and no Git, model, network or tool calls inside a transaction. Test a supported SQLite runtime with the documented WAL-reset fix before enabling WAL. WAL supports concurrent readers and a single writer on the same host. [SQLite isolation](https://sqlite.org/isolation.html) · [SQLite WAL and fixed versions](https://sqlite.org/wal.html)

| Records | Ownership and required data |
| --- | --- |
| Work items and edges | Project, assignment, task and revision, logical parent, prerequisite and requiredness, effective authority, scope, admission inputs and desired delivery |
| Attempts and claims | Generation, owner, lease, host actor, Core run, workspace and pinned refs, phase, heartbeat, progress, deadline, wait reason and resource ownership |
| Effects and events | Unique operation key, intent, external identity, observed receipt, state revision and append-only transition evidence |
| Results and waits | Accepted attempt, checks and artifact references, dependency readiness, outstanding decision, integration target and verified commit |

Use an atomic claim transaction and revision checks for competing coordinators. Require the current generation to renew, accept or release an attempt. Store Core and Git references with enough evidence to reconcile after a restart. Record the external intent before the call and observe the exact effect afterward. A database transaction covers only database state. A crash between an external effect and receipt publication can require reconciliation or an operator decision. Test duplicate and out-of-order delivery.

Keep task definitions, canonical task acceptance and current Core outcomes with the existing project queue in the pilot. The shared store owns orchestration state and references the Core receipts. Avoid simultaneous authoritative copies of the same phase or claim. A coordinating run must respect pre-existing Core claims. An orchestration database cannot acquire an existing Core resource solely by copying the claim into SQL. Use staged intent and verified Core acquisition, with compensation when a new acquisition fails.

Consider PostgreSQL behind a coordinator service if workers must run on multiple machines or local contention exceeds the pilot budget after tuning. Compare PostgreSQL row-level claiming and event wakeups against local SQLite in that case. Treat `LISTEN/NOTIFY` as a wake signal and read durable state after connecting and reconnecting. Verify backup and restore, schema revision, scoped access and redaction of worker briefs and local secrets before broader use. [PostgreSQL SELECT locking](https://www.postgresql.org/docs/18/sql-select.html) · [PostgreSQL LISTEN](https://www.postgresql.org/docs/18/sql-listen.html)

### Integration after parallel implementation

Let each implementation worker seal a scoped result at the worker branch head. Assign one integration owner per repository and target. Review and merge the smallest eligible unit in dependency order. When a previous merge advances the target, recompute the candidate against that exact head in isolation and preserve the original attempt and evidence. An optional Git `merge-tree --write-tree` preflight can report textual, rename and path conflicts without changing the index or worktree. Use a disposable repository or known object-store location for the preflight. Combined product checks still cover semantic conflicts. [Git merge-tree](https://git-scm.com/docs/git-merge-tree)

If the candidate combines cleanly, run impacted consumer checks and any required target review on the combined revision. Integrate under the existing target lock and an expected-ref guard. If the target moves again, hold and recompute. If a conflict or behavioral regression appears, return the exact conflicting paths or failed consumer assertion to the responsible worker. Admit the result to a cross-project consumer only after the required producer revision is available and the consumer check fingerprints the actual input.

## Hypotheses, checks and conditional decisions

| Hypothesis | Check | Decision if supported | Decision if unsupported |
| --- | --- | --- | --- |
| H1. Existing `Touch`, dependencies and named resources predict most safe pairs at low cost | Compare path-only, path plus impacts, and coordinator judgement blind to the outcome. Label pairs using actual diffs, resource traces and combined checks. Include same-file safe edits, hidden semantic conflicts and missing scope. | Start with derived records. Require only the extra declarations that catch observed misses. | Add targeted contract or generated-output fields and make unknowns preview-only. If broad scope dominates, improve Ready task decomposition before adding automatic planning. |
| H2. Two workers shorten time to checked integration | Compare serial, operator-planned parallel and scope-planned parallel runs at fixed worker capacity and identical checks. Include stale-base review, conflict repair and host latency. | Enable bounded parallelism for classes that meet the time and safety criteria. | Keep tasks serial in the affected class. Tune task size, merge timing or validation grouping only where recorded wait and rework time identify a cause. |
| H3. A shared protocol allows safe nested dispatch and waiting | Compare direct spawning with ancestor-brokered requests using the same hierarchy. Simulate a full worker pool, parent death, delayed child result and owner hold. | Use the host path that supplies lifecycle evidence and preserves logical parentage. Allow a deeper pilot only after end-to-end checks. | Keep delegation at the supported depth or use supervised handoff. Fix starvation, missing lifecycle observations or capability gaps before autonomous retries. |
| H4. Lease plus progress evidence supports reliable recovery | Inject confirmed exits, a live worker stuck in a tool, quiet healthy work, duplicate events, unknown effects and late results at several depths. | Adopt observed state-specific deadlines and a single recovery owner. Allow automatic retry only for rehearsed, fenced cases. | Retain suspect status and operator reconciliation. Improve host observability or deadline calibration before changing retry policy. |
| H5. A local transactional store is sufficient for project and Director coordination | Stress concurrent claim, renew, dependency completion, effect replay, restart and restore. Test both the expected and doubled burst with actual write timing. | Keep SQLite local and keep Core receipts authoritative for Core effects. | Separate store contention, event delivery and host topology as causes. Shorten transactions first. Qualify a PostgreSQL-backed service if multi-host use or measured local limits remain decisive. |
| H6. Integration on the current target avoids most repeated merge work | Start peers from one base. Compare existing guarded holds, per-result combined checks and batching ready results into a candidate. Force both Git and semantic conflicts. | Prefer a serial, current-target integration owner. Batch compatible results only if checked delivery improves and failures remain attributable. | Keep the existing guarded route. Improve scope prediction, dependency ordering or the affected check set before automating base updates. |

### Measurement and decision rules

- Measure elapsed time from admission to the last required **verified integration**, worker and coordinator time, useful concurrent time, wait by cause, merge intervention time, rerun cost, and time to detect and recover a stuck attempt. Report worker budget and verification coverage with the comparison.
- Record a confusion matrix for scope selection. A false admission is a pair the planner ran together that causes a Git conflict, shared-resource collision, undeclared scope expansion requiring coordination, or failed combined check caused by interaction. Record each cause separately. A false hold is an ordered pair whose reconciled changes, resources and evidence support parallel execution. Record also how often the planner abstains.
- Proposed pilot gate: zero duplicate accepted outcomes, stale-attempt acceptance, unauthorized writes or releases, missed required checks and data loss in the deterministic controls. Detect every injected stuck attempt within the configured detection deadline plus one supervisor wake budget. Legitimate waits and a healthy long tool must survive. A case without an observable ground truth remains inconclusive.
- Proposed expansion gate: at least 20% lower median time to checked integration for the independent fixture versus serial, with no extra human merge intervention in that fixture. Measure at least five paired trials per arm and publish the range and individual traces. Treat the result as pilot evidence. Evaluate the conflict-heavy fixture separately and retain a serial policy where no gain appears.
- Proposed local store gate: zero double claims or unreconciled committed effects with eight concurrent simulated clients and a second run at sixteen. Cap p95 durable claim and state transition latency at 100 ms on the selected pilot host, including bounded retries under the measured fixture load. Record contention, transaction length, event lag and checkpoint duration. Freeze the host, thresholds and experiment inputs before measuring.

## End-to-end pilot

### Topology and task queues

Use a disposable Director workspace with three real Git repositories and one additional registered folder area sharing the Game queue. Seed exact Ready tasks, Prioritized dependencies, an unresolved owner decision and a Pending discovery item. Replace fixture labels below with the corresponding actual task IDs. Run the existing supported workflows against installed profiles in the baseline arm. Exercise a second Game worktree to verify that queue writes route to the same canonical owner.

| Queue and task | Expected writes and other impact | Dependency or resource |
| --- | --- | --- |
| Rules `R1` defines carry attachment | `spec/carry.json`, published carry contract | Waits for owner choice between two valid requirements |
| Rules `R2` fixes unrelated terminology | `docs/controls.md` | Independent of `R1` and eligible during the owner hold |
| Art `A1` exports a lantern | `art/lantern.fbx`, `art/lantern.meta` | Approved proxy input allows preliminary work, final check requires accepted `R1` |
| Art `A2` exports an icon | `art/ui/lantern-icon.png` | Independent source edits. Uses the same exporter fixture as `A1` during validation only |
| Game `G1` implements carry and delegates required `G1a` | `game/carry/controller.cs`, reads exact `R1` and final `A1` | `G1a` updates `game/import/lantern.asset` and requires final `A1`. Both product checks use the single Editor |
| Game `G2` fixes score formatting | `game/score/formatter.cs` | Independent static check. Shares a starting target with `G3` in the first independent arm |
| Game UI `G3` adjusts HUD layout | `ui/hud/layout.uxml`, same canonical Game queue | Independent baseline. In the semantic control, G3's check consumes the output of the formatter even though the written paths differ |
| Game `G4` repairs carry input binding | `game/carry/controller.cs` and `game/input/bindings.asset` | Conflicts with `G1`. Mark the required order or verify a planner hold |
| Game `G5` and `G6` use shared prerequisite `G0` | Distinct files under `game/tutorial/` and `game/telemetry/` | `G0` writes a shared test fixture. Both workers require one accepted and integrated result |

Place a newly discovered Pending required task under `G1a` in one run. Submit the exact task through scoped processing and re-admission. Use a nonblocking Pending follow-up as a negative control. In a separate fixture variant, give two tasks isolated edits to different sections of one plain text file and compare conservative admission with the reviewed soft-overlap route. Use deterministic tool test doubles before adding one actual Unity or exporter run. Qualify a real Editor only if runtime isolation is part of the selected pilot.

### Runs and fault injections

1. Freeze expected cases, task revisions, Git bases, environment, owner answers and verification recipes. Retain a golden final tree or explicit expected files and consumer assertions. Compare serial scheduling per project, explicit parallel Core runs, and the proposed scope-aware planner. Keep the cross-project objective and checks identical. Use deterministic workers for repeatability, then repeat at least one matched case with independent host workers to observe actual dispatch and wait behavior.
2. Start `R1`, observe the owner hold, and verify `R2`, `G2` and independent art work advance. Have the project coordinator delegate `G1a` when eligible. Fill worker slots, park the parent waiting for `G1a`, and verify the child still obtains capacity. Check that cyclic and unauthorized requests fail admission.
3. Force concurrent proposals for `G0` from `G5` and `G6`. Verify one execution and exact reuse after integration. Attempt overlapping work on `G1` and `G4`. Run both art edits, then prove validation is serialized on the exporter fixture. Repeat the Editor control through different worktrees. Simulate scope growth from an independent task into a busy directory and verify re-admission.
4. At each of Director-to-project, project-to-worker and nested-worker boundaries, interrupt after intent, after host launch before acknowledgement, and after commit before result delivery. Kill a project coordinator while descendants are active. Inject a live stall, quiet healthy tool, owner wait, duplicate acknowledgement and old-generation completion. Rebuild the state view from the store, Core receipts and Git. Check original worktree preservation, one accepted outcome, cleanup and child resumption or quarantine.
5. Complete `G2` and `G3` from the same base. Merge the first and show the existing stale-target hold for the second. Integrate through the candidate route and assert both changes and current checks. In the semantic variant, introduce an incompatible formatter output and verify that a clean Git combination fails the HUD consumer check. Run `G4` as a same-path textual-conflict control. Verify that a later change to the pinned `R1` input holds only the recorded dependent checks and leaves an unaffected control current.
6. Report per-arm timings and traces keyed by task, run, attempt, resource and target head. Record worker spawn failures, terminal outcomes, unresolved cases, duplicate or late message handling and scope-prediction misses. Separate synthetic orchestration results from native host capacity and product-runtime qualification.

## Pilot results

**Execution date** 2026-11-24. **Baseline** `develop` at `02afcd2c`. The disposable sandbox contains archived Skill Tree source, three synthetic product repositories, per-arm Git worktrees and SQLite state. The experiment used macOS arm64, Apple Git 2.54.0 and SQLite 3.54.1 through Python 3.14.4. The benchmark measures synthetic subprocess workers with fixed edit and validation delays. The native host pilot below covers Codex actor behavior. Real Unity or exporter runtimes, live PR delivery and production throughput remain unqualified.

### Sequential and parallel delivery

Five paired repetitions used the same 12-task graph, three initial product trees, owner response at 5 seconds, worker work and check recipes. The arm order rotated between repetitions. The two parallel arms allowed two workers. The operator arm used a fixed compatibility list. The scope arm selected compatible tasks from the eligible frontier. The reported elapsed time includes worker dispatch, owner wait, actual Git integration, combined checks and final tree verification. Repository initialization precedes the timer. A diagnostic batch exposed a timing-dependent starting base for the Game pair. The scored batch starts the Game pair first so a shared starting base is deliberate in both parallel arms. The diagnostic timings are excluded.

| Arm | Elapsed seconds for five trials | Median | Range | Reduction vs serial | Stale-base holds | Checked integrations |
| --- | --- | --- | --- | --- | --- | --- |
| Serial | 15.00, 14.77, 15.02, 14.78, 14.71 | 14.78 s | 14.71–15.02 s | Baseline | 0 | 60/60 |
| Operator-planned parallel | 11.85, 11.94, 12.02, 11.98, 11.73 | 11.94 s | 11.73–12.02 s | 19.2% | 10 | 60/60 |
| Scope-planned parallel | 11.34, 11.51, 11.62, 11.57, 15.54 | 11.57 s | 11.34–15.54 s | 21.8% | 10 | 60/60 |

The serial implementation and the two parallel arms used the same synthetic scheduler and integration verifier. Separate native controls exercised actual Core `Implement All` delivery and Director flows. The benchmark tests a candidate coordination policy with real Git operations. The native host pilot below measures Codex dispatch and editing against the same fixture.

The independent Game pair `G2` and `G3` reached two checked merges in a median of **2.70 s serial**, **1.75 s operator parallel** and **1.77 s scope parallel**, measured from trial admission. The parallel arms started the pair on the same base. The stock Core guard rejected every moved-base probe. The sandbox integration owner kept the original source commit, built a candidate on the current target, checked exact merge parents, actual writes and combined behavior, then advanced the target under the local publication lock and rechecked the target. Revalidation of moved-base candidates took **269 ms median** across both parallel arms, including candidate preparation and target update.

One scope-planned trial took 15.54 seconds, slower than the serial range. The trace records a 1.45-second G0 integration and a 1.30-second moved-base G6 integration. The trial remains in the comparison. Sandbox controls also ran on the same host during the benchmark. The measurements establish synthetic median improvement and leave the source of tail variability unresolved.

Every arm reached the same verified final content in all three repositories. Each trial recorded twelve unique integration receipts and zero human merge interventions. `R2` integrated during the `R1` owner wait in every trial. The Game consumers `G5` and `G6` both used the single integrated `G0` result. The timed fixture exercised cross-repository input checks and a shared Game queue identity for the HUD area. The timed fixture uses deterministic resource checks. Contested resource admission was checked separately.

### Scope, hang and state controls

| Control | Observation |
| --- | --- |
| File scope and consumer effect | The path-only rule admitted a formatter change and a HUD change with disjoint paths. Git combined both cleanly and the HUD check rejected the incompatible formatter output. An explicit read/write claim on the score contract caught the pair before launch. A worker branch with an undeclared extra path failed the diff acceptance gate in the fixture. |
| Same-file edits | Two separated hunks combined and both were verified. Two conflicting edits to the same line returned a Git merge conflict before integration. Path overlap works as an inspection signal for text files. |
| Hung workers | At logical depths 1, 2 and 3, real subprocesses stopped making progress while heartbeat updates continued. The supervisor detected the stall in **352–359 ms** using a 350 ms deadline and a 120 ms wake budget. After stopping each process and releasing the claim, recovery used a fresh attempt, retained the original checkpoint and rejected a late result from the previous generation. Detection to checked recovery took **137–195 ms**. A healthy quiet process completed in **447 ms** within a longer tool-specific deadline. |
| Coordinator exit and delegated waits | A supervisor observed and stopped a live descendant after a coordinator exited. Separate POSIX direct and ancestor-brokered controls each completed the required child and parent with one implementation slot. The waiting parent released the slot before the child claimed the slot. The brokered child retained the logical parent identity. The three hang-depth controls use logical depth labels. The delegation controls exercise actual process nesting. |
| Lost merge acknowledgement | A subprocess advanced the target and exited before writing a receipt. Restart reconciliation matched the prepared target and source parents and verified the actual result. The fixture recorded one merge and one accepted receipt across replay. |
| SQLite contention | Under 8 and 16 simultaneous clients, 60 contended units per run each produced one claim and one accepted receipt. P95 latency across timed claims, renewals and acceptances was **22.64 ms** and **41.38 ms**, below the 100 ms pilot threshold. The highest observed transition time was 152.66 ms in the 16-client run. Wrong-token release, duplicate acceptance and contradictory replay were rejected. Backup restore preserved all receipts and passed the integrity check. One simulated Editor claim was held at a time. |

### Native Skill Tree controls

Seventeen existing tests passed against the archived `develop` source. The installed Director topology fixture exercised an owner hold, independent sibling intake, original worktree preservation and resumption. Other controls covered exact child dispatch recovery, overlapping task and resource claims, a shared dependency's required source integration, nested required subtasks, deferred follow-up, cycle rejection, local reviewed merge and the moved-target guard. Some delivery fixtures replace the review verifier with a deterministic test double. The tests qualify the observed workflow and Git gates on fixture inputs. [Director topology](../../tests/test-director-topologies.py#L330) · [Run workspaces](../../tests/test-run-workspaces.py#L76) · [Local delivery](../../tests/test-local-delivery.py#L343) · [Required subtasks](../../tests/test-workflow-state.py#L492)

A separate native fixture materialized all twelve Ready labels as exact Core task IDs in three canonical Future queues. The Game and HUD tasks share one queue. Two separate stock Core runs started G2 and G3 on the same base. A second consumer run was rejected while G0 was claimed by the first consumer, and an Editor claim held by one worktree blocked the other. The G2 run completed and merged via the stock reviewed delivery path. The G3 run retained the accepted source and stopped at the moved-target guard. The exact-pair control used a deterministic review verifier and genuine source commits and target updates.

### Decisions supported by the pilot

| Hypothesis | Evidence and next decision |
| --- | --- |
| H1. Scope prediction | Keep declared paths as the cheap first filter. Preserve named consumers and resources where source evidence identifies the relevant contracts. Treat same-file overlap as reviewable. The case controls establish failure modes and useful signals. A labeled sample of real Ready tasks is still needed to estimate false-admission and false-hold rates. |
| H2. Time to checked merge | The scope arm met the 20% elapsed-time gate. The operator arm fell below the gate. Measure the same pair on a representative project with real agents and checks before extending the policy. |
| H3. Nested dispatch | The shared wait protocol and ancestor-brokered fallback both work for local processes. Qualify spawn, event delivery and cancellation on the actual agent host before enabling nested agent dispatch. |
| H4. Recovery | The synthetic deadline, process-exit check and generation guard passed. Retain explicit reconciliation for unknown host state and require real lifecycle evidence before automatic retry on a product run. |
| H5. Transactional state | SQLite WAL passed the local 8- and 16-client fixture with no double claim. Keep SQLite as the local prototype candidate. A host runtime, sustained load and storage boundary still require qualification before using the store as an authority. |
| H6. Current-target integration | The checked candidate path recovered the moved-base cases without human Git intervention. Adopt current-target preview as the next integration experiment. Keep combined checks mandatory because the semantic control produced a clean Git merge and a failed consumer check. |

Sandbox evidence includes \`benchmark.json\`, the fifteen per-trial \`result.json\` event traces, \`controls.json\`, \`hierarchy.json\`, \`native-queues.json\` and the native test logs. The benchmark sets task durations and the owner delay by design. Native results, three canonical test queues, synthetic throughput and synthetic recovery are separate evidence.

## Native Codex host pilot

**Report date** 2026-11-25. **Baseline** `develop` at `02afcd2c`. The pilot reused the existing sandbox, three product repositories per trial, twelve-task fixture graph, exact write scopes and final content oracle. Two native Codex collaboration actors, `/root/worker` and `/root/project`, authored the actual fixture edits. The sandbox driver assigned worktrees and used the previous Git and consumer checks to seal commits, validate the current target and integrate each result. The driver added no simulated implementation delay. Repository initialization was outside the timer.

### Time to checked integration

Five matched pairs alternated arm order. The serial actor alternated by pair. The parallel arm used both actors, with G2 and G3 reserved on a common base and an eligible frontier for subsequent work. Elapsed time starts before the first reservation and native followup dispatch and ends after the last checked target update and final tree verification. The workload has known small JSON edits and deterministic checks, including the same simulated owner decision and resource constraints. All trial times include native turn and tool latency.

| Pair | Whole workload serial | Whole workload parallel | Relative change | G2 and G3 serial | G2 and G3 parallel |
| --- | --- | --- | --- | --- | --- |
| 1 | 67.85 s | 39.76 s | 41.4% less elapsed time | 31.96 s | 22.20 s |
| 2 | 116.36 s | 43.25 s | 62.8% less elapsed time | 24.16 s | 17.44 s |
| 3 | 53.79 s | 40.20 s | 25.3% less elapsed time | 16.82 s | 18.30 s |
| 4 | 120.03 s | 53.78 s | 55.2% less elapsed time | 25.42 s | 29.04 s |
| 5 | 52.29 s | 55.98 s | 7.1% more elapsed time | 14.46 s | 22.58 s |

Median time for the twelve checked integrations was **67.85 s serial** and **43.25 s parallel** (36.3% less elapsed time). The independent Game pair reached two checked merges in **24.16 s serial** and **22.20 s parallel** (8.1% less elapsed time). The measurements include recovery from **18 moved-base holds** across the parallel trials. The stock guard reported the changed target, then the sandbox driver built and verified a new candidate. All 120 integrations reached the expected tracked paths and parsed JSON values. Non-JSON files matched the synthetic fixture byte for byte. The only byte variation was JSON key order in `game/import/lantern.json` in 7 trials. The measured workloads had no human merge repair.

Parallel delivery was faster in 4 of five matched full workloads and in 2 of five matched G2/G3 slices. The median paired G2/G3 change was **8.8% more elapsed time**. The ratio of the two arm medians and the median of the within-pair changes answer different questions. The paired outcomes favor fan-out for the full fixture and give no repeatable gain for the two short edits.

Dispatcher timestamps showed **2/5** parallel trials with overlapping G2 and G3 edit intervals, measured from task pickup to submission. Host dispatch skew can remove the overlap even when both branches start from the same base. Other independent tasks overlapped across the two agents in **5/5** parallel trials. The per-trial event traces preserve actor, base, input acceptance and integration timestamps. The timelines measure assigned work in flight. Concurrent model inference remains unobserved.

An initial driver SQL ambiguity failed before any edits and was excluded from the comparison. An overnight session interruption left the original fourth serial arm at six verified integrations and a clean G1a worktree. The original fourth pair was set aside, and both timing arms were repeated from fresh repositories. The restarted first serial trial includes one immediate retry after a relative helper path failed. One actor reconstructed a tool helper before the first edit in the replacement parallel arm. The replacement arm includes the reconstruction time. A separate driver smoke check qualified the local submission path outside the timed arms. The timing results cover one host, reused actor contexts and the synthetic workload. Real Unity validation and product-repository merge throughput require separate evidence.

### Nested launch, waiting and recovery

A real project coordinator, `/root/project`, used the host collaboration interface to spawn `/root/project/leaf`. The coordinator observed the child running, waited for the healthy result and accepted the result from the recorded generation. The coordinator then dispatched a separate fault attempt to the same nested actor and supervised the intentionally blocked local tool.

| Checkpoint | Native observation |
| --- | --- |
| Detect while heartbeat remains current | The progress deadline was **12 s**. The coordinator classified the attempt as stuck **12.053 s** after the durable progress checkpoint. The latest heartbeat was **49.8 ms** old. |
| Interrupt and inspect the tool | The native interrupt returned previous state `running`, and the next host observation showed `interrupted`. The exact owned tool process was still alive. Detection to the recorded interrupt observation took **11.42 s**, including coordinator and tool latency. |
| Confirm cleanup before retry | The coordinator signalled the exact sandbox fixture through a cooperative stop file and verified process exit. The interval from post-interrupt process inspection to reconciled exit was **114 ms**. The coordinator advanced the attempt generation only after reconciling the stop. |
| Wait for the replacement result | The coordinator sent a native followup to the same nested actor under generation 2 and waited for completion. Detection to accepted replacement took **35.57 s**. The generation 2 result was accepted once, an injected generation 1 replay was rejected, and a duplicate generation 2 result was idempotent. The original progress checkpoint remained available. |

The nested fault was run separately from the timing arms to keep the serial and parallel workloads comparable. The harness exercises host state and a durable generation check. Product-runtime cleanup, deep recursion beyond the tested nesting and autonomous recovery with incomplete host evidence remain open.

### Design decisions from the native pilot

- Maintain separate facts for host actor state, owned process state and accepted task generation. The tool process stayed live after the host reported interruption. Keep resource ownership until exact cleanup is verified, then admit the replacement generation.
- Use recorded progress and phase deadlines alongside heartbeat. Route timeouts to the project coordinator or an ancestor with host lifecycle access. Retain the original checkpoint and reconcile the prior attempt before any retry.
- Prefer two-worker dispatch for independent, worthwhile units and include host startup skew in the decision. Keep the current-target integration check and the consumer oracle. The native fixture also passed the planned 20% full-workload timing gate. Keep the two short Game tasks eligible for serial execution and test a representative project workload before enabling default fan-out.
- The sandbox evidence bundle contains `native-agents-result.json`, per-trial `result.json` traces, sandbox Git repositories and refs, plus `nested/results.json` and the exact local-process reconciliation evidence. The fixture driver and worker control remain outside Skill Tree source.

## Two Ready tasks in Skill Tree

The next pilot used `T-868fb252-cb68-4dfd-b297-49ebbd91dd78` and `T-d476ee52-b10d-4679-87a9-ab3fabdb754e`. The exact Ready preview identified independent authored paths and nine common generated binding manifests. Both arms started from `7e3096f8a30fb84518a2c27b39176a3205f4430b`. The arms used separate disposable repositories with identical starting queues, two Codex actors and an integration owner who regenerated the shared outputs from the combined authored changes. The actor assignments were swapped between arms. Timing began at first reservation and ended when the integrated commit and tree were verified on the disposable target branch.

| Measure | Serial | Parallel |
| --- | ---: | ---: |
| Time to verified local merge | 977.01 s | 1825.69 s |
| Worker overlap | 0.00 s | 501.65 s |
| Combined verification | 237.17 s | 462.95 s |
| Authored Git conflicts | 0 | 0 |

The parallel arm took 86.9% longer than the serial arm. Reviewers rejected the first parallel candidate after finding a legacy installation regression and a guided Director path that missed the new storage exclusions. Both fixes required new checks. A late submission from the first generation was rejected and the handoff ledger stayed unchanged. The serial arm included 24.3 s for recovery from a checkout-local navigation collision. Both final candidates passed the scoped suites, package synchronization, strict repository validation and independent review. The checked targets were `7ba1bee7960c108eea69dcb31da76bc6d6a355e1` and `446176fd1b5c9e792e9101369e1972083ad7c658` respectively.

The paired results show no authored merge conflicts and substantial delivery time from verification and rework. Elapsed time includes the observed host, tool and reviewer delays. The sample contains one pair with warm actor contexts. Run traces, acceptance receipts and measurement are in `skill-tree-worker-handoff.Ax2JXg` under the local temporary directory.

## Supervised Director and Core pilot

The paired arms used the installed Director and Core entry points on one host. The Game and Story fixtures each had an exact Ready task, one writable tracked path and an executable source assertion. A Game coordinator dispatched a required native Codex subagent. The Story actor worked in a separate repository. Director persisted scoped worker receipts against exact launches. Core accepted both scoped commits and reused the matching executable evidence for the full controller review. Game used the checked current-target merge after an independent target advance. Story used the ordinary reviewed local merge. The executable check passed again on both final targets in each arm.

| Measure | Serial | Parallel |
| --- | ---: | ---: |
| First Director dispatch through verification of both local merges | 1007.463 s | 431.654 s |
| First worker reservation through verification of both local merges | 689.831 s | 267.254 s |
| Native implementation overlap, pickup to verified handoff | 0.000 s | 3.674 s |
| Native Game worker interval | 33.174 s | 11.513 s |
| Native Story worker interval | 22.352 s | 12.199 s |
| Verified local merges | 2 | 2 |

The serial Game target was `cea3cf442db93458cc676956c1e38b0a4bcd793d`. The serial Story target was `77356d13a04b693a9114f451120b899f27738dfc`. The parallel Game target was `27cecf7e1c07084a1813c0e92ca2dd4e6aa5480b`. The parallel Story target was `17282519e13af0dc48451f63da52ff4a03eb4e7e`.

The project implementations overlapped for less than four seconds. The larger elapsed difference includes concurrent Core admission and review steps, reused actor contexts and different observed host latency. The serial dispatch-to-merge interval also includes a test installation refresh after an installed topology control exposed a shared-queue writer-lock bug. Serial overlapped a separate repository test suite on the same host. The first-reservation interval excludes the installation refresh and includes the actual downstream waits. The paired arms provide observed timing on small disposable tasks. The separate stall control keeps the injected fault outside the timing comparison.

### Native stall and recovery control

The first fault setup used a 32 s pickup deadline. The parent missed the initial reservation window, and Director declined pickup. The driver stopped the unbound fixture process. A fresh disposable run used a 55 s progress deadline and a 14 s heartbeat deadline. A Game parent spawned a native child, recorded the nested wait and kept a heartbeat. The child produced one scoped commit and check artifact, then deliberately stopped progressing. Director classified the child as stalled about 55 s after verified progress, with a current heartbeat.

The durable stall event was recorded 57.956 s after progress. The recorded heartbeat was 4.182 s old. The host interrupt reported the original child running and the subsequent host status showed an interruption. The bound local process group survived the interrupt. Director refused recovery while the group was still live. Independent Story submitted one passing scoped result 14.828 s after the stall while Game remained stalled. The coordinator signalled only the owned fixture process and verified group exit before recovery. Director rejected a late submission of the original valid Game candidate after reserving the replacement, with the original attempt unchanged.

The first replacement committed the scoped edit but exceeded the heartbeat deadline after progress writes collided with parent heartbeat writes. The trace contains seven writer-lock refusals and two revision-conflict refusals for progress on generation 2. Director accepted no generation 2 result. After exact shutdown verification, the next supervisor used a seven-second heartbeat interval. Director verified the third Game worker generation 5.988 s after pickup and 315.316 s after the original stall. The result and passing check identify the new worktree and verified process-group exit.

The third Game worker result exposed a separate supervisor closeout defect. Verification of the awaited child removed the wait exemption, exposing the expired supervisor progress deadline. The coordinator recovered the supervisor and completed a new supervisor attempt against the existing checked child receipt. The repair treats a verified nested receipt as meaningful supervisor progress and preserves the independent heartbeat deadline. The installed topology regression exercises closeout after the previous deadline and compares the current parent heartbeat with the original heartbeat receipt. The native timing arms and fault control ran before the closeout repair. The local test evidence covers the repair separately.

## Improvement sequence after the pilot

1. **Scope preview first.** If H1 passes, expose a read-only independence preview for an exact Ready selection, reusing Core and Director identity and dependency checks. Keep classification reasons visible. Add fields only for observed misses. If H1 fails, focus on collecting reliable scope evidence and decomposition.
2. **Shared protocol and recovery next.** If H3 through H5 pass, add a local state adapter and one supervised dispatch/wait protocol at both Director and project boundaries. Begin with two implementation slots and a tested nesting depth. If direct spawning fails capability checks, qualify brokered dispatch first. If state or recovery fails, keep explicit runs and resolve the measured gap before widening automation.
3. **Current-target integration.** If H6 passes, adopt a per-target integration owner with current-base revalidation and exact-ref protection. Keep automation inside recorded delivery authority. If H6 fails, preserve the existing merge gates and introduce narrower targeted integration experiments based on the observed blocker.
4. **Selective expansion.** Use H2 to approve parallel scheduling by workload class. Expand the tested depth, worker budget or host topology independently. A good scope classifier can still justify preview when checked-delivery throughput remains flat. Move to a shared server-backed store only when topology or measured contention warrants the added operation cost.
