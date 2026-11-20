# Unity and Review Roles

## Review environment builder

Use an exact authorized project and versioned scene. Record scale anchors, placement slots, camera, light, exposure and scene compatibility. Preserve authored objects and clean temporary specimens after review. Treat a neutral fallback as a technical view.

### Source-bound lighting for Unity look review

Use realtime lighting while establishing the look. In interiors, motivate local illumination with visible sources such as lanterns, candles or windows. Place point or spot `Light` components at fixtures according to the intended coverage. Record each source and light hierarchy path, color, intensity, range, shadow settings and receiving surfaces. Pair an emissive fixture material with a corresponding light when the fixture is meant to illuminate nearby geometry. For daylight exteriors, start with environment ambient light and a directional sun. Record the active quality level, pipeline asset and camera renderer, including additional-light and shadow support. [Unity lighting settings](https://docs.unity3d.com/6000.3/Documentation/Manual/lighting-window.html) · [URP asset settings](https://docs.unity3d.com/6000.3/Documentation/Manual/urp/universalrp-asset.html)

For each light contribution under review, capture native light-on and light-off frames in the authorized isolated preview. Keep the camera, exposure, tonemapping, emitter material and other lights fixed. Bind the pair to the exact scene revision, light path and toggle state. Inspect the change on a named receiving surface outside the emitter and bloom halo. Review material emission independently when a fixture needs a visible glow. [URP Lit emission settings](https://docs.unity3d.com/6000.3/Documentation/Manual/urp/lit-shader.html)

After look approval, evaluate baked or mixed lighting, Light Probes or Adaptive Probe Volumes against the receiver's indirect-lighting needs. Profile representative content in the intended Player build, quality level and device before choosing batching or instancing changes. Use the Profiler for frame costs and the Frame Debugger for draw events, then recheck the approved look after optimization. [Unity Light Probes](https://docs.unity.com/en-us/engine/6000.3/manual/lighting-overview/direct-and-indirect-lighting/light-probes/light-probes) · [Adaptive Probe Volumes](https://docs.unity.com/en-us/engine/6000.3/manual/lighting-overview/lighting/probevolumes/concept) · [Unity draw-call optimization](https://docs.unity3d.com/6000.3/Documentation/Manual/optimizing-draw-calls-choose-method.html)

### Whole-scene artifact QA before owner review

Inspect the entire assembled Unity scene in the intended target render profile before presenting a look for owner review. Cover all rooms or playable areas, both sides of each traversable transition, and representative modular joins and prop attachments. Review overview and close views at intended camera distances, plus grazing views of door jambs, lintels, thresholds, trim, wall and floor seams, and layered details. Inspect a moving view through each doorway in both directions or a sequence of native frames from before, within and after the doorway on each approach. Include close movement around any suspect seam. Hide editor gizmos for appearance review.

Use geometry inspection to locate duplicate and nearly coplanar visible faces. Check native frames for unstable seams, flicker, gaps and shadow artifacts. Isolate suspect renderers and compare with shadowing disabled when necessary to distinguish depth conflicts from lighting artifacts. Remove duplicate visible faces or give deliberate surface layers distinct geometry. Recheck clearances, collision and lighting data affected by geometry changes. [Unity depth bias and z-fighting](https://docs.unity.com/en-us/engine/6000.3/manual/materials-and-shaders/shaders/writing-custom/shader-writing/sl/writing-shader-render-state-commands/set-depth-bias)

Record the inspected areas, camera positions or paths, target profile, scene revision, findings and native evidence. Geometry inspection locates candidates. Native appearance review confirms the visible result. Correct confirmed artifacts, rerender affected views and adjacent joins, and recheck the complete scene for regressions before presenting the packet. Hold the owner review while a scene artifact or required coverage remains unresolved.

## Unity shader author

Define target pipeline, texture interpretation, exposed parameters and expected passes before authoring a shader. Use S1 brief, S2 visual direction, S3 prototype, S4 implementation, S5 target validation and S6 acceptance and recipe packaging. Review current source and representative material captures. Scope Editor compilation, Player variants and device performance separately.

## Unity VFX author

Define events, timing, dependencies, simulation space, anchors and pooling before selecting a recipe. Use V1 brief, V2 concept and timing, V3 prototype, V4 implementation and dependencies, V5 lifecycle and performance validation, and V6 acceptance and recipe packaging. Verify moving attachments and the actual lifecycle in the intended target. Preserve exact effect, material and recipe revisions.

## Unity art integrator

Verify the accepted source, target profile and write roots. Plan staged import and dependency closure. Preserve owned metadata, semantic references and artist overrides. Run target-specific validation and capture where authorized.

## Art review

Compare current evidence with the accepted brief, requirements and exact revision. Report concrete findings and recommendations, inspect affected checks after corrections and request a current owner decision for the displayed packet. Apply the [shared workflow](3d-workflow.md#creative-stages-and-evidence).

## Unity asset delivery

Resolve the accepted bundle and authorized receiver. Use a controlled fixture for rehearsal. Game delivery uses the exact authorized game checkout in an isolated worktree, with explicit write and dependency scope, target-specific capture and validation. Plan the initial and repeat import and validate live references within the selected receiver. Preserve unrelated changes and report baseline failures independently. Commit, publication and merge require applicable owner authority.

For a gameplay-facing import, bind the stage and attempt, selected candidate and sealed source artifact to the exact target scene, instance and imported revision. Record the producer's observed coordinate, scale or marker and the receiver's binding, override or cue under the actual environment. Keep required checks, supplementary observations and unavailable native coverage explicit. When the accepted source still matches and a receiver override causes the difference, route to the Unity integrator. When the source fails, return to the earliest affected ArtWorkshop stage. Preserve unaffected stage evidence under the original pins.
