<!-- GENERATED FILE; Source: skill-tree/common/references/unity-safety.md; generator: skill-tree/scripts/sync-skill-references.py -->

# Unity Evidence and Safety

Detect Unity roots from Assets/Packages/ProjectSettings. Inspect the pinned Editor version, package manifests/locks, assemblies, scenes/prefabs, serialized configuration, startup/lifecycle, persistence, backend/native SDKs, platform settings, builds and tests when relevant. Exclude Library/Temp/Obj/Logs/Builds/UserSettings and dependency caches from documentation evidence.

Preserve serialized assets, GUIDs, package pins and unrelated work. Prefer Unity tooling for scene/asset changes. Never build generated solutions or run dotnet build without explicit authorization. Static inspection never establishes compilation, Play Mode, UI, player or device behavior.

Read the exact validation profile and repository authorization before Editor launch/tests. Approved Editor lifecycle includes only the stated checkout and limits. Verify save/service isolation before gameplay or resets. Use one owned Editor/controller, record PID/deadline, preserve unrelated Editors, collect fresh assertions/logs/screenshots as required and clean up only owned resources. Record failures and consumed limits; resumption never renews budgets. No build, device, package upgrade, external service or scheduling permission is implied.
