# Director Workflow Contract

Director coordinates related Skill Tree areas from one Codex conversation. The parent workspace owns a project objective, exact cross-area assignments, assignment dependencies and a review record. Narrative owns canon, art owns approved references and models, Unity owns game implementation and tests, and an optional public area owns published material. The source maintenance area owns Skill Tree implementation tasks. Each area retains the applicable Skill Tree queue, authorizations, runtime bindings and acceptance rules.

## Ownership and identity

Version 1 portable metadata has a stable Director ID, area IDs, objective IDs and assignment IDs. Each area records the area role, canonical queue identity, Git identity when applicable, repository-relative scope, declared capabilities, supported interface and allowed effects. A local binding resolves the area identity to current checkout or runtime paths. A moved path requires identity verification and an explicit rebind. An unavailable binding leaves the area visible with binding status and the last accepted evidence.

A shared repository can own several folder areas under one canonical Future queue and writer. Linked worktrees share that queue and Git common directory. A separate repository owns an independent queue even when the checkout path is nested under Director. Configured external paths support the same independent topology. Folder scopes, worktree identities and cloned queue identities participate in duplicate and overlapping writer checks. A portable manifest stores relative scope and stable references. The machine-local binding stores absolute paths and execution locators.

Each child receipt links the Director objective and assignment to exact area, queue, P, T and WR identities as applicable, the operation attempt and the immutable resulting artifact or outcome. The child queue owns child Pending, Prioritized and historical state. Parent objectives retain acceptance criteria and links to child work. A Director ledger records a local state change before a child effect and reconciles the effect through an exact canonical child receipt. Each writer owns a separate transaction independently.

## Use a shared workspace

