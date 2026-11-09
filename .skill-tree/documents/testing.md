# Testing Policy

[Behavioral verification](../tests/readme.md) owns fixture coverage. [AGENTS.md](../../AGENTS.md) owns required source commands. The [installed project profile](../../.agents/skills/skill-tree-repo-documentation-audit/references/project-profile.md) owns concrete installed recipe discovery. [Validation policy](../common/references/validation-policy.md) owns acceptance and evidence requirements.

Python fixtures cover parsing, intake, selection, scoped controllers, state recovery, evidence, source integration and review gates. Node fixtures cover composition, owned installation, providers, execution bindings and standalone flavor installation. Fixtures use temporary repositories and explicit local simulations.

Strict source validation checks canonical structure, generated resources, prose and navigation. Installed maintenance snapshots and transaction backups use separate receipt verification. The installed repository-documentation validator additionally requires the complete current-document set.

The installed profile exposes package-script recipes and source-role recipes declared in `.skill-tree/config/repository.json`. Source declarations retain stable IDs and input fingerprints. Target declarations in `.skill-tree/validation-recipes.json` supplement the recipe map; collisions reject composition.

Passing helper fixtures establish deterministic helper behavior. No fixture result establishes actual model instruction adherence, native provider behavior, hosted execution, device behavior, Unity runtime or browser runtime. External policy and live provider qualification remain separate checks.

Audit probe failures are expected reproductions of unresolved issues. Expected audit reproductions remain separate from the passing source regression suite and task acceptance.
