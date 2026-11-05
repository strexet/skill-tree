# External Skill Plugin Contract

## Contract boundary

An external skill plugin is a pinned instruction/resource package integrated through a bounded adapter at a selected existing-operation hook. The plugin is neither an arbitrary subprocess nor a native host plugin bundle. The contract defines the planned lifecycle, composition and invocation interfaces; executable capability requires the corresponding implementation and qualification.

The plugin system preserves exact task selection, dependency closure, source/check evidence, standalone installation and owner authorization. A plugin cannot replace locked invariants, mark core checks passed, change owner decisions, authorize publication or satisfy independent approval. Core-only projects retain existing operation and readiness behavior.

## Identity and resource closure

Each descriptor has a stable lowercase plugin ID, display name, upstream source URL, exact immutable revision, repository-relative skill path, content digests, license/attribution references, supported flavors/hosts, required resources/dependencies, adapter ID and allowed bindings. Mutable branches, discovery counts and catalog labels never identify installed executable content.

Dependency closure includes sibling skills such as the supplied `grill-me` wrapper and `grilling`, linked local references/scripts/assets, and required native tools/capabilities. Native tool requirements have explicit supported, missing or unqualified state. Packages retain upstream bytes and license provenance. A wrapper alone cannot claim the delegated skill or native tool is installed.

Owned plugin resources use project-local copies and repository-relative portable paths. Installation rejects escaping paths, symlinks, unresolved required content, conflicting identities and unsupported essential requirements. Unknown or modified destination ownership never permits overwrite, adoption or deletion through `--force`. Native helper scripts remain inert during acquisition, static composition, verification and listing.

## Lifecycle and installed registry

The lifecycle owns `.skill-tree/installation/plugins.json` as the canonical installed-plugin registry. Registry generations bind plugin identities/revisions, resource digests, destinations, dependency references, configured operation/hook bindings and enabled state. Catalog availability and installed state remain separate. Management views derive from the registry rather than another authoritative plugin list.

Acquisition is an explicit confirmed action. One project proposal displays exact versions, required dependencies, destinations, hook locations, enabled state and readiness effects. Actual install confirmation installs and enables precisely the displayed configuration. A changed proposal requires matching consent. Skip retains core-only behavior. Installation never executes a skill or starts a workflow.

Package generation, registry and bindings activate through one owned recoverable installation transaction with complete staging, ownership checks, locks and backups. Repeat installation can verify a matching generation. Updates, rollback and removal preserve task/run history and reject unknown or conflicting content. Dry-run, ordinary composition and installed listing remain offline and write-free.

Exact-ID removal previews affected packages and bindings, removes the selected owned plugin through the lifecycle and retains core packages, unrelated files and shared dependency resources. Remaining dependent plugins are explicit prerequisites rather than silently removed. Removing a required plugin leaves a visible missing requirement for a parked run; removal never reports successful invocation.

## Hook map and configuration

Bindings identify an existing logical operation, a `before`, `during` or `after` phase, deterministic integer order and enabled state. Hooks are bounded extension points inside the named operation. `during` contributes an additional scoped pass and preserves the complete core operation. Exact internal boundaries and any proposed new/split stages belong to the owner workflow-decision task.

Initial pilot defaults are an additional Ponytail pass after the complete core review and before PR readiness, plus an enabled post-processing interview before implementation eligibility. Other approved placements remain configurable. Enabled review failure, unavailability or stale results block PR readiness. An enabled processing interview creates a visible stable-ID T-task under a hold; actual answers, revisions, rechecks and owner confirmation precede Ready publication.

Project defaults support explicit temporary per-run overrides. Effective configuration records resolved bindings/order, plugin revisions, required capabilities and outcome policy. A configuration digest binds the complete effective snapshot to the run/invocation and remains frozen across resume. An explicit persistent edit does not silently replace an existing run configuration. An explicit disable/configuration change has a distinct recorded outcome and never counts as a successful pass or completed interview.

