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

The installation receipt and concrete profile reside at `.skill-tree/installation/profile.json`. The local manager resolves the target from the bundle location, independent of caller working directory and source checkout.

```sh
node .skill-tree/installation/manager.js --verify
node .skill-tree/installation/manager.js --refresh-profile --dry-run
node .skill-tree/installation/manager.js --refresh-profile
node .skill-tree/installation/manager.js --recover
node .skill-tree/installation/manager.js --rollback
```

Refresh is static, offline and explicit. Relevant input/inventory changes require refresh; unsupported compatibility requires a scoped bundle/source update. Queue/checkpoint identities and acceptance obligations survive refresh. Rollback restores one retained package/receipt generation; project dependencies remain unchanged and freshness still requires verification. Failed/interrupted replacement retains recoverable staging/journal evidence. Lock removal requires verified owner PID/host; stale locks are never removed automatically.

Documentation setup remains separate: invoke `skill-tree-repo-documentation`. After queue creation, invoke the installed helper `scripts/workflow-state.py capture-foundation <project-root>` and report the captured/reused Pending ID. Missing foundational tests produce one highest-open-plus-one setup task through normal intake, research and selection. Installation never runs workflow helpers, installs project dependencies or executes product code.

Non-JavaScript projects and unsupported executable configuration use `.skill-tree/validation-recipes.json`: schema 1 contains `recipes` keyed by stable recipe ID, each with a lane, argument-vector command and relevant repository-relative `input_paths`. Use existing pinned tools and environment-variable references instead of inline credentials. Explicit recipes supplement declared package scripts without overriding recipe IDs. Required unknown versions or incompatible formats stop with a concrete error; missing tests alone do not prevent installation.

Resolved package capabilities use supported npm lockfile 2/3 or Unity package-lock evidence. Exact declarations remain declared facts rather than resolved versions. Unresolved optional Web specialization is reported as a capability gap and omitted from generated instructions; required UTF flags need a supported resolved version before composition. Other package-manager lockfiles remain fingerprinted static inputs and can use explicit owner-declared recipes without guessed version-specific APIs. Recipe lanes use the versioned capability registry; task parameters become concrete argument-vector values at check preparation.

Provider references protect shared discovery destinations such as `.agents/skills`. Removing one provider retains a package or bridge still referenced by another provider. Verification includes deterministic recomposition from the owned bundle, resolved facts, package identities and complete inventories. Installer output reports profile/environment identities, input fingerprints, package identities/provider references and validation policy.
