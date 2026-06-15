# Unity Snapshot Supplement

Apply these rules in addition to `SNAPSHOT_RULES.md`.

## Unity Relevance

Unity repository documentation is relevant when it describes:

- Unity project purpose and architecture;
- Unity version, packages, assemblies, scenes, prefabs, ScriptableObjects, Addressables, Resources, StreamingAssets, or platform integrations;
- build, release, testing, persistence, networking, analytics, monetization, localization, or AI-agent workflows for the Unity project;
- implementation plans, `FUTURE.md`, or repository task workflow.

## Unity Safety

- Do not open Unity.
- Do not run package resolution.
- Do not trigger asset import, GUID changes, serialized asset rewrites, or generated project changes.
- Exclude `Library/`, `Temp/`, `Obj/`, `Logs/`, `Build/`, `Builds/`, `UserSettings/`, package caches, generated API docs, ignored files, transient reports, secrets, local endpoints, and private logs unless the user explicitly requests a safe subset.
