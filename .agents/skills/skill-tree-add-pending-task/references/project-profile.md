# Concrete Project Profile

Flavor: general. Static compatibility only; execution remains unqualified.

```json
{
  "facts": {
    "capabilities": {},
    "node": ">=18",
    "package_manager": "npm",
    "packages": {},
    "test_assemblies": [],
    "ui": []
  },
  "gaps": [],
  "instruction_profile_id": "6829d9d8c3ccc5eeeb45d98a5885da819252e286d9919ec0d6202346b0cf8081",
  "recipes": {
    "pending-boundary-installation": {
      "argv": [
        "node",
        "--test",
        ".skill-tree/tests/test-pending-boundary-installation.js"
      ],
      "input_paths": [
        ".skill-tree/config/repository.json"
      ],
      "lane": "unit",
      "qualification": "owner-declared static recipe; runner unqualified"
    },
    "pending-boundary-unit": {
      "argv": [
        "python3",
        ".skill-tree/tests/test-pending-intake-boundary.py"
      ],
      "input_paths": [
        ".skill-tree/config/repository.json"
      ],
      "lane": "unit",
      "qualification": "owner-declared static recipe; runner unqualified"
    },
    "pending-priority-installation": {
      "argv": [
        "node",
        "--test",
        ".skill-tree/tests/test-pending-priority-installation.js"
      ],
      "input_paths": [
        ".skill-tree/config/repository.json"
      ],
      "lane": "unit",
      "qualification": "owner-declared static recipe; runner unqualified"
    },
    "pending-priority-unit": {
      "argv": [
        "python3",
        ".skill-tree/tests/test-pending-priority.py"
      ],
      "input_paths": [
        ".skill-tree/config/repository.json"
      ],
      "lane": "unit",
      "qualification": "owner-declared static recipe; runner unqualified"
    },
    "quality-node": {
      "argv": [
        "node",
        "--test",
        "{test_path}"
      ],
      "input_paths": [
        ".skill-tree/config/repository.json"
      ],
      "lane": "unit",
      "qualification": "owner-declared static recipe; runner unqualified"
    },
    "quality-python": {
      "argv": [
        "python3",
        "{test_path}"
      ],
      "input_paths": [
        ".skill-tree/config/repository.json"
      ],
      "lane": "unit",
      "qualification": "owner-declared static recipe; runner unqualified"
    },
    "script-test-node": {
      "argv": [
        "npm",
        "run",
        "test:node"
      ],
      "command_digest": "8d70f3bc56930afba27f11fe773c7efa45bb2267291dd199e8b4439dc6bed3ac",
      "input_paths": [
        "package.json"
      ],
      "lane": "unit",
      "qualification": "static-recipe; runner unqualified"
    },
    "script-test-py": {
      "argv": [
        "npm",
        "run",
        "test:py"
      ],
      "command_digest": "2a3e2a49b470d46f96a4c21609e9ea7fe8c9139951e2c3d29d17843db07835a0",
      "input_paths": [
        "package.json"
      ],
      "lane": "unit",
      "qualification": "static-recipe; runner unqualified"
    },
    "static-inspection": {
      "assertion_contract": "explicit source and artifact assertions",
      "input_paths": [],
      "lane": "static"
    }
  },
  "source_version": "0.3.0",
  "worktree_environment": {
    "exclusive_resources": [],
    "isolated_directories": [],
    "required_files": [],
    "schema": 1
  }
}
```
