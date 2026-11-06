# Plugin Binding and Invocation Boundaries

## Definition layer

The binding foundation describes owned operation anchors, independent binding occurrences, typed input contexts and dispatch identities. The definition layer performs no plugin or native host execution, creates no workflow metadata and grants no task, installation or publication authority. Composition and actual invocation use separate implementation contracts.

The ordered registry binding array is the sole order authority. Each occurrence has an independent stable ID, plugin ID, operation, anchor, enabled state, optional declarative condition, extra instruction text and arbitrary JSON parameters. Repeated plugin IDs at one anchor remain separate occurrences and share one installed package. Move and removal actions select an exact occurrence ID; moving preserves identity and removal preserves every other occurrence.

## Trusted anchors and location resolution

`createAnchorCatalog(operations, {boundaries, named, aliases})` derives the actual owned operation set from the supplied operation catalog. A trusted boundary record contains the owned operation, a stable implementation version, accepted context kinds and an actual callable handler. Boundary handlers remain controller-owned executable registrations rather than plugin-supplied configuration. Catalog creation and location resolution never invoke a handler.

The returned catalog freezes boundary metadata, callable references and location mappings. The caller remains responsible for the actual host implementation and matching source/version identity; the catalog does not freeze function closure state. Location resolution rechecks actual callable records against catalog metadata and the catalog digest. JSON serialization supplies portable inspection data rather than a callable registration; a resumed host rebuilds the catalog from current owned dispatchers.

Every owned operation has before, during and after location definitions. A location remains unresolved when the trusted dispatcher catalog supplies no matching callable boundary. Named records map an operation and lowercase name to an existing trusted boundary ID. A name, source label or boolean executable flag supplies no callable boundary. The current source operation set can gain the management operation without changing a fixed operation count.

`resolveLocation(request, catalog)` accepts an exact operation/anchor object, a canonical location string or a declared free-text alias. Unknown or ambiguous mappings return an explicit unresolved status and reason. Free text cannot create an operation or executable boundary. The management agent can present a concrete verified mapping before configuration acceptance.

## Compilation and selection

`compileBindings(bindings, {packages, catalog, parameterDefaults, runOverrides})` validates occurrence identities, preserves array order and resolves locations. Effective parameters use upstream, project, occurrence and explicit run layers through the parameter resolver. Parameters remain separate from core context and authority. The compiled configuration digest covers ordered occurrences, effective values, conditions and the trusted catalog identity.

Compiled rows, effective values and ordering remain immutable. The compiled object retains the current callable catalog and a separate portable metadata projection. A JSON-roundtripped configuration requires recompilation against current owned dispatchers before selection; serialized resolved flags alone supply no executable boundary.

`validateContext(context)` checks typed request, project, document, snapshot, management, controller, Pending, task/group and review identities. Document paths remain repository-relative. Real Pending and task identities retain the required P/T forms. Context normalization supplies no fabricated task, queue or controller. Ordinary core selection, existence, admission, authorization and writer/installation guards remain mandatory outside definition validation.

Pending contexts carry Pending identities without premature task identities. Task/group contexts can retain real Pending provenance. Controller and review contexts can carry actual task identities when applicable. Request, project, document, snapshot and management contexts remain task-free; nonapplicable task identity fields reject validation.

`selectBindings(compiled, event, context)` selects enabled matching occurrences in configured order. Missing callable locations and incompatible context kinds remain visible unresolved entries rather than successful integrations. Declarative conditions support booleans, equality, membership, presence, all, any and negation over JSON-pointer context fields. Unknown executable condition forms reject validation without evaluation.

`moveBinding(bindings, id, index)` and `removeBinding(bindings, id)` return independent ordered copies. Missing IDs, duplicate IDs and invalid move positions reject mutation. Lifecycle proposals still own persistent configuration changes, exact confirmation and frozen parked-run reconciliation.

## Delivery and lineage identities

`dispatchIdentity(binding, event, context, inputs)` separates a stable delivery key from the current input digest. The delivery key binds occurrence ID, operation/anchor event and an explicit attempt identity when supplied. The input digest binds configuration, accepted context and effective parameter data. Controller and leaf bindings remain separate deliberate calls.

