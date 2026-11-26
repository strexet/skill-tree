# Director Workflow

Project setup verifies the coordinator Git owner, Core locator and owned installation before preparing maintenance sources or changing a child. A moved coordinator reports the verified queue and the applicable recovery command. After a move, recover the matching locator before rebinding the installed profile. Pass the reported recovery input with `--input` and supply exact paths for any listed retained worktrees. Recovery preserves existing workflow receipts and installation evidence. Retry the original setup after both checks pass.

Coordinator setup protects machine-local maintenance checkouts in `sources/skill-tree/` and `sources/projects/`, plus `.skill-tree/artifacts/director/local-bindings.json`, through the coordinator Git local exclude file. The portable Director registry remains visible to Git. Tracked conflicts and higher-precedence ignore rules report the affected storage boundary.

Director coordinates exact assignments across registered Skill Tree areas from Codex. Each child keeps ownership of the canonical queue, child work, acceptance and delivery.

Run the installed `scripts/director-entry.py` with an operation, exact Director project root and `--input <request.json>`. Setup prepares the approved coordinator and projects, registers exact canonical areas and readies explicit rebinds. Intake owns versioned objectives. Plan owns reviewed immutable scope. Run and decide require current separate authority. Status projects read-only state. Review verifies independent producer and consumer evidence with review-preview. Use review-apply for the exact accepted review, review-read for a retained record, impact-preview for two exact revisions and amend-apply for the reviewed scope change.

