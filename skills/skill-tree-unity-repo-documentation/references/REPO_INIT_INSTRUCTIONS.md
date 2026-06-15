# Repository Documentation Initialization Instructions for an Existing Unity Project

Last updated: 2026-06-10
Primary audience: AI agents and senior developers documenting an existing Unity repository
Output language: English
Target repository type: an existing Unity project, Unity package repository, or monorepo containing one or more Unity projects

## 1. Purpose

This document defines a repeatable process for deeply analyzing an existing Unity repository and creating a coherent, AI-oriented documentation system for it.

The result must allow a future AI agent to understand, with minimal rediscovery:

- what the project is and what it is not;
- how the project is structured;
- which Unity version, packages, platforms, and build systems it uses;
- how runtime, editor, platform-specific, and test code interact;
- which features are implemented, partial, disabled, or planned;
- which files and systems own each behavior;
- which architectural and serialization constraints must not be violated;
- how to build, test, validate, and release the project;
- which changes require documentation updates;
- what work is active, pending refinement, or deferred;
- how to avoid polluting live source documents with snapshot copies.

The task is not complete after producing plausible prose. Every material statement must be derived from repository evidence, explicitly marked as an assumption, or recorded as an open question.

Do not copy domain-specific content from another project. Reuse only the documentation principles, responsibility boundaries, and validation discipline.

## 2. Required Deliverables

Create the documentation under the following default layout:

```text
README.md
AGENTS.md

Documents/
  PROJECT.md
  TECHNICAL.md
  FEATURES.md
  FUTURE.md
  RULES.md
  REPOSITORY_MAP.md
  BUILD_AND_RELEASE.md
  TESTING.md
  DEPENDENCIES.md
```

Create additional documents only when the repository provides enough evidence and the subject is materially important:

```text
Documents/
  UX_UI_MANIFEST.md
  PLATFORM_INTEGRATIONS.md
  BACKEND_AND_NETWORKING.md
  DATA_AND_PERSISTENCE.md
  ANALYTICS_AND_MONETIZATION.md
  LOCALIZATION.md
  SECURITY.md
  TROUBLESHOOTING.md
  REFERENCES.md
  DECISIONS.md
  GLOSSARY.md
```

### 2.1 Root-file exception

Keep the complete documentation set in `Documents/`, except:

- `README.md` must remain at repository root because it is the human entry point.
- `AGENTS.md` should remain at repository root because many AI coding tools discover it automatically.

`AGENTS.md` should be a concise handoff document that points agents to `Documents/RULES.md` and the relevant source-of-truth documents. Do not duplicate the full rule set in both places.

If the repository already uses another agent instruction file such as `CLAUDE.md`, `.github/copilot-instructions.md`, or tool-specific rule files, preserve them and make their responsibilities explicit. Avoid contradictory copies. Prefer one canonical rules document and thin tool-specific pointers.

### 2.2 Live filenames

Live repository documents must use stable names without snapshot markers or dates:

```text
PROJECT.md
TECHNICAL.md
FEATURES.md
FUTURE.md
RULES.md
AGENTS.md
```

Never create live files such as:

```text
PROJECT.snapshot-2026-06-10-12-30.md
FUTURE-2026-06-10.md
RULES_snapshot.md
```

Snapshot prefixes, suffixes, and timestamps are reserved for generated snapshot copies inside an explicitly requested snapshot archive.

## 3. Non-Negotiable Documentation Principles

### 3.1 Code and serialized project state are evidence

For current implementation claims, verify against the repository:

- C# source;
- assembly definition files;
- scenes;
- prefabs;
- ScriptableObject assets;
- package manifests and lock files;
- Project Settings;
- build scripts;
- CI configuration;
- native plugins;
- tests;
- generated configuration that is intentionally committed.

Documentation is not evidence merely because it already exists. Existing documentation may be stale.

### 3.2 Distinguish facts, decisions, assumptions, and plans

Use these meanings consistently:

- **Implemented**: verified in current code or serialized assets.
- **Partial**: some behavior exists, but important paths, platforms, tests, or UX are incomplete.
- **Configured**: enabled through project or build configuration, even if little project-owned code exists.
- **Disabled**: code or assets exist but are excluded, feature-flagged off, not included in builds, or otherwise inactive.
- **Deprecated**: retained for compatibility but should not be used for new work.
- **Planned**: not implemented; belongs in `FUTURE.md`.
- **Assumption**: plausible interpretation not fully proven by repository evidence.
- **Open question**: material uncertainty that requires owner input, runtime inspection, or external verification.

Never describe planned behavior as implemented.

### 3.3 Record exact ownership

Avoid statements such as “the project uses analytics” without ownership details.

Prefer:

```text
Runtime entry point:
  Assets/Game/Infrastructure/Analytics/AnalyticsManager.cs

Initialization:
  Bootstrap scene -> GameCompositionRoot -> AnalyticsManager.InitializeAsync()

Platform adapters:
  Assets/Plugins/Android/...
  Assets/Plugins/iOS/...

Configuration:
  Assets/Resources/AnalyticsSettings.asset

Tests:
  Assets/Tests/EditMode/Analytics/...
```

Use repository-relative paths. Include important types, methods, scenes, assets, and assembly names.

### 3.4 Optimize for future AI work

Documents must help an agent decide:

- what to read before editing;
- where behavior belongs;
- what must not be changed casually;
- which files are generated;
- which files are safe to edit;
- which validations are required;
- which docs must be updated with a change;
- where uncertainty remains.

Avoid marketing language, vague summaries, and prose that merely repeats class names.

### 3.5 Prefer one source of truth per subject

Each document must have a defined responsibility. Do not maintain the same detailed description in several files.

A recommended ownership map is:

```text
README.md                         repository entry point and basic setup
AGENTS.md                         short AI-agent handoff and mandatory reading
Documents/PROJECT.md              product/project purpose, scope, users, non-goals
Documents/TECHNICAL.md            foundational stack, architecture, data flow, constraints
Documents/FEATURES.md             current implemented and partial feature behavior
Documents/FUTURE.md               active work queue, pending intake, deferred backlog
Documents/RULES.md                AI-agent workflow and repository editing rules
Documents/REPOSITORY_MAP.md       physical repository layout and code ownership map
Documents/BUILD_AND_RELEASE.md     local builds, CI, signing, platform release flow
Documents/TESTING.md              test topology, commands, environments, validation matrix
Documents/DEPENDENCIES.md         packages, SDKs, plugins, sources, update constraints
```

Optional documents own only their specialized subject.

## 4. Phase 0 — Protect the Repository Before Analysis

Before reading broadly or creating files:

1. Confirm the repository root.
2. Check worktree state.
3. Identify whether the repository contains one Unity project, several Unity projects, Unity packages, native companion projects, or external tools.
4. Do not discard, reset, overwrite, reimport, upgrade, or normalize unrelated user changes.
5. Do not open the project in a different Unity version.
6. Do not let Unity regenerate serialized files merely for documentation.
7. Do not run package resolution, builds, tests, migrations, signing, uploads, or deployment unless the task explicitly permits them.
8. Do not edit project files during the discovery phase.
9. Record pre-existing uncommitted changes and keep documentation changes isolated.

Recommended initial commands:

```bash
git status --short
git rev-parse --show-toplevel
find . -name ProjectVersion.txt -path '*/ProjectSettings/*' -print
find . -name manifest.json -path '*/Packages/*' -print
find . -name '*.asmdef' -o -name '*.asmref'
find . -name '*.sln' -o -name '*.csproj'
```

Adapt commands to the environment. Do not assume GNU-only flags are available on macOS.

### 4.1 Unity-root detection

A Unity project root normally contains:

```text
Assets/
Packages/
ProjectSettings/
```

Confirm the version from:

```text
ProjectSettings/ProjectVersion.txt
```

Do not infer the Unity version from a CI image, README, or package metadata when `ProjectVersion.txt` is available.

### 4.2 Generated and transient directories

Exclude transient content from documentation analysis unless a build issue specifically requires it:

```text
Library/
Temp/
Obj/
Logs/
Build/
Builds/
UserSettings/
MemoryCaptures/
Recordings/
.gradle/
DerivedData/
```

Also identify project-specific generated folders. Document whether they are committed and who generates them.

## 5. Phase 1 — Build an Evidence Inventory

Create a temporary evidence ledger before writing narrative documentation. The ledger may remain outside the repository or be discarded after the documents are complete.

Use a table with at least these fields:

