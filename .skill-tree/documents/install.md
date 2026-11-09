# Installation

Local installation requires Node.js 18 or later. Workflow helpers require Python 3.9 or later and the standard library. One explicitly selected project root receives one flavor and project-scoped copy packages.

```sh
node .skill-tree/bin/install.js --list
node .skill-tree/bin/install.js --target <project-root> --only codex --flavor unity --copy --dry-run
node .skill-tree/bin/install.js --target <project-root> --only codex --flavor unity --copy
node .skill-tree/bin/install.js --target <project-root> --only codex --verify
```

Fresh noninteractive installation requires `--flavor general|web|unity`; interactive installation asks once. `--yes` never chooses a flavor. Repeat installation retains the receipt flavor; explicit switches regenerate all owned packages in the scope. `--skills` selects logical operations. `--all` selects non-soft provider-matrix entries; soft providers require explicit selection. Generic provider target denotes the covered root and explicit discovery destination. Global, symlink and uncomposed upstream specialization fail before writes.

Dry-run reports facts, gaps, exact changed destinations and ownership conflicts without writes. Matching installations are verified no-ops. `--force` cannot adopt unowned content or discard local modifications. A stopped cleanup/handoff checkpoint precedes replacement during a controller. Optional `--with-init` inserts a receipt-owned bridge while preserving surrounding instructions. Scoped `--uninstall` removes only matching owned packages; `--with-init` removes the bridge when no packages remain.

The installation receipt and concrete profile reside at `.skill-tree/installation/profile.json`. The `source_version` field identifies the source release; `config/flavors.json` owns the bundled release version and matches root `package.json`. Composed project profiles expose the same version. The local manager resolves the target from the bundle location, independent of caller working directory and source checkout.

```sh
node .skill-tree/installation/manager.js --verify
node .skill-tree/installation/manager.js --refresh-profile --dry-run
node .skill-tree/installation/manager.js --refresh-profile
node .skill-tree/installation/manager.js --recover
node .skill-tree/installation/manager.js --rollback
node .skill-tree/installation/manager.js --rebind
```

Refresh is static, offline and explicit. Relevant input/inventory changes require refresh; unsupported compatibility requires a scoped bundle/source update. Queue/checkpoint identities and acceptance obligations survive refresh. Rollback restores one retained package/receipt generation for the current project root; project dependencies remain unchanged and freshness still requires verification. Pending core or plugin journals block verification and rollback until explicit recovery. Failed/interrupted replacement retains recoverable staging/journal evidence. Lock removal requires verified owner PID/host; stale locks are never removed automatically.

The local manager accepts exactly one operation. `--dry-run` applies only to `--refresh-profile`; unsupported combinations reject before writes. A relocated owned installation uses explicit `--rebind` after review. Rebinding verifies existing package/bundle bytes, composition and current inputs before changing the receipt root. The retained package generation remains available at the rebound root. Unknown ownership, local edits and pending installation transactions remain blockers. Rebinding never launches a workflow helper.

For a clean clone with a retained schema-3 queue, explicit `workflow-state.py recover-locator <project> --input <recovery.json>` restores the machine-local locator. The request contains the exact `queue_id` and a `worktrees` object covering every unfinished run. Completed delivery mappings can be omitted; historical checkpoints and terminal outcomes remain unchanged. A linked controller worktree retains the canonical queue owner.

Source-role recipes in `.skill-tree/config/repository.json` feed installed composition with stable recipe IDs and declaration fingerprints. Target recipes reside in `.skill-tree/validation-recipes.json`. Duplicate IDs across package scripts or declarations reject composition.

The installed receipt and concrete project profile expose the built-in `static-inspection` recipe when the project leaves the ID undeclared. The built-in recipe uses the static lane with explicit source and artifact assertions, an empty input-path list and no command vector. An explicit recipe with the same ID takes precedence. Older owned profiles verify against the installed bundle, and the workflow helper resolves the same fallback. An update from current source adds the discovery entry.

Documentation setup remains separate: invoke `skill-tree-repo-documentation`. After queue creation, invoke the installed helper `scripts/workflow-state.py capture-foundation <project-root>` and report the captured/reused Pending ID. Missing foundational tests produce one highest-open-plus-one setup task through normal intake, research and selection. Installation never runs workflow helpers, installs project dependencies or executes product code.

Non-JavaScript projects and unsupported executable configuration use `.skill-tree/validation-recipes.json`: schema 1 contains `recipes` keyed by stable recipe ID, each with a lane, argument-vector command and relevant repository-relative `input_paths`. Use existing pinned tools and environment-variable references instead of inline credentials. Explicit recipes supplement declared package scripts without overriding recipe IDs. Required unknown versions or incompatible formats stop with a concrete error; missing tests alone do not prevent installation.

