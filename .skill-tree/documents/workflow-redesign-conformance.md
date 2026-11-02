# Workflow Redesign Conformance

## Scope and evidence

The source audit evaluates version 0.2.0 against [the approved plan](workflow-redesign-rnd-plan.md), including U-01 through U-08 and the named lifecycle fixtures. [Qualification evidence](../history/validation/redesign-conformance/final-report.json) records current executed source checks. Regression fixtures use temporary repositories, owned installation destinations and synthetic execution sessions. No Unity Editor, application server, browser, Player, device, live provider installation or actual model-behavior evaluation runs during the audit.

## Confirmed gaps and repairs

| ID | Plan obligation | Reproduced gap | Current repair and regression evidence |
| --- | --- | --- | --- |
| R-01 | Timely focused feedback and current evidence | Scheduler batching recognizes a pass without checking current sources/artifacts; focused unit timing can move to group end. | Scheduler validates matching immediate receipts; unit/EditMode checks remain immediate. `test-conformance-gates.py` covers stale immediate checks and timing refusal. |
| R-02 | Frozen controller scope and recorded execution stops | Unrelated processing can admit a manually injected dependency; out-of-scope completion or blocked-task resume can affect another controller. | Processing admits only captured required closure; initial required IDs remain frozen; completion/mutation/resume enforce scope and task-owned stops. Scoped negative controls preserve queue/checkpoint bytes. |
| R-03 | Original-receipt recovery and trustworthy Red/Green | Repeated check delivery changes the receipt; pending attempts can be overwritten; a new Red leaves an earlier Green usable. | Receipts are immutable/idempotent per attempt; pending controls require original-result recovery; Red prevents final acceptance. Check reuse validates the selected passed obligation independently of unrelated pending checks. |
| R-04 | Justified product execution and concrete recipes | Product checks can omit session context; prepared commands retain unresolved task parameters; timing observations are discarded. | Product lanes require owned session identity/evidence, exact checkout, authorization/profile, deadline and cleanup. Unity adds pinned Editor and isolation. Parameters become concrete argument vectors; operation timings remain separate. Synthetic fixtures establish helper gates only. |
| R-05 | Final acceptance rejects stale completed evidence | Finish trusts terminal disposition after relevant sources/artifacts change; history views retain stale artifact availability. | Finish selects immutable completed checks for revalidation; accepted receipts remain in the same run without implementation or duplicate outcomes. Pending revalidation blocks finish. History updates derived availability/source matching without rewriting the ledger. |
| R-06 | Explicit profile activation and preserved checkpoint | Refresh accepts unsupported workflow schema, ignores standalone pending attempts and leaves waiting controllers unstopped. Rollback can restore an older checkpoint. | Activation validates schema, observes both writer locks and pending controls, records the stopped re-admission boundary and preserves current workflow progress across rollback. Actual helper-controller fixtures resume through explicit admission. |
| R-07 | Preserve concurrent edits and failed-refresh generation | Destination edits or project-input drift during staging can be overwritten or activate a failed generation. | Validated destination hashes bind staging to activation; raw input/environment checks precede activation. Failed post-activation verification restores a matching owned generation; conflicts preserve edits/backups for review. Project dependencies are never rolled back implicitly. |
| R-08 | Preserve packages referenced by another installation | Shared `.agents/skills` destinations retain one provider owner; scoped uninstall removes another provider's package/bridge. | Explicit provider reference sets retain shared packages and bridges until the final recorded owner releases the resource. Multi-provider fixtures cover package and bridge release. |
| R-09 | Verify composition identity and installed policy | Matching modified hashes can substitute unrelated package content or a different flavor. | Verification checks receipt identity, resolved facts, provider destinations, complete inventories and deterministic recomposition from the verified local bundle. Rehashed unrelated content is rejected. |
| R-10 | Distinguish declaration from resolution | Exact manifest declarations become resolved package facts without lock evidence; reload settings are absent from relevant inputs. | Facts preserve declared-version provenance and supported lock resolution separately. Required UTF ambiguity fails once; optional unsupported Web specialization is reported and omitted. Editor settings participate in the appropriate environment identity. |
| R-11 | Complete static integrity and install diagnostics | Opaque binary locks are hashed after lossy UTF-8 decoding; recipe lanes are unchecked; install output omits requested identities/fingerprints. | Raw-byte digests detect opaque input changes. The versioned registry validates recipe lanes. Output includes package/profile/environment identity, input fingerprints, provider references and validation policy. |
| R-12 | Target catalog covers supported destinations | Generic root packages are absent from target manifest discovery. | Root package discovery supplements provider-required locations; target manifest regression validates exact generic entrypoints. |

## Implementation-unit coverage

| Unit | Current coverage |
| --- | --- |
| U-01 | Minimal structured tasks, criterion/check ownership, one dependency graph, immutable common slots and flavor contracts. |
| U-02 | Hidden source/target paths, launchers, snapshots, transaction/history ownership, explicit source-role metadata and provider/generic catalog discovery. |
| U-03 | Deterministic composition across eight operations and three flavors, complete links/resources, collision refusal, standalone packages and inactive-resource omission. |
| U-04 | Missing-foundation handoff/deduplication, owned copy installation, shared references, local maintenance, unknown schema/version errors, staging recovery, rollback and deterministic verification. |
| U-05 | Pinned admission, standalone progress, scoped group scheduling, early verified dependencies, original receipts, source/recipe/environment/artifact freshness and completed-contract revalidation. |
| U-06 | EditMode-first policy, focused PlayMode boundaries, serialized identity, owned Editor/isolation policy and version-gated UI/input/performance resources. |
| U-07 | Unit/API/browser distinctions, browser-backed component classification, non-JavaScript static recipes, server/build identity policy and local Web major-change refresh fixtures. |
| U-08 | Standalone/controller handoffs, source qualification, compact audit evidence, current documentation and the manual target-update checklist. |

## Qualification limits

Supported resolved dependency readers cover npm lockfile formats 2/3 and Unity package locks. Other lockfiles remain raw fingerprinted inputs; explicit owner-declared recipes provide unsupported-stack commands without guessed version-specific APIs. Missing infrastructure remains installable. Essential unsupported compatibility requires an explicit source/bundle update. Static compatibility never proves a working product runner.

The [npm lockfile contract](https://docs.npmjs.com/cli/v11/configuring-npm/package-lock-json/) and [Unity lockfile contract](https://docs.unity.com/en-us/engine/6000.0/manual/packages-list/dependencies-lp/upm-conflicts-auto) support the declaration/resolution boundary. Source fixtures establish deterministic mechanisms and failure refusal. Prompt contracts, synthetic sessions and test names do not establish actual agent adherence, product behavior, hosted deployment or physical-device qualification.

Live installation and existing-target adaptation remain owner-selected follow-up scope under the [manual checklist](manual-target-update.md). The source audit adds no migration machinery, automatic package upgrade, watcher, global specialization or extra outcome ledger.
