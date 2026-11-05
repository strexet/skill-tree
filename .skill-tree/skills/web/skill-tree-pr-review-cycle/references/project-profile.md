# Concrete Project Profile

Flavor: web. Static compatibility only; execution remains unqualified.

```json
{
  "facts": {
    "capabilities": {
      "playwright-test": {
        "package": "@playwright/test",
        "state": "absent",
        "version": null
      }
    },
    "node": null,
    "package_manager": "npm",
    "packages": {},
    "test_assemblies": [],
    "ui": []
  },
  "gaps": [],
  "instruction_profile_id": "4c1c1a7d0b9684c5a6d51c04fb2d4865b1441385bc5308c2d8b768de02ab7d8f",
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
    }
  },
  "worktree_environment": {
    "exclusive_resources": [],
    "isolated_directories": [],
    "required_files": [],
    "schema": 1
  }
}
```
