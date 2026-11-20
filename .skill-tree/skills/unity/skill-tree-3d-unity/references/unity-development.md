# Unity Development

Use the concrete profile's pinned Editor, UTF, assembly inventory, UI resources and named recipes. Static compatibility is distinct from runner qualification. Preserve package pins, serialized fields, GUIDs and existing architecture. Missing foundational tests require the deduplicated setup intake; a missing optional specialist package supplies no automatic top-priority task or upgrade permission.

Prefer deterministic rules/state transitions with explicit clock, randomness, persistence and service inputs. Keep a minimal behavior-preserving test seam inside the selected change. A broader necessary seam becomes one required researched descendant with exact coupling, blocked assertion and preservation checks; optional architecture work stays deferred. Keep lifecycle adapters small without imposing a DI framework or ScriptableObject rewrite.

UTF EditMode is the executable default for suitable domain/configuration/Editor assertions. UTF PlayMode in Editor covers Awake/OnEnable/Start ordering, frame/coroutine behavior, physics, scenes and runtime bindings through a focused isolated fixture. Player/native/AOT and physical-device assertions require matching build/device scope. A frame-related defect alone never justifies normal-level traversal. EditMode still executes inside an authorized Unity Editor.

Run the profile recipe with an explicit test filter and result/log paths in an authorized matching Editor lifecycle. Parse NUnit XML and logs, require nonzero expected discovery and preserve failures/skips. A successful launch or CLI transport is not a passing test suite. Use deterministic NUnit assertions for domain behavior and bounded UnityTest frame/condition assertions for lifecycle. Never silently omit asynchronous fixtures through incompatible synchronous options.

Reuse one owned Editor/controller per exact checkout; record PID, process start and project identity after a fresh unrelated-Editor preflight. Verify save/service isolation, deadlines and cleanup before runtime checks. Reuse suitable isolated scenes/prefabs, restore static state, event subscriptions, temporary objects and time settings. No save reset, backend call, generated-solution build or package upgrade is implicit.

Warm-Editor iteration preserves lifecycle acceptance. Disabled domain reload requires proven static/event cleanup and separate configuration scope; startup semantics retain a cold-start regression. Focused test assemblies can reduce measured compilation cost, but moving runtime/Editor code requires assembly-dependency and serialization review. No assembly-per-class rule exists.

Performance fixes identify the changed hot path, representative workload and actual allocation/timing/resource assertions. Record first-failure evidence and investigate flakiness instead of retrying until Green. Editor timing never qualifies mobile release performance; development-Player and release-Player results remain distinct. Mutation experiments use authorized isolated UTF/harness execution with guaranteed restoration, never an unrequested generated-solution build.

## Organize feature assets

Keep a prefab and dedicated feature assets together within the project's established layout. Create only the subfolders the feature needs. Keep types and UI controls used across features with the shared owner. Preserve script assembly membership. Check the nearest assembly definition or assembly reference before moving scripts within authorized scope. Preserve the `.meta` files for moved files and folders so existing GUID references and import settings survive.

The example shows dedicated Goblin assets, a script-only shield feature, and a standalone inventory screen that uses the same shared item slot as the equipment screen.

```text
Assets/Features/Goblin/README.md
Assets/Features/Goblin/catalog.json
Assets/Features/Goblin/Model/Goblin.fbx
Assets/Features/Goblin/Textures/GoblinAlbedo.png
Assets/Features/Goblin/Materials/Goblin.mat
Assets/Features/Goblin/Scripts/GoblinBehaviour.cs
Assets/Features/Goblin/Animations/Goblin.controller
Assets/Features/Goblin/Animations/Idle.anim
Assets/Features/Goblin/Animations/Attack.anim
Assets/Features/Goblin/Prefabs/Goblin.prefab
Assets/Features/Goblin/UI/GoblinHealthBar.uxml

Assets/Features/ShieldRecharge/ShieldCharge.cs
Assets/Features/ShieldRecharge/ShieldRecharge.cs
Assets/Scripts/Enemies/EnemyBehaviour.cs

Assets/UI/Screens/Inventory/Inventory.uxml
Assets/UI/Screens/Inventory/InventoryPresenter.cs
Assets/UI/Screens/Equipment/Equipment.uxml
Assets/UI/Shared/ItemSlot.uxml
```

The shield scripts form one small feature and need no separate index. The inventory layout and presenter stay with the screen. The inventory and equipment screens both refer to the shared item slot.

The README at `Assets/Features/Goblin/README.md` gives the usage and entry point. Resolve sample README links from the README directory.

```markdown
# Goblin

Encounter scenes spawn the goblin enemy. Start at the [prefab][goblin-prefab].
The [catalog][goblin-catalog] points to the attack behavior and the shared base type.

[goblin-prefab]: Prefabs/Goblin.prefab
[goblin-catalog]: catalog.json
```

