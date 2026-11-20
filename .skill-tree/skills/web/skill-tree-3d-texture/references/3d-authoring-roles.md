# 3D Authoring Roles

## Visual design

Resolve reference roles, intent, dimensions and unknowns. Compare concepts before choosing a silhouette. Derive a measured layout from canonical dimensions and stable object IDs for spatial work. Bind reference views to the selected [Unity-target design](3d-workflow.md#unity-target-reference-styling) and preserve assumptions. Supplied references can support portable work when image generation is unavailable.

## Blender character builder

Choose a suitable base, adapt an authorized candidate or create new geometry. Use the [accepted neutral orthographic references](3d-workflow.md#neutral-orthographic-reference-approval) for a viewable character. Preserve scale, axes, silhouette, deformation and attachment requirements. Advance from accepted blockout to detailed mesh, UV, materials and rig evidence. Record tested topology and LOD scope.

## Creature character routing

Confirm the target appearance, body plan, movement, camera distance and intended use. Choose the simplest rig for the agreed motion and target renderer. Record whether a reusable template, a licensed base or original geometry supplies the starting asset. Apply the current character review gates to new creative revisions.

Generate species-specific 2D concepts before modeling a new animal form, including a reusable technical specimen. Use consistent landmarks across side and frontal views to derive measured orthographic guides. Record estimated depth separately from observed dimensions. Include a fixed-pose body turnaround, a fixed-expression head turnaround, and separate key pose references for each gait or action in the review. Compare shoulder and hip movement, paw or foot contact, tail or fin response and the head profile against matched 2D panels. Review the current 3D revision before catalog reuse and retain any required owner decision on the exact displayed packet.

- For a compatible biped with an animal head, reuse a validated Humanoid body mapping. Compare a separate head skin with a continuous neck skin when seam quality or runtime cost changes the choice. Validate each Avatar and the same exact body clip on each variant. Review head silhouette, posed neck and required accessory motion.
- For a cat or dog, fit a reusable quadruped template to the species proportions. Use a Generic motion root and separately authored gaits unless matching exported paths and target playback establish reuse. Review four planted paw windows, root behavior, tail deformation, turns and repeated import. Match the in-place speed during contact measurement.
- For an interactive or close-view fish, use a small Generic deform rig and a repeatable swim cycle and turn. Review the forward axis, tail and fin deformation, loop seam and bounds. Consider a separately measured shared mesh and vertex animation route when the brief requires a decorative school.

Search the current project catalog for a matching template and exact rig and motion evidence. In the Skill Tree source repository, the creature examples reside in `.skill-tree/examples/3d/recipes/character/creatures/`. Installed projects use the locally available asset and recipe catalog.

## Blender location and prop builder

For standalone props and decor visible from multiple sides, start from the [accepted neutral orthographic references](3d-workflow.md#neutral-orthographic-reference-approval). Record pivot, attachment, and collider requirements. Review the Blender blockout before producing the detailed mesh, UVs and materials.

For modular environments, start from a measured plan and stable module and instance IDs. Preserve playable clearances, pivots, snap rules and ownership. Build an accepted blockout before detail. Record collision, placement, material and vegetation constraints for Unity.

## Character motion

Complete the [continuous playback gate](3d-stages.md#continuous-playback-evidence) before submitting a live motion candidate. Review fixed left, right, underside and oblique views at both speeds through the loop boundary. A visible deformation that appears for a single frame or subframe blocks presentation.

Identify the exact rig type, rest pose, locomotion or interaction objective and root-motion policy. Reuse, adapt or author a clip with explicit contacts, transitions, bounds and attachment checks. Preserve baked curve provenance and confirm complete cycle evidence on the intended target before acceptance. Follow the [ventral body continuity review](3d-stages.md#ventral-body-continuity-in-motion) for skinned organic creatures.

### Creature rig symmetry

A creature rig uses bilateral symmetry by default. The brief can define an exception directly or through a concrete requirement, such as a right-sided hump, a longer left arm, or a limp on the left leg. Record the exact brief evidence and scope. A structural exception covers only the affected bones. A movement exception covers only the affected clips or actions and keeps the rest-pose check in force wherever the anatomy is symmetric.

The [neutral model contract](3d-workflow.md#exact-symmetry-in-the-neutral-model) checks exact geometry separately from the rig measurements. Preserve the agreed neutral stance when evaluating the skin. Evaluate action phases using the motion requirements and matched local phases.

Inspect the exact Blender candidate in the rig's rest or bind pose before approving the rig or accepting motion. Record the anatomical left–right plane and an explicit mapping for every bone, including facial bones and rig helpers. In one common coordinate space, reflect the head and tail of each bone in a bilateral pair across the plane and compare the result with the corresponding endpoints of the opposite bone. Check paired hierarchy and corresponding lengths. Centerline bone endpoints lie on the plane. Record coverage, the numerical tolerance in model units and the largest residuals. An unmapped bone or an out-of-tolerance mismatch outside the brief's exception requires correction and recheck.

For symmetric actions, review opposing sides at equivalent local phases in the clip. Compare a walking left paw at lift-off with the right paw at lift-off. Check joint travel, contacts and deformed skin in matched views. A request for an asymmetric action such as a limp changes the bilateral motion expectation only for the described action.

### Biological segment lengths

Biological limb and bone segments preserve fixed rest lengths throughout motion. Joint rotation and sliding, skin compression, and tendon or muscle deformation can change the silhouette while biological bones retain fixed lengths. Blender helper bones and controllers may use scale or stretch internally only when the evaluated anatomical segments remain within numerical precision of the recorded reference lengths. Record any requested stretch as a scoped exception with the exact explicit user instruction, affected segments and covered clips. A style label, reference image, tool default or agent judgment supplies no exception.

Freeze the anatomical segment endpoints and bind lengths in motion requirements. Measure evaluated joint-to-joint and corresponding effective bone lengths on both sides throughout every clip, including subframes, contact transitions, extrema and the loop seam. Review matched neutral material renders at normal and reduced speed for convincing reach, joint range and continuous skin. Treat apparent limb elongation caused by pose, delayed swing or skin deformation as a visual defect even when the lengths pass. Correct the rig, trajectory or skin and repeat both checks before handing off.

Derive quadruped walk and trot contact schedules from species-specific continuous motion studies. For each cycle, include both sides of the body and cover touchdown, loading, passing, push-off, and swing to the next contact. Select at least eight distinct reference phases per gait for the cat and dog pilot. Use paired side and front three-quarter views at every phase to expose same-side fore and hind clearance. Record the ground contact, paw identity and support set before generating the color and clay references. Run the [cross-view pose review](3d-workflow.md#cross-view-pose-and-asymmetry-review) on each phase before accepting the reference. Validate the full animation at native and reduced speed, with frame and subframe checks of posed skin intersections, planted paw slip and floor penetration, limb reach, joint continuity, weight transfer and loop seam. Record whether IK runs during authoring or in the target player. Review the baked result independently of the solver or contact-marker tests. Recheck protected clips on the changed rig and skin.

## Author a gameplay-facing cue or anchor

Use the selected gameplay brief to identify the player action and the asset trait the player must be able to see, reach or interact with. Name the exact camera, view or clip, relevant starting state, acceptance threshold and compatible units. Review dimensions, silhouettes or anchors during the earliest applicable geometry stage. Review a timed contact or signal on the relevant evaluated motion clip before export. Preserve the verified source position, timing and link to the protected requirement in the candidate handoff.
