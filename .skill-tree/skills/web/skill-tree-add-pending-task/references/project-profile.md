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
  "instruction_profile_id": "57a225f767b2c4635d3ad4686b25d00479d26c69df466200cbe12b93226346c8",
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
  "source_version": "0.4.0",
  "worktree_environment": {
    "exclusive_resources": [],
    "isolated_directories": [],
    "required_files": [],
    "schema": 1
  }
}
```
