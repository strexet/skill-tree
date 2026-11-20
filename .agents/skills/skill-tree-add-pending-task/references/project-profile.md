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
  "instruction_profile_id": "4b7fc07eb1be6745a63811f92fab99cfcc3331b5eb5c495d2a6b328c784b33ea",
  "recipes": {
    "creature-catalog-closeout-package": {
      "argv": [
        "python3",
        ".skill-tree/examples/3d/recipes/character/creatures/verify-catalog-pilot.py",
        "--project",
        "{project_root}",
        "--control",
        "package"
      ],
      "input_paths": [
        ".skill-tree/config/repository.json",
        ".skill-tree/examples/3d/recipes/character/creatures/verify-catalog-pilot.py"
      ],
      "lane": "static",
      "qualification": "owner-declared static recipe; runner unqualified"
    },
    "creature-catalog-native-receipts": {
      "argv": [
        "python3",
        ".skill-tree/examples/3d/recipes/character/creatures/verify-catalog-pilot.py",
        "--project",
        "{project_root}",
        "--queue",
        "{queue_root}",
        "--local-native-archive",
        "--control",
        "{control}"
      ],
      "input_paths": [
        ".skill-tree/config/repository.json",
        ".skill-tree/examples/3d/recipes/character/creatures/verify-catalog-pilot.py"
      ],
      "lane": "native",
      "qualification": "owner-declared static recipe; runner unqualified"
    },
    "director-blender-observed": {
      "argv": [
        "python3",
        ".skill-tree/tests/fixtures/director/verify-lantern-art.py",
        "{project_root}"
      ],
      "input_paths": [
        ".skill-tree/validation-recipes.json",
        ".skill-tree/tests/fixtures/director/lantern-fixture.json",
        ".skill-tree/tests/fixtures/director/produce-lantern-blender.py",
        ".skill-tree/tests/fixtures/director/run-lantern-blender.py",
        ".skill-tree/tests/fixtures/director/verify-lantern-art.py"
      ],
      "lane": "native",
      "qualification": "owner-declared static recipe; runner unqualified"
    },
    "director-codex-observed": {
      "argv": [
        "python3",
        ".skill-tree/tests/fixtures/director/verify-codex-host.py",
        "{project_root}"
      ],
      "input_paths": [
        ".skill-tree/validation-recipes.json",
        ".skill-tree/tests/fixtures/director/verify-codex-host.py"
      ],
      "lane": "native",
      "qualification": "owner-declared static recipe; runner unqualified"
    },
    "narrative-ink-replay": {
      "argv": [
        "bash",
        ".skill-tree/examples/narrative/run-paths.sh"
      ],
      "input_paths": [
        ".skill-tree/config/repository.json",
        ".skill-tree/examples/narrative/run-paths.sh",
        ".skill-tree/examples/narrative/quest.ink",
        ".skill-tree/examples/narrative/route-traces.json",
        ".skill-tree/examples/narrative/runtime-check/program.cs",
        ".skill-tree/examples/narrative/runtime-check/runtime-check.csproj"
      ],
      "lane": "integration",
      "qualification": "owner-declared static recipe; runner unqualified"
    },
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
  "source_version": "0.6.0",
  "worktree_environment": {
    "exclusive_resources": [],
    "isolated_directories": [],
    "required_files": [],
    "schema": 1
  }
}
```
