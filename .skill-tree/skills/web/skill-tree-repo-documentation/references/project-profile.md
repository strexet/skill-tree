# Concrete Project Profile

Flavor: web. Static compatibility only; execution remains unqualified.

```json
{
  "environment_id": "511b4f0bc37ab5bc115e4281bbd1aabfbcc1429af3da98bc9cedeedc9001d4e0",
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
