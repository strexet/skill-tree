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
  "instruction_profile_id": "5797acd6c02b9711fb22903b1277efa65e219e5550c754de019e0d8e76f9af2c",
  "recipes": {
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