```text
Subject
Claim
Evidence path
Evidence symbol or key
Evidence type
Confidence
Conflicting evidence
Target document
Open question
```

Example:

```text
Subject: Startup
Claim: MainMenu is the first player scene.
Evidence path: ProjectSettings/EditorBuildSettings.asset
Evidence key: enabled scene index 0
Evidence type: serialized project setting
Confidence: high
Conflicting evidence: CI build script replaces scene list for benchmark build
Target document: TECHNICAL.md, REPOSITORY_MAP.md
Open question: whether benchmark build is shipped externally
```

### 5.1 Confidence levels

Use:

- **High**: directly established by code, serialized settings, package lock, or tests.
- **Medium**: established by several consistent indirect signals.
- **Low**: inferred from naming, dead code, comments, or incomplete configuration.

Do not silently convert low-confidence findings into facts.

### 5.2 Source precedence

Use this default precedence for current behavior:

1. Current code, serialized assets, Project Settings, and package lock.
2. Build scripts and CI configuration actually used by current pipelines.
3. Tests that exercise current code.
4. Current repository documentation.
5. Commit history and release notes.
6. Official third-party documentation.
7. Issue descriptions, comments, community posts, or assumptions.

A higher-ranked source is not automatically correct in every conflict. Investigate whether the lower-ranked source describes intended behavior while code contains a bug. Record the discrepancy instead of flattening it.

## 6. Phase 2 — Perform a Deep Unity Repository Analysis

The analysis must cover the following areas. Mark irrelevant areas as not present only after checking.

## 6.1 Repository topology

Determine:

- single Unity application, package, SDK, sample project, or monorepo;
- locations of Unity roots;
- embedded or local UPM packages;
- native Android/iOS projects;
- backend, web dashboard, tools, generators, or deployment scripts;
- test-only projects;
- submodules and Git LFS usage;
- generated source or generated assets;
- ownership boundaries between first-party and third-party code.

Inspect:

```text
Assets/
Packages/
ProjectSettings/
.github/
.gitlab-ci.yml
Jenkinsfile
TeamCity configuration
build scripts
fastlane/
gradle files
Podfile or CocoaPods integration
external tool directories
```

Document repository-relative paths, not machine-specific absolute paths.

## 6.2 Unity and player baseline

Extract and verify:

- exact Unity editor version and revision;
- active or supported build targets;
- scripting backend per target;
- API compatibility level;
- managed stripping level;
- IL2CPP settings;
- architecture settings;
- minimum and target OS versions;
- graphics APIs;
- color space;
- render pipeline;
- input system;
- domain reload and scene reload settings if relevant;
- serialization mode;
- asset pipeline version if material;
- package manager configuration and scoped registries;
- scripting define symbols per target;
- compiler response files;
- unsafe-code settings;
- assembly versioning if present.

Primary evidence usually includes:

```text
ProjectSettings/ProjectVersion.txt
ProjectSettings/ProjectSettings.asset
ProjectSettings/EditorSettings.asset
ProjectSettings/GraphicsSettings.asset
ProjectSettings/QualitySettings.asset
ProjectSettings/PackageManagerSettings.asset
Packages/manifest.json
Packages/packages-lock.json
Assets/**/*.rsp
```

Do not dump entire YAML files into documentation. Summarize decisions and cite the exact keys or paths used.

## 6.3 Package and dependency analysis

Classify dependencies as:

- Unity registry package;
- scoped-registry package;
- Git package;
- local package;
- embedded package;
- Asset Store or manually imported plugin;
- native SDK;
- generated dependency;
- transitive dependency;
- project-owned package.

For each material dependency record:

```text
Name
Resolved version or revision
Source
Purpose
Primary integration path
Initialization owner
Platform scope
Update constraints
Known conflicts
License location when available
Whether the dependency is safe to upgrade independently
```

Inspect both `manifest.json` and `packages-lock.json`. The manifest expresses intent; the lock file expresses resolution.

For manually imported SDKs, inspect plugin metadata, version files, changelogs, native binaries, package manifests, and integration code. Do not guess versions from folder names alone.

## 6.4 Assembly and code architecture

Build an assembly-level map from `.asmdef` and `.asmref` files.

Record:

- runtime assemblies;
- editor-only assemblies;
- EditMode and PlayMode test assemblies;
- platform-constrained assemblies;
- optional-reference or version-define behavior;
- friend assemblies;
- cyclic or suspicious dependencies;
- code compiled into `Assembly-CSharp` because no `.asmdef` exists;
- package assembly boundaries.

Then identify architectural layers actually present, for example:

```text
Bootstrap / composition root
Presentation / UI
Gameplay
Domain rules
Application or use-case orchestration
Infrastructure
Networking
Persistence
Analytics
Monetization
Platform adapters
Editor tooling
Build tooling
Tests
```

Do not impose a clean-layered architecture that the repository does not have. Describe the current architecture first. Recommendations belong in `FUTURE.md`, not in the current-state sections.

## 6.5 Startup and lifecycle

Trace startup from actual evidence:

- first enabled scene in build settings;
- custom scene-list generation in build scripts;
- runtime initialization attributes;
- static constructors;
- bootstrap prefabs;
- preloaded assets;
- ScriptableObject-based installers;
- dependency-injection containers;
- service locators;
- persistent `DontDestroyOnLoad` objects;
- addressable startup;
- authentication or remote-config gates;
- app lifecycle hooks;
- pause, focus, quit, low-memory, deep-link, and notification handling.

Relevant evidence may include:

```text
ProjectSettings/EditorBuildSettings.asset
ProjectSettings/ProjectSettings.asset
Assets/**/Bootstrap*
RuntimeInitializeOnLoadMethod
InitializeOnLoad
InitializeOnLoadMethod
DefaultExecutionOrder
ScriptExecutionOrder
Resources/
Preloaded Assets
Addressables settings
```

Produce a concise startup sequence such as:

```text
Player launch
-> bootstrap scene
-> composition root
-> local configuration load
-> platform services initialization
-> consent gate
-> remote configuration
-> authentication/profile load
-> main scene transition
```

Mark conditional, asynchronous, and platform-specific branches.

## 6.6 Scenes, prefabs, and serialized assets

Inventory:

- scenes included in player builds;
- scenes used only by tests, tools, demos, or benchmarks;
- additive scene flows;
- bootstrap and persistent scenes;
- major prefabs;
- prefab variants;
- ScriptableObject databases and settings;
- Addressables groups and labels;
- Resources and StreamingAssets;
- asset bundles;
- remote content catalogs;
- localization tables;
- timeline, animator, input, shader, and render-pipeline assets when architecturally important.

Unity serialization is a critical constraint. Document:

- whether text serialization and visible meta files are enabled;
- whether scenes and prefabs are expected to be edited manually;
- any custom migration tooling;
- GUID-sensitive content;
- `FormerlySerializedAs` usage;
- managed-reference serialization;
- polymorphic or custom-serialized data;
- generated assets;
- rules for moving or renaming assets.

Never tell agents to recreate `.meta` files, change GUIDs, or edit serialized YAML casually.

## 6.7 Runtime feature inventory

Derive features from user-visible flows and code ownership, not from menu labels alone.

Search for:

- screens, windows, panels, and navigation;
- gameplay states and game modes;
- save/load flows;
- networking and account flows;
- in-app purchases;
- advertisements;
- analytics;
- notifications;
- remote configuration;
- content delivery;
- localization;
- audio;
- tutorials;
- accessibility;
- cheats and debug menus;
- moderation or customer-support tools;
- platform services;
- crash reporting;
- privacy and consent.

For each feature, determine status, entry point, owning modules, data, side effects, platform differences, failure behavior, and tests.

## 6.8 Data, persistence, and migrations

Document all persistent state:

- `PlayerPrefs`;
- JSON, binary, protobuf, SQLite, or custom files;
- ScriptableObject configuration;
- cloud save;
- backend profiles;
- addressable catalogs;
- cached remote configuration;
- secure storage;
- platform keychain/keystore;
- analytics identity;
- consent state;
- save schema and migration versions;
- editor-only caches that affect generated output.

For each store record:

```text
Purpose
Location
Format
Schema/versioning
Read/write owner
Encryption or protection
Migration path
Clear/reset behavior
Cloud synchronization
Test coverage
Sensitive fields
```

Do not claim `PlayerPrefs` or local files are secure storage.

## 6.9 Networking and backend integrations

Identify:

