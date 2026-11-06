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
| Add occurrence / reorder | Add the same package again at the same anchor or move an existing binding occurrence while preserving the binding ID; preview every occurrence in execution order. |
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

Each binding occurrence has independent identity, order, enabled state, optional condition and parameter overrides. Every compatible catalog or custom plugin can appear repeatedly at the same anchor without duplicate package installation. Initial setup and later `skill-tree-plugins` management expose the same add-occurrence, move, configure and exact-remove controls. Moving an occurrence preserves the binding ID. Removing one occurrence preserves the package and remaining occurrences. The preview displays the complete ordered chain; matching confirmation activates exactly the displayed sequence.

Sequential dispatch passes the latest accepted guarded context to the next occurrence. A configured after-Processing chain of `writing-for-agents` A, `grill-me` B and `writing-for-agents` C invokes both editorial occurrences; C reviews the task additions accepted after B. The mechanism applies to arbitrary compatible plugins rather than hard-coded candidate names. Waits, failures and unresolved required rework preserve incomplete chain state and occurrence receipts. Resume uses the frozen order and reconciles original attempts; a project reorder never silently changes a parked run. Expected downstream edits retain earlier stage-input history while affected final checks require current evidence.

Explicit controller and leaf bindings remain distinct intended calls. Accidental repeat delivery deduplicates the same binding/event/attempt rather than suppressing another deliberate occurrence. A finite A-to-B-to-A sequence is valid and does not imply recursive re-entry. Dispatch lineage detects actual recursive re-entry or cycles and returns a visible unresolved outcome under the existing no-progress policy. Management changes never invoke newly installed skills as a side effect of listing or activation.

## Additional parameters

Plugins accept extra instruction text and arbitrary JSON values. A plugin may declare an optional schema; validation and unsupported-schema limitations remain visible. Effective values resolve in order: upstream defaults, project plugin values, binding overrides and explicit per-run overrides. The preview shows resulting values and origins. The selected adapter receives the actual resolved JSON values and extra instruction text in a separate input envelope. Passing a digest alone is insufficient; marker-based adapter/agent fixtures prove that selected overrides reach the skill and superseded values do not. Parameters never replace core identity, authority or execution fields.

Attempts/receipts freeze effective parameter, source, binding, adapter and configuration digests. A changed value creates a current proposal/attempt rather than silently altering a parked execution. Explicit secret references retain reference names in previews/history; resolution occurs only in the allowed invocation context, and resolved secrets are omitted from ordinary views and receipts.

## Source and parameter foundation

The pure helpers in `.skill-tree/lib/plugin-sources.js` and `.skill-tree/lib/plugin-parameters.js` expose acquisition preparation and parameter resolution separately from lifecycle activation. The `.skill-tree/lib/plugins.js` facade imports no composer, installer or workflow controller. The helpers create no installed package, known-source registry, task queue or run. Lifecycle, dispatch and management integration remain separate implementation tasks.

`normalizeSource(input, {known, baseDir})` returns a portable `definition` and a separate acquisition `locator`. Input accepts known IDs, source URLs, local files/folders or explicit source objects. Known definitions retain original metadata and authoring-host labels. Local absolute paths and URL credentials/query values remain in the locator rather than portable definitions. A conflicting package ID requires an explicit source-change proposal instead of silently adopting another source.

`resolveSource(normalized, options)` reads local files directly. Remote resolution requires an explicit `acquire({definition, locator})` adapter returning actual resource bytes and an immutable repository commit when applicable; absence returns `source-acquisition-required`. The helper closes declared resources/dependencies and relative Markdown links, preserves original bytes and frontmatter, and rejects missing, escaping, symlinked or changed resources. Adapter overlays remain separate from upstream content. A complete snapshot retains `unqualified` or missing-capability `unavailable` execution status; acquisition supplies no native execution evidence. `verifySnapshot(snapshot)` checks the staged resource/content identity without reacquisition or execution.

`resolveParameters({upstream, project, binding, run, schema})` accepts optional layers containing `values` and `instructions`. JSON objects merge recursively; arrays, scalar values and null replace earlier values. Omission preserves an earlier value. The highest explicitly provided instruction string wins, including an empty string. Exact secret-reference objects replace atomically and remain unresolved. Resolution preserves input objects and returns effective values/text, JSON Pointer origins, a deterministic digest, schema status and secret-reference names. Plugin keys such as `mode` and `authority` remain data inside `values` and never become core envelope fields.

The optional schema subset supports boolean schemas, scalar `type`, `properties`, `required`, `additionalProperties`, `items`, `enum`, `const`, numeric bounds and string/array length bounds. Unsupported constraints fail explicitly with `parameter-schema-unsupported`; supported validation failures use `parameter-schema`. A missing schema reports `absent`; successful supported validation reports `validated`. Non-JSON values, cycles, sparse arrays and accessors reject as `parameter-json`. Configuration never resolves secrets, executes getters or fetches schema references.

## Mutation and removal integrity

Package and binding activation, update, rollback and removal use owned recoverable transactions and the canonical installation/writer barrier. Affected active invocations reach a stopped cleanup/handoff point; changed generations require explicit re-admission. Staging and matching consent cover the exact displayed resources and configuration.

Removal preview identifies affected bindings, destinations, retained shared resources and dependent or parked requirements. Unknown or edited ownership rejects deletion rather than adopting content through force. Removing an original local source is outside package uninstall. Removing a required package/binding preserves the frozen run's missing requirement and historical outcomes. An explicit later reconciliation can change the requirement without claiming earlier execution success.

## Qualification

Fixtures cover zero-plugin initial install, optional initial/later setup, repeat preservation, offline known/installed views, curated and noncatalog imports, raw/local instruction wrappers, Claude-shaped metadata, absent native capabilities, source drift, parameter precedence/schema/secret-reference handling, all-operation/named anchors, explicit multiple bindings, same-anchor repeated packages, reorder/cancel/resume, per-occurrence context/parameters, replay/recursion, no-task/no-documentation bootstrap contexts, raw inventory dispatch bypass, single-binding removal, complete live-binding cleanup on package uninstall and known-entry forgetting.

Standalone general/web/unity packages include required helpers/resources without source-checkout or sibling-package dependency. Controlled actual-agent management scenarios record observed request interpretation and exact proposals separately from deterministic helper fixtures. Package installation and a source-backed Codex case supply no universal native-host or candidate-efficacy qualification.
