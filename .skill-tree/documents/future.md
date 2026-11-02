# Future Work

## Pending Task Format

Fixed metadata records task identity and dependency scope.

## Pending Queue

## Prioritized Next Changes

### Qualify workflow redesign conformance repairs

```yaml
id: T-d6dfa7ea-3bbe-4293-9d49-a3470c8d9f54
priority: 111
status: Ready
parent_pending_ids: ["P-c526b036-fd1d-4a9a-b5b5-6e53fcf778b8"]
processing_run_id: PR-9c772e36-381c-4f7d-9f70-1a1744eb5ad2
root_task_id: T-d6dfa7ea-3bbe-4293-9d49-a3470c8d9f54
related_task_id: null
relation: main
depends_on: ["T-c91cc58b-b81f-4e27-9e9f-710090d7c9c3"]
```

Goal:
- A source-backed conformance matrix and all required source checks cover the reproduced gaps.

Touch:
- .skill-tree/common/scripts/workflow-state.py, .skill-tree/lib/composer.js, .skill-tree/lib/installation.js

Validation:
```json
{
  "checks": [
    {
      "id": "source-qualification",
      "recipe_id": "static-inspection",
      "criteria": [
        "A source-backed conformance matrix and all required source checks cover the reproduced gaps."
      ],
      "sources": [
        ".skill-tree/common/scripts/workflow-state.py",
        ".skill-tree/lib/composer.js",
        ".skill-tree/lib/installation.js"
      ],
      "parameters": {},
      "assertion": "A source-backed conformance matrix and all required source checks cover the reproduced gaps.",
      "timing": "immediate"
    }
  ]
}
```

Acceptance:
- A source-backed conformance matrix and all required source checks cover the reproduced gaps.

## Backlog