- backend base URLs and environment selection;
- transport libraries;
- request abstraction;
- authentication;
- retry and timeout policy;
- offline behavior;
- request signing;
- certificate pinning;
- WebSockets or realtime transport;
- API DTO generation;
- remote config;
- CDN and Addressables remote paths;
- telemetry endpoints;
- development, staging, and production environments;
- mock servers and test endpoints.

Never copy live secrets into documentation. Use secret names and provisioning paths, not values.

If endpoint semantics cannot be established locally, create `REFERENCES.md` and record the official source that must be checked before changes.

## 6.10 Platform-specific integrations

Inspect at minimum:

```text
Assets/Plugins/Android/
Assets/Plugins/iOS/
Assets/Plugins/macOS/
Assets/Plugins/Windows/
Assets/Plugins/WebGL/
Assets/Editor/
```

Record:

- Android manifests, Gradle templates, repositories, ProGuard/R8 rules, AAR/JAR libraries, activities, services, providers, permissions, intent filters, and dependency-resolution tooling;
- iOS frameworks, XCFrameworks, bundles, plist edits, entitlements, CocoaPods, post-process build code, privacy manifests, and signing capabilities;
- desktop native libraries and architecture support;
- WebGL templates, JavaScript libraries, browser storage, and hosting assumptions;
- platform compile guards and fallback behavior.

Describe which layer owns each integration and whether the native files are source, vendored binaries, generated output, or post-build modifications.

## 6.11 Build and release pipeline

Trace the real build path:

- local developer build;
- command-line Unity build method;
- CI pipeline entry point;
- target matrix;
- environment selection;
- version and build-number generation;
- content build;
- pre-build validation;
- post-build processing;
- Android Gradle build;
- iOS Xcode/CocoaPods/Fastlane flow;
- signing and provisioning;
- symbols and crash-reporting upload;
- artifact naming;
- store upload;
- release notes;
- rollback or hotfix process.

For every command, establish:

```text
Working directory
Required Unity version
Required external tools
Required environment variables or secret names
Expected outputs
Whether the command is safe locally
Whether it mutates generated project files
```

Do not invent a build command from a method name. Verify how CI invokes it.

## 6.12 Testing and validation

Inventory:

- Unity Test Framework version;
- EditMode tests;
- PlayMode tests;
- integration tests;
- scene tests;
- device tests;
- native plugin tests;
- backend contract tests;
- screenshot/golden tests;
- performance tests;
- smoke tests;
- manual QA checklists;
- CI test jobs;
- code coverage;
- static analysis;
- formatting or linting.

Separate:

- commands verified in the repository;
- commands inferred but not run;
- tests actually run during the documentation task;
- tests not run.

Do not state that tests pass unless they were executed successfully in the current environment.

## 6.13 Diagnostics and observability

Identify:

- logging facade;
- log levels and categories;
- file logs;
- in-game console;
- debug overlays;
- crash reporting;
- analytics diagnostics;
- remote logging;
- symbol upload;
- redaction rules;
- support bundles;
- device identifiers and privacy implications.

Document how to gather logs on supported platforms without exposing secrets.

## 6.14 Performance-sensitive architecture

Record material performance constraints:

- central update loops;
- object pooling;
- allocation-sensitive paths;
- Burst/Jobs/DOTS;
- async model: coroutines, Tasks, UniTask, custom schedulers;
- main-thread requirements;
- asset-loading strategy;
- scene loading;
- shader variants;
- memory budgets;
- platform-specific quality tiers;
- known profiler markers;
- startup-time constraints.

Do not perform speculative optimization during documentation initialization. Put validated improvement work in `FUTURE.md`.

## 6.15 Security, privacy, and destructive operations

Identify:

- credentials and API keys;
- signing material;
- user identifiers;
- purchase receipts;
- personal data;
- analytics and attribution;
- consent management;
- data deletion;
- debug exports;
- test accounts;
- admin/debug commands;
- remote code or content loading;
- encryption and secure storage;
- anti-cheat or integrity checks.

Document secret *locations and provisioning mechanisms*, never secret values.

Treat these as high-risk changes requiring explicit review:

- authentication;
- purchases and receipt validation;
- consent and privacy flows;
- production endpoints;
- signing;
- certificate pinning;
- account deletion;
- cloud save migrations;
- remotely controlled behavior;
- anti-cheat;
- code stripping and native plugin integration.

## 6.16 Existing documentation and drift audit

Read all repository-owned Markdown and relevant text documentation.

For each document classify it as:

- current and useful;
- partially stale;
- duplicated;
- generated;
- vendor-owned;
- obsolete;
- missing critical context.

Do not overwrite useful specialized documentation. Integrate it into the new responsibility map.

When docs and code disagree:

1. Verify current code and configuration.
2. Check tests and build scripts.
3. Check recent history when available.
4. Determine whether code is wrong, docs are stale, or intended behavior is incomplete.
5. Record unresolved conflict as an open question or `FUTURE.md` task.
6. Do not “fix” code merely to make it match old documentation during a documentation task.

## 6.17 Code issue discovery during documentation

Documentation review must not silently ignore meaningful code or architecture problems discovered during inspection.

Before finalizing documents, inspect:

- key implementation paths;
- tests;
- error handling;
- state transitions;
- persistence and mutation logic;
- existing `FUTURE.md` entries.

Add noteworthy findings to the active `FUTURE.md` `Backlog` section when evidence supports them. Do not add documentation/audit findings to `Pending Queue`. Valid findings include confirmed bugs, strongly suspected bugs, broken or risky logic, documentation/code drift, architectural issues, missing validation, missing tests, error-handling gaps, security or data-safety concerns, maintainability problems, performance risks, and dead or misleading code.

Each added backlog entry should include:

- finding type: confirmed bug, strongly suspected issue, documentation inconsistency, or improvement opportunity;
- evidence;
- affected paths and symbols;
- user or technical impact;
- suggested investigation or implementation direction;
- acceptance criteria;
- focused tests where relevant.

Merge with existing backlog entries when the same issue is already documented. Do not duplicate tasks. Do not present speculation as a confirmed bug. Do not add trivial style observations unless they materially affect maintainability or correctness. Do not automatically fix unrelated code bugs unless implementation work is explicitly requested.

## 7. Phase 3 — Create the Documentation Set

Create documents in this order so later files can reference established facts:

1. `Documents/REPOSITORY_MAP.md`
2. `Documents/TECHNICAL.md`
3. `Documents/PROJECT.md`
4. `Documents/FEATURES.md`
5. `Documents/BUILD_AND_RELEASE.md`
6. `Documents/TESTING.md`
7. `Documents/DEPENDENCIES.md`
8. Optional specialized documents
9. `Documents/FUTURE.md`
10. `Documents/RULES.md`
11. root `AGENTS.md`
12. root `README.md`

Do not write `README.md` first. It should summarize the already validated documentation, not become the source from which the rest is guessed.

## 8. Document Specification — `README.md`

`README.md` is the concise entry point for developers.

Include:

```text
Project name
One-paragraph purpose
Current project status
Major implemented features
Technical baseline
Repository layout
Prerequisites
How to open the Unity project
How to run the most common verified build/test flow
Links to detailed documents
Important safety notes
```

Unity-specific baseline should normally mention:

- exact Unity version;
- primary target platforms;
- render pipeline if material;
- major package or framework choices;
- whether the repository is an app, package, SDK, or monorepo.

Do not turn README into a complete architecture manual.

Use only verified commands. If project opening or build steps require proprietary tooling, state that explicitly.

## 9. Document Specification — `AGENTS.md`

Keep `AGENTS.md` short enough that an AI agent will actually read it.

Recommended content:

```markdown
# AI Agent Entry Point

Before making non-trivial changes:

1. Read `Documents/RULES.md`.
2. Read `Documents/TECHNICAL.md` for architecture, Unity, package, platform, build, persistence, or dependency work.
3. Read `Documents/FEATURES.md` for current feature behavior.
4. Read `Documents/FUTURE.md` only when implementing or refining planned work.
5. Read `Documents/BUILD_AND_RELEASE.md` before changing build, CI, signing, versioning, native post-processing, or release behavior.
6. Read `Documents/TESTING.md` before running or changing tests.
7. Inspect current code, serialized assets, and tests in the affected area.

Do not change Unity version, package versions, scripting backend, serialization mode, assembly boundaries, native plugins, signing, scenes, prefabs, ScriptableObject schemas, or asset GUIDs without evidence and explicit scope.

Update the owning documentation in the same change set when behavior changes.
```

