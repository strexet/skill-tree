# Concrete Project Profile

Flavor: general. Static compatibility only; execution remains unqualified.

```json
{
  "facts": {
    "capabilities": {},
    "node": null,
    "package_manager": "npm",
    "packages": {},
    "test_assemblies": [],
    "ui": []
  },
  "gaps": [],
  "instruction_profile_id": "5dc086595fea9db82dd4605fa7edced5ece09025b18fcaa2830c1d83ab1f73f9",
  "recipes": {
    "script-test": {
      "argv": [
        "npm",
        "run",
        "test"
      ],
      "command_digest": "f90321a3f3beab5b298ce4c7878f7c4db1e376ad5b15295a0dc01c36f1722446",
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
