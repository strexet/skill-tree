# Concrete Project Profile

Flavor: unity. Static compatibility only; execution remains unqualified.

```json
{
  "facts": {
    "capabilities": {},
    "editor": "6000.0.83f1",
    "node": null,
    "package_manager": "npm",
    "packages": {
      "com.unity.test-framework": {
        "declaration_digest": "4f7e39ff822ea1097acede5f7b8773ffb24822c1192124129cd676cd5a9eda4b",
        "declared_version": "1.4.6",
        "resolution_source": "Packages/packages-lock.json",
        "state": "known",
        "version": "1.4.6"
      },
      "com.unity.ugui": {
        "declaration_digest": "f22abd6773ab232869321ad4b1e47ac0c908febf4f3a2bd10c8066140f741261",
        "declared_version": "2.0.0",
        "resolution_source": "Packages/packages-lock.json",
        "state": "known",
        "version": "2.0.0"
      }
    },
    "reload": {
      "enabled": null,
      "options": null,
      "state": "absent"
    },
    "test_assemblies": [
      "Assets/Tests/EditMode/Tests.asmdef"
    ],
    "ui": [
      "ugui"
    ]
  },
  "gaps": [],
  "instruction_profile_id": "ba6f256ea572bd23146d4a70a59b27227d6c1f3f9b449fa9d508530665d78d58",
  "recipes": {
    "static-inspection": {
      "assertion_contract": "explicit source and artifact assertions",
      "input_paths": [],
      "lane": "static"
    },
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
        "ProjectSettings/EditorSettings.asset",
        "ProjectSettings/ProjectSettings.asset",
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
        "ProjectSettings/EditorSettings.asset",
        "ProjectSettings/ProjectSettings.asset",
        "Packages/manifest.json",
        "Packages/packages-lock.json",
        "Assets/Tests/EditMode/Tests.asmdef"
      ],
      "lane": "unity-playmode",
      "qualification": "static-recipe; authorized matching Editor and isolated fixture required",
      "utf_version": "1.4.6"
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