Adjust paths for the repository. Add only critical project-specific warnings.

## 10. Document Specification — `Documents/PROJECT.md`

This file describes the project from a product and operational perspective.

Include:

- project summary;
- current lifecycle state;
- intended users or players;
- core value;
- supported platforms;
- primary feature areas;
- expected high-level user flow;
- product principles;
- non-goals;
- known operational constraints;
- relation to technical documents.

Do not include detailed class diagrams, package versions, or build commands.

A suitable structure:

```text
# Project

Last validated:
Primary audience:

## Purpose
## Current Status
## Target Users
## Supported Platforms
## Core User or Player Flow
## Major Product Areas
## Product Principles
## Non-Goals
## Known Constraints
## Documentation Map
## Open Questions
```

For internal SDK or infrastructure repositories, replace “players” with integrators, game teams, QA engineers, build engineers, or other actual consumers.

## 11. Document Specification — `Documents/TECHNICAL.md`

This is the source of truth for foundational technical decisions.

Include:

```text
# Technical Architecture

Last validated:
Primary audience:
Project type:
Unity version:

## Purpose
## Source-of-Truth Hierarchy
## Technical Baseline
## Repository Topology
## Assembly Architecture
## Startup and Lifecycle
## Scene and Content Architecture
## Runtime Data Flow
## Persistence and Migrations
## Networking and Backend
## Platform Integrations
## Build Architecture
## Testing Baseline
## Logging and Diagnostics
## Performance Constraints
## Security and Privacy
## Foundational Decisions Requiring This Document to Change
## Current Technical Decision Summary
## Open Questions
```

### 11.1 Technical baseline

Record exact, current values where evidence exists:

```text
Unity editor:
Primary language:
API compatibility:
Scripting backend by target:
Render pipeline:
Input system:
Async model:
Dependency injection or service location:
Primary persistence:
Networking:
Primary target platforms:
Package source policy:
Serialization mode:
```

### 11.2 Architecture boundaries

Document real boundaries and explicit rules. Examples:

- runtime code must not depend on editor assemblies;
- UI must not call native SDK wrappers directly;
- business rules must not be hidden in MonoBehaviour view scripts;
- platform adapters must be behind interfaces;
- build-time mutation belongs in Editor/build tooling;
- generated files must not be edited manually;
- ScriptableObject configuration ownership must be explicit;
- domain code must not assume Unity main-thread access unless documented;
- scene objects must not become global service locators accidentally;
- package code must not reference game-specific assemblies.

Use only rules justified by current architecture or clearly adopted as repository policy.

### 11.3 Unity serialization rules

Include a dedicated section when the repository contains meaningful serialized content:

- keep `.meta` files with assets;
- never regenerate GUIDs intentionally unless performing a documented migration;
- use Unity or approved tooling for complex scene/prefab edits;
- avoid broad YAML formatting;
- preserve serialized field names or use `FormerlySerializedAs`;
- update migrations when changing persisted ScriptableObject or save schemas;
- review prefab overrides and missing script references;
- do not move assets across package/project boundaries casually.

### 11.4 Update policy

State what requires updating `TECHNICAL.md`, for example:

- Unity version;
- supported platforms;
- render pipeline;
- scripting backend;
- package source policy;
- assembly topology;
- startup/composition model;
- persistence technology;
- backend integration model;
- native plugin architecture;
- build pipeline;
- test baseline;
- security policy.

Do not update it for isolated bug fixes or UI copy changes.

## 12. Document Specification — `Documents/REPOSITORY_MAP.md`

This is the physical navigation map for humans and AI agents.

Include:

- repository tree with only meaningful paths;
- path responsibility table;
- Unity roots;
- packages;
- runtime code;
- editor code;
- tests;
- scenes;
- serialized data;
- platform plugins;
- build tooling;
- CI;
- generated output;
- vendor code;
- documentation;
- files that must not be edited manually.

Example:

```text
Assets/Game/Runtime/          project-owned runtime code
Assets/Game/Editor/           project-owned editor tooling
Assets/Game/Tests/EditMode/   EditMode tests
Assets/Game/Tests/PlayMode/   PlayMode tests
Assets/Plugins/               native and managed third-party plugins
Packages/                     UPM dependencies and local packages
ProjectSettings/              Unity project configuration
BuildScripts/                 command-line and CI build entry points
Documents/                    live project documentation
```

Add an assembly ownership table:

```text
Assembly
Type
Primary responsibility
Allowed dependencies
Platform constraints
Tests
```

Add a “Start here for…” index:

```text
Startup bug -> ...
Android manifest issue -> ...
Save migration -> ...
Analytics event -> ...
UI screen -> ...
Build versioning -> ...
```

Do not reproduce every directory.

## 13. Document Specification — `Documents/FEATURES.md`

This file contains current implemented or partial behavior only.

Planned-only work belongs in `FUTURE.md`.
Future sections, roadmaps, pending implementation plans, proposed features, and deferred work do not belong in `FEATURES.md`.
Current limitations may be documented only as present behavior; plans to resolve them belong in `FUTURE.md`.

Use this template for each material feature:

```text
## Feature Name

Status:
Owner assemblies/modules:
Runtime entry point:
Editor/build entry point:
Primary scenes/prefabs/assets:
Primary data:
External services or SDKs:
Mutates persistent or remote state:
Platform scope:
Offline behavior:
Feature flags:
Performance sensitivity:

### Goal
### User or System Flow
### Inputs
### Outputs
### State and Persistence
### Runtime Interaction
### Platform-Specific Behavior
### Algorithm or Rules
### Validation and Preconditions
### Error Handling and Recovery
### Security and Privacy
### Diagnostics
### Tests
### Known Limitations
### Open Questions
```

Omit fields that are truly irrelevant, but keep the structure consistent.

### 13.1 Feature status rules

Use:

```text
Implemented
Partial
Configured
Disabled
Deprecated
```

Do not use `Planned` in `FEATURES.md`.
Do not include a `Future Work`, `Roadmap`, `Next Steps`, `Pending`, or equivalent planning section in `FEATURES.md`.

### 13.2 Feature granularity

Create feature sections for coherent user or infrastructure behavior, not every class.

Good examples:

- authentication and profile loading;
- save system;
- remote configuration;
- analytics initialization;
- advertisement mediation;
- consent flow;
- addressable content update;
- combat loop;
- inventory;
- tutorial;
- build versioning;
- crash reporting;
- deep links;
- push notifications.

Bad examples:

- every button;
- every utility;
- every DTO;
- every MonoBehaviour.

### 13.3 Evidence requirements

Each section must name concrete owners. When behavior depends on scene wiring or a ScriptableObject, name those assets. When a feature is platform-specific, describe the compile guards and native integration points.

## 14. Document Specification — `Documents/FUTURE.md`

`FUTURE.md` is the single source of truth for not-yet-implemented work, planned improvements, backlog items, known bugs awaiting fixes, documentation improvements, proposed features, refactoring plans, and deferred investigations.

It must contain three distinct queues:

```text
## Pending Queue
## Prioritized Next Changes
## Backlog
```

### 14.1 Queue semantics

**Pending Queue**

Use for raw owner/user requests, rough task notes, or explicitly captured intake that is not yet implementation-ready.

Do not put issues discovered during Unity documentation initialization or documentation audit in `Pending Queue`. Documentation/audit findings must go to `Backlog` unless the owner explicitly asks to treat the item as pending intake.

A pending item may lack:

- confirmed reproduction;
- affected paths;
- technical approach;
- dependencies;
- acceptance criteria;
- implementation constraints;
- explicit non-goals;
- required contextual decisions;
- priority placement.

Pending items must never be implemented directly. They must first be researched, validated, expanded, and moved into `Prioritized Next Changes`.

**Prioritized Next Changes**

Use for validated, maximally detailed, self-contained work that is ready for implementation.

Order entries from top to bottom by priority.

A task in this section must contain enough verified context and implementation guidance that the implementing agent can normally complete it without:

- rediscovering the original request;
- reading unrelated areas of the repository;
- modifying components not named or justified by the task;
- inventing product decisions;
- inventing architecture or ownership;
- searching the `Backlog` for missing context;
- performing opportunistic cleanup;
- broadening scope merely because neighboring code could also be improved.

The expected standard is deliberately high: a prioritized task should describe the intended change so completely that nearly all code, assets, settings, tests, and documentation outside its stated `Touch`, dependencies, and justified discovery scope can remain untouched.

