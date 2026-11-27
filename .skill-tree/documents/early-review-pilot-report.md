# Early Review Timing Pilot

## Cohort and protocol

The pilot applies the four triggers in the [early review policy study](early-review-policy-study.md), revision SHA-256 `02484cd40cdd1463cb5a415f1bbcff0cee7536c62e9e40c559e472856fe900b8`. The two-task delivery group combines a PR state transition and a research report, which gives a different scope and baseline from the historical five-task rollout. The pilot uses the recorded Skill Tree run `WR-8c97c22a-1e66-4ca3-b6e7-5bbc31fe9544` and combined review `DO-074cde8f-fe42-592f-8a5b-066ade498929`. The retained base is `5cc0bedd`, the accepted candidate is `bc1859fb`, and the local target merge is `5bd31ec0`.

The replay uses the five archived task definitions from the run event journal. The stored task bodies in each event's `changes[].before.body` field establish the pre-review task scope. Review outcomes are used to check the classifications after applying the rules. The exercise is retrospective. All active task, dependency, validation and delivery gates remain in force during the pilot.

The baseline includes the five independent task reviews and one combined review. The selective comparison assigns early review when there is positive evidence for authority, shared state or effect, downstream consumption, or failure visibility and recovery. Deferral requires affirmative bounded-scope evidence and a matching check. The final-only baseline is illustrative. Success requires a classification and evidence pointer for every task, a recorded safety-stop result, and zero high-impact false deferrals in the selected cohort. An attempted material action on an unreviewed candidate triggers a stop before the affected action.

## Replay and outcomes

Each event is under `.skill-tree/history/run-events/wr-8c97c22a-1e66-4ca3-b6e7-5bbc31fe9544/` in the original queue. The first column gives the journal sequence and event then the relevant source commit. The final review consumes the full combined candidate.

| Task input | Pre-review evidence | Selective classification |
| --- | --- | --- |
| 10 · `e-15b3b30e-c1dc-4173-9b47-1ded3cec757f` · `33982813` | Shared policy invariants bind task acceptance, check evidence and review across several transitions. | Early on authority and downstream consumption. |
| 25 · `e-8cf53954-5d30-4339-914c-26d1c0c400d6` · `da139d53` | Parallel workers can reserve shared resources, interact with accepted commits and affect release scope. | Early on shared state and recovery. |
| 32 · `e-3c1c7d69-3521-411e-b9c0-5c2e3897d8fe` · `a12eaf01` | Profile activation and renewed attempts consume prior owner approval and can clear an execution stop. | Early on authority and recovery. |
| 39 · `e-902f0aad-1a8d-46da-bcf8-102d6eca68f6` · `3510ab59` | The handoff is read-only, and the result selects the PR and candidate for later review and publication operations. | Early on downstream consumption and failure visibility. |
| 46 · `e-7a5eac0b-04d0-4064-bd61-498da82f731a` · `240aa619` | Resumable check receipts can satisfy downstream prerequisites or permit acceptance after recovery. | Early on authority, downstream consumption and recovery. |
| Final review · `DO-074cde8f-fe42-592f-8a5b-066ade498929` · `bc1859fb` | The combined tree includes interactions between controller, review and validation paths. | Keep independent integrated review. |

Selective timing retains all six review boundaries, with zero deferrals to assess for false negatives. Final-only would defer five risk-bearing tasks in the replay. The combined history records one corrected issue in the wave recovery guard, which now verifies the exact checked HEAD in `0087a3f5`. The final recorded review has zero outstanding findings. The retained evidence establishes the integrated stage and correction commit. Exact severity and reviewer effort for the earlier finding are unknown.

## Measured cost

The original queue can reproduce the timelines with `workflow-state.py orchestration-timeline` using run `WR-8c97c22a-1e66-4ca3-b6e7-5bbc31fe9544`, task frames `DO-2890e3c7-190e-5baf-9c57-b9cd634fa8f5`, `DO-b4251e28-4433-5ccd-bbe5-efc8babf03a0`, `DO-32980e67-7a91-509b-adf2-7a80191475b3`, `DO-8130f2a0-e7c9-5a85-9e6b-74049a4fc23a` and `DO-ea52db5d-9295-5c30-9e29-8fb6b287806c`, and the final review frame above. The event and decision ledgers provide local telemetry. The check logs are retained with the repository. [Check logs](../run-evidence/wr-8c97c22a-1e66-4ca3-b6e7-5bbc31fe9544)

