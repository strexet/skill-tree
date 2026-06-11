<!--
GENERATED FILE
Source: REPO_INIT_INSTRUCTIONS.md
Generator: scripts/sync_skill_references.py
Do not edit manually. Update the source document and rerun the generator.
-->

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

Keep pending entries concise but preserve enough source context for later research:

```text
- Priority placement: Top | Middle | Bottom | Unspecified
- Request:
- Source/context:
- Evidence or reproduction:
- Known constraints:
- Missing information:
- Candidate area:
- Potentially related tasks:
```

Pending entries do not need the full questions section. The mandatory questions section is created during `Process pending tasks` or `Process pending`.

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