This does not prohibit inspecting dependencies or adjacent code needed to implement the task safely. It prohibits changing unrelated behavior or treating a concise task description as permission for broad repository work.

Every task in `Prioritized Next Changes` must contain an explicit `Questions and required clarifications` section. The section may state that no unresolved questions remain, but it must not be omitted.

**Backlog**

Use for valid but deliberately deferred work.

Use `Backlog` for issues discovered while creating or auditing documentation, including confirmed bugs, strongly suspected bugs, documentation/code drift, maintainability problems, missing validation, missing tests, performance risks, security/data-safety concerns, and improvement opportunities.

Backlog items may be less implementation-ready than prioritized tasks, but they should still preserve the original intent and useful evidence.

A task must be explicitly promoted from `Backlog` into `Prioritized Next Changes` and expanded to the full prioritized-task standard before implementation.

Implementation commands must never select work directly from `Backlog`.

### 14.2 Task intake and validation

Gather future work from:

- explicit user or owner requests;
- existing issue/task documents;
- repository TODOs and FIXMEs;
- reproducible defects;
- incomplete code paths;
- disabled features with clear intent;
- failing or skipped tests;
- current documentation open questions that require implementation;
- release notes identifying known limitations.

Do not create tasks solely because an agent imagines a “better architecture.”

Before adding or promoting a task:

1. Check whether it is already implemented.
2. Search the affected code, assets, scenes, prefabs, settings, tests, and current documentation.
3. Identify the actual owners and affected paths.
4. Check for related tasks in all three queues to avoid duplication.
5. Verify whether the requested behavior conflicts with current architectural or platform constraints.
6. Identify product, UX, technical, platform, migration, compatibility, and validation questions.
7. Remove, merge, or rewrite stale tasks.
8. Preserve unresolved decisions as explicit questions rather than silently choosing an implementation.

### 14.3 Required file header

```text
# Future Work

Last validated: YYYY-MM-DD.

This is the single implementation queue. Items higher in
`Prioritized Next Changes` are higher priority.

`Process pending tasks` and `Process pending` refine Pending Queue entries
and move implementation-ready tasks into `Prioritized Next Changes`.

`Implement next feature` and `Implement next` operate only on
`Prioritized Next Changes`. They never select tasks from `Backlog`.

Implemented behavior belongs in `FEATURES.md`.
Foundational decisions belong in `TECHNICAL.md`.
Build/release behavior belongs in `BUILD_AND_RELEASE.md`.
Remove an item from this file when it ships.
```

The generated `FUTURE.md` must also include a repo-local `## Pending Task Format` section before `## Pending Queue`. This section must tell agents to use the pending item template from section 14.8 when a user asks them to add a new pending task, and it must include the full nested Markdown template so agents working only inside the initialized repository can follow the format without access to this skill.

### 14.4 Command semantics

The generated `FUTURE.md` and `RULES.md` must define the following command behavior.

#### 14.4.1 `Process pending tasks` and `Process pending`

Treat these commands as equivalent.

When instructed to process pending tasks, the agent must:

1. MUST read repository `AGENTS.md`, `RULES.md`, or equivalent rules.
2. MUST read the repository/document map if one exists.
3. MUST read current `FEATURES.md`, active `FUTURE.md`, and source-of-truth documents relevant to each pending item.
4. Read the complete `Pending Queue`.
5. MUST inspect current implementation, serialized assets, settings, tests, and history as needed.
6. MUST verify referenced paths and symbols still exist.
7. Check whether each request is already implemented, obsolete, duplicated, contradictory, or blocked.
8. Check existing `FUTURE.md` tasks for overlap.
9. Merge overlapping pending entries when they describe the same coherent change.
10. Expand each valid request into a maximally detailed task using the full prioritized-task template and current code/test paths.
11. Add a mandatory `Questions and required clarifications` section to every promoted task.
12. Include questions about possible implementation approaches and additional task context, not only obvious missing acceptance criteria.
13. Answer questions from repository evidence when possible.
14. Mark answers as verified, inferred, recommended, or unresolved.
15. Move only implementation-ready entries into `Prioritized Next Changes`.
16. Leave blocked or insufficiently understood entries in `Pending Queue` with an explanation of what is missing.
17. Place promoted tasks according to explicit priority placement or the repository’s documented prioritization rules.
18. Remove the original pending entry only after its information has been preserved in the promoted task.
19. Report which repository rules, documents, code paths, and tests were inspected.

Processing pending work is a documentation and research operation. It does not implement the task unless the user explicitly combines the commands.

A promoted task must not be a lightly expanded version of the pending bullet. It must be detailed enough to serve as the implementation contract.
Agents MUST NOT process pending work from `FUTURE.md` alone. Stop or mark the item blocked when required repository context is missing or contradictory.

#### 14.4.2 Mandatory implementation questions

Every task promoted to `Prioritized Next Changes` must include implementation-oriented questions covering all material ambiguity.

Potential question areas include:

- intended user-visible behavior;
- exact trigger and entry point;
- supported and unsupported flows;
- UI/UX placement and states;
- architecture and ownership;
- reuse versus introduction of new abstractions;
- scene, prefab, ScriptableObject, and serialization impact;
- data ownership, persistence, and migration;
- networking or backend contract changes;
- platform differences;
- package or SDK constraints;
- backward compatibility;
- failure and recovery behavior;
- diagnostics and telemetry;
- testing strategy;
- rollout or feature-flag behavior;
- out-of-scope neighboring behavior;
- documentation ownership.

Do not add generic filler questions. Questions must be specific to the task and grounded in repository findings.

Use question states such as:

```text
- [Resolved — repository evidence] Question?
  Answer:
  Evidence:

- [Resolved — owner decision] Question?
  Answer:

- [Recommended default — confirmation optional] Question?
  Recommendation:
  Rationale:

- [Unresolved — blocks implementation] Question?
  Why it matters:
  Required answer from:

- [Unresolved — non-blocking] Question?
  Safe default:
  Consequence:
```

When processing pending tasks, resolve what can be resolved from evidence. Preserve genuine ambiguity.

#### 14.4.3 Clarification gate before implementation

Before implementing a task from `Prioritized Next Changes`, the agent must read its complete `Questions and required clarifications` section.

Before editing, the agent MUST read repository `AGENTS.md`, `RULES.md`, or equivalent rules; MUST read the repository/document map if one exists; MUST inspect all documents referenced by the task; MUST read current-state docs such as `FEATURES.md` and task-relevant architecture/domain docs; MUST inspect current code and tests for affected paths and symbols; MUST check for recent changes that invalidate task assumptions or make the task already complete; and MUST check active `FUTURE.md` tasks for duplicate or overlapping work.

The agent MUST NOT implement from `FUTURE.md` alone.

If any unresolved question can materially affect:

- public or user-visible behavior;
- architecture;
- affected files or systems;
- serialized or persistent data;
- backend or native contracts;
- compatibility;
- security or privacy;
- migration;
- destructive behavior;
- acceptance criteria;

the agent must ask the user or designated owner for clarification and stop implementation of that task until the necessary answer is provided.

The agent must not guess merely to keep implementation moving.

Non-blocking questions may use an explicitly documented safe default only when the task already states that default and its consequences.

After receiving answers:

1. update the task’s question entries;
2. incorporate the decisions into implementation notes and acceptance criteria;
3. keep relevant rationale and evidence;
4. then begin implementation.

#### 14.4.4 `Implement next feature` and `Implement next`

Treat these commands as equivalent.

Without a task name:

```text
Implement next feature
Implement next
```

the agent must:

1. Open `FUTURE.md`.
2. Read `Prioritized Next Changes`.
3. Select the first task in that section.
4. Ignore `Pending Queue` and `Backlog` for task selection.
5. Stop and report that no prioritized task is available when the section is empty.
6. Perform mandatory repository orientation and the clarification gate before editing.
7. Implement only the selected task.

With a task name:

```text
Implement next feature: Task Name
Implement next: Task Name
```

the agent must:

1. Search only `Prioritized Next Changes`.
2. Match the requested task name against headings in that section.
3. Use an exact case-insensitive normalized heading match unless repository rules define aliases.
4. Implement the matching task only.
5. Stop without implementation when no matching prioritized task exists.
6. Report clearly that the named task was not found in `Prioritized Next Changes`.
7. Do not fall back to:
   - the first prioritized task;
   - a similarly named backlog task;
   - a pending entry;
   - repository TODOs;
   - an inferred task.
