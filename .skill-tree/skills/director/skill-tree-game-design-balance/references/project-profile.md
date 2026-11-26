# Concrete Project Profile

Flavor: director. Static compatibility only; execution remains unqualified.

```json
{
  "facts": {
    "capabilities": {},
    "director": {
      "artworkshop": {
        "observed_source_sha256": "6cef226a82b646e11de36d018b5df18fd291d52b36d306a146719b74fb09ecad",
        "reason": "A reviewed current installed ArtWorkshop adapter is required.",
        "status": "unsupported"
      },
      "logs": {
        "observed_source_sha256": "4dcae8ec5bc099a2c65f7b3d151e7b6e5d3b86401789611f587f18387e7a8480",
        "reason": "A reviewed current installed logs adapter is required.",
        "status": "unsupported"
      },
      "narrative": {
        "sha256": "ad6618d06fc1b2cac79694a64ff5733bdd03a330e0714851e04e185d108c1388",
        "status": "source-verified"
      },
      "unity": {
        "status": "unavailable"
      }
    },
    "node": null,
    "package_manager": "npm",
    "packages": {},
    "test_assemblies": [],
    "ui": []
  },
  "gaps": [],
  "instruction_profile_id": "e105808b72b0e03da2c8d3f03865be0b30db9004463ab438ded86adbc00affd3",
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
  "source_version": "0.9.0",
  "worktree_environment": {
    "exclusive_resources": [],
    "isolated_directories": [],
    "required_files": [],
    "schema": 1
  }
}
```
