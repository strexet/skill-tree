# Plugin Installation Interaction Contract

## Contract and implementation boundary

The [approved workflow decisions](plugin-workflow-decisions.md), [management contract](plugin-management-contract.md) and [ordered-occurrence amendment](../history/research/plugin-sequence-task-amendment.json) define the installation policy. The contract owns selection, preview, consent and stage outcomes. The management contract owns source intake, binding semantics and removal actions; the external plugin contract owns resource closure and invocation.

The current installer selects a flavor and installs core operations through provider-specific transactions. The current installer has no external-plugin selection, acquisition or management stage. The current source contains ten core operations; the approved complete core installation includes `skill-tree-plugins` after the manager implementation and eleven-operation qualification. The interactions below are the approved implementation specification rather than current executable CLI behavior. Installation supplies no skill invocation, workflow continuation or publication authority.

## Default installation and optional setup

The default path installs or updates core Skill Tree with zero new external plugins. Normal complete core installation includes the management operation without requiring an external package, task queue or initialized documentation. Explicit selection of individual core operations retains the existing scoped-selection contract.

The initial flow has separate core and optional-plugin stages:

1. Resolve the explicit target, flavor, selected providers and core operations through existing ownership, compatibility and stopped-handoff checks.
2. Install or verify the selected core destinations and report each provider result. Core provider transactions retain independent results; partial success is never described as complete core installation.
3. After every required selected core destination verifies, expose optional plugin setup with **Continue without new plugins** as the default and **Configure plugins** as the explicit alternative. A supplied explicit plugin-configuration request enters the same setup path.
4. Plugin setup browses known entries or accepts a direct source, configures the desired occurrences, resolves a concrete proposal and presents the complete change before plugin writes.
5. Actual matching confirmation acquires, stages and activates exactly the proposal through the owned plugin lifecycle. One project proposal covers the selected provider destinations; confirmation does not repeat per provider.
6. Report core and plugin results separately and expose later management through `skill-tree-plugins`. Setup never invokes the installed plugins.

Skipping, declining or intentionally cancelling optional setup preserves the successful core stage and all previously installed plugins, occurrence order and enabled states. A core provider failure leaves optional plugin mutation unattempted until the required core destinations verify. The installer never silently reduces a confirmed destination set to successful providers. A later retry reconciles existing provider results before applying a fresh matching proposal.

## Shared source and configuration flow

Optional initial setup and later `skill-tree-plugins` management use one proposal and mutation flow. Known entries include curated discovery metadata and project-added definitions. Direct catalog IDs, repository/path/ref URLs, raw instruction URLs and local files/folders enter the same configuration path. Claude or another authoring-host label never acts as an admission allowlist. Missing catalog data or an empty recommendation set leaves direct source selection and core-only continuation available.

Selection remains distinct from installation and execution. Recommendations show revision, application-specific evidence, qualification and limitations; recommendation status supplies no selection or consent. Explicit manual/custom selection remains available for unqualified candidates. Unresolved required source resources prevent package activation, while an explicitly displayed inactive package or unavailable binding can retain missing native-tool or unqualified-adapter status without claiming successful invocation.

Online source inspection is an explicit resolution action outside listing and dry-run. Source resolution establishes immutable revisions/content, required resource closure and expected digests before a mutation proposal becomes actionable. Resolution never executes upstream scripts or native dependency installers. Persistent known-source changes, package resources and binding changes require the corresponding matching mutation proposal; browsing or merely supplying a URL creates no installed package.

## Ordered occurrence controls

Each selected operation/anchor exposes the complete execution sequence. Every compatible plugin supports the same controls, regardless of curated/custom origin:

- Add a new occurrence, including another occurrence of the same installed package at the same anchor.
- Move an occurrence to an exact position while retaining the stable binding ID.
- Configure independent enabled state, conditions, extra instruction text and arbitrary JSON parameters for each occurrence.
- Remove one exact binding occurrence while retaining the package and remaining occurrences.

The setup preview displays occurrence IDs and positions rather than a deduplicated plugin list. Duplicate package references are valid; duplicate binding IDs are rejected. For example, `writing-for-agents` A, `grill-me` B and `writing-for-agents` C remain three configured occurrences. C receives task additions accepted after B through the generic sequential invocation contract. The ordering interface applies equally to arbitrary compatible plugins; candidate names supply no special execution rule.

Confirmed reorder/configuration changes create a new effective configuration. Parked runs retain the frozen sequence until explicit reconciliation and applicable re-admission. Package uninstall removes every live occurrence; exact unbind, disable and forget-known actions remain separate under the management contract. Installation or configuration changes never execute a chain to demonstrate success.

## Exact proposal and consent

An actionable proposal binds one stable request identity and a deterministic content digest to the expected project/plugin generation. The preview includes:

