# Narrative Projects

`skill-tree-narative` supports game worldbuilding, character and quest development, narrative review and canon management. The operation is available with general, web and Unity project profiles. A narrative project can work in Markdown from a text editor or Obsidian. The profile retains the existing runtime and validation rules for the game.

## First session

The [topic router](../common/references/narrative-topic-routing.md) selects focused procedures for worldbuilding, characters, dramaturgy, quests and canon. The [craft catalog](../common/references/narrative-craft-catalog.md) routes individual methods by the problem observed in a scene or quest.

Invoke the installed operation with an explicit narrative project and a small target episode. For example, provide a premise and one playable decision. Ask for the context review, consequential questions with recommendations, and a draft of the episode. The [authoring workflow](../common/references/narrative-workflow.md) describes the modes, input scope and commands.

1. Select the work, continuity, time, possible route and accepted snapshot. Initialize a store for a new project.
2. Use one to three material questions per round to agree on the experience and the scope of changes. Keep reversible draft work moving while other choices remain open.
3. Draft the scene and linked rules, people and quest states. Include entry conditions, available actions, visible outcomes and the evidence available to the player.
4. Review the candidate and affected sources. Record structural checks, continuity and craft findings, and any played routes as separate evidence.
5. Review the exact proposal with the author. The author accepts the reviewed digest before the operation creates an immutable snapshot. The work definition explicitly selects the snapshot used by the work.
6. Prototype interactive dialogue in ink when applicable. A Unity handoff specifies variable ownership and checks the relevant runtime paths.

## Project records

| Location | Contents |
| --- | --- |
| `.narrative/records/<id>.md` | Human-readable working material. |
| `.narrative/records/<id>.json` | Stable `id`, `kind`, normative `depends_on` and optional project data. |
| `.narrative/snapshots/<digest>.json` | Immutable accepted package with exact Markdown and metadata bytes, retirement state and the bound decision receipt. |
| Work definitions and author decisions | Project-owned files outside the helper-managed record pairs and snapshots. A work definition records scope, the selected snapshot and any predecessor policy. |

A working record pair shares a basename and directory within `.narrative/records/`. The sidecar supplies the stable ID. Move or rename both files together to keep the same record and revision. Duplicate IDs, incomplete pairs and symlinks require correction before discovery.

Working records remain drafts. An accepted snapshot resolves exact revisions by content hash. A retired entry is outside the active composition of the selected snapshot. Earlier snapshots retain the accepted records. Markdown links and narrative prose can refer to material without creating a normative dependency. The helper checks recorded edges and exact bytes. The [narrative review criteria](../common/references/narrative-review.md) cover judgments that require source interpretation or playthrough observation.

Use `context --snapshot <digest> --ids <id> ...` to return selected record bodies and the normative dependency closure. The proposal command is read-only. The acceptance command verifies the exact proposal, unchanged working inputs and the project-relative decision receipt before atomically publishing a snapshot. The agent must obtain the actual author decision. Normal Git commit and delivery permissions apply independently. A project can reproduce a snapshot by retaining the snapshot file in version control.

## Skill Tree workflow

The [qualification guide](../common/references/narrative-qualification.md) records structural, semantic, standalone runtime and human observations separately. The [second-work fixture](../examples/narrative/second-work/README.md) demonstrates related works and historical pins.

Use Add Pending for authorized, understood narrative implementation or validation work that remains actionable. Process Pending researches the relevant records and game implementation, promotes the scoped work and retains unresolved prerequisites. Implement Next or an explicitly launched controller applies the accepted scope with review and evidence. Task completion and PR review have separate records from canon acceptance.

The [implementation plan](../history/research/narrative-workflow-plan.md) records the playbook choices and research. The [synthetic quest](../examples/narrative/README.md) provides a small authoring and ink exercise with recorded branch expectations.
