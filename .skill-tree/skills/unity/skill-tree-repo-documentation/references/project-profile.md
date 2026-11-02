# Concrete Project Profile

Flavor: unity. Static compatibility only; execution remains unqualified.

```json
{
  "facts": {
    "editor": "6000.0.83f1",
    "node": null,
    "package_manager": "npm",
    "packages": {
      "com.unity.test-framework": {
        "declaration_digest": "4f7e39ff822ea1097acede5f7b8773ffb24822c1192124129cd676cd5a9eda4b",
        "state": "known",
        "version": "1.4.6"
      },
      "com.unity.ugui": {
        "declaration_digest": "f22abd6773ab232869321ad4b1e47ac0c908febf4f3a2bd10c8066140f741261",
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
  "instruction_profile_id": "b372689a8f917dbf40c2517380c9bb9962af730caac830aad5877e64f2f104d2",
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
