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

## Evidence boundary

Pure module fixtures establish deterministic definition, identity and context behavior. Copied module fixtures establish the declared module dependency closure without a source checkout or sibling skills. General/web/unity installed hook composition, actual host invocation, current task holds and candidate efficacy require the corresponding later checks. Source and fixture results supply no native or universal host qualification.
