# Force Process Pending

Use deep processing when the owner asks to resolve a complex Pending request through research, worked examples and useful validation before promotion. Resolve the same exact selectors, topic or batch as ordinary [Process Pending](future-workflow.md#process-pending). An explicit selection must resolve completely. With no selection, an explicit request for deep Pending processing covers the Pending Queue.

## Establish first runnable work

1. Read the captured intent, current repository instructions, implementation, configuration, tests, accepted decisions and relevant retained evidence. Resolve factual gaps with the closest available source. Search external primary sources when requested or necessary. Record concrete findings, contradictions, source revisions and assumptions. Leave actual owner preferences or authority with the owner.
2. Compare plausible treatments of material uncertainty. Work through a representative example and an adverse case. Run safe, bounded checks when useful. Distinguish executed observations from future acceptance checks. Match each claimed result to the evidence lane that can establish the result.
3. Determine the first useful work each proposed task can execute. Specify inputs, observable results, scope, dependencies and a check that can discriminate success from failure. Split independent deliverables and retain exact Pending ancestry. Reuse compatible work only with preserved acceptance and ownership.
4. If material owner input is required before useful work can begin, retain the Pending item with the smallest unresolved question or use a configured ordinary blocking clarification. Report known facts and current options. Continue independent authorized items while waiting.
5. If initial work is independently runnable, define the artifact or check to produce before the later decision and name the step where execution waits. At that step the executor rechecks available evidence, presents the artifact and asks only the unresolved question. State which answer, observed fact or approval permits resumption and which actions must wait. A task instruction is an execution obligation. A configured clarification hold is enforced by the ordinary workflow.

## Apply the guarded ordinary operation

Use the [workflow helper contract](workflow-metadata.md) for the exact proposal and guarded mutation. Keep local per-invocation evidence under `.skill-tree/artifacts/force-process/` or an equivalent task-owned location. Record stable filenames or explicit locators for the pre-application snapshot, `preview.json`, approved `proposal.json`, original `receipt.json` and post-application `verification.json`.

- Before applying, save the exact selected P-IDs and Pending definitions, canonical source SHA-256, relevant existing T baselines, run scope, research findings, disposition reasons and exact proposed payload digest. Pin the accepted specification decision to the inspected selection. A changed payload needs current acceptance.
- Use the existing Process Pending write path with the accepted payload and inspected source hash. For a standalone mutation, use `scripts/workflow-state.py process <project> --standalone --input <proposal.json>`. A controller handoff uses the exact admitted run and the ordinary processing contract. Keep the actual ordered before, during and after hooks on the installed ordinary operation when configured. Inspect the owned Force Process binding manifest before research. Force Process defines no outer hook execution. An enabled Force Process binding requires a visible setup prerequisite and an owner-selected resolution before processing. Keep configured ordinary hooks on the actual Process Pending operation. Follow the [plugin boundary contract](plugin-invocation.md) and retain any blocked task or outstanding hook. Core-only projects can use the bundled copy of the canonical helper. A missing verified ordinary package for a required hook is a prerequisite.
- Capture successful helper output as the original receipt with the exact selected, created, reused, retained and resolved work. Re-read the canonical queue and index. Save the resulting source hash, actual T-IDs, readiness and holds, verification of Pending ancestry, check-plan coverage and unchanged unrelated work. Record actual check results separately from planned checks.
- Verify post-apply effects against the resulting task identities and original receipt. Keep the accepted pre-apply context as history even when promotion consumes the selected Pending items. Do not try to accept the observed effects by changing a decision guarded by consumed P-IDs.

## Standalone Preview and Verify on develop

Run from the repository checkout on `develop`. Keep the proposal and output directory in that checkout. The helper reads the canonical Future and index through the shared worktree locator and reports the canonical queue path in the Preview. A branch-local Future copy can differ. The queue writer still uses the exact selected Pending IDs and source hash from the proposal.

Use the generated Force Process helper from the source checkout for a core-only run. An installed Force Process package exposes the same read commands. Record the proposal and Preview digests in the plan acceptance before applying. For plan governance, invoke `orchestration-start "$project" --input "$evidence/orchestration-start.json"` through the helper and omit `--standalone` from orchestration commands. The orchestration input comes from the exact scoped decision preparation.

```sh
test "$(git branch --show-current)" = develop
project="$PWD"
workflow="$project/.skill-tree/skills/general/skill-tree-force-process/scripts/workflow-state.py"
evidence="$project/.skill-tree/artifacts/force-process/example"
proposal="$evidence/proposal.json"

python3 "$workflow" force-process-preview "$project" --input "$proposal" > "$evidence/preview.json"
preview_sha=$(shasum -a 256 "$evidence/preview.json" | cut -d " " -f 1)
```

Review and accept the exact saved proposal and the recorded `preview_sha`. Pass the accepted digest to both Verify calls. After acceptance, run the ordinary writer once and preserve the original stdout. When ordinary Processing has configured hooks, use the owned hook orchestration at the applicable before, during and after boundaries.

```sh
python3 "$workflow" process "$project" --standalone --input "$proposal" > "$evidence/receipt.json"
canonical_queue=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["canonical_queue"])' "$evidence/preview.json")
shasum -a 256 "$canonical_queue" "${canonical_queue%.md}.json" > "$evidence/queue-before-verify.sha256"

python3 "$workflow" force-process-verify "$project" --input "$proposal" \
  --preview "$evidence/preview.json" --receipt "$evidence/receipt.json" --expected-preview-sha256 "$preview_sha" > "$evidence/verification.json"
shasum -a 256 -c "$evidence/queue-before-verify.sha256"

python3 "$workflow" force-process-verify "$project" --input "$proposal" \
  --preview "$evidence/preview.json" --receipt "$evidence/receipt.json" --expected-preview-sha256 "$preview_sha" > "$evidence/verification-repeat.json"
shasum -a 256 -c "$evidence/queue-before-verify.sha256"
cmp "$evidence/verification.json" "$evidence/verification-repeat.json"
```

Preview uses the ordinary core planner and returns a projected result with provisional IDs. Verify requires the reviewed Preview digest, fingerprints the supplied receipt, compares the original allocations and processing ID with the current scoped task metadata, and checks task content independently from the rendered heading and YAML. For dispositions with no resulting tasks, Verify can confirm the receipt fields and observable queue effects. Only a resulting task can independently corroborate the processing ID. Both commands reject inconsistent queue or index snapshots and leave the canonical files untouched. A receipt that reports newly opened or reopened clarification sessions requires ordinary verification of the recorded holds. For a missing receipt, use recovery before any retry.

## Recover an interrupted acknowledgment

Read the original attempt evidence and fresh canonical state before any retry. Reconcile pending transactions and hook attempts through ordinary workflow recovery. Find any original receipt in local evidence or the recorded controller before drawing conclusions.

- With the original receipt, compare the expected result with the current T-IDs, Pending ancestry, processing identity, holds and queue hash. Report relevant drift from the recorded post-application snapshot.
- With a missing receipt, compare selected Pending rows, relevant T baselines and current T-IDs against the sealed proposal. Record a recovered observation only when the effects have one unambiguous match. Check each scoped output and disposition, including split ancestry and an exact declared reuse target. Match the processing identity and task contract. Record proof limits, including any disposition that lacks attributable history. A recovered observation never substitutes for original receipt bytes.
- Stop for missing, ambiguous or incompatible evidence, including a removed Pending item without an attributable result. Preserve both the sealed proposal and observed state. A later guarded retry is eligible only when the original action is established as unapplied, the accepted source and selection still match, and no transaction or hook attempt remains unresolved.

Report current outcomes and use the [ordinary next-action handoff](future-workflow.md#processing-result-and-next-action). Readiness authorizes the declared starting scope only after explicit implementation selection. The evidence record grants no execution or delivery authority.
