<!-- GENERATED FILE; Source: skill-tree/documents/repo-init-instructions.md; generator: skill-tree/scripts/sync-skill-references.py -->

# Unity Repository Documentation Contract

Read the shared documentation-output-contract, repository-discovery-checklist, document-rules, workflow-metadata and unity-safety references before initialization or audit.

## Unity evidence inventory

Inspect repository topology and Unity roots; pinned Editor/player baseline; package manifests/locks; assemblies/code architecture; startup/lifecycle; scenes/prefabs/serialized assets; runtime feature flows; persistence; networking/backend; platform/native integrations; build/release/CI; test assemblies/fixtures; diagnostics/performance; security/privacy and documentation drift.

Verify claims against code, serialized state and configuration. Classify assumptions and gaps explicitly. Document concrete ownership, paths, symbols, flows, inputs/outputs, mutations, preconditions, failure handling and platform constraints. Apply checks for UniTask, DOTween, Addressables or DI only when repository evidence establishes usage.

## Deliverables

Create root README.md and AGENTS.md with concise pointers into skill-tree/documents/. Create the required shared document set and evidence-backed optional specialized documents. Technical owns foundational architecture; features owns current behavior; future owns planned work; rules owns safe editing/validation and source precedence. Avoid duplicated subjects. Initialize the manifest and queue index explicitly.

## Safety and completion

Use static source/serialized inspection by default. Unity launch, compilation, Play Mode, player/device checks, resets and real services require applicable authorization. Preserve assets/GUIDs, settings, pins and unrelated work. Inspect key error/state/persistence paths and capture confirmed audit findings in Backlog; avoid speculative findings. Review cross-document consistency, concrete evidence, broken links, secrets, duplication and English declarative prose. Report actual checks separately from unrun validation. Snapshots and commits require applicable explicit authorization.
