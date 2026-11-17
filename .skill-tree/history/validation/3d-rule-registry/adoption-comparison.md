# Validation rule adoption comparison

The 3D registry selects checks on a recurring stage and asset matrix. The shared rules reuse the same report structure and evaluator across different review packets.

The workflow controller already prepares required checks from the task specification and binds source fingerprints, recipe arguments, environment and result artifacts to each attempt. Moving required check selection into the 3D registry would introduce another owner for check coverage and require migration of prepared attempts, replay guards, completed contracts and validation grouping. The observed overlap is limited to revision and evidence concepts. The workflow controller retains the existing check specification and receipt contract.

The Narrative Ink replay uses an explicit runner recipe, scenario traces and pinned inputs. The scenarios drive the actual runtime path. A separate catalog would add selectors and configuration without removing a runner or improving scenario coverage. The narrative replay retains the existing recipe and fixture data.

| Example | Source evidence |
| --- | --- |
| Workflow check receipts | `.skill-tree/common/references/validation-policy.md` and `.skill-tree/common/scripts/workflow-state.py` |
| Narrative runtime replay | `.skill-tree/config/repository.json`, `.skill-tree/examples/narrative/run-paths.sh` and `.skill-tree/examples/narrative/route-traces.json` |
