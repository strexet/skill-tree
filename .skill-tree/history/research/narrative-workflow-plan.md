# Narrative Workflow Implementation Plan

## Scope

The narrative operation supports one complete authoring cycle for a small game episode. The same operation composes into general, web and Unity installations. The public name `skill-tree-narative` preserves the owner-provided invocation. The existing plugin infrastructure remains available for project-selected review extensions. The existing Skill Tree queue owns actionable implementation work. The narrative project owns creative decisions, drafts and canon.

## Decisions from the playbook

| Open choice | First implementation |
| --- | --- |
| Identity | Typed, stable lowercase IDs identify records across name and text changes. A content hash identifies a record revision. |
| Snapshot | An immutable, SHA-256-addressed file contains the exact accepted record bytes and acceptance record. Each work selects an exact snapshot. Normal Git versioning preserves the store without making a commit part of acceptance. |
| Utility | Python standard library matches the installed workflow helper and keeps Markdown authoring and machine JSON sidecars independent of optional editors and YAML libraries. |
| Ink source | A playable prototype can live with narrative content. A Unity handoff names one authoritative ink source and the owners of state variables. |
| Continuation | Each real sequel selects a predecessor policy and compatible outcomes. The first-work pilot requires no sequel policy. |
| Claim granularity | Formalize only claims that affect causality, access, knowledge, reveals or continuity. Authoring prose carries the rest. |

## Prioritized delivery

1. Define the authoring and review workflow. Route playbook procedures through focused modes. Bind review to exact sources, distinguish blocking evidence from advice and record material author answers.
2. Implement and test the file helper. Resolve pinned accepted bytes, report known impacts, reject stale proposals and reject missing normative dependencies. A valid mutually dependent package succeeds as a unit.
3. Compose the operation, refresh the installed snapshot and qualify a synthetic playable quest. Review the complete owned changes, fix actionable findings and recheck affected evidence.

## Qualification

The structural lane covers identifiers, references, draft drift, historical snapshots, retirement and same-proposal cycles. The narrative lane covers creative clarification, provenance, the truth/knowledge/reveal boundary, dramatic setup and gameplay consequences. Executed ink traces cover branch conditions, skipped content and recovery. A human playtest is separate evidence of comprehension and pacing. The scope uses synthetic material and a standalone ink runtime.

## Research sources

- [Emily Short, Storylets](https://emshort.blog/2019/11/29/storylets-you-want-them/) informs the content, preconditions and effects model.
- [DendryScope](https://ojs.aaai.org/index.php/AIIDE/article/view/27527) informs author-facing reachability and knowledge questions over named traces.
- [Versu](https://cs.uky.edu/~sgware/reading/papers/evans2014versu.pdf) illustrates behavior conditioned on attributed beliefs.
- [Choice of Games testing](https://www.choiceofgames.com/make-your-own-games/testing-choicescript-games-automatically/) illustrates complementary structural and path checks.
- [Mobius Digital prototype](https://www.mobiusdigitalgames.com/outer-wilds-text-adventure.html) illustrates testing narrative comprehension before engine integration.
- [Inkle runtime guide](https://github.com/inkle/ink/blob/master/Documentation/RunningYourInk.md) documents runtime state and external integration.