- Target project identity, core profile identity, expected registry/configuration generation, selected providers and exact destinations.
- Package IDs, immutable source revisions/content digests, entry paths, dependency/resource closure and owned resource additions, replacements or removals.
- Every operation/anchor and ordered binding occurrence, including stable occurrence IDs, positions, enabled states and conditions.
- Effective extra instruction text and JSON parameter values with origins, optional schema results and adapter/native-capability status.
- Readiness obligations, affected parked-run requirements, ownership conflicts and unresolved prerequisites.

Ordinary previews and receipts show secret reference names rather than resolved secret values. Machine-local acquisition locators remain separate from portable configuration. Core authority, context identity and required-check fields cannot be replaced through plugin parameters.

Actual owner confirmation identifies the displayed proposal and digest. Displaying a proposal, a preselected recommendation, silence, an agent recommendation or the existing `--yes` flag supplies no plugin consent. Confirmation authorizes installation and enablement of the exact displayed configuration; execution occurs later in an authorized operation. A changed revision, destination, occurrence order, parameter value, adapter state or readiness policy requires a refreshed proposal and matching confirmation.

Activation rechecks expected source, ownership and generation identities before writes. Stale proposals reject mutation. Exact duplicate confirmation first reconciles the original request/transaction and returns the matching original result; retry never creates another binding occurrence or overwrites an unrelated newer generation. A lost response remains an uncertain original operation until lifecycle reconciliation establishes the result.

## Noninteractive and read-only behavior

The approved CLI extension has an explicit interactive entry, `--configure-plugins`, and a structured noninteractive path, `--plugins <proposal.json>` with `--confirm-plugins <proposal-digest>`. The new options belong to the installer integration task; the current parser does not support the new options. Later manager actions consume the same proposal contract.

Noninteractive invocation without an explicit plugin request remains core-only. Existing `--non-interactive`, `--yes` and `-y` retain prompt-suppression semantics and never accept a plugin proposal. A noninteractive plugin mutation requires a complete resolved proposal plus explicit matching digest confirmation; missing, mismatched or stale confirmation leaves plugin state unchanged and reports a concrete prerequisite. Noninteractive processing never waits for chat input or invents an answer.

`--list`, known/installed inventory, `--verify` and `--dry-run` stay offline, read-only and free of plugin dispatch. Listing creates no queue, run, worktree or package cache. Dry-run reports proposed core/plugin changes and unresolved resolution requirements from supplied/local data; unresolved remote content produces an explicit prerequisite instead of network access or invented executable identity. Verify never enters optional setup. Explicit core uninstall does not implicitly uninstall external packages; plugin removal uses the exact owned management action.

## Repeat installation and stage recovery

Ordinary core repeat/update preserves existing plugin resources, bindings, order, disabled states and frozen run requirements. A matching unchanged generation is a verified no-op. No recommendation refresh or new curated entry silently installs, upgrades, reorders or enables a plugin. Requested source/configuration changes use a new proposal; a core flavor switch exposes affected plugin compatibility rather than silently dropping bindings.

Core and plugin activation have separate transaction outcomes. A failed or cancelled optional-plugin stage never rolls back a successfully verified core stage. A failed plugin replacement restores the prior matching plugin generation, registry and bindings together. Initial plugin failure leaves no partially active package or occurrence. Interrupted staging/journals remain available for owned recovery; unknown or modified content prevents destructive automatic rollback.

The plugin stage uses canonical installation/writer barriers, inspects affected retained runs and reaches a stopped cleanup/handoff point before activation. Changed generations preserve workflow progress and require explicit profile/configuration re-admission. Core checks, original local sources, shared resources, history and unrelated files remain outside incidental cleanup.

The result distinguishes core provider rows from plugin-stage states: `not-requested`, `skipped`, `cancelled`, `verified-no-op`, `installed`, `failed`, `blocked` or `recovery-required`. An intentionally inactive/unavailable configuration retains visible capability status and never reports successful invocation. Successful core installation with intentionally skipped/cancelled setup returns success; requested plugin mutation failure or an unresolved required core destination returns nonzero with both stage outcomes. Invalid arguments remain distinct from operation failure under the existing CLI error contract.

## Required qualification

The installer integration and manager tasks verify initial core-only installation, optional initial/later parity, direct/custom selection with an empty catalog, exact proposal confirmation, noninteractive rejection without matching consent, repeat preservation, separate provider/core/plugin failures, interrupted recovery, offline/no-write listing and dry-run, and stable ordered repeated occurrences with independent parameters. Cancellation and stale/replayed confirmation controls prove unchanged plugin state where required. Installed fixture evidence establishes lifecycle behavior; actual agent interpretation, native invocation and recommendation benefit require separate matching evidence.