8. Perform the clarification gate before editing.

If more than one prioritized task has the same normalized name, stop and report the ambiguity. Do not choose one arbitrarily.

#### 14.4.5 Selection boundaries

`Implement next` commands interact only with `Prioritized Next Changes`.

They must never:

- promote a backlog item automatically;
- implement a pending item;
- search the backlog for a requested name;
- interpret backlog ordering as implementation priority;
- process pending tasks implicitly;
- combine multiple prioritized tasks;
- replace a missing named task with a similar task;
- implement unrelated cleanup discovered during repository inspection.

A user must explicitly request backlog promotion or pending processing before such work becomes eligible for `Implement next`.

### 14.5 Implementor rules

Include rules such as:

1. Read the owning source-of-truth documents.
2. Select work only according to the command semantics above.
3. Process pending intake before starting a matching task that has not yet been promoted.
4. Implement one prioritized entry at a time.
5. Read the entire selected task, including questions, dependencies, non-goals, risks, and documentation updates.
6. Ask blocking unresolved questions before implementation.
7. Do not bundle unrelated cleanup.
8. Respect `Touch` limits unless new evidence requires a documented expansion.
9. When scope must expand, explain why and update the task before changing the additional area.
10. Add or update tests.
11. Update current-state documentation when behavior ships.
12. Do not guess third-party SDK behavior.
13. Do not change Unity/package/platform foundations silently.
14. Remove the shipped entry instead of marking it completed forever.
15. Never use `Backlog` as hidden implementation context for an `Implement next` command.
16. Report which repository rules, documents, code paths, and tests were inspected.

### 14.6 Prioritized-task completeness standard

Every task in `Prioritized Next Changes` must be a practical implementation contract.

It should normally contain enough detail to establish:

- why the change exists;
- verified current behavior;
- desired behavior;
- exact scope;
- affected modules and likely paths;
- known entry points;
- relevant scenes, prefabs, assets, settings, and assemblies;
- data and state changes;
- dependencies;
- explicit non-goals;
- implementation constraints;
- possible implementation approaches;
- chosen or recommended approach;
- unresolved implementation questions;
- Unity serialization implications;
- platform-specific implications;
- compatibility and migration requirements;
- error handling and recovery;
- diagnostics;
- test plan;
- manual validation;
- acceptance criteria;
- documentation updates;
- risks.

The task may instruct the implementer to inspect a small, defined area before editing when exact symbols are likely to drift. It must not use broad phrases such as:

```text
Update whatever is necessary.
Refactor related code.
Fix all affected systems.
Clean up nearby logic.
Handle edge cases.
Add tests as needed.
```

Replace such phrases with explicit boundaries and expected outcomes.

A prioritized task should make unrelated modifications unnecessary. When a required change cannot be identified during task refinement, state the narrow discovery rule that allows the implementer to locate it.

Example:

```text
Discovery allowance:
- Follow references from `PlayerBootstrap.InitializeAsync()` only far enough to identify
  the current save-service registration.
- Add newly discovered files to `Touch` before editing them.
- Do not inspect or refactor unrelated services registered by the same composition root.
```

### 14.7 Self-contained prioritized-task template

Use:

```text
### Task Title

Priority:
Status: Ready | Blocked pending answers
Origin:
Evidence:
Goal:

Current behavior:
- ...

Desired behavior:
- ...

Touch:
- ...

Discovery allowance:
- ...

Dependencies:
- ...

Out of scope:
- ...

Implementation constraints:
- ...

Possible implementation approaches:
1. ...
2. ...

Recommended approach:
- ...

Implementation notes:
- ...

Data, persistence, and migration:
- ...

Unity/serialization considerations:
- ...

Platform considerations:
- ...

Failure handling and recovery:
- ...

Diagnostics and observability:
- ...

Questions and required clarifications:
- [Resolved — repository evidence] ...
  Answer:
  Evidence:

- [Recommended default — confirmation optional] ...
  Recommendation:
  Rationale:

- [Unresolved — blocks implementation] ...
  Why it matters:
  Required answer from:

Validation:
- ...

Acceptance:
- ...

Documentation updates:
- ...

Risks:
- ...
```

Every prioritized task must include at least:

- `Goal`;
- `Current behavior`;
- `Desired behavior`;
- `Touch`;
- `Discovery allowance`;
- `Out of scope`;
- `Implementation constraints`;
- `Questions and required clarifications`;
- `Validation`;
- `Acceptance`;
- `Documentation updates`;
- `Risks`.

Use `None identified` with a brief rationale when a required section genuinely has no content. Do not omit the section.

The questions section must always be present, even when all questions are resolved:

```text
Questions and required clarifications:
- No unresolved questions. Repository evidence and existing project rules establish
  the implementation decisions listed above.
```

A task with a blocking unresolved question must use:

```text
Status: Blocked pending answers
```

It may remain in `Prioritized Next Changes` to preserve priority, but `Implement next` must stop at the clarification gate rather than skipping it automatically. The agent may only skip a blocked first task when the user explicitly requests another named task.

### 14.8 Pending item template

Use this format when an AI agent adds an item to `Pending Queue`. Keep the entry concise, preserve source context, and use nested Markdown lists only. Include only relevant sections.

When initializing or repairing repository documentation, copy this template into the target repository's `Documents/FUTURE.md` under `## Pending Task Format`.

```text
- Task title
  - Description
    - State what should change, why, where it applies, and what problem it solves.
  - Current context
    - Summarize known current behavior, relevant Unity systems, assemblies, scenes, prefabs, ScriptableObjects, settings, tests, docs, or tooling.
  - Source verification requirements
    - MUST inspect current project code, assets, settings, and tests before promotion when assumptions may be stale.
    - MUST verify official Unity, package, platform, SDK, backend, store, or other external behavior before relying on it.
    - MUST update the task if source inspection contradicts the current assumptions.
  - Requirements
    - List concrete, testable requirements.
  - Unity/game behavior
    - Describe runtime, Editor, build, platform, scene/prefab, input, UI, gameplay, content, or tool behavior when relevant.
  - Data/model behavior
    - Describe state, persistence, serialization, save migration, Addressables/Resources, networking, cache, backend, analytics, or mutation behavior when relevant.
  - Edge cases
    - Include missing data, stale data, disabled states, duplicate entries, partial failure, cancellation, concurrency, offline behavior, platform differences, or old save/config compatibility when relevant.
  - Expected behavior
    - Describe the final observable outcome.
  - Suggested implementation
    - Name likely files, symbols, assets, tests, helpers, docs, and reuse points without over-constraining the developer.
  - Acceptance criteria
    - List concrete checks that can be verified manually, by tests, or by code review.
  - Tests
    - List focused test scenarios or validation steps when logic, state, serialization, platform behavior, tooling, or important UI behavior changes.
  - Documentation updates
    - Name docs that likely need updates, especially `FEATURES.md`, `FUTURE.md`, `TECHNICAL.md`, `REPOSITORY_MAP.md`, `TESTING.md`, or specialized integration docs.
```

Pending entries do not need the full questions section. The mandatory questions section is created during `Process pending tasks` or `Process pending`.

Do not use vague titles such as `Fix UI`, `Improve things`, `Update page`, or `Bug`. Use short action-oriented titles. Do not add empty sections. Do not put future work in `FEATURES.md` while drafting pending items.

### 14.9 Task lifecycle

```text
Raw request
-> Pending Queue
-> `Process pending` research and validation
-> maximally detailed task with implementation questions
-> Prioritized Next Changes
-> clarification gate
-> implementation
-> tests and validation
-> current-state docs updated
-> task removed from FUTURE.md
```

Backlog lifecycle:

```text
Deferred idea or validated future work
-> Backlog
-> explicit promotion request
-> full task expansion and questions
-> Prioritized Next Changes
-> clarification gate
-> implementation
```

`Implement next` does not perform promotion.

Do not use `FUTURE.md` as a changelog.

### 14.10 Optional validated-removal section

During a one-time backlog cleanup, an agent may temporarily include:

```text
## Validated Implemented and Removed from Backlog
```

Use it to explain why stale tasks were removed. Delete or move this historical record to release notes after the cleanup if it no longer helps implementation.

## 15. Document Specification — `Documents/RULES.md`

This is the canonical AI-agent rule set.

Include the following sections.

### 15.1 Purpose and responsibility map

Define what each document owns and require agents to read `RULES.md` before non-trivial changes.

### 15.2 Required reading order

Use a conditional reading order:

