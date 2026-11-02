# Installation Profile

The selected project root receives exactly one flavor: general, web or unity. Eight stable `skill-tree-*` operation names carry common invariants plus selected domain sections. The registry declares section slots and exact resource replacements; owner authorization, selection, checkpoint integrity, truthful evidence and publication boundaries are non-replaceable.

Composition is deterministic and static. The capability resolver reads configuration as data, records known/absent/ambiguous/unsupported facts and emits concrete applicable recipes. Installation never evaluates project configuration, executes application code, upgrades dependencies or initializes documentation. Missing optional infrastructure does not prevent installation. Unknown essential compatibility produces a clear error.

`.skill-tree/installation/profile.json` owns flavor, project identity, bounded input/inventory digests, recipes, capability gaps, source/output digests and provider destinations. Mutable workflow state remains separate. Project-scoped copy installation is supported; specialization through global, symlink or uncomposed upstream installation fails before writes.

Owned matching packages support verified no-op, replacement and uninstall. Unowned or locally modified packages conflict even with `--force`. Complete staging, ownership validation, locking, journal/backups and recoverable destination replacement precede activation. Verification checks complete inventory/content, identity, flavor, bridge and profile freshness.

The self-contained local manager locates the target from the maintenance bundle and refreshes using installed source modules without source-checkout/network access. Explicit refresh preserves queue/checkpoint identities and required obligations. Active execution reaches a stopped cleanup/handoff point before activation. Failed refresh preserves the stale prior generation. Profile activation supplies no continuation instruction.

Implementation admission checks bounded input digests once per invocation/resume and pins the profile in the checkpoint. Nested focused iterations reuse admission. Stale inputs return the exact local refresh command; read-only inspection and intake remain available. A toolchain change ends admission. Authorization and process/isolation verification remain execution-time requirements.

A missing foundational test framework persists as one deduplicated setup finding. Normal Add Pending captures or reuses the finding at highest-open-plus-one priority after a queue exists, returning the Pending ID. Setup covers framework research/selection, compatible configuration, meaningful smoke coverage, focused commands and profile refresh. Missing optional specialist packages never create automatic top-priority work. Intake and readiness grant no package upgrade or product-execution permission.

Activation validates workflow schema 2 and refuses unresolved prepared operations. Workflow writers and installation transactions honor both owned locks. Destination snapshots bind ownership validation to activation; a concurrent edit during staging stops replacement. A changed generation marks a waiting controller stopped and requires explicit profile re-admission. Rollback preserves current workflow progress and never restores an older checkpoint from package backups.

Shared provider destinations retain an explicit provider reference set. Scoped uninstall releases the selected provider and retains packages/bridges referenced by another provider. Verification re-resolves static facts and recomposes expected standalone bytes from the verified local bundle; matching edited hashes alone cannot establish the installed flavor/policy. Package declarations retain separate declared-version provenance; version-specific resources require resolved lock evidence. Required UTF compatibility without resolution returns one installation-time error. Task check preparation substitutes concrete argument-vector parameters without shell evaluation.

Activation rechecks relevant project inputs after staging. Failed verification restores a matching owned generation while retaining current project inputs and workflow progress. Conflicting external edits preserve generation backups and stop automatic restoration. Opaque input digests use raw bytes rather than decoded text.

## Isolated Unity execution bindings

An explicit `.skill-tree/validation-recipes.json` can declare `execution_bindings`. Each binding owns a repository-relative local locator, execution subdirectory, queue/execution source paths, workspace runner/profile paths, source-review path and exact Editor/CLI/Pipeline/UTF pins. The ignored `.skill-tree/local/` locator records the exact machine-local queue and workspace roots. Portable declarations contain no absolute paths. The generated machine-bound installation receipt records resolved roots and current content digests.

Static composition reads source bytes only. Complete source snapshots include fixture-only and extra files; the review classifies every difference as fixture, encoding or unqualified with exact queue/execution hashes and a reason. Unqualified differences remain product-execution blockers. A source, runner, locator, review or pin change requires reviewed profile refresh. Missing paths, symlinks, overlapping roots, foreign queue identities and non-Unity recipe relabeling fail before activation or product operations.

Bound recipes retain Unity lanes. `{project_root}` resolves to the reviewed execution checkout; `{queue_root}` retains the single task authority; `{binding_workspace}` resolves the reviewed runner workspace. Check parameters cannot override reserved roots. Product sessions additionally match the queue, binding, source digest, CLI/Pipeline pins, Editor, ownership evidence, deadline, cleanup and save/service isolation. Static identity verification grants no Editor launch, admission into a stopped game controller or runtime acceptance.

A binding declaration uses the following shape. Snapshot exclusions are explicit reviewed repository-relative paths; a required check source cannot appear in the exclusions. `.git`, `__pycache__` and `.DS_Store` entries remain outside source snapshots.

```json
{
  "schema": 1,
  "execution_bindings": {
    "isolated": {
      "locator": ".skill-tree/local/isolated.json",
      "execution_subdir": "scratch/pilot",
      "source_paths": ["Assets", "Packages", "ProjectSettings"],
      "exclude_paths": [],
      "workspace_paths": ["scripts/runner.py", "docs/validation-profile.md"],
      "review_path": ".skill-tree/validation/isolated-review.json",
      "pins": {
        "editor_version": "6000.3.27f2",
        "cli_version": "1.0.0-beta.10",
        "pipeline_version": "0.7.0-exp.1",
        "utf_version": "1.6.0"
      }
    }
  },
  "recipes": {
    "isolated-check": {
      "lane": "unity-playmode",
      "editor_version": "6000.3.27f2",
      "execution_binding": "isolated",
      "argv": ["python3", "{binding_workspace}/scripts/runner.py", "--project", "{project_root}"],
      "input_paths": []
    }
  }
}
```

The example pins describe data syntax, not a qualified toolchain combination. The review records schema 1, queue/execution/workspace snapshot digests and a complete `differences` list with `path`, exact nullable `queue`/`execution` SHA-256 values, `classification` and `reason`. The locator records schema 1 plus exact absolute machine-local `queue_root` and `workspace_root`. The generated receipt never replaces an owner authorization or actual toolchain check.