The adjacent catalog lists only selected files. Every entry and relationship `path` is relative to the Unity project root. Every entry has a `purpose`. Use `extends` for a base type or `implements` for an interface, with the actual type and declaring file path. Include `source`, `date` or `version` only when provenance matters and the value is absent from the owning record. The code and asset references own the real relationships. Maintain catalog and README links when the referenced paths change.

```json
{
  "entries": [
    {
      "path": "Assets/Features/Goblin/Prefabs/Goblin.prefab",
      "purpose": "Spawns the configured goblin in encounter scenes"
    },
    {
      "path": "Assets/Features/Goblin/Scripts/GoblinBehaviour.cs",
      "purpose": "Controls the goblin attack",
      "extends": {
        "type": "EnemyBehaviour",
        "path": "Assets/Scripts/Enemies/EnemyBehaviour.cs"
      }
    }
  ]
}
```

Unity imports Markdown and JSON under `Assets` as text assets. Check project-specific importers, addressable asset rules and build inclusion before placing documentation beside a prefab. Keep guidance out of runtime-loaded `Resources` and copied `StreamingAssets` unless the project intentionally ships the files. When guidance must avoid asset import, keep the README and catalog under the project's documentation root and update the links while retaining the catalog's Unity-project-relative path base.

See the Unity Manual for [asset metadata](https://docs.unity3d.com/6000.0/Documentation/Manual/AssetMetadata.html), [assemblies](https://docs.unity3d.com/6000.0/Documentation/Manual/assembly-definitions-intro.html), [text assets](https://docs.unity3d.com/6000.0/Documentation/Manual/class-TextAsset.html) and [reserved folders](https://docs.unity3d.com/6000.0/Documentation/Manual/SpecialFolders.html).

## Trace an effective setting or state write

Pin the accepted rule and placement, exact project, scene or prefab variant, relevant object and component identity, and the selected configuration. Record the intended parameter and unit, clock, configured source and value, inherited value, local override and runtime assignment that can change the effective value. Identify the writer or precedence decision and relevant observation conditions. Static inspection establishes the declared or serialized values and the observed precedence in source. An unexercised interaction remains open.

For a disputed event, record the starting state and saved version, ordinary player input, expected sequence and final state, and observed writer, order, timestamp and final state. Identify the first step that diverges and later checks that were unreached. Compare competing writers or an effective override before proposing a new rule. Route an implementation or binding discrepancy against the accepted rule to Unity. Route a proposed behavior or tuning change to the design owner. Retain exact prior evidence.

Select an executable EditMode check for deterministic logic, resolved configuration or migration. Use PlayMode for actual scene input, lifecycle, competing writes and runtime binding. Select matching Player evidence for build-specific behavior and device evidence for input, platform or native effects. Pin the affected save schemas and reimported object or event binding. Retain a save-compatibility or receiver check, or report the missing input and next owner.

## Summarize engine messages for one attempt

Select the exact project and Editor session or Player build, actual lane and attempt. Record capture source digest and availability, start and end boundaries and whether the producing context observed the entire window. Keep required cases and reached steps identifiable. Report expected, discovered, passed, failed and skipped NUnit counts independently of engine message groups.

Group fresh relevant messages by a stable digest of the locally normalized signature and severity. Record the count and the affected case or step when known. Keep expected diagnostics separate. For Director Audit, retain the case-specific expectation locally, record the case, severity, signature digest and expectation digest, and provide the exact reviewed expectation with the selection. Only a reached case and matching reviewed expectation support exclusion. Keep historical or out-of-window messages separate with an exclusion reason. If relevance or occurrence cannot be tied to the selected scope, record a gap for the affected claim. Preserve raw messages and stack traces in the owning project.

A missing source, missing page, truncated tail, unknown capture format or foreign session leaves engine health unknown. A complete, available and empty relevant window supports a clean verdict for the selected scope only. A relevant fresh exception holds the covered criterion and can coexist with passing functional counts. Keep the verification lane and original tested condition in the report.

## Specify a project-owned interaction regression

Pin the target revision, admitted scene and test assembly, accepted Narrative and Game Design records, selected rule and placement, exact adapter and effective bindings. Specify relevant initial state and save variants. Drive the ordinary player action through the same input and event path the fixture covers. Record the visible cue, action availability, acknowledged transition and before-and-after state from the named writer. Pin any supported replay or save restore and the exact before-and-after count for each one-time effect.

Run a normal control, one isolated prerequisite substitution and one separately isolated writer substitution. Each substitution identifies the first changed step, expected result, actual result and later assertions left unexecuted. Restore both accepted behaviors and exercise the combined normal route and replay with an unaffected control. Distinguish the deliberately substituted fixture from an observed defect in the selected product.

Use the authorized named PlayMode recipe, exact case IDs and expected discovery. Retain NUnit results, relevant engine capture, run and test identity, save and service isolation and cleanup. Report uncovered device, Player and human observations under the appropriate lane. Native execution requires an authorized target, a matching Editor or build, usable inputs and an isolated project fixture.
