# Future Work

## Pending Task Format

Fixed metadata records task identity and dependency scope.

## Pending Queue

## Prioritized Next Changes

### Expose the built-in static inspection recipe in validation discovery

```yaml
id: T-5a43a18f-ffd7-4d25-8ca7-4422e8ddaf1e
priority: 127
status: Ready
parent_pending_ids: ["P-9bf5b8af-1e50-4f53-9ab9-56ef46997428"]
processing_run_id: PR-8b369a65-2c1d-4162-81f4-891ec60797fe
root_task_id: T-f63559f1-4663-41b7-b085-f55ba7b47fe5
related_task_id: T-f63559f1-4663-41b7-b085-f55ba7b47fe5
relation: followup
depends_on: []
```

Goal:
- Expose the existing static-inspection fallback through owned installed profile discovery and validation documentation.

Touch:
- `.skill-tree/lib/composer.js`
- `.skill-tree/common/references/installation-profile.md`
- `.skill-tree/common/references/validation-policy.md`
- `.skill-tree/documents/install.md`
- `.skill-tree/tests/test-installation-integrity.js`

Implementation constraints:
- Keep the existing assertion lane, fallback result shape and explicit recipe precedence. Keep fallback discovery distinct from executable runner recipes and product qualification.
- Use authored references and the normal generator for installed package copies. Preserve verification of the owned profile and support previously installed profiles.

Source evidence:
- The installed profile recipes map lacks static-inspection. The installed recipe_for helper resolves the same ID to the static lane with an explicit source and artifact assertion contract and no argument vector.
- `.skill-tree/history/validation/plugin-system/clarification-observation-oracle-failure.json` retains the initial discovery error and the correction after source verification.

Validation:
```json
{
  "checks": [
    {
      "id": "static-recipe-discovery-contract",
      "recipe_id": "static-inspection",
      "criteria": [
        "Owned profile discovery and the bundled validation documentation identify static-inspection as an assertion-only built-in fallback when no explicit recipe overrides the ID."
      ],
      "sources": [
        ".skill-tree/lib/composer.js",
        ".skill-tree/common/references/installation-profile.md",
        ".skill-tree/common/references/validation-policy.md",
        ".skill-tree/documents/install.md",
        ".skill-tree/common/scripts/workflow-state.py"
      ],
      "parameters": {},
      "assertion": "Owned profile discovery and the bundled validation documentation identify static-inspection as an assertion-only built-in fallback when no explicit recipe overrides the ID.",
      "timing": "immediate"
    },
    {
      "id": "installed-static-recipe-discovery",
      "recipe_id": "quality-node",
      "criteria": [
        "An installed standalone fixture discovers the built-in fallback without an executable command and resolves the existing static assertion contract. An explicit recipe retains existing precedence."
      ],
      "sources": [
        ".skill-tree/lib/composer.js",
        ".skill-tree/tests/test-installation-integrity.js",
        ".skill-tree/lib/installation.js",
        ".skill-tree/common/scripts/workflow-state.py"
      ],
      "parameters": {
        "test_path": ".skill-tree/tests/test-installation-integrity.js"
      },
      "assertion": "An installed standalone fixture discovers the built-in fallback without an executable command and resolves the existing static assertion contract. An explicit recipe retains existing precedence.",
      "timing": "immediate"
    }
  ]
}
```

Acceptance:
- Owned profile discovery and the bundled validation documentation identify static-inspection as an assertion-only built-in fallback when no explicit recipe overrides the ID.
- An installed standalone fixture discovers the built-in fallback without an executable command and resolves the existing static assertion contract. An explicit recipe retains existing precedence.

### Reconcile an interrupted prepared check after source drift

```yaml
id: T-3fe8425d-6740-4b45-99cf-f2b0b29c3656
priority: 114
status: Ready
parent_pending_ids: ["P-09bfa38c-d805-45ee-9b15-e4c9fc1d16f8"]
processing_run_id: PR-8b369a65-2c1d-4162-81f4-891ec60797fe
root_task_id: T-657e5621-efb8-4c53-8ab9-bdd2a7e6ec69
related_task_id: T-657e5621-efb8-4c53-8ab9-bdd2a7e6ec69
relation: followup
depends_on: []
```

Goal:
- Add a guarded recovery path for an interrupted prepared validation check after verified cleanup and observed source or check identity drift.

Touch:
- `.skill-tree/common/scripts/workflow-state.py`
- `.skill-tree/common/references/workflow-metadata.md`
- `.skill-tree/common/references/validation-policy.md`
- `.skill-tree/tests/test-workflow-state.py`

Implementation constraints:
- Use the existing owned writer, scope admission and original attempt receipt model. Require a current observation of drift and matching evidence of a stopped original execution.
- Keep cancellation separate from the check result, runner counters and workflow continuation. Preserve existing Red, result and parked run records. Test check preparation and completion through the normal workflow entry points.

Source evidence:
- The prepare_check helper rejects another attempt while the exact original lacks a terminal receipt. The record_check helper rejects the original after source or check identity drift.
- `.skill-tree/history/validation/plugin-system/processing115-interrupted-focused-attempt.json` retains a stopped unit process, different observed check key, earlier Red identity and cancellation without a result.

Validation:
```json
{
  "checks": [
    {
      "id": "stale-check-reconciliation-regressions",
      "recipe_id": "quality-python",
      "criteria": [
        "The owned workflow helper reconciles only an exact stale pending attempt with matching run or standalone task scope, original check identity and independently inspectable cleanup evidence.",
        "Reconciliation preserves the original attempt and earlier Red or result artifacts. A matching replay returns the original cancellation receipt, and conflicting replay leaves the workflow unchanged.",
        "Wrong identity, live or uncertain cleanup, missing evidence and unverified drift preserve the pending attempt. A valid cancellation permits fresh preparation without supplying a pass, a runner invocation or unrelated continuation."
      ],
      "sources": [
        ".skill-tree/common/scripts/workflow-state.py",
        ".skill-tree/common/references/workflow-metadata.md",
        ".skill-tree/common/references/validation-policy.md",
        ".skill-tree/tests/test-workflow-state.py",
        ".skill-tree/lib/installation.js",
        ".skill-tree/history/validation/plugin-system/processing115-interrupted-focused-attempt.json"
      ],
      "parameters": {
        "test_path": ".skill-tree/tests/test-workflow-state.py"
      },
      "assertion": "The owned workflow helper reconciles only an exact stale pending attempt with matching run or standalone task scope, original check identity and independently inspectable cleanup evidence. Reconciliation preserves the original attempt and earlier Red or result artifacts. A matching replay returns the original cancellation receipt, and conflicting replay leaves the workflow unchanged. Wrong identity, live or uncertain cleanup, missing evidence and unverified drift preserve the pending attempt. A valid cancellation permits fresh preparation without supplying a pass, a runner invocation or unrelated continuation.",
      "timing": "immediate"
    }
  ]
}
```

Acceptance:
- The owned workflow helper reconciles only an exact stale pending attempt with matching run or standalone task scope, original check identity and independently inspectable cleanup evidence.
- Reconciliation preserves the original attempt and earlier Red or result artifacts. A matching replay returns the original cancellation receipt, and conflicting replay leaves the workflow unchanged.
- Wrong identity, live or uncertain cleanup, missing evidence and unverified drift preserve the pending attempt. A valid cancellation permits fresh preparation without supplying a pass, a runner invocation or unrelated continuation.

## Backlog
