# Director Workflow

Director coordinates exact assignments across registered Skill Tree areas from Codex. Each child keeps ownership of the canonical queue, child work, acceptance and delivery.

Run the installed `scripts/director-entry.py` with an operation, exact Director project root and `--input <request.json>`. Setup registers exact canonical areas and readies explicit rebinds. Intake owns versioned objectives. Plan owns reviewed immutable scope. Run and decide require current separate authority. Status projects read-only state. Review verifies independent producer and consumer evidence with review-preview. Use review-apply for the exact accepted review, review-read for a retained record, impact-preview for two exact revisions and amend-apply for the reviewed scope change.

Apply the [shared feature folder guidance](development-practices.md#organize-files-by-feature) within the responsible area. For example, the Director registry identifies the game area at `areas/game/` by role, scope and capabilities. The child repository map directs developers to `areas/game/src/profile/` and a local README when the profile feature needs further explanation. Keep feature dependencies with the child or shared owner. The Director registry owns area boundaries and routing.

Use the shared root profile for areas in the same repository. External areas retain the selected verified profile for each area. A recognized shared Unity root supplies static recipes from the exact supported Editor and resolved Test Framework. A matching native check and exclusive runtime resources remain required for execution.

Read the [capability pins](director-capabilities.json). Accepted Narrative snapshots and representative fixture adapters retain separate identities. Unintegrated ArtWorkshop and logs adapters remain visible prerequisites. A source or fixture observation does not admit an unverified adapter.

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

Repair routes one reviewed failure to the source maintenance area and records the exact tested candidate. Use the install operation as `python3 scripts/director-entry.py preview --input <request.json>` with one approved target. Activation verifies the candidate. Explicit same-run admission precedes replay of the original scenario.

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
