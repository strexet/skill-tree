# Concrete Project Profile

Flavor: unity. Static compatibility only; execution remains unqualified.

```json
{
  "environment_id": "7cd035b2a84a761bfaf6a69898f48fc1a1aaa3215b0d88a7a6c65814f23bbdb3",
  "facts": {
    "editor": "6000.0.83f1",
    "node": null,
    "package_manager": "npm",
    "packages": {
      "com.unity.test-framework": {
        "declaration": "1.4.6",
        "state": "known",
        "version": "1.4.6"
      },
      "com.unity.ugui": {
        "declaration": "2.0.0",
        "state": "known",
        "version": "2.0.0"
      }
    },
    "test_assemblies": [
      "Assets/Tests/EditMode/Tests.asmdef"
    ],
    "ui": [
      "ugui"
    ]
  },
  "gaps": [],
  "recipes": {
    "unity-editmode": {
      "argv": [
        "Unity",
        "-batchmode",
        "-projectPath",
        "{project_root}",
        "-runTests",
        "-testPlatform",
        "EditMode",
        "-testFilter",
        "{test_filter}",
        "-testResults",
        "{result_path}",
        "-logFile",
        "{log_path}"
      ],
      "editor_version": "6000.0.83f1",
      "input_paths": [
        "ProjectSettings/ProjectVersion.txt",
        "Packages/manifest.json",
        "Packages/packages-lock.json",
        "Assets/Tests/EditMode/Tests.asmdef"
      ],
      "lane": "unity-editmode",
      "qualification": "static-recipe; authorized matching Editor and isolated fixture required",
      "utf_version": "1.4.6"
    },
    "unity-playmode": {
      "argv": [
        "Unity",
        "-batchmode",
        "-projectPath",
        "{project_root}",
        "-runTests",
        "-testPlatform",
        "PlayMode",
        "-testFilter",
        "{test_filter}",
        "-testResults",
        "{result_path}",
        "-logFile",
        "{log_path}"
      ],
      "editor_version": "6000.0.83f1",
      "input_paths": [
        "ProjectSettings/ProjectVersion.txt",
        "Packages/manifest.json",
        "Packages/packages-lock.json",
        "Assets/Tests/EditMode/Tests.asmdef"
      ],
      "lane": "unity-playmode",
      "qualification": "static-recipe; authorized matching Editor and isolated fixture required",
      "utf_version": "1.4.6"
    }
  }
}
```