1. `RULES.md`
2. `TECHNICAL.md`
3. `REPOSITORY_MAP.md`
4. `FEATURES.md`
5. specialized documents relevant to the change
6. `BUILD_AND_RELEASE.md` for build, CI, signing, native post-processing, or release work
7. `TESTING.md`
8. affected code, scenes, prefabs, assets, Project Settings, and tests
9. official external documentation when local evidence is insufficient

Do not require every large document for every trivial edit.

### 15.3 Minimal-change rule

Agents must:

- make the smallest technically correct change;
- avoid opportunistic refactors;
- avoid mass formatting;
- preserve unrelated user changes;
- avoid changing generated or vendor files directly;
- explain necessary scope expansion.

### 15.4 Unity project safety rules

Include explicit rules:

- use the exact Unity version from `ProjectVersion.txt`;
- do not upgrade Unity or packages without explicit scope;
- do not change serialization mode casually;
- preserve `.meta` files and GUIDs;
- do not delete or regenerate assets to solve reference problems;
- avoid manual scene/prefab YAML edits unless the repository approves them;
- inspect prefab variants and scene references after serialized field changes;
- use `FormerlySerializedAs` or a documented migration for renamed serialized fields;
- keep runtime assemblies independent from editor-only assemblies;
- respect platform compile guards and plugin import settings;
- do not assume Editor behavior matches IL2CPP device behavior;
- do not edit generated Gradle/Xcode projects as the source fix when a Unity-side template or post-process owns the behavior;
- do not commit machine-local Unity files.

### 15.5 Architecture rules

Translate the actual architecture into enforceable boundaries.

Examples:

- startup orchestration belongs in the composition root;
- UI views call application/services rather than SDK wrappers;
- platform SDKs are isolated behind adapters;
- deterministic rules are tested outside MonoBehaviours where practical;
- build configuration is owned by build tooling, not scattered menu scripts;
- persistence migrations are versioned;
- event names and analytics parameters use a centralized contract;
- package runtime code cannot depend on game-specific assemblies.

Do not include rules that the repository cannot currently follow without a major rewrite unless they are clearly labeled as desired future policy.

### 15.6 Dependency and external-source research rule

Require current official verification before changing:

- Unity APIs with version-sensitive behavior;
- package or SDK versions;
- Android Gradle, manifest, permissions, or target-SDK behavior;
- iOS/Xcode, privacy manifest, entitlement, signing, or CocoaPods behavior;
- store requirements;
- analytics, ads, attribution, consent, purchases, notifications, or backend contracts;
- security-sensitive integration behavior.

Use primary sources when possible. Record source URLs and access dates in `REFERENCES.md` or the specialized integration document.

### 15.7 Security and privacy rules

At minimum:

- never commit or print secrets;
- never copy signing keys, passwords, tokens, private endpoints, or real user data into docs;
- redact logs and screenshots;
- use placeholders in examples;
- document secret variable names and provisioning paths only;
- treat test credentials as secrets;
- do not upload builds, symbols, or artifacts without explicit instruction;
- do not weaken consent, certificate, receipt, or authentication checks to make tests pass.

### 15.8 Testing rules

Require tests or validation proportional to the change.

Examples:

- pure logic: EditMode/unit tests;
- scene behavior: PlayMode or scene validation;
- serialized-field change: migration/reference validation;
- native plugin change: target-platform build and device smoke test when available;
- build tooling: command-line build dry run or CI-equivalent validation;
- UI change: relevant scene/prefab review and supported resolutions;
- package change: compile against supported Unity versions if the repository maintains a matrix.

Never claim tests were run when they were not.

### 15.9 Documentation update policy

Map behavior changes to owning documents:

```text
project purpose or scope -> PROJECT.md
architecture or stack -> TECHNICAL.md
repository ownership paths -> REPOSITORY_MAP.md
implemented feature behavior -> FEATURES.md
planned work -> FUTURE.md
build/release flow -> BUILD_AND_RELEASE.md
test workflow -> TESTING.md
dependency versions or integration constraints -> DEPENDENCIES.md
agent workflow -> RULES.md
```

Update all affected documents in the same change set. Keep edits minimal and factual.
Completing implemented work must remove or update the matching `FUTURE.md` entry. Historical planning details must not be copied into `FEATURES.md`.

### 15.10 When to propose instead of implement

Require a proposal or explicit approval for:

- Unity version upgrade;
- render pipeline replacement;
- scripting backend or API compatibility change;
- broad package upgrade;
- assembly-boundary redesign;
- save format or cloud schema migration;
- scene/bootstrap rewrite;
- new backend or third-party SDK;
- signing or store configuration changes;
- destructive asset migration;
- security-policy change;
- large generated-project changes;
- deletion of apparently unused assets when reference safety is uncertain.

### 15.11 Final review and handoff

Before reporting completion:

- review the diff;
- inspect changed serialized files;
- check for accidental `.meta` changes;
- check for secret leakage;
- verify documentation links;
- list tests actually run;
- list tests not run;
- state remaining risks and open questions;
- do not invent issues.

## 16. Document Specification — `Documents/BUILD_AND_RELEASE.md`

Create this document even when the project has only a simple local build; state what is and is not automated.

Include:

```text
# Build and Release

Last validated:
Primary audience:

## Supported Targets
## Required Toolchain
## Local Development Build
## Command-Line Build Entry Points
## Build Profiles and Environments
## Versioning
## Content/Addressables Build
## Android Build Flow
## iOS Build Flow
## Desktop/WebGL Build Flow
## CI Pipeline
## Signing and Secrets
## Artifact Outputs
## Symbols and Diagnostics Upload
## Release Validation
## Store or Distribution Upload
## Rollback/Hotfix Notes
## Known Limitations
## Open Questions
```

For each command, include prerequisites and whether it was verified.

Never place signing credentials or secrets in this file.

## 17. Document Specification — `Documents/TESTING.md`

Include:

```text
# Testing and Validation

Last validated:

## Test Strategy
## Test Assemblies
## EditMode Tests
## PlayMode Tests
## Integration and Device Tests
## Manual Smoke Tests
## Platform Matrix
## CI Test Jobs
## Static Analysis and Formatting
## Coverage
## Test Data and Credentials
## Safe AI-Agent Test Rules
## Known Gaps
## Commands
```

### 17.1 Safe AI-agent test rules

Specify which actions are safe without user confirmation and which mutate external or persistent state.

Examples of actions requiring explicit approval:

- purchases;
- production backend mutations;
- analytics test events in production;
- ads revenue callbacks;
- cloud-save deletion;
- account deletion;
- push notifications;
- store uploads;
- signing;
- remote configuration publication;
- live economy changes.

If manual UI testing requires credentials, state how to use them without persisting or documenting them.

## 18. Document Specification — `Documents/DEPENDENCIES.md`

Include a verified dependency inventory.

Recommended table:

```text
Dependency
Resolved version
Source
Purpose
Owned integration path
Platforms
Initialization
Update constraints
Known conflicts
Official reference
Last verified
```

Separate:

- Unity packages;
- project-owned packages;
- managed plugins;
- native Android dependencies;
- native Apple dependencies;
- build-time tools;
- CI tools;
- optional/test-only dependencies.

Identify duplicate SDK ownership, mediation adapters, transitive conflicts, and packages that must be upgraded as a coordinated stack.

Do not claim every transitive package is an intentional project dependency.

## 19. Optional Specialized Documents

Create these only when justified.

### 19.1 `UX_UI_MANIFEST.md`

Create when the project has substantial UI or several screens.

Include:

- UI framework;
- navigation and screen map;
- design tokens;
- common components;
- input methods;
- supported aspect ratios and safe areas;
- keyboard/gamepad/touch behavior;
- localization constraints;
- accessibility;
- modal and loading patterns;
- current screen-by-screen behavior;
- responsive or device-specific rules;
- visual regression and manual review checklist.

Do not treat screenshots as the only source of truth. Reference prefabs, UI documents, scenes, USS/UXML, canvases, and controllers.

### 19.2 `PLATFORM_INTEGRATIONS.md`

Create when native platform behavior is substantial.

Include one section per platform and integration ownership, generated-vs-source files, native build mutations, permissions/capabilities, testing, and known conflicts.

### 19.3 `BACKEND_AND_NETWORKING.md`

Create when backend behavior is complex enough that `TECHNICAL.md` would become overloaded.

Include environments, API ownership, authentication, DTOs, retry policy, offline behavior, WebSockets, error mapping, and test/mocking strategy.