The dedicated service lives under `.skill-tree/.director`. Use the [shared workspace entry](../common/references/director-workflow.md#shared-workspace-entry) to inspect the registered projects and preview the receiving project before applying an operation. The [installation guide](install.md) describes upgrading a legacy workspace.

An ordinary workspace audit requests a separate documentation audit from each available authorized subproject. The workspace audit report includes verified results and coverage gaps for the registered scope.

## Register areas

For first-time setup, review the coordinator, project placements, package sources and prerequisites through the [guided setup preview](../common/references/director-workflow.md#preview-first-time-setup). Once approved, [prepare the workspace](../common/references/director-workflow.md#prepare-the-approved-workspace) with `setup-bootstrap`. Use the [prepared-area registration and status flow](../common/references/director-workflow.md#register-the-prepared-areas) for the exact prepared set. The explicit area registration commands below remain available.

Use `python3 .skill-tree/common/scripts/director-state.py setup-preview <director-root> --input <request.json>` from the source checkout. The request identifies `director_id` and exact `areas`. Each area supplies a stable `id`, `role`, canonical `checkout` path, relative `scope`, capability tokens, an interface declaration `{"kind":"skill-tree","version":1}` and allowed effects. Optional expected queue and repository IDs restrict a binding to previously reviewed identities. Register one `source-maintenance` area backed by a canonical Skill Tree source. Separate repositories use existing verified Skill Tree profiles and registered Core queue identities. Shared folder scopes use the same canonical owner.

Use `setup-apply` with the reviewed `expected_preview_sha256` and identical area request. The parent stores `.skill-tree/director/registry.json` and local `.skill-tree/artifacts/director/local-bindings.json` through one guarded writer. The selected child checkouts and Core queues receive no writes. Linked checkout input resolves to the canonical queue owner. Duplicate queue writers, an overlapping writable scope, symlinks and stale probes stop application.

Use `rebind-preview` with `director_id`, `area_id` and the exact available canonical checkout. Use `rebind` with the reviewed digest after verifying the same queue and repository identity. A moved checkout can require Core locator recovery first. Rebind updates the local queue binding for all registered areas on the same owner and leaves the portable declaration unchanged.

## Inspect current status

Use `status` with a Director root and an optional JSON request containing exact assignments to inspect. Each entry identifies an assignment and registered area. Entries can supply exact task and run IDs, proposed workspace kind, area-relative write paths and stable exclusive resource keys. An absent local binding remains visible as `unbound`. The status report distinguishes unavailable roots, mismatched queue or repository identity, scoped dirt, overlapping writes and conflicting runtime claims. A child run is visible through the exact registered queue and locator.

Status returns recommendations for serial checkout, artifact directory, registered Git worktree and separate clone or runtime. The ability to isolate source and the availability of runtime claims have distinct checks. Write overlap uses canonical source scope across linked worktrees. A recommendation creates no checkout or claim and grants no launch authority. Status shows available independent work only when current scoped inputs demonstrate disjoint writes and resources. Director coordinates directly from the parent root.

## Objectives, plans and source pins

An objective records a stable identity, revision, digest, owner reference and observable acceptance. A plan freezes the objective revision, exact assignment set, plan revision and digest. Each assignment names the qualified area capability, allowed write paths and resources, existing task IDs or bounded intake scope, source pins, dependencies, expected result, matching check, authority and stop conditions. The worker brief projects the selected assignment and relevant pins. Preview reports missing, inferred and unsupported inputs, required external dependencies and overlap. Cycles and missing required inputs hold execution before mutation.

A source pin identifies the owning area, record or artifact, accepted revision, content SHA-256 and semantic role. An edge names the consuming assignment, check and requirement strength. Required, optional and expressly provisional edges carry distinct acceptance consequences. The carried-lantern fixture pins a cave quest requirement, form, scale, grip, attachment and game checks. A story change from hand to belt revisits only recorded affected links where narrow coverage exists. A whole-document pin uses conservative impact. An authored extinction event requires a matching story pin before entering product scope. A provisional proxy carries preliminary checks and an explicit final replacement gate.

The completed-work index separates owner acceptance, current source, evidence availability, consumer verification, integration and delivery. Status projects recorded objective and child health. Plan projects impacted pins and proposes exact amendments. A changed source opens affected recorded consumers and preserves historical and independent evidence. An approved amendment binds the frozen next revision after affected writers reconcile.

## Route a design or production order

Start intake with the requested result, owner and observable end condition. A short brief or rule revision, mechanics inventory or placement, balance study, and asset-only request each use a scoped owner result. A standalone Game Design, Mechanics or Balance request can use the matching direct operation and end with a project document. A deliverable already inside a Director objective uses a scoped assignment and matching child result. An asset-only request has the agreed producer and applicable preview or import criterion for the stated delivery.

A playable character or location is a production milestone with the following required handoffs.

| Area | Accepted input and check |
| --- | --- |
| Narrative | Pin the work and continuity with the selected character role or location purpose, permitted interactions, relevant routes or scene facts and outstanding questions. Request only the facts the planned interaction consumes. |
| Game Design | Pin the audience, repeated player activity, core mechanics and observable interaction from input to consequence. Record choices still open and any assumptions used in a workshop. |
| 3D | Pin the selected art brief and the gameplay-relevant visibility, scale, attachment or collision requirements, with a matching review. The producer may present the approved handoff manually while the ArtWorkshop adapter is unavailable. |
| Unity | Pin the selected imported artifact and actual rule or setting. Check the observable interaction under the recorded starting state. Record whether a preliminary proxy or the replacement asset supplied the observed behavior. |

Request the missing story facts from Narrative and the missing gameplay question from Game Design before freezing affected production assignments. A separately scoped workshop can start on labeled assumptions and return choices for acceptance. Production freezes exact accepted input, write scope, effect, check and dependencies. After plan approval and exact execution selection, start independent art and preliminary gameplay work in parallel when the recorded resource and write scopes permit. A proxy supports the preliminary criterion only. Milestone review requires the applicable Unity consumer check on the selected imported revision and all required accepted evidence.

Return to the Core queue only when the owner adopts a production change that requires child work. The bounded intake supplies the exact deliverable, accountable area, expected check and selected source pins. The normal authorization to intake, process or start applies to each effect. Keep unresolved comparisons or an author's creative question in the objective and review scope.

## Keep objective and completion records

Use `objective-preview` with the stable objective ID, owner reference, original intent and acceptance criteria. An existing objective requires the current revision digest. `objective-apply` binds the reviewed preview and records the exact next revision. A matching retry returns the original receipt. `objective-read` can select the current objective or a retained revision. The parent workspace owns the objective journal and the existing recovery transaction.

`plan-pin` records the reviewed plan revision, exact objective revision and assignment task references. A revision retains earlier pins. `outcome-link` checks the named child queue, task, original run, terminal outcome and matching check and artifact evidence. Outcome records retain the original child owner and provenance. Availability, source freshness, verified integration and delivery remain separate observations. The child queue supplies evidence and receives no objective journal write.

## Preview and freeze assignments

Use `plan-preview` with exact plan and objective revisions and the selected assignments. The preview validates declared effect scopes, canonical area ownership, current qualified capabilities, exact child task or bounded intake and source pins. The preview returns a digest, portable assignment scope, a scoped worker brief and unverified coverage. A required missing pin, ambiguous area, dependency cycle or unsafe overlap stops preview before any write.

Use `plan-freeze` with the same request and the reviewed `expected_preview_sha256`. The objective journal retains the frozen plan and digest. A repeated exact request preserves one plan version. `plan-context` and `plan-impact` read the frozen revision. Request `plan_context` inside status to include pinned sources and use `plan-impact` to inspect recorded consumers for an exact changed source. Representative fixture artifacts can support fixture planning. Real ArtWorkshop qualification requires verified source and runtime evidence for the selected area.

### Look up project context for one assignment

Pass `assignment_id` with the exact objective ID, plan ID and plan revision to `plan-context`. The returned `context_search.request` carries the frozen plan digest. Add a literal-term `query` and an optional `limit` to that request, then call `context-search` on the Director root. Use project terms or identifiers such as `cave-lantern-carry belt`.

The lookup searches areas owned by the selected assignment and dependency assignments at the recorded Git commits. Each searched area requires a registered read-only effect. A verified Narrative or Art fixture pin with a path permits lookup of the exact file. For a pin queue without an unambiguous frozen commit, the lookup uses the observed local HEAD and checks the file against the recorded SHA-256 before returning context. Each hit supplies the area, repository identity, path, commit, SHA-256 and nearby source lines. Check the per-source status for unavailable material. Narrow the query if Git output exceeds the byte limit. Treat matches as research evidence and use the normal source-pin review to adopt a required input.

For a standalone checkout, run `python3 .skill-tree/common/scripts/context-search.py search <checkout> --commit <full-commit-id> --scope <repository-relative-path> --query '<terms>'` from the Skill Tree source. Git reads locally available objects with protocol access disabled.

## Effects and decisions

Owner design approval accepts a plan revision. Execution selection authorizes specific child effects on that revision. Delivery retains independent authority. Read-only status, plan preview and audit supply no task execution. A current confirmed plan can authorize exact child intake, processing and launch when current profiles, IDs, scope, dependencies and resource claims match. Installation, commit, publication, scheduling and wider rollout require applicable authority. Standalone Process Pending preserves the normal next-action handoff. Child controllers preserve original admission and claims.

Before a child mutation, Director records intent with stable Director, assignment, operation and destination identities, a semantic payload digest and current-state guards. The child effect and receipt share the child transaction. Identical replay recovers original P, T or WR identity. A different payload under the same key conflicts. A lost response requires exact reconciliation, including Git workspace creation when applicable. Incomplete provenance holds the ambiguous effect for review.

Director first resolves child questions using accepted pinned facts, approved defaults and current authority. Material unresolved product choices reach the owner in one question with options, a recommendation, affected areas and the blocked action. Director product decisions start in Manual mode. Scoped Auto requires actual independent actors, bounded authority and current decision evidence. Question and answer receipts bind plan, assignment, child run, recipient, actor, authority and attempt. An expired, late, stale or wrong-context delivery has no effect. An absent or declined answer keeps the decision pending. A waiting run checkpoints and resumes the same worktree once the applicable decision arrives. Independent work can continue within the independent assignment authority. Pause stops new dispatch, cancellation preserves work, and repeated unchanged failures leave one concrete blocker.

## Reconcile a child dispatch

Record the exact parent `dispatch-intent` before invoking an authorized child mutation. The protocol binds the Director and assignment IDs, canonical queue, operation, frozen plan digest and exact semantic request. The queue hash guards a first application and stays outside the semantic retry identity.

Probe `director-dispatch-read` in the selected canonical child checkout before a new effect. The supported `director-dispatch` interface accepts the original typed intake, process or start request and the required selection. A successful child write retains the original receipt in the same canonical transaction. A matching retry recovers the original effect result, while a changed request under the same key fails. An unknown receiver or missing provenance requires review before dispatch. A reserved launch recovers the same matching worktree and run ID through the child workspace contract.

## Run an approved plan and resolve questions

`run-start` selects the exact objective and frozen plan digest, an explicit assignment set that includes required dependencies, current owner evidence and the authorized effect for each selected assignment. New intake uses the frozen assignment. Processing binds a separately reviewed exact task specification and rejects unplanned write paths and checks. `run-dispatch` uses the exact current run and child queue digests. The original canonical receipt reconciles a repeated request. `run-status` reads the Director run, waiting assignments, dependency and resource conflicts, and eligible next effects. `run-pause` stops new dispatch, `run-resume` rechecks the current plan, and `run-cancel` retains child checkpoints, receipts and edits.

`decide-open` records one question for the exact running child task and worktree after verifying child Core support for the hold. A verified approved default delivers the pinned fact. A material question names the addressed owner, distinct options, recommendation, affected areas, blocked action and UTC deadline. The original child checkpoint remains held while independent assignments can advance. `decide-answer` requires the original question, attempt, queue and run with current owner evidence. An accepted answer restores the original child checkpoint. Explicit child continuation uses the existing controller admission. An absent response keeps the hold. Identical delivery can be observed again without a second child effect.

### Run managed Implement All

Use the managed project route to identify the canonical queue and initial prioritized scope. Freeze an approved Director plan with one exact assignment per unfinished required task. Retain the Core dependency edges. Add deterministic sequencing edges for overlapping writes in dependency order, using the prioritized order for ties.

Pass `implement_all` to `run-start` with the inspected `expected_source_hash` and positive `workers` limit. An explicit `snapshot_ids` list restricts the roots. The launch also records the original checked-out target branch and head.

Call `run-advance-all` with the exact Director run ID and current run digest. Execute each returned child in the recorded worktree and record the current reviewed child outcome before integration. Incorporate reviewed results through the existing local delivery commands. Use the checked current-target candidate path for a moved base. Call `run-advance-all` again after accepting and incorporating child results or resolving a recorded hold. After a lost batch response, read `run-status` for the exact recorded assignment. Use `run-dispatch` with that assignment and the original start request to recover the same child run and worktree. Check the existing worker and child progress before handing the recovered checkout to an actor.

The controller schedules unfinished admitted tasks and preserves concrete task and integration holds. A run completes after every assignment has a checked delivery on the original target. Later unrelated tasks require a new invocation.

### Supervise workers on one host

For an explicitly selected disposable pilot, pass `supervision` to `run-start` with the local `host`, `progress_timeout_seconds` and `heartbeat_timeout_seconds`. Start each exact product assignment using `run-dispatch` with an explicit local base. The child is a reviewed Work Through Next run. Separate owner authority governs delivery of the reviewed child result.

Use `run-supervise` with `action: status` to inspect the durable assignments and attempts. The coordinator can reserve two writing slots and one supervising parent. Reservations bind the recorded child launch, actor, generation, worktree, base, write scope, resources and prerequisites. Independent admitted work can continue while a parent waits for the nested result. Use the current run digest and a unique request ID for each mutation. Retain the original request and request ID when reconciling a lost response.

Record pickup with the live local process group, then record heartbeat, meaningful progress or the reason for waiting. Use `sweep` to evaluate deadlines. A current heartbeat still permits a no-progress stall. Before replacing a bound attempt, record the exact host stop observation and verify that the bound process group has exited. For a pickup timeout before binding, the host adapter first fences the dispatch so the old actor cannot start, then supplies a `host-stopped-unbound` observation with the exact host, actor, evidence reference, and observed `process_groups`. An empty list requires positive host evidence that the actor started no process groups. The runtime checks that every reported group has exited. Keep the reservation if the host adapter cannot establish either condition. After recovery the worker can be reassigned with the next generation. The ledger retains each prior attempt and related evidence.

For an actual exclusive tool call, acquire the normal Core resource token. Submit after the owned group exits. `submit` verifies the linked worktree, exact Git commit, allowed paths and check artifact. The project coordinator incorporates the scoped result and runs the required Core checks and review. Record Director assignment completion against the exact child outcome. For checked delivery, retain proof of the target ref and passing target checks.

## Review cross-area handoffs

Use `python3 .skill-tree/common/scripts/director-handoff.py review-preview <director-root> --input <request.json>` from the source checkout. Select the exact frozen objective and plan digest and provide each edge with producer and consumer assignments, the source pin, the accepted producer artifact ID and the repository-relative path observed by the consumer check. The outcome links name exact child task, run, outcome and receipt evidence. The consumer check must fingerprint the accepted producer bytes.

Review reports producer acceptance, consumer evidence, integration and delivery separately. Missing or stale required coverage holds objective acceptance. A provisional artifact supports only the recorded preliminary check and keeps the final artifact gate open. `review-apply` archives the reviewed result with the original identities and receipt. `review-read` retrieves the immutable archive.

`impact-preview` compares consecutive frozen revisions of the same plan and reports affected and independent assignments. `amend-apply` verifies the preview digest and reconciles affected writers before applying the approved amendment. Affected prior evidence becomes superseded in current review. Unchanged assignments can reuse matching evidence across the accepted amendment. Original archives retain historical proof.

Run status identifies the accepted amendment, both plan revisions and the withheld action for each affected assignment. Fresh intake, processing and launch require the current run digest and current eligibility under the Director writer lock. Prepared and invoking effects hold amendments that affect the active assignment, including assignments inherited from an earlier revision. A current supersession denial records one event for the same request. A stale fresh request leaves the journal intact. Exact child receipt replay and reconciliation preserve the original result.

An affected new assignment cannot reuse a reachable dispatch identity claimed by a different plan. `impact-preview` reports `dispatch-identity-already-claimed` with the target queue, assignment, operation and earlier plan digest. Give the fresh effect a new assignment ID and review the revised plan. Keep an existing ID for evidence and status when the new assignment has no conflicting reachable effect. The provisional replacement gate still requires the verified final pin and matching check.

## Review reciprocal impact after a design change

Select the previous accepted revision and the proposed or newly accepted revision and identify the exact changed fact, rule, placement, asset binding or effective event. Read the consuming record before changing the scope. Record unchanged meaning, confirmed dependencies, suspected links and unexamined areas. Name an unaffected control with working source and evidence. Keep historical checks under the original pins and reopen the affected checks when the consumed condition changes. A changed whole-document pin keeps the existing conservative impact rule. A narrowly pinned unaffected condition can retain matching evidence after comparison.

| Finding | Owner and disposition |
| --- | --- |
| Accepted canon changes a permitted action or route | Narrative identifies the accepted fact. Game Design and the affected Unity or 3D owner inspect the referenced event, binding and check. |
| A design rule changes a cue, geometry requirement or state transition | Game Design records the revised rule. Narrative reviews any changed meaning, and 3D or Unity checks the applicable cue or effective event. |
| A receiver differs from the accepted rule or artifact | The owner of the earliest mismatching source or binding repairs the implementation and rechecks the affected case. |
| An optional idea conflicts with applicable canon or design | The proposing and owning areas revise or decline with the exact constraint, rationale and reconsideration condition. |

Use existing impact preview and a reviewed amendment for changes to frozen required pins. Source history or a proposal grants no new effect. Ask the author when resolving the finding changes experience or canon, trades material cost, or expands approved scope. Present the feasible options, affected owners and checks, and one recommendation. Final review records current producer and consumer revisions, expected and executed rechecks and remaining scope. A later approved iteration gets a new assignment and retains the previous review.

## Review selected branch reports

Select the exact plan revision, assignment, criterion, producer and consumer revisions, attempt, actual environment and read-only artifact references. Verify the supported report format, required inputs and digests. Compare the required case set with the cases reached and reported. Keep supplementary observations in the report with separate coverage. Record the expected and observed result, earliest established divergence, missing and unreached steps, next owner and the evidence needed. Leave current verification open when the selected revision, format or evidence is unavailable.

| Selected finding | Next owner and action |
| --- | --- |
| A route passes on foreign canon or a replaced accepted Narrative source | Narrative resolves the selected work and accepted source, then replays affected routes on that input. |
| An accepted ArtWorkshop stage used a replaced predecessor | The 3D stage owner reconciles the earliest stale input and rechecks affected candidates. |
| A current imported asset has a wrong effective value, writer or runtime binding | Unity inspects the selected object, actual environment and first differing input or write. |
| A gameplay rule or tuning change requires a design decision | Game Design and the designated rule owner compare scoped alternatives. |
| The result raises a question about comprehension, response or enjoyment | The observation owner proposes a suitable human attempt. An author decision covers the selected creative result. |
| The required target or evidence is unavailable | The responsible area supplies the named prerequisite. The report records an open verification rather than a measured discrepancy. |

An exact redelivery keeps one observation. A new attempt adds a separate result with the same criterion where applicable. Conflicting bytes under one identity, expired evidence and unsupported formats leave current verification open while original observations remain visible. Keep an unaffected sibling eligible when the criterion and consumed sources still match. Apply an accepted review or scope change through the existing guarded procedures and retain original source and plan references.

## Workspace selection and packaging

Director coordination runs from the registered parent root. Serial work can use an existing clean or disjoint checkout. A scoped candidate can use an isolated artifact directory. A Git child controller can use the recorded worktree. An independent clone or runtime can supply required tool or writer isolation. Source checkout isolation and runtime isolation require separate evidence. Unity uses one named verified Editor, an exact project, independent caches, saves and outputs, and appropriate resource claims. Preserve existing child edits and locks.

The Director flavor adds setup, intake, plan, run, decide, status, review, audit and install to the [shared catalog](features.md). The initial seven Director operations established the package and topology pilot before maintenance qualification. Source maintenance starts from exact read-only audit evidence and separately authorized Pending, processing and implementation. A stopped owned installer handoff applies a pinned repair candidate to a selected canary. Source acceptance, installed generation verification and replay of the original failed scenario remain separate. D8 audit, bounded source repair and pinned canary follow pilot qualification. D9 adoption of externally completed work, milestone reconstruction and optional operator decisions follow D8 at lower priority.

## Audit selected runs

Use `audit` with an exact `director_run_id` and a `selections` list. Each selection names the registered `assignment_id` and canonical child `run_id`. Add exact `event_ids` to narrow the reviewed events. An optional `journal_export_sha256` reads an existing portable export from the recorded worktree. The audit creates no export or queue entry. Run status includes normalized Director dispatch state and verified owner waits.

Add `unity_receipt` to select one reviewed Unity summary from a recorded Core attempt. The [installed Audit reference](../common/references/director-workflow.md#audit-a-selected-unity-summary) defines the selection, versioned summary, minimal clean case and required evidence for excluding an expected diagnostic.

Start diagnosis with `director_timeline` for the parent dispatch, recovery, question and lifecycle stages. An empty `selections` list inspects the parent alone. Use `child_status` for the current checkpoint, unresolved check attempts and coverage, and `child_timeline` for checkpoint transitions, prepared and recorded checks and final outcomes. Event references carry the owning queue, exact identity, sequence and repository-relative path. Check records retain the recorded lane, timing, diagnostic fingerprint and evidence hashes when present. Known holds distinguish profile refresh, Director questions, repeated unchanged failures and host-policy rejection. Private error text, question content and local paths remain in the owning context.

New events carry UTC recording times. Older child events retain sequence numbers and available check receipt times. Older Director runs can have an incomplete parent timeline. Audit reports missing sequence ranges for a full child selection, and reports missing selected IDs for an explicit subset. A reviewed export can supply the exact missing events. Audit reports recorded observations without assigning times to old events or inferring results for unresolved attempts.

Source findings group by component, symptom, checked conditions and generation. The evidence preserves both canonical identity and exact byte fingerprints. A confirmed finding needs a matching executed check, a reproducible bounded observation and the verified installed helper. Other product failures, runtime prerequisites and owner waits remain observations. Missing or changed evidence is visible as incomplete coverage. Queue-ready findings contain controlled behavior summaries and portable evidence references. Source repair requires a separately authorized exact selection.

## Route a confirmed source repair

Use `repair-preview` to re-observe the exact confirmed source finding and bound maintenance area. `repair-intake` requires explicit maintenance authority and links one canonical Pending request to original run and check evidence. Research and process the exact task using the normal Core boundary. Select the exact reviewed child task for bounded source implementation.

Use `repair-candidate-preview` and `repair-candidate-apply` to retain reviewed source bytes, owned composed output and the original failing assertion. A repair candidate requires exact canonical Pending, task, run and outcome references with matching failed and repaired checks. Candidate creation supplies no target installation authority.

## Install the Director flavor

Use `node .skill-tree/bin/install.js --list --flavor director` to inspect operation membership. Use an explicit workspace target and `--dry-run --all --flavor director` to preview the dedicated coordinator. Run `--flavor director --verify` on that workspace to verify the coordinator and host launchers. For a direct low-level profile, pass `--project --flavor director` at the exact target. An existing direct Director receipt remains usable at the original installation root. Use `--flavor director --only <host> --uninstall` at the workspace to remove the selected host launcher and package ownership. Remaining hosts retain access from the workspace. After the last host is removed, reinstall a host to resume the retained coordinator, projects and source work. An owned installation or flavor change requires a stopped checkpoint and current target verification. Verify the installed target through the project-owned installation manager.

The shared-folder topology uses one canonical queue for distinct scopes. The external topology uses the verified profile of the registered external project. A moved external checkout requires Core locator reconciliation, owned profile rebind and guarded Director rebind. A plan with changed execution inputs requires current admission before another effect.

## Verify the repaired generation on one target

The source candidate retains the accepted prior failure, reviewed repair, exact source inventory and exact composed output inventory. Select one stopped installation on a disposable linked worktree and the receipt owner of the operation, the original queue, task and run, a current owner authority reference, and any product paths whose bytes require preservation. Keep the candidate source snapshot immutable. The source candidate alone grants no installation authority.

Use `python3 scripts/director-entry.py preview --input <request.json>` to inspect the exact previous and planned profiles. The request holds the exact local target and candidate source, the reviewed candidate, the candidate digest and the selected scope. Preview performs no writes. Retain the returned portable preview and exact digest.

Use `apply` with the reviewed preview digest and original local target and candidate. The owned installer checks the same stopped handoff and exact composition under the writer lock. Activation verifies ownership and candidate digests. The selected queue, checkout, stopped checkpoint, existing history, plugin bindings and protected files remain intact. Candidate activation holds wider rollout and still requires replay.

Use `reconcile` to inspect the exact prior profile, candidate generation or matching interrupted journal. Running `recover` requires the observed journal digest and original preview. Mixed, stale and unrecognized effects stay held for review.

Use the current child Core operation to explicitly admit the same original run into the newly verified profile. Replay checks the retained admission event and original task/worktree identities before executing the exact installed snapshot helper in dry-run mode against the original Markdown input. The replay result preserves the original lane and links the candidate, profile and same run. A successful replay supplies canary evidence for the selected target. Wider rollout requires separate selection.

The replay report records elapsed time and an execution cause. Distinct causes identify a timeout, a launch failure, an unsuccessful process exit or a report that fails the original assertion. Exact target and scenario identities remain available for diagnosis. The report excludes process output and local paths.

Use `rollback-preview` and `rollback` for an explicitly reviewed reversal of the exact current candidate generation. The owned manager verifies the retained transaction and destination bytes. Review a conflict before another attempt. Re-admit the same run under the restored profile before subsequent execution.

## Adopt existing child work

Use `adopt-preview` in Director review with the exact frozen plan, assignment and canonical child task, run and outcome. A previously completed canonical task can supply the original immutable task body fingerprint for a new plan. The existing child launch path requires a live Prioritized task.

The selected result can bind a child run, accepted artifact, scoped recorded commit or accepted Manual owner decision. Adoption checks the frozen scope, current required pins, matching child checks and evidence bytes. An existing Director dispatch requires reconciliation through the original run. Use `adopt-apply` for the exact reviewed basis and owner authority. Use `adopt-read` to inspect the original receipt and current status. Adoption writes a parent receipt and retains original child ownership and delivery.

## Record and reconstruct milestones

Use `milestone-preview` to select an exact frozen plan and retained story, art and game evidence. Select public evidence when relevant. An accepted Narrative pin can establish story evidence. Art and game require matching checked child results or accepted adoptions. The required check covers the owning area and any linked artifacts belong to the assignment write scope. Supply the reviewed cross-area handoff when the plan contains required edges. A required provisional asset holds final acceptance until verified replacement.

Use `milestone-apply` with the reviewed digest and exact owner authority to retain a reproducible slice. `milestone-read` reports archived evidence, current objective revision, current role evidence, missing inputs and applicable handoff status. An approved amendment affecting a required role holds the superseded milestone while preserving historical evidence. Current approval and release qualification remain separate. Release requires explicit delivery authority.

## Review repair and prepare human acceptance

Find the first divergence from an accepted fact, gameplay rule, visible asset or effective binding. Return the exact discrepancy to the area responsible for the first mismatch. Current technical recheck records the selected target, new producer and consumer revisions, affected cases, observed input and result, unchanged control and remaining coverage. Preserve earlier evidence and the missing steps that require a fresh attempt.

Use the existing human observation procedure to present the supported build, scene entry, starting state, control and clock. Record the participant's first choice before intervention, stated expectation and relevant cue. Record the time and content of coaching and label the later observation. A known-route execution can establish reachability. Unaided discovery needs the selected relevant participant observation.

| Observation | First check to distinguish the cause |
| --- | --- |
| The participant reports an unclear goal | Compare intended fact, delivered wording and the visible or audible cue before attributing meaning to Narrative, UI or integration. |
| The goal is clear and the route was missed | Inspect the first choice and camera or affordance cue. Use a known-route control to distinguish discoverability from blocked traversal. |
| The participant intended and tried an action that had no effect | Inspect ordinary input, current binding, guard and first state writer under the selected build conditions. |

Return the playable entry point, current revisions, observed behavior, affected and unobserved scope, and one precise creative decision. Only the actual author's scoped response records creative acceptance. A technical pass can make the presentation eligible. Reopen the specific claim when a new technical or usability finding changes the evidence or the scope presented to the author.

## Locate the first divergence in comparable handoffs

Choose an ordinary and revised handoff under equivalent request, authorized scope, accepted facts and deliverable. Freeze both instruction revisions, actual available inputs, expected and consumed source pins and independent outcome criteria. Record differing conditions as comparison limits. Give the same compact records and controls to two separate reviewers. Ask each reviewer to reconstruct pins, coverage, earliest known discrepancy and next owner without the other review.

Compare owner, affected step, missing evidence and unaffected control. Preserve disagreement and the evidence that could resolve the disagreement. Trace accepted intent, selected configuration and bindings, available evidence and owner waits before assigning an instruction or product cause. Missing decisive input leaves causal attribution open. A skill-level finding requires reproduction on the identified instruction revision and an independent outcome for the same conditions.

Record adopt, revise or defer for an exact selected scope, known risk and residual uncertainty. An authorized fix rechecks the original case, an unaffected negative control and a new comparable request. A paper reconstruction qualifies the review procedure. Live comparative effectiveness requires matched project requests and reported actual results.

## Operator selections after the pilot

The pilot exercised one owner wait and an independent sibling, exact hand and belt dependency revalidation, one isolated Editor, and a pinned update on one disposable target. Context and impact remain in status and plan. Current resource control uses serial acquisition and exact named claims. Provisional asset work uses a named preliminary check and a separate final replacement gate.

Future creative variants require a shared accepted baseline, independent outputs and an explicit selected result. Future automated arbitration, notifications, scheduling, separate context commands and external hosts require an observed recurring need, selected authority and a bounded success and failure interaction. The pilot evidence remains available in the [Codex observation](../history/validation/director/codex-host-result.json), [lantern handoff](../history/validation/director/lantern-handoff.json) and [repair canary](../history/validation/director/repair-canary.json).

The portable lantern handoff retains the compact receipts, original fingerprints and fixture model. Byte-exact replay of the historical Blender attempt uses the retained machine-local archive with the original installed profile and raw process log.

## Fixture and native evidence gates

The [Narrative workflow](narrative-workflow.md) uses accepted source snapshots for Director assignments. The [3D workflow](../common/references/3d-workflow.md) owns the art production stages. Director capability pins track adapter availability separately from standalone source. An adapter requires a verified selected generation and current qualification before use.

| Lane | Required evidence |
| --- | --- |
| Static | Canonical ownership, exact task and source inputs, schemas, portable references and matching review. |
| Portable behavior | Disposable three-area tree, local Git baseline and queue, two story revisions, exact art bytes, a failing consumer, independent dirty work and interruption recovery. |
| Actual Codex | Observed independent host actor and actual owner input, exact stopped and resumed child run, wrong-recipient and duplicate controls with unaffected sibling progress. |
| Native tools | Approved disposable copy of `skill-tree-sandbox`, verified current tool identities and owned child recipes, matching Editor, stock build-scene EditMode, later lantern import and carry checks and corresponding cleanup. |
| Package and topology | Actual owned package inventory and verification, shared-root and external child fixtures, moved-path rebind and cross-area recovery. |

The Unity baseline preserves original Assets and metadata, Packages manifest and lock, and ProjectSettings through byte comparisons. Native qualification records Editor, Test Framework, Pipeline and Blender builds, exact copy, PID and profile, run method, input pins, fresh report digests and cleanup. Fixture tests and source verifiers cannot substitute for observed child execution. The original sandbox and product environments remain outside fixture writes.

Existing [workspace](../common/references/run-workspaces.md), [workflow metadata](../common/references/workflow-metadata.md), [decision governance](../common/references/decision-governance.md), [validation](../common/references/validation-policy.md) and [installation profile](../common/references/installation-profile.md) contracts govern the relevant child effects. Checkpoint state and past success supply evidence for review and no new authority.
