# Skill Tree 3D project guide

Skill Tree 3D is a project-scoped operation for drafting, reviewing and delivering Unity 3D assets. The operation uses portable ArtWorkshop records for briefs, exact revisions, recipes and evidence. The installed general and web flavors support portable work. The Unity flavor can use the native tools and validation recipes qualified for the selected project. [Role and recipe coverage](../examples/3d/qualification/coverage.md)

## Start a project run

Install the reviewed operation through the owned installer for the selected project and verify the resulting installation. Follow the current installation handoff before changing an existing owned snapshot.

```sh
node .skill-tree/bin/install.js --project --target "$project_root" \
  --flavor unity --only codex --skills skill-tree-3d --non-interactive
node "$project_root/.skill-tree/installation/manager.js" --verify
```

Invoke the locally installed `skill-tree-3d` operation in the project chat. Name the asset or location, intended use, current review stage and allowed write scope. Supply available references, measured dimensions and the intended Unity project. Existing project files identify the Editor version, package versions, pipeline, quality settings and known conventions. The operation records facts, assumptions and unresolved choices separately.

> Use the locally installed skill-tree-3d operation to draft a wall lantern for the corridor. Write the reversible draft under ArtWorkshop/drafts. Review the draft and identify the decision needed before advancing.

The operation asks up to three consequential questions per round and explains the recommendation, alternatives and tradeoff. A reversible draft can proceed within the agreed scope while a consequential decision is pending. Earlier review material applies to the recorded revision and environment. [Installed-agent example](../history/validation/3d-agent-observation.json)

## Use focused stages

The common operation runs the requested asset route. Install the focused operations for independently requested work: `skill-tree-3d-references`, `skill-tree-3d-blender`, `skill-tree-3d-texture`, `skill-tree-3d-motion` and `skill-tree-3d-unity`. Pass selected skill names to the same owned installer. The [stage controller](../common/references/3d-stages.md) freezes revision inputs and shot requirements, enforces predecessor acceptance, records concrete failures and resumes the same attempt or affected branch. The host dispatches production tools and obtains independent review observations before presenting a revision.

## Choose or create the asset

Search the [library](../examples/3d/workshop/library/readme.md) for the target profile and intended permissions. Use, adapt, search and create depend on exact source rights, technical evidence, dependencies and the requested capabilities. Third-party packages pass [source admission](../examples/3d/workshop/source-admission/readme.md) before normalization or import. The [catalog view](../examples/3d/workshop/catalog-views/readme.md) shows exact revisions, provenance, measurements, eligible candidates and pinned Unity setup.

Use G1 for concept, GP for a constrained spatial plan, G2 for measured references, G3 for Blender blockout, G4 for detailed source, G5 for Unity look and G6 for motion. Applicability follows the asset and brief. A spatial constraint can move GP ahead of G1. The [design handoff](../examples/3d/workshop/design-handoff/readme.md) keeps measured constraints, assumptions and derived views tied to the current design. Use the independent [shader](../examples/3d/recipes/shaders/readme.md) and [Particle System](../examples/3d/recipes/vfx/readme.md) routes for S1–S6 and V1–V6.

Accept G3 before detail work and G4 before final Unity integration. For a dimensioned object review, use front, side and top views in a common metric frame. Include a rear view or section when attachment, depth, fit or clearance affects the decision. [Creative stages and review contract](../common/references/3d-workflow.md#creative-stages-and-evidence)

After stylization, pair every Blender design reference with a matte gray clay view in the same pose and framing. Review the pair before modeling. Compare the resulting color and clay renders with the paired references at every planned angle and motion phase. Record and resolve visual findings before handing off the stage. [Reference and review views](../common/references/3d-workflow.md#reference-and-review-views)

The [creature routes](../examples/3d/recipes/character/creatures/readme.md) cover animal-headed humanoids, cats and dogs, and animated fish. Each route lists reusable authoring inputs, sample catalog revisions, and the exact sandbox validation scope.

## Review and revise

Use actual Blender or Unity evidence for native claims. The project profile defines the exact target and tools. The [review packet](../examples/3d/workshop/review/README.md) binds the asset, stage, revision, dependencies, target and shown evidence. Technical QA, visual review and the owner decision remain separate records. Changes re-run affected checks and preserve the earlier accepted revision.

For Unity look review, inspect the entire scene before presenting the scene. Include close and grazing views of joins, layered surfaces, doors and traversable thresholds. Check both sides and views along the traversal path. Fix unstable faces, seams or shadows and repeat the affected captures before the owner review. Show the exact review image in chat with links to the underlying evidence. Use [review environments](../examples/3d/workshop/review-environments/readme.md) to bind the camera, placement, scene revision and cleanup.

Bind local light to the visible fixture and verify the effect on a nearby receiver. For exteriors, use the appropriate ambient and sun setup. After look approval, choose probes, bake, batching or instancing using measurements and a repeat render on the target. [Unity lighting and visual QA](../common/references/3d-unity-roles.md)

## Package and deliver

Promote the approved sealed revision into the [accepted revision store](../examples/3d/workshop/accepted-revisions/readme.md). Plan delivery against the exact authorized receiver, dependency closure and write paths. The [delivery planner](../examples/3d/workshop/delivery/readme.md) protects local edits and metadata. The [Unity bridge](../examples/3d/unity-bridge/README.md) checks live imported bindings and scopes capture and recovery. Preserve gameplay wrappers, manual content and target-owned settings.

The [sandbox rehearsal](../history/validation/3d-sandbox/delivery-rehearsal/readme.md) covers forward and repeat import. [Recovery evidence](../history/validation/3d-sandbox/delivery-recovery/readme.md) covers the exact prior package and conflict with hand-edited generated content. The production game, Player and devices each require separate acceptance. The current [coverage matrix](../examples/3d/qualification/coverage.md) identifies the tested scopes and gaps.

## Reproduce portable qualification

Run the [qualification supervisor](../examples/3d/qualification/run.py) against reviewed source, with a fresh external evidence directory. The focused run executes positive and adverse workflow fixtures. The full run adds repository synchronization, strict validation and the complete Python and Node suites. The temporary installer profiles use scoped general, web and Unity fixtures and verify the package after removing the source copy.

```sh
python3 -B .skill-tree/examples/3d/qualification/run.py \
  --source "$PWD" --output "$qualification_root/report" --mode full
```

The output records command results, test counts, source hashes and log digests. Local Unity workspaces and capture files belong outside the authored example tree. [Qualification procedure](../examples/3d/qualification/readme.md)