| Observation | Baseline |
| --- | --- |
| Run start to combined review readiness | 14,126.779 s, from 12:40:28.679 to 16:35:55.457 UTC. |
| Run start to verified target delivery | 14,367.854 s, with verified delivery at 16:39:56.533 UTC. |
| Review-phase recording elapsed | 5.029, 4.510, 4.529, 3.481 and 4.600 s for the leaves. 3.999 s for the combined review. |
| Recorded pending plan actor intervals | 201.736, 333.858, 282.634, 285.613 and 288.231 s summed per leaf, and 202.801 s for the combined frame. |
| Reviewer pickup, review wait and active reviewer work | Unknown. The phase elapsed and pending plan actor intervals measure controller transitions and recorded pending time. |
| First passing checks | Five commands, 158 discovered cases and 1,454.703 s summed command elapsed. |
| Final passing checks | Five commands, 159 discovered cases and 1,513.745 s summed command elapsed. |
| All recorded attempts | 18 terminal records, including ten passes, seven prerequisite-wait unavailable records and one executed failure. Unavailable intervals can overlap and do not measure process wall time. |

Command totals use each retained unittest elapsed summary or TAP `duration_ms`, divided by 1,000 for TAP. The initial checks ran in 30.954, 905.209, 90.577, 189.768 and 238.195 s in cohort order. The final checks ran in 32.707, 924.600, 115.741, 192.959 and 247.738 s. The sums describe workload. The actual elapsed timeline establishes the end-to-end interval. The difference between the two totals includes changed evidence and reruns. The selective timing counterfactual removes zero review boundaries in the reconstructed cohort, and the run supplies no measured speedup for a different policy.

### Check-cost cases

The existing-PR handoff originally passed 55 cases in 189.768 s under receipt `C-2edca6e6-4e97-471e-a6f1-3aa103292c7a`. The check contract explicitly reads the shared Full Cycle reference. A change to the mapped reference made the accepted receipt stale. Some provider tests exercise only the helper. The final rerun under `C-f924324e-3688-45f7-8e54-37de7e7233e9` also passed 55 cases in 192.959 s. A narrower recipe or source set requires a separate proof that acceptance and effective operator instructions still receive coverage, with the current focused dependency and delivery obligations intact. [Initial handoff log](../run-evidence/wr-8c97c22a-1e66-4ca3-b6e7-5bbc31fe9544/task-4-validation.log) · [Revalidated handoff log](../run-evidence/wr-8c97c22a-1e66-4ca3-b6e7-5bbc31fe9544/resumed-final-4-behavior.log)

The wave check separately reported a false failure while a passing unittest completion block was followed by metrics. The verdict guard in `86a9b388` recognizes the successful adjacent count and verdict with trailing metrics present. The recorded failed attempt occupied about 942 s of recorded controller time. The post-fix policy uses the original result format and a current focused regression. The 36.298 s focused wave controls and the original 905.209 s topology suite cover different cases. Any saved time from narrower checks or correct verdict parsing is independent of review timing. [Testing policy](testing.md) · [Wave log](../run-evidence/wr-8c97c22a-1e66-4ca3-b6e7-5bbc31fe9544/task-2-validation.log)

## Safety exercise and recommendation

The provocative case defers the wave recovery change as a small read operation. The changed read actually selects the checked candidate for adoption, so the shared-effect and recovery conditions require early review. Reclassify as early before a downstream consumer starts. If an affected consumer has already started, pause before an additional write, preserve the original check and operation receipts, establish actual effects, then require a current candidate, affected checks and independent review before continuation.

Disposable controls exercised stale plan invalidation before dependent execution, a required question preventing implementation, and current check and clean re-review before acceptance. Separate Git fixtures rejected a stale review or moved target and required a review on the exact partial-delivery candidate before a merge. The five selected controls passed. The retrospective exercise produced no live policy bypass. [Orchestration controls](../tests/test-decision-orchestration.py) · [Local delivery controls](../tests/test-local-delivery.py)

Retain the timing matrix as guidance. The selected cohort is high-risk across all five tasks and establishes no benefit from adding a provisional controller state. A later comparable shadow cohort with affirmatively deferrable tasks and measured reviewer pickup, effort, and check overlap would support a separate design decision. Any implementation proposal must retain current review, acceptance, dependency and delivery behavior until an authorized new policy passes adverse-case qualification.