Resolved package capabilities use supported npm lockfile 2/3 or Unity package-lock evidence. Exact declarations remain declared facts rather than resolved versions. Unresolved optional Web specialization is reported as a capability gap and omitted from generated instructions; required UTF flags need a supported resolved version before composition. Other package-manager lockfiles remain fingerprinted static inputs and can use explicit owner-declared recipes without guessed version-specific APIs. Recipe lanes use the versioned capability registry; task parameters become concrete argument-vector values at check preparation.

Provider references protect shared discovery destinations such as `.agents/skills`. Removing one provider retains a package or bridge still referenced by another provider. Verification includes deterministic recomposition from the owned bundle, resolved facts, package identities and complete inventories. Installer output reports profile/environment identities, input fingerprints, package identities/provider references and validation policy.

## Installed plugin inventory

The source installer and installed manager expose offline installed-plugin views without flavor/provider selection, Future initialization, source acquisition or plugin dispatch. Human output groups the current occurrences by plugin or integration point; JSON includes the full installed and point projections.

```sh
node .skill-tree/bin/install.js --list-plugins --target . --json
node .skill-tree/bin/install.js --list-plugins --target . --group-by point
node .skill-tree/installation/manager.js --list-plugins --json
node .skill-tree/installation/manager.js --list-plugins --group-by plugin
```

The inventory retains source/revision/content identities, owned destinations, dependencies, recorded adapter/capability state and every ordered occurrence. Global and per-point positions use one-based numbering. Repeated package references retain separate IDs, conditions, enabled states, reference-level parameters and extra instructions. Enabled configuration supplies no successful invocation evidence.

Readable resource drift remains visible with diagnostics. Opaque or foreign ownership remains unavailable without recovery or adoption. Exit codes are zero for a healthy view, one for readable drift and two for unavailable state or invalid arguments. The list route rejects installation-option mixtures; JSON and grouping options require the list route.

Frozen HC requirements remain separate from current defaults. The view records chain state and verified, foreign or uncertain installation association without claiming readiness. Removal preserves frozen state and can expose missing requirements. The installed `skill-tree-plugins` operation previews and applies exact-ID changes through the [shared management backend](plugin-management-contract.md#installed-inventory-and-exact-id-management).

## Optional external plugins

A complete core installation includes `skill-tree-plugins` and adds zero external plugins by default. A terminal offers to continue without new plugins or configure plugins after every selected core destination verifies. Use `--configure-plugins` to enter setup directly.

```sh
node .skill-tree/bin/install.js --target <project-root> --only codex --flavor general --configure-plugins
node .skill-tree/bin/install.js --target <project-root> --only codex --plugins <proposal.json> --confirm-plugins <proposal-digest> --non-interactive
```

Setup groups known candidates by workflow point and accepts direct source URLs, local files or directories, and typed source descriptors. The `request` option accepts the same manager request as inline JSON or `@file`. For an ordered chain, supply the complete array of binding occurrences. Each occurrence carries a separate ID, plugin, location, parameters, enabled state, optional condition and extra instructions. Repeating a package in one location uses a distinct ID for each occurrence.

An eligible recommendation appears only when the catalog has qualifying evidence for the selected flavor and host. The current recommendation sets are empty. Individual known or custom sources remain selectable. The terminal asks before resolving a remote source and shows the exact proposal before asking whether to activate the proposal. `--yes` only suppresses prompts. A structured request requires a matching proposal digest. Save the `proposal` object from a manager preview as the proposal file.

The structured result separates core provider rows from `plugin_stage`. Skipping or cancelling keeps verified core and existing plugin state. A provider failure blocks the plugin stage. An interrupted plugin transaction requires explicit owned recovery. `--dry-run` with a supplied proposal compares the proposal with the offline plan and skips activation. Installation never invokes a selected plugin or starts a parked run. See the [installation contract](plugin-installation-contract.md) for consent and recovery details.

### Remove an installed plugin by ID

Run `skill-tree-plugins` and select the exact plugin ID from the installed inventory. The uninstall preview lists every binding occurrence, the affected package resources and the frozen run requirements. Confirm the exact preview to apply the removal. Use an exact binding ID with `unbind` when only one occurrence should be removed.

For a Codex installation, the equivalent typed preview command from the project root is:

```sh
printf '%s\n' '{"action":"prepare","request":{"action":"uninstall","request_id":"remove-example-plugin","plugin_id":"example-plugin"}}' |
  node .agents/skills/skill-tree-plugins/scripts/plugin-manager.js --project-root . --input -
```

Pass the returned `proposal` and `confirmation` containing the reviewed `proposal_digest` to the manager with `action: "apply"`. The installed registry is `.skill-tree/installation/plugins.json`. The owned manager applies the confirmed change and preserves frozen run requirements for explicit reconciliation.