## Host adapter and activation lifetime

Codex is the first target for verified invocation. Portable descriptors and envelopes remain host-neutral; other host execution remains unavailable or unqualified until matching evidence exists. Existing core provider installation support remains unchanged. A declared provider destination supplies no native execution proof.

The Codex adapter prepares a bounded instruction/resource context for a host-controlled invocation. The host agent loads the pinned resources and invokes the supported context mechanism, then records actual host/agent/context identity and observed results. Missing host tools or unresolved dependency closure returns an explicit prerequisite. Prompt preparation, native tool invocation and observed agent execution remain separate facts.

Session-wide upstream modes such as the supplied Ponytail skill require a fresh isolated invocation context with a defined end. Mode instructions cannot leak into the parent workflow after the invocation. Delegated interview resources reuse the shared clarification protocol. A missing native Skill tool permits only an explicitly supported source-backed adapter; the adapter never claims a nonexistent native call.

## Input, result and receipt envelopes

An invocation input binds a unique attempt ID, operation/hook, exact selected task/group or review identity, plugin ID/revision/content, dependency closure, source/profile identity, frozen effective configuration, allowed tools/actions and bounded context. Review inputs include current base/head and full reviewed-diff scope. Interview inputs identify the stable T-task and clarification session.

Results distinguish `passed`, `findings`, `questions`, `failed`, `unavailable` and `cancelled`. Findings contain concrete source location, observation and consequence. Questions bind the actual clarification session/round and wait for owner answers. Rework returns proposed task or code findings to the ordinary authorized workflow; external instructions never directly mutate queue or review state.

Prepare/invoke/record/reconcile operations use original attempt identities and guarded helpers. Exact duplicate delivery returns the original result; conflicting replay, stale source/review/configuration or unmatched context rejects mutation. A timeout preserves the unresolved original attempt until actual host evidence reconciles the operation. No prepared record alone proves execution or success.

Long invocation, research and owner waits occur outside the writer lock. Receipts retain actual execution mechanism, host/model configuration when exposed, resource/context identity, effective configuration, result, source artifacts, limitations and cleanup. Model identity, tokens or cost remain explicitly unknown when the host does not expose the values. Immutable historical outcomes remain unchanged.

## Evidence and recommendations

Source inspection establishes content, compatibility prerequisites and available primary evidence. Installation telemetry and popularity supply discovery evidence. Recommendation eligibility requires bounded comparison in the target workflow against a no-plugin baseline, with actual activation evidence, independent behavioral/finding oracles, negative controls, measured quality outcomes and explicit time/cost limitations.

Unqualified or compatibility-only candidates remain distinguishable in manual catalog selection. The recommendation set can be empty when no candidate qualifies. A separate hosted marketplace, universal host support and favorable outcomes are outside the approved assumptions.

## Contract examples

| Case | Required outcome |
| --- | --- |
| Core-only install or plugin skip | Existing workflows remain usable with no new mandatory global stage. |
| Confirmed exact proposal | Install and enable displayed versions/bindings without invoking skills. |
| Missing delegated `grilling` resource or native tool | Report the missing requirement; never report wrapper execution as successful interview completion. |
| Enabled review pass fails after the core review | Retain a visible PR-readiness block; preserve the independent complete core review. |
| Interrupted interview or semantic task edit | Keep the same T-task/session; apply shared answer/revision/confirmation freshness rules. |
| Project defaults change during a parked run | Retain the recorded effective configuration; explicit reconciliation never fabricates successful execution. |
| Removed plugin remains required by another plugin/run | Report dependent or missing requirements and preserve shared resources/history. |
| Unsupported host or unexposed model identity | Retain honest compatibility/evidence limitations without claiming native or universal support. |

The workflow-decision task owns actual approval for concrete new stages, operation splits or unresolved material hook policies. Source/tool availability remains research, and unqualified runtime remains a validation gap rather than an assumed owner answer.
