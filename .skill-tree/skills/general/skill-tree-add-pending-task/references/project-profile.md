# Concrete Project Profile

Flavor: general. Static compatibility only; execution remains unqualified.

```json
{
  "environment_id": "db0b5aac65ff1e447c4d5716f7c33f05b3f11813134553b4eb217c0ea0903a1b",
  "facts": {
    "node": null,
    "package_manager": "npm",
    "packages": {},
    "test_assemblies": [],
    "ui": []
  },
  "gaps": [],
  "recipes": {
    "script-test": {
      "argv": [
        "npm",
        "run",
        "test"
      ],
      "declared_command": "node --test",
      "input_paths": [
        "package.json"
      ],
      "lane": "unit",
      "qualification": "static-recipe; runner unqualified"
    }
  }
}
```
