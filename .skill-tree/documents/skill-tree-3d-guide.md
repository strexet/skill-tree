# Skill Tree 3D project guide

Skill Tree 3D guides the creation, review and delivery of Unity assets. The [shared workflow](../common/references/3d-workflow.md) defines role handoffs and evidence requirements. The selected project profile define the tools qualified for native Blender and Unity work.

## Start a project run

Install the operation into the intended Unity project and verify the owned package.

```sh
node .skill-tree/bin/install.js --project --target "$project_root" \
  --flavor unity --only codex --skills skill-tree-3d --non-interactive
node "$project_root/.skill-tree/installation/manager.js" --verify
```

Invoke the installed operation in the project chat. Name the asset, intended use, current review stage and permitted write scope. Supply available references, dimensions and the target Unity project. Project files identify the Editor version, packages, pipeline and quality settings. The operation asks up to three consequential questions per round and explains the available choices. A reversible draft can proceed within the agreed scope while owner decisions are pending.

## Use focused stages

Install the focused operations when a request starts at a specific step. Available operations include `skill-tree-3d-references`, `skill-tree-3d-blender`, `skill-tree-3d-texture`, `skill-tree-3d-motion` and `skill-tree-3d-unity`. The [stage controller](../common/references/3d-stages.md) binds the current inputs and planned views to the stage attempt. Each attempt checks required predecessor evidence and records the result for the exact candidate.

For a dimensioned object, use front, side and top views in a common metric frame. Include rear and opposite side views when symmetry or a design feature requires additional views. After stylization, pair each Blender design reference with a matte gray clay view in the same pose and framing. Compare the model with the paired reference views before applying textures. [Reference and review views](../common/references/3d-workflow.md#reference-and-review-views)

## Review in Unity

Use the saved scene on the intended target. Inspect the model, lighting and scene surfaces from multiple angles. Include close and grazing views of joints, door frames and layered surfaces. The [Unity roles](../common/references/3d-unity-roles.md) describe lighting, integration and evidence collection.

For animated models, evaluate foot contact, surface deformation, trajectory continuity and the midpoint of every exposed continuous blend. The [Unity motion acceptance contract](../common/references/3d-stages.md#unity-motion-acceptance) defines capture, review and repair routing. Record the exact receiver, dependencies and authorized write paths before delivery. Technical results, independent visual review and owner acceptance each apply to a specific revision.

## Verify the portable operation

Run the shipped checks from the Skill Tree source checkout.

```sh
npm run sync:check
npm run validate
npm run test:py
npm run test:node
```

The [stage fixtures](../tests/test-3d-stages.py) exercise accepted and rejected evidence. The [installation fixture](../tests/test-3d-operation-installation.js) verifies the standalone package in each supported flavor. Blender and Unity claims require captures from the selected environment.
