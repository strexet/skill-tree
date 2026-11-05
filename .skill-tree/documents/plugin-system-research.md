# External Plugin System Research

## Processing scope

The inspected source baseline is commit `853c913` on `codex/next-version`. Seven Pending requests cover an external skill integration framework, market research, owner workflow discussion, a grouped catalog, two pilot integrations and confirmed installation. The prioritized queue owns future implementation scope and dependencies. No external plugin implementation, installation or execution belongs to the processing pass.

Source inspection covers authored operations, locked invariants, composition, installation, workflow/checkpoint mutation, review gates and existing behavioral fixtures. External source discovery supplies a research starting point and compatibility observations, not an approved recommendation bundle or a completed comparative market study. External observations are dated 2026-11-05 and require revision/freshness checks during execution.

## Current source boundaries

`templates/operations.json` directs agents through bundled contracts. `common/scripts/workflow-state.py` applies supplied intake/processing/check results and persists state; `common/scripts/pr-review-state.py` explicitly treats CLI operations as metadata-only. Neither helper supplies a general host skill-execution engine.

`lib/composer.js` protects locked slots, resolves local resources and composes standalone packages. `lib/installation.js` stages owned generations, verifies receipt/profile freshness and preserves stopped workflow state. External packages and dependencies require explicit inclusion in composition and maintenance inventories. A source URL alone supplies no standalone runtime dependency closure.

`bin/install.js` currently offers a flavor prompt and then writes each provider installation. `--yes` selects noninteractive behavior and supplies no plugin consent. Plugin selection requires one project-level plan before the provider write loop. Offline/no-write dry-run and installation without skill execution remain existing boundaries.

The proposed execution seam separates preparation under the writer lock, agent/host invocation outside the lock, and guarded result recording. Exact task/source, plugin revision, profile and review head/base identities remain necessary for stale-result rejection and idempotent recovery. Plugins cannot replace selection, acceptance, permission or merge gates.

## Supplied pilot compatibility

[Ponytail at inspected revision](https://github.com/DietrichGebert/ponytail/blob/96608e078b2d5ea607c5c3b8b5a54d1c1fba6846/skills/ponytail/SKILL.md) is a broad coding mode with review applicability and session-wide activation. The declared MIT metadata, levels and persistent reply conventions require package/license inspection and explicit context lifetime in an adapter. The source supplies no isolated review-hook contract.

[The supplied interview wrapper](https://github.com/mattpocock/skills/blob/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d/skills/productivity/grill-me/SKILL.md) delegates through a host-specific Skill tool to [grilling](https://github.com/mattpocock/skills/blob/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d/skills/productivity/grilling/SKILL.md). The implementation asks question rounds, waits for answers and requires confirmation of shared understanding before action. A post-processing adapter therefore needs dependency resolution and a persistent question/rework/readiness loop. Copying the wrapper alone cannot establish compatibility.

## Market discovery starting points

| Source | Relevant evidence and limits |
| --- | --- |
| [Agent Skills specification](https://agentskills.io/specification) | Portable package structure and progressive resources; no universal host Skill invocation API. |
| [skills.sh methodology](https://skills.sh/docs) | Installation telemetry supplies adoption evidence; task effectiveness remains a separate measurement. |
| [Vercel skills CLI reference](https://github.com/vercel-labs/skills/blob/cabe07254cddf16a3a650253f0ba03d543d8a86e/docs/commands.md) | Exact references, project/copy installation and lock restoration are lifecycle comparison material, without establishing Skill Tree hook execution. |
| [Sentry dotagents](https://github.com/getsentry/dotagents) | Source/trust/lock and host projection are relevant comparison surfaces; global/symlink defaults differ from the current owned project-copy model. |
| [OpenAI plugins](https://github.com/openai/plugins) | Native host bundles can include surfaces beyond skills. Workflow skill extensions and native host plugins require distinct catalog identities. |
| [Unity skills](https://github.com/Unity-Technologies/skills) | Domain candidates require Editor/tool prerequisites and separate runtime qualification. |
| [Superpowers review](https://github.com/obra/superpowers/blob/22f0b463e7a5e579904dd6211a520321035526f7/skills/requesting-code-review/SKILL.md) | Templates, delegation and prescribed review timing require dependency and workflow-policy review. |
| [Vercel agent evaluations](https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals) | A scoped Next.js experiment demonstrates the importance of actual activation and invocation wording; no universal skill ranking follows. |
| [Anthropic skill evaluation procedure](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md) and [Warden evals](https://github.com/getsentry/warden/blob/main/packages/evals/README.md) | Baselines, independent grading and negative controls inform a comparison protocol. Pipeline evaluation and candidate quality remain separate claims. |

The future research separates a dated market map from bounded comparative qualification. Recommendations require source/revision, license and maintenance facts, dependency/host compatibility, relevant workflow outcomes and explicit evidence gaps. Popularity, install counts and promotional recommendations remain discovery signals.

## Owner decision boundary

The owner requests discussion and agreement before adding mandatory workflow stages or splitting existing stages. A dedicated design task owns concrete alternatives and the approval record. Configurable before/during/after placements around existing operations remain distinct from structural workflow changes.

Approved initial pilot policies reside in `.skill-tree/documents/plugin-workflow-decisions.md`: an additional bounded review pass defaults after full review and blocks PR readiness while enabled; an enabled processing interview keeps a visible stable-ID T-task non-implementable until answers, revisions, rechecks and owner confirmation complete. The current processing helper still creates Ready tasks immediately; the approved hold remains planned implementation work.

The installation design owns explicit install/skip/choose-alternatives behavior, grouped complete selection, repeat installation and noninteractive/failure policy. A displayed recommendation supplies no consent. Actual installation confirmation installs and enables the exact displayed versions and bindings; execution occurs later in authorized workflows. The owner also requires an installed-plugin registry and simple removal, with management views distinct from the available catalog. A hosted marketplace is not an established delivery requirement.

## Qualification limits

Current fixtures provide reusable Node/Python seams for ownership, profile changes, exact selection, checkpoint recovery and review gates. Future implementation units require focused new plugin fixtures and standalone general/web/unity checks. Actual candidate/model execution, benchmark costs and native-host support remain separate scoped evidence. No plugin receives a recommendation from the processing pass alone.
