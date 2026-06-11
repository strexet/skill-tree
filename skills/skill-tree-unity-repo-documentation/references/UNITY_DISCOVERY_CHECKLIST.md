# Unity Discovery Checklist

Use this checklist while building the evidence inventory. Mark areas not present only after checking likely evidence paths.

## Roots and Topology

- Unity roots: `Assets/`, `Packages/`, `ProjectSettings/`
- Packages: `Packages/manifest.json`, `Packages/packages-lock.json`, embedded packages
- Monorepo/tooling: `.github/`, build scripts, native companion projects, backend/tools folders

## Unity Baseline

- Exact editor version: `ProjectSettings/ProjectVersion.txt`
- Player settings: `ProjectSettings/ProjectSettings.asset`
- Editor and serialization settings: `ProjectSettings/EditorSettings.asset`
- Graphics and quality: `ProjectSettings/GraphicsSettings.asset`, `ProjectSettings/QualitySettings.asset`
- Package manager settings: `ProjectSettings/PackageManagerSettings.asset`

## Assemblies and Code

- `.asmdef` and `.asmref` files
- Runtime, editor, test, platform-specific assemblies
- `RuntimeInitializeOnLoadMethod`, `InitializeOnLoad`, `DefaultExecutionOrder`
- Compiler response files: `*.rsp`

## Startup and Content

- Build scenes: `ProjectSettings/EditorBuildSettings.asset`
- Bootstrap scenes/prefabs/assets
- `Resources/`, `StreamingAssets/`, Addressables settings
- ScriptableObject settings and databases
- Prefabs, prefab variants, scene references

## Runtime Systems

- Screens, navigation, gameplay modes
- Persistence: `PlayerPrefs`, `persistentDataPath`, save files, cloud save
- Networking: `UnityWebRequest`, HTTP clients, WebSockets, backend DTOs
- Platform integrations: `Assets/Plugins/Android/`, `Assets/Plugins/iOS/`, post-build scripts
- Analytics, ads, IAP, consent, notifications
- Localization, audio, accessibility, diagnostics

## Build and Test

- Build entry points: `BuildPipeline.BuildPlayer`, build scripts, CI jobs
- Android Gradle templates, iOS post-process build code, signing/secrets names
- Unity Test Framework assemblies, EditMode, PlayMode, integration/device tests
- Manual QA docs and smoke checks

## Safety

- Generated/transient directories: `Library/`, `Temp/`, `Obj/`, `Logs/`, `Build/`, `Builds/`, `UserSettings/`
- Secrets and credentials: document locations/names only, never values
- Existing docs drift: compare against current code and serialized state
- `FEATURES.md`/`FUTURE.md` split: current behavior only in `FEATURES.md`, planned work and known bugs awaiting fixes in `FUTURE.md`
- Issue discovery: inspect key code paths, tests, error handling, state transitions, persistence, mutation logic, and existing backlog before final handoff
