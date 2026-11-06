# Plugin Management Contract

## Approved scope and implementation boundary

[W3 owner approval](../history/research/plugin-management-decisions.json) defines a core-only default, optional plugin setup during installation and later management through `skill-tree-plugins`. The curated catalog supplies discovery and evidence annotations rather than an admission allowlist. The current source contains ten operations and no executable external-plugin management engine. The planned management operation is the eleventh core operation after implementation and qualification.

## Initial and repeat installation

The default path installs or updates core Skill Tree without acquiring, enabling or invoking a new external plugin. The core includes `skill-tree-plugins` even with zero external packages. Optional plugin setup offers known entries and direct source input; the same configuration flow serves initial setup and later management. Recommendations can be displayed with evidence status, but no plugin is selected automatically.

A core update preserves already installed packages, bindings and frozen run requirements. Continue without new plugins never means uninstall existing plugins. Core activation and optional plugin activation have explicit transaction boundaries: a failed or cancelled optional-plugin stage preserves the successful core installation and leaves no partially activated plugin generation. Installed resources and bindings remain unchanged until a matching plugin proposal is confirmed.

## Offline management entry point

Opening `skill-tree-plugins` uses a no-dispatch inventory path and shows installed/known views without network acquisition, including immediately after core installation before task documentation or future.md exists. Raw inventory bypasses plugin hooks and starts no queue, controller or worktree. Explicit management workflow actions can dispatch configured management anchors; a read-only view never hides plugin execution. The installed view shows stable plugin IDs, exact source/content revisions, destinations, all binding IDs/locations, enabled state, order/conditions, parameter summaries, adapter status and dependency or parked-run requirements. The known view combines curated entries and project-added sources, identifies installed state and separates suggested locations from actual bindings.

The management agent accepts direct natural-language actions such as adding a supplied URL, placing a selected skill after Processing with extra instructions, changing one binding or removing a selected package. The agent resolves the request into a concrete preview. Read-only inspection and discovery require no installation confirmation. A sufficiently explicit exact removal instruction or one matching mutation confirmation starts the owned action; nested approval dialogs add no authority.

| Action | Owned outcome |
| --- | --- |
| Add source / save as known | Register a project-known source definition without installing or enabling a package. |
| Install / configure | Resolve resources, adapter, bindings and parameters; confirm and activate exactly the displayed proposal. |
| Bind / unbind | Add or remove one location while preserving the package and other bindings. |
| Enable / disable | Change a selected binding without deleting package resources or history. |
| Update | Resolve an explicit source revision/content update, show changed resources and configuration, and activate through the guarded lifecycle. |
| Uninstall package | Preview and remove the exact owned package and every current project binding referencing the package, preserving shared resources, original source and history. |
| Forget custom source | Remove the project discovery definition independently of installed state. Uninstall normally leaves the source known for reinstall. |

## Open source intake and adaptation

Accepted source descriptions include catalog IDs, repository URLs with path/ref, GitHub/GitLab skill links, raw instruction-document URLs and local files/folders. An entry need not originate from Codex or appear in the curated catalog. Claude and other authoring-host labels remain provenance/capability facts rather than rejection rules.

Source resolution records a stable project identity and an immutable repository revision or content snapshot. Owned snapshot paths remain repository-relative; absolute local acquisition paths and credential-bearing locators stay machine-local and outside portable descriptors/exports. A relocated project can explicitly rebind the original source without changing an installed content snapshot. Upstream bytes, metadata, local resource references and attribution remain preserved. Nonstandard instruction documents receive a separate owned wrapper/adapter rather than silent upstream rewriting. Discovery imports never execute scripts or native package installers. Local original files remain outside uninstall ownership.

Known registration, resource installation, binding configuration and verified invocation are separate states. Required source resources must resolve before a package generation activates. Missing native tools or an unqualified adapter can leave an installed package visibly inactive or a configured binding visibly unavailable. A missing native requirement never becomes a successful call. The selected host uses a native adapter when available or an explicitly described source-backed translation with visible limitations.