Apply the [shared feature folder guidance](development-practices.md#organize-files-by-feature) within the responsible area. For example, the Director registry identifies the game area at `areas/game/` by role, scope and capabilities. The child repository map directs developers to `areas/game/src/profile/` and a local README when the profile feature needs further explanation. Keep feature dependencies with the child or shared owner. The Director registry owns area boundaries and routing.

Use the shared root profile for areas in the same repository. External areas retain the selected verified profile for each area. A recognized shared Unity root supplies static recipes from the exact supported Editor and resolved Test Framework. A matching native check and exclusive runtime resources remain required for execution.

Read the [capability pins](director-capabilities.json). Accepted Narrative snapshots and representative fixture adapters retain separate identities. Unintegrated ArtWorkshop and logs adapters remain visible prerequisites. A source or fixture observation does not admit an unverified adapter.

## Run managed Implement All

Use the managed project route to identify the canonical queue and initial prioritized scope. Freeze an approved Director plan with one exact assignment per unfinished required task. Retain the Core dependency edges. Add deterministic sequencing edges for overlapping writes in dependency order, using the prioritized order for ties.

Pass `implement_all` to `run-start` with the inspected `expected_source_hash` and positive `workers` limit. An explicit `snapshot_ids` list restricts the roots. The launch also records the original checked-out target branch and head.

Call `run-advance-all` with the exact Director run ID and current run digest. Execute each returned child in the recorded worktree and record the current reviewed child outcome before integration. Incorporate reviewed results through the existing local delivery commands. Use the checked current-target candidate path for a moved base. Call `run-advance-all` again after accepting and incorporating child results or resolving a recorded hold. After a lost batch response, read `run-status` for the exact recorded assignment. Use `run-dispatch` with that assignment and the original start request to recover the same child run and worktree. Check the existing worker and child progress before handing the recovered checkout to an actor.

The controller schedules unfinished admitted tasks and preserves concrete task and integration holds. A run completes after every assignment has a checked delivery on the original target. Later unrelated tasks require a new invocation.

## Shared workspace entry

Run the local `skill-tree-director` launcher. The menu offers project registration before setup and objective intake, status, audit and setup once projects are registered. The service directory is excluded from ordinary product Git staging through a local Git rule. Existing product rules retain priority.

Run `project-route` through the installed Director Setup entry before a project operation. Set `operation` to a registered skill identifier or a workspace action. Common actions include `discovery`, `project-read`, `status`, `workspace-status`, `audit`, `diagnose`, `setup`, `intake`, `process`, `implement-next` and `implement-all`. Discovery shows the installed operation catalog and the registered projects. Use the returned Director entry, command and input, or the exact child skill. A child-skill preview exposes requirements for scoped delegation and grants no new effect.

Pass an exact `project_id` when selection is ambiguous. Optional `task_ids` limits the inspected queue selection to exact IDs. Show the returned project, queue, dependencies and limitations before effects. Director implementation dispatch binds one exact task to each authorized frozen assignment. An explicitly chosen direct route uses `route: "direct"` for the preview and `--direct-project` for direct Core queue effects. Pipe the JSON request into the entry with `--input /dev/stdin` to preview without changing project files.

### Bounded batch intake and processing

A Director queue assignment can freeze `child.intake_batch_id` and ordered `child.items` with distinct `key` values. Each item carries a title, description and acceptance list. Optional Core metadata includes numeric priority, topic, source, context, priority rationale and Pending prerequisites. Use exact P-IDs or `@key` references for Pending prerequisites. Freeze intake and process authority for the assignment through `run-start`.

For batch processing, compute `process_spec_sha256` from the complete Core processing proposal with the frozen intake item keys in `selectors`, disposition keys and `parent_pending_ids`. Omit `expected_source_hash` from the approved proposal. Keep new Ready task keys and `depends_on` values verbatim. Send the actual P-IDs from the canonical intake receipt to `run-dispatch`, in original batch order, with the inspected queue digest. Core validates the resulting dependency graph and derives exact T-ID edges from Pending provenance. The same dispatch can be repeated after acknowledgement loss with the original request.

The Director records canonical intake and processing receipts as completion of the authorized queue effects. The processed Ready tasks require separate implementation authority. Existing child check requirements and any Core clarification holds remain visible on the resulting tasks.

Director status reports the first 50 tasks, total task count, and whole-project runs for each canonical queue, including direct project runs and standalone outcomes. Supply `project_work` with `area_id` and optional `run_id` for a focused view. A verified Director start links to the audit selector. Use `adopt-preview` with an exact frozen assignment and outcome to inspect an eligible completed direct run.

Run `workspace-audit` through the installed Director Audit entry for an ordinary audit from the shared workspace. The audit inventories registered subprojects and requests a separate read-only child audit for each available authorized whole project. Include each returned verdict, verified scope and coverage gap in the workspace report. Pass `project_ids` in the JSON input for an explicit selection. A project run audit still uses the exact run and assignments. The child tool evidence covers repository documentation and queue integrity. Any separate implementation or native validation requires the matching operation and evidence.

Run `diagnose` through the installed Director Audit entry with `area_id`, `run_id` and `attempt_id`. Diagnosis runs on request and reads the selected canonical check evidence. Coverage gaps identify unavailable results or source proofs. Arbitrary project logs require a reviewed adapter. When a structured reproduced failure matches the installed and maintenance generations and the recipe, Director shows a read-only source repair proposal. Source changes and publication follow the existing explicit authorization workflow.

Run `operation-receipt` through Director Audit with the exact installation or Director workspace root and an input file containing `operation_id`. Installation and Director setup results report an operation ID. Director `project-init` and `project-setup` accept the original operation ID in the input for an exact retry. The owned manager reports the operation ID for `--recover` and accepts `--operation-id=OP-…` for an exact retry. Receipt lookup is read-only and works before a task run exists. The receipt records the stage and status with bounded profile and journal digests. A pending record can survive an interruption. Reusing an operation ID checks the original journal identities and available evidence for consumed journals. A different pending journal requires a fresh recovery operation.

## Open the installed workspace

Open the selected workspace and invoke `skill-tree-director`. Use the installed Setup entry with `project-menu` to read the current choices. For `project-preview` and `project-setup`, pass the Director directory and `--input` with a JSON file. For example, `{"kind":"new","name":"example"}` places the project in the workspace's `example/` folder. Supply `path` for a different location. For an existing project supply `{"kind":"existing","name":"site","path":"/absolute/path"}`. Show the proposed path, profile and hosts before applying the user's choice. The registration reports the verified child queue and source maintenance branch. Repeat the original project choice to verify the registration and refresh the owned project packages if the menu reports a Core routing upgrade.

## Preview first-time setup

Use `setup-preview <absolute-director-root> --input <request.json>` with a `workspace` object to review first-time setup. The request contains a portable `director_id`, a workspace `kind` of `new` or `existing`, an explicitly selected `source`, and the selected `areas`. A source names an absolute local Skill Tree source `checkout` and a local `revision`. The source checkout must already match the selected revision and contain the exact committed package inputs. The coordinator selects the Director flavor.

Each area declares an `id`, `role`, `capabilities`, `allowed_effects` and a `project` object. Select one existing `source-maintenance` area. The project declares `kind`, `topology` and `path`. A new project uses `placement` of `inside` or `alongside` with a relative path, or `custom` with an absolute path. An existing project uses an absolute path. An existing separate repository can include a relative `scope`. A separate repository requires an explicit `flavor` and `source` at the area level. A `shared` folder inherits the coordinator queue, package source and flavor. A `separate` repository owns an independent queue even when the checkout is nested under the coordinator.

The local review record freezes paths, scoped effects, canonical ownership proofs, package inputs, required files and setup prerequisites in `preview_sha256`. Destination overlap checks account for case and Unicode aliases. Setup preview performs read-only discovery.

### Prepare the approved workspace

After approval, run `setup-bootstrap <absolute-director-root> --input <apply.json>` from the installed Setup operation. The apply JSON contains `request` with the original guided request and `expected_preview_sha256` with the approved digest. A shared folder uses the canonical coordinator checkout. A new Git root starts on `develop` with an empty initial commit. Bootstrap preserves existing Git refs and Core state. Profile changes that would alter an unfinished run defer until that run finishes.

A `prepared` result reports the observed queue and installation identities for the coordinator and selected areas. A `deferred` result identifies the current prerequisite and the recorded completed stages. Retry with the exact approved input after resolving the prerequisite. If preparation stopped before recording a newly created coordinator directory, review a fresh preview of the empty destination. The local setup journal under `.skill-tree/artifacts/director/` keeps the original destination and intended effects so a retry can verify completed work. Use the approved preparation digest to register the exact prepared set.

### Register the prepared areas

Run the installed Setup operation `setup-preview` with `director_id` and `prepared_preview_sha256`. The preparation digest comes from the `prepared` result. Review the exact current scope, queue and installation. Run `setup-apply` with the same fields and the registration preview's `expected_preview_sha256` after approval.

Use `setup-status` with `director_id` and `prepared_preview_sha256` to inspect preparation, registration and routing verification for each area. For routing evidence, supply `routing` as a list of objects with `director_run_id` and `assignment_id`. The installed Setup operation projects a verified route after the authorized `run-dispatch` intake returns a matching canonical child receipt. The status read performs no intake. Retry dispatch with the original request to reconcile the original receipt.

## Look up project context

Request `plan-context` with an exact plan selector and `assignment_id`. Give the worker `context_search.request` with the assignment brief when the worker needs related project sources. Add a literal-term `query` to the request and call `scripts/director-entry.py context-search <director-root> --input <request.json>`.

The lookup reads committed scopes under a registered read-only effect for the selected assignment and predecessor assignments. The lookup also covers exact verified fixture files pinned by the selected chain. Hits give the area, Git commit, source path, line and SHA-256. Use the pin review path when a discovered source becomes a required input.

Use exact queue, task and run identities. Keep a durable child attempt and original workspace when asking the owner. Verify the matching guarded answer before explicit continuation. Delivery requires separate authority.

Audit reads exact retained receipts. Inspect `director_timeline` for parent dispatch, recovery and decision stages. Inspect `child_status` for current holds and open checks, and `child_timeline` for exact checkpoint and check events. Follow portable event references in the owning queue. Missing events and legacy time coverage remain explicit. Private inputs and error text remain in the owning context.

### Audit a selected Unity summary

Run `python3 scripts/director-entry.py audit <director-root> --input <request.json>` from the installed Audit package. The request names the exact `director_run_id` and a `selections` array. Each child selection names the registered `assignment_id` and child `run_id`. Add `unity_receipt` to the child selection to inspect one recorded Unity attempt.

| Field in `unity_receipt` | Required content |
| --- | --- |
| `attempt_id` | Exact Core check attempt ID with prefix `C-`. |
| `path` and `sha256` | Repository-relative JSON path in the recorded child worktree and the lowercase SHA-256 of the exact bytes. The executed Core attempt must retain the same available evidence pointer. The summary limit is 256 KiB. |
| `required_cases` | One to 256 distinct lowercase case IDs. Each begins with a letter and contains at most 64 letters, digits and hyphens. |
| `capture_identity` | An object with `kind` set to `editor-session` or `player-build` and the lowercase `sha256` identifying the reviewed session or build. |
| `expected_diagnostics` | Optional array of up to 128 distinct reviewed expectations. Each object names `case_id` from `required_cases`, `severity`, `signature_sha256` and `expectation_sha256`. Review the local case-specific expectation before selecting the expectation digest. |

The producer writes a summary with integer `schema: 1`, `assignment_id`, `run_id`, `attempt_id`, the recorded `lane` and `environment_identity`, and the matching `capture_identity` object. The `capture` object contains `available` and `complete` booleans, `start_utc` and `end_utc` with UTC offsets, and the raw capture's lowercase `sha256`. The complete window starts at or after preparation, has positive duration and ends by Core recording. Use a timezone-qualified timestamp. Missing scope, incomplete capture or mismatched evidence leaves a coverage gap.

For a minimal clean case the review selects `"required_cases": ["carry"]` and the matching summary contains `"cases": {"carry": "pass"}, "message_groups": []` alongside the identity and capture fields. The `cases` object maps up to 256 case IDs to `pass`, `fail`, `skipped` or `unreached`. Each of at most 128 `message_groups` objects contains a `signature_sha256`, `severity` from `info`, `warning`, `error`, `exception` or `assertion`, a `classification` from `fresh`, `expected`, `prior-session` or `out-of-window`, a positive integer `count` of at most 1,000,000, and a `case_id` when attributed.

A group classified as `expected` also supplies `expectation_sha256`. Only a reached case and an exact match to the reviewed expectation in the selection support exclusion. A missing or mismatched expectation leaves that case open. Missing attribution leaves the selected cases open. An already established fresh error, exception or assertion still holds the affected case. The owning project retains source expectations and raw engine text. Read the case verdicts and retained Core counts in `child_status[].unity_receipt` and gaps in `coverage_gaps`.

Repair routes one reviewed failure to the source maintenance area and records the exact tested candidate. Use the install operation as `python3 scripts/director-entry.py preview --input <request.json>` with one approved target. Preview resolves the selected host against the verified installation and lists all affected destinations and co-owners. Activation verifies the candidate. Explicit same-run admission precedes replay of the original scenario.

Review also adopts existing child evidence and retains exact product milestones. A milestone records accepted story, art and game evidence and selected public results. Review current coverage before requesting separate release authority.

## Route the requested deliverable

Use the named design result to choose the acceptance path. A brief or rule goes to Game Design, an inventory or placement to Mechanics, and a tuning study to Balance. A document, asset-only request, inventory or study inside a Director objective finishes on the scoped owner's artifact and the matching criterion. A direct request can use the installed operation independently of Director.

A playable character or location uses the existing story, art and game milestone. Request the smallest missing accepted scene facts from Narrative. Request the audience, repeated activity, effective gameplay rules and explicit assumptions from Game Design. An authorized design workshop can draft from labeled assumptions. Freeze production assignments against accepted required facts and behavior. Record each exact revision, expected artifact, owner, consumer and observable check.

After plan approval and exact execution selection, art and a gameplay proxy can proceed in parallel when assignments have independent effects and resources. A producer can present the reviewed handoff to 3D manually when the ArtWorkshop adapter is unavailable. Label the proxy scope and the final replacement gate. Unity checks the intended interaction on the exact selected imported asset and rule revision. A proxy result leaves final integration open. Send Core only adopted changes with an exact deliverable, owner and observable check.

## Review the effect of a changed design input

Compare exact previous and proposed or accepted revisions with the consumed fact, placement and effective event. A wording-only change or unrelated asset edit can preserve evidence when the consumed condition and scoped dependency remain current. Review a changed whole-document pin conservatively. A material accepted change names confirmed consumers, suspected dependencies, unexamined scope and one unaffected control. A mismatch against an accepted fact, rule, marker or runtime binding returns to the corresponding implementing owner for repair.

Revise or decline an incompatible optional mechanic with the reason. Present an author decision for a consequential creative, cost or scope trade-off with options, affected evidence and a recommendation. Final review records current producer and consumer revisions, required rechecks and retained independent evidence. A later iteration uses a fresh assignment in the approved scope and preserves earlier decisions.

## Interpret one branch report

Select the exact plan revision, assignment, criterion, producer and consumer revisions, attempt and actual environment. Compare expected and observed scope and digests before interpreting the result. Separate required and supplementary checks, missing cases and later steps left unexecuted. Name the earliest evidenced divergence and the observation needed to distinguish a prerequisite from a discrepancy.

A mismatched canon pin returns to Narrative, a replaced ArtWorkshop input to 3D, and a receiver binding or effective value mismatch to Unity. Game Design owns an unresolved rule or experience choice. Request human evidence when the selected question concerns a person's response. Creative acceptance requires the actual author decision. An unavailable environment or unsupported format leaves verification open.

Match redelivery by exact observation identity and digest. Keep a distinct new attempt and earlier result. A changed digest under the same identity or expired source holds current verification. An unaffected sibling keeps matching evidence and the original acceptance remains readable.

## Present a playable decision after repair

Route an accepted-rule discrepancy to the area that owns the first mismatching fact, rule, cue, asset or runtime binding. After repair pin current revisions and rerun the affected checks and one independent control. Retain the technical lane, actual result and uncovered cases.

Use the selected supported build or scene and exact entry state for a human observation. Record the first uncoached choice and any later facilitation. Separate an unclear goal, missed route and failed control by evidence. Present the author with the playable entry point, observed result, remaining scope and one precise decision. Technical results establish observable behavior in the recorded lane. Creative acceptance requires the actual author response on the current presented revision. Reopen the affected criterion when a new technical or usability finding changes the basis.

## Measure comparable design work

Freeze the decision and eligible population before counting. Keep stable request, revision, handoff, evidence and attempt identities. Compare equivalent scope, clock and source availability. Count identical delivery once. Preserve new attempts under the original request and report excluded and unmeasured cases with reasons. An empty eligible denominator yields no estimate.

| Decision | Calculation and evidence |
| --- | --- |
| Is the GDD sufficient for independent predictions? | Accepted rule revisions with both normal and boundary outcomes predicted correctly by an independent reader divided by sampled accepted rule revisions with both known expected outcomes. Cite the accepted rule and independent check. Report missing expected outcomes separately from absent predictions against a known oracle. |
| Are the recommendations applicable? | Applicable recommendations divided by independently judged original slots within a frozen K and held-out request scope. Count identical delivery once. Count the first occurrence of a repeated suggestion and keep the original later rank as a repeat. Report no-fit, empty and unjudged results separately. Cite the ranked suggestion and independent judgement. |
| Did the atlas find affected placements? | Known affected placements omitted from the report divided by the confirmed affected set in the audited scope. Pair the exact placement record and independent audit. Keep suspected links and unexamined regions separate. |
| Does impact review reopen too much? | Confirmed unnecessary rechecks divided by all distinct proposed rechecks in the selected scope. Cite each proposed recheck and the independent verdict for the same dependency. Report unresolved verdicts alongside the count. |
| Can a Balance result be reproduced? | Studies reproduced within the declared tolerance by an independent reviewer divided by reviewed studies with sufficient matching inputs. Record the study version, selected comparison, units, assumptions and separate count of insufficient inputs. Retain retries as attempts within the study and pin the comparison evidence. |
| How well did the tuning forecast match? | Measured change minus the change predicted before observation for the same parameter, conditions, units and clock. Record matched denominators when applicable, effective setting, direction and any adverse outcome separately. Use the study and matching evidence record. An unmeasured forecast stays unscored. |
| How long until usable evidence? | Median elapsed UTC time from input readiness to first adequate evidence for comparable completed requests with both timestamps. Record incomplete work or missing timestamps, environment and author waits, wrong routes and insufficient data from the request and evidence receipts. |
| How often does a handoff return? | Distinct reviewed handoffs returned at least once for a confirmed description fault divided by all distinct reviewed handoffs in the named cohort. Keep reasons such as an unavailable environment, authorization wait or other return separate. Use the reviewed handoff and return receipts. Retain actual revisions and later attempts. |

Store compact local inputs and evidence IDs so a second reader can recompute each measure. Standalone documents may use local project identities without a Director run. Follow [compact evidence retention](history-retention.md) for locators, gaps and original outcomes.

## Compare ordinary and revised handoffs

Freeze equivalent briefs, accepted facts, available inputs, controls, and exact ordinary and revised instruction revisions. Ask two independent reviewers to reconstruct expected and consumed revisions, coverage, earliest evidenced divergence and next owner. Record reviewer disagreement and unavailable evidence. An unavailable decisive input leaves causal attribution open. Record the missing evidence and the responsible owner.

Check changed intent, effective configuration, available artifacts and author waits before assigning a recurring problem to a skill. A skill finding requires reproduction under a known instruction revision and an independently established outcome. Record adopt, revise or defer for the selected scope with residual uncertainty. Recheck the original case, an unaffected negative control and a comparable new request after an authorized fix.

### Attribute an installed resource failure

An executed unit check can report a verified Skill Tree resource defect. Record the installed resource and relevant fixture paths as check sources. Write the observed result to `.skill-tree/artifacts/director/<check-id>.json` and include that file in the failed check evidence. For example, a control that actually inspected a selected document count can emit:

```json
{"schema":1,"kind":"director-resource-check","assertion_id":"snapshot-count-matches-selection","installed_path":".agents/skills/skill-tree-create-documents-snapshot/scripts/create-documentation-snapshot.py","expected":"one-document","observed":"zero-documents"}
```

Use the actual installed path for the selected host. The unit check owns the meaning of the expected and observed tokens. The audit verifies the result digest against the Core receipt, maps the exact packaged bytes to the canonical source file using the verified installation resource map and retains portable input fingerprints. A missing receipt or an ambiguous mapping leaves the failure available for investigation. Repair preview also requires the registered maintenance checkout to contain the same source and fixture bytes and a resolvable unit recipe. An owner can select the resulting proposal and explicitly authorize intake, processing and launch on the project's source branch.

During source repair, repeat the same check with the reviewed source path in `installed_path`, record a red result and a passing result in distinct evidence files, and select a review reference to freeze the candidate. The checked source diff, composed operation resource, original finding and both observations bind the candidate. The built-in snapshot canary remains available for the documented snapshot scenario.

For a guided project whose original repair approval includes `integrate`, run `repair-integrate` with the exact `repair_id`, `candidate_sha256` and owner reference. The integration command commits the frozen source change on the recorded Git base and fast-forwards the matching project maintenance branch. The product repository and the queues stay independent. Use the project's maintenance checkout for the subsequent authorized PR to the upstream repository.
