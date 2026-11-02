# Skill Repository Maintainer Contract

## Ownership

The source repository contains eight logical operations composed into representative general, web and unity packages under `.skill-tree/skills/<flavor>/`. Authored templates and domain slots own entry-point instructions; generated packages receive no independent edits. Shared canonical references/scripts reside under `.skill-tree/common/`. `resource-map.json` defines generated standalone resources; `providers.json` defines provider IDs, detection, installation destinations and optional bridge paths.

## Skill packages

Each package contains `SKILL.md` with YAML name/description/license fields, optional `agents/openai.yaml`, focused references and required deterministic helpers. Names match directories and use the `skill-tree-` prefix. Required format: [Agent Skills specification](https://agentskills.io/specification). Descriptions identify invocation intent; entry points route conditional detail progressively. No runtime sibling/source dependency is permitted.

## Document contract

Generated prose uses English, current declarative descriptions and explicit entities instead of ambiguous pronouns. Quoted technical labels and grammatical clauses retain exact meaning; prose warnings require contextual review. Technical identifiers and externally required syntax retain exact spelling. Owned files/directories use lowercase kebab-case. Required discovery filenames and standard manifests are exceptions. Current documentation owns current behavior; future.md owns planned work; compact history owns recorded outcomes. No migration handlers, format converters or legacy aliases are supported.

## Source changes

Inspect affected canonical contracts, callers, generated resources, installer and tests before editing. Preserve serialized Unity assets, package pins and unrelated changes. Generated resources receive changes only through the generator. Provider installation destinations remain defined by the provider matrix; changes to support claims require official-source verification. Soft directory probes never trigger automatic installation. Optional provider bridges use marker-fenced, backed-up edits and preserve unowned content. Installation never executes bundled skill helpers.

## Verification

Run synchronization checks, strict repository validation, behavioral Python/Node tests and installer dry runs. Tests verify selection boundaries, evidence requirements, state recovery, dependency handling, retention and portable installation. Tests avoid mirroring prose. Local commits require developer authorization and scoped staging. No publishing, pushing, tags or license changes are implied.