Custom source definitions own discovery metadata; `.skill-tree/installation/plugins.json` remains the single installed-state authority. Views merge curated/custom definitions with installed state without another authoritative installed list. Repeated source input reuses a matching known identity or presents a collision/update proposal, preserving an unrelated entry.

## Extensible placement

Before/during/after bindings cover all owned operations, including intake, snapshot, clarification, controllers and plugin management where the dispatcher exposes the boundary. Registered named internal anchors extend the standard phases and can describe project-specific workflow steps. A free-text placement request resolves to an exact executable anchor in the preview; an unresolved location remains a visible unbound/prerequisite state rather than a successful integration label.

Core selection, task identity, required checks, authorization and writer/installation transaction boundaries remain mandatory. An anchor registration describes a real dispatch boundary; a name alone executes nothing. Context compatibility is checked per binding. Every call has attempt/binding/event identity and a typed operation context: request/project scope for pre-ID intake, document/snapshot scope, management proposal scope, controller scope or actual Pending/task/group/review identity as applicable. Pre-promotion Processing uses real Pending identities; no fabricated task or premature promotion supplies a task-free anchor context.

Each binding has independent identity, order, optional condition and parameter overrides. Explicit controller and leaf bindings are distinct intended calls. Accidental repeat delivery deduplicates the same binding/event/attempt rather than suppressing another deliberate placement. Dispatch lineage detects recursive re-entry or cycles and returns a visible unresolved outcome under the existing no-progress policy. Management changes never invoke newly installed skills as a side effect of listing or activation.

## Additional parameters

Plugins accept extra instruction text and arbitrary JSON values. A plugin may declare an optional schema; validation and unsupported-schema limitations remain visible. Effective values resolve in order: upstream defaults, project plugin values, binding overrides and explicit per-run overrides. The preview shows resulting values and origins. The selected adapter receives the actual resolved JSON values and extra instruction text in a separate input envelope. Passing a digest alone is insufficient; marker-based adapter/agent fixtures prove that selected overrides reach the skill and superseded values do not. Parameters never replace core identity, authority or execution fields.

Attempts/receipts freeze effective parameter, source, binding, adapter and configuration digests. A changed value creates a current proposal/attempt rather than silently altering a parked execution. Explicit secret references retain reference names in previews/history; resolution occurs only in the allowed invocation context, and resolved secrets are omitted from ordinary views and receipts.

## Mutation and removal integrity

Package and binding activation, update, rollback and removal use owned recoverable transactions and the canonical installation/writer barrier. Affected active invocations reach a stopped cleanup/handoff point; changed generations require explicit re-admission. Staging and matching consent cover the exact displayed resources and configuration.

Removal preview identifies affected bindings, destinations, retained shared resources and dependent or parked requirements. Unknown or edited ownership rejects deletion rather than adopting content through force. Removing an original local source is outside package uninstall. Removing a required package/binding preserves the frozen run's missing requirement and historical outcomes. An explicit later reconciliation can change the requirement without claiming earlier execution success.

## Qualification

Fixtures cover zero-plugin initial install, optional initial/later setup, repeat preservation, offline known/installed views, curated and noncatalog imports, raw/local instruction wrappers, Claude-shaped metadata, absent native capabilities, source drift, parameter precedence/schema/secret-reference handling, all-operation/named anchors, explicit multiple bindings, replay/recursion, no-task/no-documentation bootstrap contexts, raw inventory dispatch bypass, single-binding removal, complete live-binding cleanup on package uninstall and known-entry forgetting.

Standalone general/web/unity packages include required helpers/resources without source-checkout or sibling-package dependency. Controlled actual-agent management scenarios record observed request interpretation and exact proposals separately from deterministic helper fixtures. Package installation and a source-backed Codex case supply no universal native-host or candidate-efficacy qualification.