### 19.4 `DATA_AND_PERSISTENCE.md`

Create for complex save systems, cloud synchronization, migrations, or several stores.

Include schemas, versioning, ownership, migration sequence, reset behavior, backup/recovery, and sensitive fields.

### 19.5 `ANALYTICS_AND_MONETIZATION.md`

Create when analytics, attribution, ads, purchases, consent, or subscriptions are material.

Document initialization order, event ownership, automatic events, user identifiers, test-mode behavior, consent gates, platform differences, and validation. Never include production keys.

### 19.6 `SECURITY.md`

Create when the repository has material authentication, secrets, purchases, backend authorization, anti-cheat, or user data obligations.

Document repository-specific security boundaries and reporting contacts if available. Do not create unsupported compliance claims.

### 19.7 `REFERENCES.md`

Create when implementation depends on external version-sensitive contracts.

For each source record:

```text
Subject
Official source
Version or branch
Last checked
Local applicability
Known uncertainty
```

### 19.8 `DECISIONS.md`

Use as an index of architecture decisions when the repository already has ADRs or when several high-impact decisions need preserved rationale.

Do not use it as a duplicate of `TECHNICAL.md`.

### 19.9 `TROUBLESHOOTING.md`

Create when recurring, validated setup/build/runtime failures have known fixes.

Each entry should include symptoms, affected environment, root cause, verified fix, and references. Avoid folklore.

## 20. Documentation Snapshot Boundary

Do not create `Documents/DOCUMENTS_SNAPSHOT.md` during documentation initialization or maintenance.

Snapshot archive creation is owned by the separate `skill-tree-create-documents-snapshot` skill. Documentation initialization and audit skills should only enforce that live Markdown filenames remain stable and free of snapshot markers.

## 21. Deep Review Before Finalizing the Documentation

After drafting all documents, perform a dedicated review pass. Do not treat proofreading as the review.

## 21.1 Cross-document consistency review

Verify:

- Unity version matches everywhere;
- platform lists match;
- package versions match manifest/lock or verified plugin metadata;
- feature statuses match code;
- scene names and paths are valid;
- assembly names and dependencies are valid;
- startup sequence is consistent;
- build commands match CI;
- test commands match actual assemblies and tooling;
- planned work is absent from `FEATURES.md`;
- implemented behavior is absent from active `FUTURE.md`;
- document responsibility is not duplicated;
- all relative links resolve.

## 21.2 Unity safety review

Check that the docs do not encourage agents to:

- regenerate `.meta` files;
- change GUIDs;
- open with an arbitrary Unity version;
- edit generated Xcode/Gradle output as the permanent source fix;
- change package versions casually;
- hand-edit scenes/prefabs without safeguards;
- rename serialized fields without migration;
- assume Editor behavior equals device behavior;
- commit secrets or machine-local files;
- run production mutations during validation.

## 21.3 Evidence review

For every high-impact claim, ask:

- What exact file, key, symbol, asset, or test proves this?
- Is the evidence current?
- Is there conflicting evidence?
- Is the claim implementation, configuration, intent, or assumption?
- Should it be moved to `FUTURE.md` or `Open Questions`?

Remove unsupported certainty.

## 21.4 Usability review for AI agents

A future agent should be able to answer quickly:

- Which documents must I read for this task?
- Which Unity version must I use?
- Where does startup happen?
- Which scene or prefab owns this UI?
- Which assembly owns this rule?
- Which file owns Android/iOS integration?
- Which files are generated?
- How do I build and test safely?
- What docs must I update?
- What work is currently prioritized?
- What must I not change without approval?

If these answers require broad rediscovery, improve the documents.

## 21.5 Duplication and size review

Remove repeated detail from secondary documents. Keep:

- concise summaries and links in `README.md`;
- foundational decisions in `TECHNICAL.md`;
- physical path ownership in `REPOSITORY_MAP.md`;
- feature-specific current behavior in `FEATURES.md`;
- future work in `FUTURE.md`;
- workflow constraints in `RULES.md`.

Large documents are acceptable when the project is complex, but they must remain navigable and responsibility-focused.

## 22. Validation Commands and Safe Static Checks

Use static checks that do not mutate Unity state.

Examples:

```bash
git status --short
git diff --check
git ls-files '*.md'
find Assets -name '*.asmdef' -o -name '*.asmref'
find Assets -name '*.unity' -o -name '*.prefab' -o -name '*.asset'
rg -n 'RuntimeInitializeOnLoadMethod|InitializeOnLoad|InitializeOnLoadMethod'
rg -n 'TODO|FIXME|HACK|NotImplementedException'
rg -n 'PlayerPrefs|persistentDataPath|JsonUtility|Newtonsoft|SQLite'
rg -n 'UnityWebRequest|HttpClient|WebSocket'
rg -n '#if UNITY_ANDROID|#if UNITY_IOS|#if UNITY_WEBGL'
rg -n 'PostProcessBuild|IPreprocessBuild|IPostprocessBuild'
rg -n 'BuildPipeline\.BuildPlayer|BuildPlayerOptions'
```

Use YAML-aware or Unity-aware tooling when available. Plain text search is discovery, not semantic proof.

Build and test commands may be documented without being executed. Clearly label verification status.

## 23. Final Handoff Requirements

After creating and reviewing the documentation, report:

- created and updated files;
- repository layout chosen;
- optional documents created and why;
- major verified technical findings;
- significant documentation/code drift found;
- open questions;
- snapshot files not created unless explicitly requested;
- tests or builds actually run;
- checks not run;
- remaining risks;
- suggested commit message.

A suitable commit message:

```text
docs: initialize Unity repository documentation
```

Do not claim completion if major documents contain placeholders that could have been resolved from the repository.

## 24. Completion Checklist

The task is complete only when all applicable checks pass.

### Repository analysis

- [ ] Unity root or roots identified.
- [ ] Exact Unity version verified.
- [ ] Package intent and resolved versions inspected.
- [ ] Assembly map created.
- [ ] Startup path traced.
- [ ] Build scenes and major serialized assets inspected.
- [ ] Runtime features inventoried.
- [ ] Persistence and migrations inspected.
- [ ] Networking/backend inspected.
- [ ] Native/platform integrations inspected.
- [ ] Build and CI path traced.
- [ ] Tests inventoried.
- [ ] Secrets and generated files identified.
- [ ] Existing docs audited for drift.

### Core documents

- [ ] `README.md`
- [ ] `AGENTS.md`
- [ ] `Documents/PROJECT.md`
- [ ] `Documents/TECHNICAL.md`
- [ ] `Documents/FEATURES.md`
- [ ] `Documents/FUTURE.md`
- [ ] `Documents/RULES.md`
- [ ] `Documents/REPOSITORY_MAP.md`
- [ ] `Documents/BUILD_AND_RELEASE.md`
- [ ] `Documents/TESTING.md`
- [ ] `Documents/DEPENDENCIES.md`
### Quality

- [ ] All documents are in English.
- [ ] Live documents have no snapshot date in their filenames.
- [ ] Current behavior and future work are separated.
- [ ] High-impact claims have repository evidence.
- [ ] Assumptions and open questions are explicit.
- [ ] Paths and symbols are repository-relative and valid.
- [ ] No secrets are present.
- [ ] No vendor documentation was rewritten unnecessarily.
- [ ] Cross-document facts are consistent.
- [ ] Links resolve.
- [ ] Documentation ownership is clear.
- [ ] Final diff contains no accidental Unity asset or `.meta` changes.

## 25. Recommended Execution Summary for an AI Agent

Use this condensed sequence only after understanding the detailed requirements above:

```text
1. Protect the worktree and identify all Unity roots.
2. Inventory code, assemblies, settings, packages, scenes, assets, platforms,
   build scripts, CI, tests, persistence, networking, and external SDKs.
3. Build an evidence ledger with confidence and conflicts.
4. Audit existing documentation against current repository state.
5. Create REPOSITORY_MAP and TECHNICAL first.
6. Create PROJECT and FEATURES from verified current behavior.
7. Create BUILD_AND_RELEASE, TESTING, and DEPENDENCIES.
8. Create only justified specialized documents.
9. Validate and structure FUTURE into Pending, Prioritized, and Backlog.
10. Create RULES and the short root AGENTS handoff.
11. Write README last.
12. Review facts, links, duplication, Unity safety, and secret handling.
13. Report exact files, evidence gaps, checks run, and remaining risks.
```
