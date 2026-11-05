# Task Clarification Contract

## Scope and implementation boundary

The shared protocol derives from the pinned [grilling instructions](https://github.com/mattpocock/skills/blob/4ae2317ddb22b046e26455e4f9c9b3aaaf62212d/skills/productivity/grilling/SKILL.md). Explicit task/group clarification and the post-processing interview adapter share one round, answer, revision and confirmation protocol. Explicit clarification requires no generic plugin engine, native Skill tool, implementation run or new worktree.

The contract specifies the controller interface. The controller implementation task supplies executable commands and installed entry points; the contract alone establishes no executable capability. The current source-backed manual session remains distinguishable from a controller invocation.

## Selection and state ownership

The owner selects exact unique Prioritized `T-` identities. Selection preserves numeric priority and document order, freezes the selected identities and never adds dependencies or later queue additions silently. Ready and clarification-blocked tasks can participate. Missing, duplicate, terminal or non-prioritized identities reject selection atomically. An ID-shaped title cannot substitute for a missing identity.

Canonical mutable records reside in `.skill-tree/clarifications/cl-<uuid>.json`, identified by `CL-<uuid>`. The queue remains the task definition authority. A session stores selected IDs, mode, round/question identities, source facts, actual answers, full-content and semantic baselines, revision history, confirmation and stop information. Clarification records remain separate from implementation progress, run checkpoints and immutable terminal outcomes.

The shared Git queue locator resolves the canonical owner. Clarification never implicitly selects, admits, provisions, resumes or rewrites an implementation run. Parked run identities, claims, counters, admission, evidence and stops remain unchanged. Session-only operations leave queue/index bytes unchanged; task revisions update only task-owned content and derived task/index/manifest data in the same recoverable transaction as the session.

An open explicit session holds implementation admission for the selected tasks. Unrelated exact Ready selections remain available. Cancellation ends discussion without asserting answered questions or successful plugin execution. A required post-processing interview hold remains until the configured obligation is actually satisfied or explicitly changed under the recorded policy; cancellation supplies no successful completion.

## Rounds and actual answers

The agent maps dependent decisions and researches source-answerable facts. Each round presents the complete currently independent frontier: numbered questions whose prerequisites already have actual settled answers, with a recommendation for every question. A dependent question remains in a later round. A running fact investigation leaves only the dependent branch waiting.

Questions have stable IDs, prerequisite IDs and affected task/semantic-field bindings. Source facts include inspected source identity and limitations. Owner decisions require actual owner messages or structured submitted answers, with source evidence. A displayed default, preselection, silence, elapsed time or agent recommendation supplies no owner answer.

Answers bind the session, round, question identity and question revision. Exact duplicate delivery recovers the original result; conflicting replay or an answer for another identity rejects mutation. The agent applies accepted decisions to the selected task specifications, then rechecks the decision frontier and clarity rubric. Research, interviews and waits occur outside the writer lock.

## Guarded task revisions

Every mutator requires the inspected complete queue source hash. Existing-session mutations also require the inspected session content hash and monotonically increasing session revision. The exclusive writer lock snapshots clarification records; guarded transactions reject stale source/session baselines and external conflicting edits. Interrupted writes recover only when every target matches the recorded old or new bytes.

Task revision preserves task ID, Pending provenance, processing identity, relationship context and optional validation headers. The revision interface validates document rules, exact task ownership, acceptance/check mapping and the complete dependency graph before any write. Missing dependencies, self-dependencies, cycles, terminal task edits and unowned task edits reject the entire revision. Prepared implementation checks require an explicit safe handoff before task content changes; clarification never erases progress to bypass a pending attempt.

Complete-content hashes protect writes. Separate case-sensitive semantic projections protect answers and confirmation. Semantic fields cover title, goal, scope, exclusions, dependencies, acceptance, validation, required plugin policy and remaining substantive task content. Code/data values, list order and identifiers retain exact meaning. Conservative prose whitespace/emphasis normalization and JSON layout normalization can identify formatting-only edits; unsupported equivalence remains a semantic change.

A semantic edit invalidates final confirmation and reopens only answers whose task/field bindings or prerequisite answers changed. Unrelated answers remain available. A formatting-only edit updates transactional baselines and preserves semantic confirmation. The existing validation `task_signature` cannot substitute for full-task semantic identity.

## Completion, interruption and resume

The session states are `researching`, `awaiting-answers`, `revising`, `awaiting-confirmation`, `complete`, `blocked` and `cancelled`. An interrupted session retains selected IDs, questions, answers, revisions, facts and the exact next action. Resume reconciles current source drift against the saved semantic baselines; resume never restarts selection or infers an answer.

Clarity requires concrete goals, scope and exclusions, dependencies, observable acceptance and feasible validation. Required product decisions have actual answers; remaining research belongs to explicit scoped deliverables with dependent work gated accordingly. Contradictory definitions, hidden dependency cycles, unsupported facts and unanswered mandatory branches prevent confirmation eligibility.

An empty frontier and a complete clarity recheck lead to `awaiting-confirmation`. The owner receives a current task summary and explicitly confirms shared understanding of the current selected task semantics. Confirmation binds the exact scope and semantic fingerprints. A stale or missing confirmation cannot complete the session. Repeated rounds with no new facts, answers or semantic progress retain a visible blocked state and a concrete next action rather than inventing clarity.

Completion records clarification acceptance only. The session never starts implementation, commits, publication or another workflow controller. Explicit implementation instructions remain separate.

## Contract examples

| Case | Required outcome |
| --- | --- |
| Two independent product questions plus one source-answerable fact | Research the fact and ask both independent questions; a question depending on an unanswered decision waits for a later round. |
| Interrupted owner wait followed by higher-priority task insertion | Resume the same session and original selected IDs; retain the unanswered question and exclude the new task. |
| Actual answer changes a task acceptance criterion | Revise the selected task and matching check mapping atomically; reopen affected answers and final confirmation, preserving unrelated answers. |
| Markdown spacing or equivalent JSON layout changes | Refresh complete-content baselines while preserving matching semantic answers and confirmation. |
| Goal, dependency, code literal or required plugin policy changes | Treat the changed field as semantic; reject stale confirmation and recheck affected branches. |
| Stale queue/session hash, invalid dependency or concurrent edit | Reject before mutation and retain every unrelated task, implementation checkpoint and terminal receipt. |
| Silence, unavailable external skill or cancelled interview | Retain the unsatisfied obligation; report actual availability and never claim successful answers or native invocation. |

The controller task validates deterministic state behavior and standalone installation separately from bounded actual-agent observations. Helper fixtures, manual protocol use and native external-skill invocation remain distinct evidence classes.