Selection returns the actual trusted boundary ID in the event. A named occurrence mapped to the same boundary uses the selected event without losing the occurrence identity. A mismatched event or a forged boundary hint cannot redirect an occurrence into another anchor.

The configured binding anchor remains separate audit data from the actual event anchor. Renaming a mapping to the same actual boundary retains the delivery key for the same occurrence/event while the changed configuration and binding data change the input digest.

`classifyDelivery(identity, previous)` distinguishes a new or distinct delivery from exact replay. A matching delivery key with changed inputs rejects conflicting replay. The definition helper records no invocation receipt and establishes no successful execution. The runtime reconciles original uncertain attempts and persists actual observed outcomes.

`enterLineage(lineage, identity)` rejects active re-entry of the same occurrence at the same boundary. Different occurrences of the same plugin remain valid, including a finite A-to-B-to-A chain. Sequential stage history and active recursive lineage remain distinct concepts. A changed configuration or source requires current verification and explicit parked-run reconciliation rather than silent replay.

## Standalone composition and boundary preparation

The composer reads verified owned plugin state as data and emits only the selected operation resource closures. `resolveInputs(root, operations)` binds the registry, package inventory and ordered definitions to the actual registered operation catalog. `composeOperation(source, profile, operation, ownedFiles)` produces the operation-local `references/plugin-bindings.json` manifest and selected `plugins/<id>/upstream/` and `plugins/<id>/overlay/` resources. Repeated occurrences share one package copy while retaining every configured occurrence and parameter layer in order.

Generated instructions retain locked core governance and reference the bounded local manifest. Raw upstream resource bytes remain separate from owned instructions. Binary data and original byte-order marks survive copying and content hashing. Composition, installation, list and dry-run never execute upstream helpers, acquire dependencies or invoke a skill.

The bundled `scripts/plugin-hooks.js` uses the declared local helper closure. `prepareBoundary(packageRoot, request)` rebuilds current callable registrations from the owned operation declarations and verifies the copied manifest and package resources before selection. The manifest binds the actual composed owned instruction/helper/reference bytes, including domain replacements. The CLI bootstrap verifies the owned inventory with built-in readers before loading local dispatcher modules; module calls verify the inventory before scope-helper execution. Direct module callers retain responsibility for the trusted module entry. Local inventory checks detect partial content drift and supply no cryptographic origin proof against rewriting an entire trust root. Serialized executable flags never create a dispatcher. A missing local helper supplies no source or sibling fallback. The boundary scope process selects a fresh nonexistent Python bytecode-cache prefix before owned imports and disables cache writes. Existing cache bytes remain unchanged; the guard reads the verified Python source rather than an older matching cache. The execution guarantee covers the bounded guard process rather than arbitrary provider or host processes.

Boundary preparation keeps actual operation scope. Process Pending before/during preparation verifies the real selected Pending identities before promotion. Implementation During requires the current task-bound draft plan in the plan-review phase before current plan acceptance and source edits. An accepted plan requires explicit core reopening before another During contribution. Applying a plan-changing result and retaining the corresponding readiness obligation belongs to the invocation runtime; core governance then invalidates affected acceptance and requires fresh plan review. Read-only preparation creates no successful invocation, task promotion, source edit or fabricated result hold.

A false occurrence condition excludes the occurrence before context obligations. An empty selected/unresolved occurrence set returns a no-op without creating a queue or optional-plugin hold. Core-only entry points read the empty manifest and continue without requiring optional plugin tools. Configured unavailable locations, missing native capabilities and unqualified invocation retain explicit prerequisites. Native launch, original invocation attempts, current result receipts and contribution application belong to the separate invocation implementation; composition alone never reports a plugin as executed.

Registry, revision, content, order and effective configuration changes participate in composition and profile freshness. Refresh follows the owned stopped writer/installation barrier and explicit re-admission. A live registry edit never rewrites a parked run's recorded effective configuration or historical results.

## Evidence boundary

Pure module fixtures establish deterministic definition, identity and context behavior. Copied module fixtures establish the declared module dependency closure without a source checkout or sibling skills. General/web/unity copied-operation qualification covers only the declared composition and boundary assertions. Actual host invocation, current runtime holds and candidate efficacy require separate checks. Source and fixture results supply no native or universal host qualification.
