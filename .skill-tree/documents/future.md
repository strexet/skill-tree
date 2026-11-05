# Future Work

## Pending Task Format

Fixed metadata records task identity and dependency scope.

## Pending Queue

## Prioritized Next Changes

### Define the shared iterative task clarification protocol

```yaml
id: T-21b1c999-8586-4e70-a3bc-69cad3ea65aa
priority: 131
status: Ready
parent_pending_ids: ["P-e5de6bf4-99d6-481e-b158-7d302efde259"]
processing_run_id: PR-595a7e56-0da2-4b81-afc6-f5cff249c1e2
root_task_id: T-21b1c999-8586-4e70-a3bc-69cad3ea65aa
related_task_id: null
relation: main
depends_on: []
```

Goal:
- Specify the shared explicit task-clarification protocol and the common interview loop derived from the inspected upstream grilling protocol for owner-invoked sessions and the planned post-processing adapter.

Current behavior:
- Existing helpers resolve task groups and persist guarded transactions but provide no clarification-round or task-revision command. The processing reuse interface merges provenance/dependencies and ignores supplied task bodies.

Touch:
- `.skill-tree/documents/task-clarification-contract.md`
- `.skill-tree/common/references/future-workflow.md`
- `.skill-tree/common/references/workflow-metadata.md`
- `.skill-tree/common/scripts/workflow-state.py`
- `.skill-tree/documents/plugin-system-research.md`

Implementation constraints:
- Product decisions receive actual owner answers; facts come from source research. Silence never settles a question or confirms clarity.
- Keep explicit clarification independent of implementation-run creation, source worktree provisioning and mandatory global workflow stages. Native external-skill invocation requires a verified adapter; a manual source-backed interview remains distinguishable from an installed controller.

Validation:
- Strategy: source-backed contract design with positive, negative, stale-answer and interrupted-round examples.
```json
{
  "checks": [
    {
      "id": "clarification-contract",
      "recipe_id": "static-inspection",
      "criteria": [
        "The shared protocol defines exact task/group scope, dependency-ordered question rounds, source facts, actual owner answers, guarded revisions and interruption/resume.",
        "Completion requires concrete goals, scope, dependencies, acceptance and feasible validation, no unresolved mandatory decisions and actual owner confirmation bound to the current task revision.",
        "The shared loop derives from the inspected upstream grilling protocol and supports explicit clarification without a generic plugin engine; the planned post-processing adapter reuses the same loop.",
        "The contract separates complete-content write guards from semantic confirmation identity; formatting-only edits preserve confirmation, semantic edits reopen affected answers and final confirmation, and unrelated answers remain valid."
      ],
      "sources": [
        ".skill-tree/documents/task-clarification-contract.md",
        ".skill-tree/common/references/future-workflow.md",
        ".skill-tree/common/references/workflow-metadata.md",
        ".skill-tree/common/scripts/workflow-state.py",
        ".skill-tree/documents/plugin-system-research.md"
      ],
      "parameters": {},
      "assertion": "The shared protocol defines exact task/group scope, dependency-ordered question rounds, source facts, actual owner answers, guarded revisions and interruption/resume. Completion requires concrete goals, scope, dependencies, acceptance and feasible validation, no unresolved mandatory decisions and actual owner confirmation bound to the current task revision. The shared loop derives from the inspected upstream grilling protocol and supports explicit clarification without a generic plugin engine; the planned post-processing adapter reuses the same loop. The contract separates complete-content write guards from semantic confirmation identity; formatting-only edits preserve confirmation, semantic edits reopen affected answers and final confirmation, and unrelated answers remain valid.",
      "timing": "immediate"
    }
  ]
}
```

Acceptance:
- The shared protocol defines exact task/group scope, dependency-ordered question rounds, source facts, actual owner answers, guarded revisions and interruption/resume.
- Completion requires concrete goals, scope, dependencies, acceptance and feasible validation, no unresolved mandatory decisions and actual owner confirmation bound to the current task revision.
- The shared loop derives from the inspected upstream grilling protocol and supports explicit clarification without a generic plugin engine; the planned post-processing adapter reuses the same loop.
- The contract separates complete-content write guards from semantic confirmation identity; formatting-only edits preserve confirmation, semantic edits reopen affected answers and final confirmation, and unrelated answers remain valid.


Approved clarification decisions:
- Q2: An enabled post-processing interview is required before implementation; actual answers, revisions and rechecks are necessary. Core-only projects receive no mandatory global interview.
- Q3: Codex is the first verified plugin invocation host. The contract remains portable; invocation on other hosts is explicitly unqualified or unavailable until verified. Existing core installation support remains unchanged.
- Q6: Processing with an enabled interview creates a visible stable-ID T-task in a non-implementable clarification state; the same task becomes Ready only after actual answers, revisions, rechecks and owner confirmation.
- Q8: Semantic changes reopen affected answers and final confirmation while preserving unrelated answers; formatting-only changes preserve confirmation. Semantic identity covers goal, scope, exclusions, dependencies, acceptance, validation and required plugin policy.
- Decision evidence: `.skill-tree/documents/plugin-workflow-decisions.md`; Q1-Q11 have actual owner approval. Final shared-understanding confirmation remains separate.

### Define the external skill plugin contract

```yaml
id: T-6d3df9b8-1712-4a41-b38e-aed827e28bfc
priority: 130
status: Ready
parent_pending_ids: ["P-97789c00-ffd4-450f-a0ca-8cd5fd68f8de"]
processing_run_id: PR-e41ce0ec-099e-4072-ace9-59e7acb2ec45
root_task_id: T-6d3df9b8-1712-4a41-b38e-aed827e28bfc
related_task_id: null
relation: main
depends_on: []
```

Goal:
- Specify a provider-neutral contract for third-party skills and optional before/during/after extension points around existing operations.

Current behavior:
- Current helpers record supplied results; no general subprocess-based skill execution engine exists. External wrappers and session-wide modes require explicit invocation and context boundaries.

Touch:
- `.skill-tree/documents/plugin-system-research.md`
- `.skill-tree/documents/plugin-system-contract.md`
- `.skill-tree/templates/invariants.json`
- `.skill-tree/templates/operations.json`
- `.skill-tree/common/references/workflow-metadata.md`
- `.skill-tree/lib/composer.js`

Implementation constraints:
- Define advisory findings, questions, rework and failed/unavailable results without allowing plugins to waive core selection, check receipts or merge authorization.
- Installation and invocation remain separate; the contract introduces no mandatory workflow stage.

Validation:
- Strategy: not-applicable to behavior-changing TDD; source-backed contract review and concrete positive/negative examples.
```json
{
  "checks": [
    {
      "id": "contract-review",
      "recipe_id": "static-inspection",
      "criteria": [
        "The external plugin contract defines pinned identity, dependency closure, host invocation, activation lifetime, input/result envelopes and existing-operation hook names.",
        "The contract preserves standalone resources, core authorization and acceptance boundaries, offline composition and guarded resume semantics.",
        "Workflow-changing choices and unresolved host limitations are explicitly routed to the owner workflow decision task.",
        "Project defaults, explicit temporary run overrides and frozen effective configuration are defined separately from installed-package state; confirmed installation enables only the exact displayed hooks and readiness effects."
      ],
      "sources": [
        ".skill-tree/documents/plugin-system-research.md",
        ".skill-tree/documents/plugin-system-contract.md",
        ".skill-tree/templates/invariants.json",
        ".skill-tree/common/scripts/workflow-state.py",
        ".skill-tree/common/scripts/pr-review-state.py"
      ],
      "parameters": {},
      "assertion": "The external plugin contract defines pinned identity, dependency closure, host invocation, activation lifetime, input/result envelopes and existing-operation hook names. The contract preserves standalone resources, core authorization and acceptance boundaries, offline composition and guarded resume semantics. Workflow-changing choices and unresolved host limitations are explicitly routed to the owner workflow decision task. Project defaults, explicit temporary run overrides and frozen effective configuration are defined separately from installed-package state; confirmed installation enables only the exact displayed hooks and readiness effects.",
      "timing": "immediate"
    }
  ]
}
```

Acceptance:
- The external plugin contract defines pinned identity, dependency closure, host invocation, activation lifetime, input/result envelopes and existing-operation hook names.
- The contract preserves standalone resources, core authorization and acceptance boundaries, offline composition and guarded resume semantics.
- Workflow-changing choices and unresolved host limitations are explicitly routed to the owner workflow decision task.
- Project defaults, explicit temporary run overrides and frozen effective configuration are defined separately from installed-package state; confirmed installation enables only the exact displayed hooks and readiness effects.


Approved clarification decisions:
- Q1: Ponytail is an additional bounded review pass focused on unnecessary complexity and minimal complete changes; findings follow the ordinary authorized fix/re-review flow, and before/during/after placement remains configurable.
- Q2: An enabled post-processing interview is required before implementation; actual answers, revisions and rechecks are necessary. Core-only projects receive no mandatory global interview.
- Q3: Codex is the first verified plugin invocation host. The contract remains portable; invocation on other hosts is explicitly unqualified or unavailable until verified. Existing core installation support remains unchanged.
- Q5: Ponytail defaults to an additional bounded pass after the ordinary full review and before PR readiness; before/during/after placement remains configurable.
- Q6: Processing with an enabled interview creates a visible stable-ID T-task in a non-implementable clarification state; the same task becomes Ready only after actual answers, revisions, rechecks and owner confirmation.
- Q7: An enabled Ponytail pass must complete before PR readiness. Missing capability, failure or unavailability retains a visible block; explicit disabling never counts as successful execution.
- Q9: Project defaults permit explicit temporary per-run overrides. The effective configuration is recorded and frozen across resume; persistent edits are explicit and never silently satisfy or replace parked-run obligations.
- Q11: The installation proposal displays exact versions, hook locations, enabled state and readiness effects. Actual confirmation installs and enables exactly the displayed configuration; skill execution occurs later in authorized workflows.
- Decision evidence: `.skill-tree/documents/plugin-workflow-decisions.md`; Q1-Q11 have actual owner approval. Final shared-understanding confirmation remains separate.

### Implement explicit task clarification rounds and guarded revisions

```yaml
id: T-f63559f1-4663-41b7-b085-f55ba7b47fe5
priority: 128
status: Ready
parent_pending_ids: ["P-e5de6bf4-99d6-481e-b158-7d302efde259"]
processing_run_id: PR-595a7e56-0da2-4b81-afc6-f5cff249c1e2
root_task_id: T-f63559f1-4663-41b7-b085-f55ba7b47fe5
related_task_id: null
relation: main
depends_on: ["T-21b1c999-8586-4e70-a3bc-69cad3ea65aa"]
```

Goal:
- Implement the agreed owner-invoked clarification controller over one existing task or an exact task group, reusing the common interview loop.

Touch:
- `.skill-tree/common/scripts/workflow-state.py`
- `.skill-tree/common/references/workflow-metadata.md`
- `.skill-tree/common/references/future-workflow.md`
- `.skill-tree/templates/operations.json`
- `.skill-tree/config/resource-map.json`
- `.skill-tree/tests/test-task-clarification.py`
- `.skill-tree/tests/test-clarification-installation.js`
- `.skill-tree/scripts/agent-conformance.py`
- `.skill-tree/documents/task-clarification-contract.md`

Implementation constraints:
- Research, long interviews and waits occur outside the writer lock. Preparation and revision recording use source-hash guards and recoverable owned transactions.
- A dedicated revision interface is required: processing reuse does not update task content, and refresh does not guard a preceding external task edit.
- The implementation entry point follows the agreed contract rather than silently adding another mandatory stage or assuming a native Skill tool exists. External plugin adapters can reuse the controller; the generic plugin engine is not a prerequisite of source-backed task discussion.

Validation:
- Strategy: test-first focused state/revision negative controls, isolated installed fixtures and separately recorded actual-agent cases.
```json
{
  "checks": [
    {
      "id": "clarification-state",
      "recipe_id": "quality-python",
      "criteria": [
        "Exact selected identities and round state survive interruption, cancellation and source drift without scope expansion or resetting parked implementation progress.",
        "Atomic task revisions reject stale baselines, conflicting edits, invalid dependencies and unmatched answer/confirmation identities while preserving Pending provenance and immutable terminal outcomes.",
        "Each round rechecks clarity after actual answers and revisions; unresolved prerequisites or repeated no-progress rounds stop honestly, and completion never starts implementation.",
        "Formatting-only edits preserve semantic confirmation; changes to goal, scope, exclusions, dependencies, acceptance, validation or required plugin policy reopen affected answers and final confirmation while retaining unrelated answers."
      ],
      "sources": [
        ".skill-tree/common/scripts/workflow-state.py",
        ".skill-tree/common/references/workflow-metadata.md",
        ".skill-tree/common/references/future-workflow.md",
        ".skill-tree/templates/operations.json",
        ".skill-tree/config/resource-map.json",
        ".skill-tree/tests/test-task-clarification.py",
        ".skill-tree/tests/test-clarification-installation.js",
        ".skill-tree/scripts/agent-conformance.py",
        ".skill-tree/documents/task-clarification-contract.md"
      ],
      "parameters": {
        "test_path": ".skill-tree/tests/test-task-clarification.py"
      },
      "assertion": "Exact selected identities and round state survive interruption, cancellation and source drift without scope expansion or resetting parked implementation progress. Atomic task revisions reject stale baselines, conflicting edits, invalid dependencies and unmatched answer/confirmation identities while preserving Pending provenance and immutable terminal outcomes. Each round rechecks clarity after actual answers and revisions; unresolved prerequisites or repeated no-progress rounds stop honestly, and completion never starts implementation. Formatting-only edits preserve semantic confirmation; changes to goal, scope, exclusions, dependencies, acceptance, validation or required plugin policy reopen affected answers and final confirmation while retaining unrelated answers.",
      "timing": "immediate"
    },
    {
      "id": "clarification-installation",
      "recipe_id": "quality-node",
      "criteria": [
        "Standalone general/web/unity fixtures verify the copied clarification entry point and resource closure without source-checkout or sibling-package dependencies."
      ],
      "sources": [
        ".skill-tree/common/scripts/workflow-state.py",
        ".skill-tree/common/references/workflow-metadata.md",
        ".skill-tree/common/references/future-workflow.md",
        ".skill-tree/templates/operations.json",
        ".skill-tree/config/resource-map.json",
        ".skill-tree/tests/test-task-clarification.py",
        ".skill-tree/tests/test-clarification-installation.js",
        ".skill-tree/scripts/agent-conformance.py",
        ".skill-tree/documents/task-clarification-contract.md"
      ],
      "parameters": {
        "test_path": ".skill-tree/tests/test-clarification-installation.js"
      },
      "assertion": "Standalone general/web/unity fixtures verify the copied clarification entry point and resource closure without source-checkout or sibling-package dependencies.",
      "timing": "immediate"
    },
    {
      "id": "clarification-agent-observation",
      "recipe_id": "static-inspection",
      "criteria": [
        "Bounded independent actual-agent observations demonstrate round, answer, task-revision and confirmation boundaries, with helper behavior and native skill invocation reported separately."
      ],
      "sources": [
        ".skill-tree/common/scripts/workflow-state.py",
        ".skill-tree/common/references/workflow-metadata.md",
        ".skill-tree/common/references/future-workflow.md",
        ".skill-tree/templates/operations.json",
        ".skill-tree/config/resource-map.json",
        ".skill-tree/tests/test-task-clarification.py",
        ".skill-tree/tests/test-clarification-installation.js",
        ".skill-tree/scripts/agent-conformance.py",
        ".skill-tree/documents/task-clarification-contract.md"
      ],
      "parameters": {},
      "assertion": "Bounded independent actual-agent observations demonstrate round, answer, task-revision and confirmation boundaries, with helper behavior and native skill invocation reported separately.",
      "timing": "immediate"
    }
  ]
}
```

Acceptance:
- Exact selected identities and round state survive interruption, cancellation and source drift without scope expansion or resetting parked implementation progress.
- Atomic task revisions reject stale baselines, conflicting edits, invalid dependencies and unmatched answer/confirmation identities while preserving Pending provenance and immutable terminal outcomes.
- Each round rechecks clarity after actual answers and revisions; unresolved prerequisites or repeated no-progress rounds stop honestly, and completion never starts implementation.
- Standalone general/web/unity fixtures verify the copied clarification entry point and resource closure without source-checkout or sibling-package dependencies.
- Bounded independent actual-agent observations demonstrate round, answer, task-revision and confirmation boundaries, with helper behavior and native skill invocation reported separately.
- Formatting-only edits preserve semantic confirmation; changes to goal, scope, exclusions, dependencies, acceptance, validation or required plugin policy reopen affected answers and final confirmation while retaining unrelated answers.


Approved clarification decisions:
- Q2: An enabled post-processing interview is required before implementation; actual answers, revisions and rechecks are necessary. Core-only projects receive no mandatory global interview.
- Q3: Codex is the first verified plugin invocation host. The contract remains portable; invocation on other hosts is explicitly unqualified or unavailable until verified. Existing core installation support remains unchanged.
- Q6: Processing with an enabled interview creates a visible stable-ID T-task in a non-implementable clarification state; the same task becomes Ready only after actual answers, revisions, rechecks and owner confirmation.
- Q8: Semantic changes reopen affected answers and final confirmation while preserving unrelated answers; formatting-only changes preserve confirmation. Semantic identity covers goal, scope, exclusions, dependencies, acceptance, validation and required plugin policy.
- Decision evidence: `.skill-tree/documents/plugin-workflow-decisions.md`; Q1-Q11 have actual owner approval. Final shared-understanding confirmation remains separate.

### Build a dated evidence map of the external skill market

```yaml
id: T-dbebbff9-9d4f-42c6-9377-f9d00cf12b3d
priority: 125
status: Ready
parent_pending_ids: ["P-3f7df14a-88b7-48c8-ac14-eaef552d08aa"]
processing_run_id: PR-e41ce0ec-099e-4072-ace9-59e7acb2ec45
root_task_id: T-dbebbff9-9d4f-42c6-9377-f9d00cf12b3d
related_task_id: null
relation: main
depends_on: []
```

Goal:
- Perform the detailed Internet market study requested by the owner and identify defensible candidates for each relevant workflow location.

Current behavior:
- The processing survey identifies primary ecosystems and compatibility issues but completes no comprehensive market evaluation or candidate recommendation.

Touch:
- `.skill-tree/documents/plugin-system-research.md`
- `.skill-tree/history/research/plugin-market-map.json`
- `.skill-tree/documents/plugin-market-research.md`
- `.skill-tree/documents/agent-compatibility.md`

Implementation constraints:
- Inspect actual current skill packages and source-owned evaluation evidence rather than deriving efficacy from stars, installs or promotional lists.
- Use the source families and supplied revisions in the processing report as starting points, rechecking freshness and recording unknowns.

Validation:
- Strategy: exploratory primary-source research with traceable records and explicit evidence levels.
```json
{
  "checks": [
    {
      "id": "market-source-review",
      "recipe_id": "static-inspection",
      "criteria": [
        "The market map covers distribution ecosystems and relevant planning, processing, implementation, review, validation, documentation and domain candidates with dated primary sources.",
        "Candidate records distinguish adoption signals from demonstrated outcomes and identify revision, maintenance, license, dependencies and host/flavor compatibility.",
        "The research defines a justified comparison shortlist and bounded evaluation plan, including both supplied pilots and unsupported or unqualified cases."
      ],
      "sources": [
        ".skill-tree/documents/plugin-system-research.md",
        ".skill-tree/history/research/plugin-market-map.json",
        ".skill-tree/documents/plugin-market-research.md"
      ],
      "parameters": {},
      "assertion": "The market map covers distribution ecosystems and relevant planning, processing, implementation, review, validation, documentation and domain candidates with dated primary sources. Candidate records distinguish adoption signals from demonstrated outcomes and identify revision, maintenance, license, dependencies and host/flavor compatibility. The research defines a justified comparison shortlist and bounded evaluation plan, including both supplied pilots and unsupported or unqualified cases.",
      "timing": "immediate"
    }
  ]
}
```

Acceptance:
- The market map covers distribution ecosystems and relevant planning, processing, implementation, review, validation, documentation and domain candidates with dated primary sources.
- Candidate records distinguish adoption signals from demonstrated outcomes and identify revision, maintenance, license, dependencies and host/flavor compatibility.
- The research defines a justified comparison shortlist and bounded evaluation plan, including both supplied pilots and unsupported or unqualified cases.


Approved clarification decisions:
- Q3: Codex is the first verified plugin invocation host. The contract remains portable; invocation on other hosts is explicitly unqualified or unavailable until verified. Existing core installation support remains unchanged.
- Q4: Recommendations prioritize demonstrated task/review quality improvement, with explicit time/cost reporting and limitations; adoption alone supplies no outcome evidence.
- Q10: Recommended bundles require bounded comparison evidence in the target workflow. Untested or compatibility-only candidates remain manually selectable with explicit evidence status; no eligible candidate produces an explicit empty recommendation set.
- Decision evidence: `.skill-tree/documents/plugin-workflow-decisions.md`; Q1-Q11 have actual owner approval. Final shared-understanding confirmation remains separate.

### Discuss and agree workflow extension decisions with the owner

```yaml
id: T-a5a738da-c182-4206-bb61-75ffa21946fb
priority: 124
status: Ready
parent_pending_ids: ["P-8f13728d-b0df-4097-afa3-677e7dc939b5"]
processing_run_id: PR-e41ce0ec-099e-4072-ace9-59e7acb2ec45
root_task_id: T-a5a738da-c182-4206-bb61-75ffa21946fb
related_task_id: null
relation: main
depends_on: []
```

Goal:
- Co-design a complete workflow extension map through active owner discussion; produce a decision record before changing stages or readiness behavior.

Current behavior:
- Processing currently publishes Ready tasks immediately. The approved enabled-interview policy requires a visible stable-ID T-task with an implementation hold until the interview and owner confirmation complete.

Touch:
- `.skill-tree/documents/plugin-system-research.md`
- `.skill-tree/documents/plugin-workflow-decisions.md`
- `.skill-tree/templates/operations.json`
- `.skill-tree/common/references/future-workflow.md`
- `.skill-tree/common/references/orchestration.md`
- `.skill-tree/common/scripts/workflow-state.py`

Implementation constraints:
- A proposed stage, task recommendation or installed plugin never supplies owner agreement. No workflow implementation belongs to the design unit.

Decision boundary:
- Present a concrete proposal before requesting agreement. Preserve standalone processing waits and explicit bounded-controller continuation.

Validation:
- Strategy: exploratory design with source inspection, owner discussion and recorded actual decisions.
```json
{
  "checks": [
    {
      "id": "owner-decision-evidence",
      "recipe_id": "static-inspection",
      "criteria": [
        "The owner receives concrete alternatives for existing hook boundaries, missing stages and possible operation splits, with costs and workflow tradeoffs.",
        "Actual owner decisions record approved, rejected or deferred structural changes and the permitted optional hook map.",
        "Every decision consumed by a dependent pilot is actually resolved and approved before the design task completes; unrelated structural proposals can remain explicitly rejected or deferred."
      ],
      "sources": [
        ".skill-tree/documents/plugin-system-research.md",
        ".skill-tree/documents/plugin-workflow-decisions.md",
        ".skill-tree/common/references/future-workflow.md",
        ".skill-tree/common/scripts/workflow-state.py"
      ],
      "parameters": {},
      "assertion": "The owner receives concrete alternatives for existing hook boundaries, missing stages and possible operation splits, with costs and workflow tradeoffs. Actual owner decisions record approved, rejected or deferred structural changes and the permitted optional hook map. Every decision consumed by a dependent pilot is actually resolved and approved before the design task completes; unrelated structural proposals can remain explicitly rejected or deferred.",
      "timing": "immediate"
    }
  ]
}
```

Acceptance:
- The owner receives concrete alternatives for existing hook boundaries, missing stages and possible operation splits, with costs and workflow tradeoffs.
- Actual owner decisions record approved, rejected or deferred structural changes and the permitted optional hook map.
- Every decision consumed by a dependent pilot is actually resolved and approved before the design task completes; unrelated structural proposals can remain explicitly rejected or deferred.


Approved clarification decisions:
- Q1: Ponytail is an additional bounded review pass focused on unnecessary complexity and minimal complete changes; findings follow the ordinary authorized fix/re-review flow, and before/during/after placement remains configurable.
- Q2: An enabled post-processing interview is required before implementation; actual answers, revisions and rechecks are necessary. Core-only projects receive no mandatory global interview.
- Q3: Codex is the first verified plugin invocation host. The contract remains portable; invocation on other hosts is explicitly unqualified or unavailable until verified. Existing core installation support remains unchanged.
- Q4: Recommendations prioritize demonstrated task/review quality improvement, with explicit time/cost reporting and limitations; adoption alone supplies no outcome evidence.
- Q5: Ponytail defaults to an additional bounded pass after the ordinary full review and before PR readiness; before/during/after placement remains configurable.
- Q6: Processing with an enabled interview creates a visible stable-ID T-task in a non-implementable clarification state; the same task becomes Ready only after actual answers, revisions, rechecks and owner confirmation.
- Q7: An enabled Ponytail pass must complete before PR readiness. Missing capability, failure or unavailability retains a visible block; explicit disabling never counts as successful execution.
- Decision evidence: `.skill-tree/documents/plugin-workflow-decisions.md`; Q1-Q11 have actual owner approval. Final shared-understanding confirmation remains separate.

### Specify plugin selection and consent behavior for installation

```yaml
id: T-2da07d09-0b1a-4407-b375-defd23720387
priority: 123
status: Ready
parent_pending_ids: ["P-14584d76-6e8b-418a-b04b-8de586f10f0a"]
processing_run_id: PR-e41ce0ec-099e-4072-ace9-59e7acb2ec45
root_task_id: T-2da07d09-0b1a-4407-b375-defd23720387
related_task_id: null
relation: main
depends_on: ["T-6d3df9b8-1712-4a41-b38e-aed827e28bfc"]
```

Goal:
- Define the installer interaction and failure/consent policy before implementing plugin acquisition or a recommendation wizard.

Current behavior:
- The current installer asks for flavor only, then enters the provider write loop. The existing noninteractive flag supplies no positive plugin consent.

Touch:
- `.skill-tree/documents/plugin-system-research.md`
- `.skill-tree/documents/plugin-installation-contract.md`
- `.skill-tree/bin/install.js`
- `.skill-tree/documents/install.md`
- `.skill-tree/common/references/installation-profile.md`

Implementation constraints:
- Distinguish selection and package installation from skill execution. Resolve material product choices through discussion; routine implementation details can use documented repository-consistent choices.
- Avoid repeated confirmation per provider and avoid treating a displayed or preselected bundle as submitted input.

Validation:
- Strategy: source-backed interaction and failure-case design; no package execution.
```json
{
  "checks": [
    {
      "id": "installation-design-review",
      "recipe_id": "static-inspection",
      "criteria": [
        "One project-level installation proposal shows exact plugin versions, integration locations, enabled state and readiness effects before provider writes; install confirmation installs and enables exactly the displayed configuration.",
        "Alternative selection exposes the complete available catalog grouped by integration point, while skip retains a functional core-only result.",
        "The interaction contract defines actual consent, noninteractive and repeat-install behavior, plugin failure policy and offline/no-write dry-run semantics.",
        "An empty eligible recommendation set remains a valid outcome with explicit evidence status, optional grouped manual selection and a functional core-only skip path."
      ],
      "sources": [
        ".skill-tree/documents/plugin-system-research.md",
        ".skill-tree/documents/plugin-installation-contract.md",
        ".skill-tree/bin/install.js",
        ".skill-tree/common/references/installation-profile.md"
      ],
      "parameters": {},
      "assertion": "One project-level installation proposal shows exact plugin versions, integration locations, enabled state and readiness effects before provider writes; install confirmation installs and enables exactly the displayed configuration. Alternative selection exposes the complete available catalog grouped by integration point, while skip retains a functional core-only result. The interaction contract defines actual consent, noninteractive and repeat-install behavior, plugin failure policy and offline/no-write dry-run semantics. An empty eligible recommendation set remains a valid outcome with explicit evidence status, optional grouped manual selection and a functional core-only skip path.",
      "timing": "immediate"
    }
  ]
}
```

Acceptance:
- One project-level installation proposal shows exact plugin versions, integration locations, enabled state and readiness effects before provider writes; install confirmation installs and enables exactly the displayed configuration.
- Alternative selection exposes the complete available catalog grouped by integration point, while skip retains a functional core-only result.
- The interaction contract defines actual consent, noninteractive and repeat-install behavior, plugin failure policy and offline/no-write dry-run semantics.
- An empty eligible recommendation set remains a valid outcome with explicit evidence status, optional grouped manual selection and a functional core-only skip path.


Approved clarification decisions:
- Q3: Codex is the first verified plugin invocation host. The contract remains portable; invocation on other hosts is explicitly unqualified or unavailable until verified. Existing core installation support remains unchanged.
- Q9: Project defaults permit explicit temporary per-run overrides. The effective configuration is recorded and frozen across resume; persistent edits are explicit and never silently satisfy or replace parked-run obligations.
- Q10: Recommended bundles require bounded comparison evidence in the target workflow. Untested or compatibility-only candidates remain manually selectable with explicit evidence status; no eligible candidate produces an explicit empty recommendation set.
- Q11: The installation proposal displays exact versions, hook locations, enabled state and readiness effects. Actual confirmation installs and enables exactly the displayed configuration; skill execution occurs later in authorized workflows.
- Decision evidence: `.skill-tree/documents/plugin-workflow-decisions.md`; Q1-Q11 have actual owner approval. Final shared-understanding confirmation remains separate.

### Implement pinned external plugin package lifecycle

```yaml
id: T-6f4500f7-91e2-410d-8172-a4c4cd232fc5
priority: 120
status: Ready
parent_pending_ids: ["P-97789c00-ffd4-450f-a0ca-8cd5fd68f8de"]
processing_run_id: PR-e41ce0ec-099e-4072-ace9-59e7acb2ec45
root_task_id: T-6f4500f7-91e2-410d-8172-a4c4cd232fc5
related_task_id: null
relation: main
depends_on: ["T-6d3df9b8-1712-4a41-b38e-aed827e28bfc", "T-2da07d09-0b1a-4407-b375-defd23720387"]
```

Goal:
- Implement explicit source/dependency resolution and owned local plugin generations using the existing installation/profile transaction boundary.

Touch:
- `.skill-tree/installation/plugins.json`
- `.skill-tree/lib/plugins.js`
- `.skill-tree/lib/composer.js`
- `.skill-tree/lib/installation.js`
- `.skill-tree/bin/install.js`
- `.skill-tree/tests/test-plugin-installation.js`
- `.skill-tree/documents/plugin-system-contract.md`
- `.skill-tree/documents/plugin-installation-contract.md`

Implementation constraints:
- The owned project-local registry `.skill-tree/installation/plugins.json` records plugin generations, provenance, destinations, dependencies and configured operation/hook bindings. Package, registry and binding changes share the installation transaction.
- Remote acquisition is a distinct confirmed install action, never hidden in static composition, verification or dry-run.
- Preserve upstream content/license provenance and repository-local paths; no implicit global or symlink installation, format conversion or unreviewed helper execution.

Validation:
- Strategy: test-first focused behavioral regressions.
```json
{
  "checks": [
    {
      "id": "package-lifecycle",
      "recipe_id": "quality-node",
      "criteria": [
        "Exact external revisions, complete local resources and required sibling/native-tool dependencies resolve into an owned project-scoped plugin generation.",
        "Modified or unknown ownership, missing dependencies, unsupported host requirements, drift and interrupted replacement fail or recover without corrupting core packages and checkpoints.",
        "Enable, disable, update, uninstall and rollback follow the agreed consent/lifecycle contract; ordinary dry-run remains offline and no installation executes a skill.",
        "The canonical registry, owned package generation and configured hook bindings update or roll back atomically; install confirmation enables only displayed bindings and the registry supports downstream inventory views without requiring the management interface."
      ],
      "sources": [
        ".skill-tree/installation/plugins.json",
        ".skill-tree/lib/plugins.js",
        ".skill-tree/lib/composer.js",
        ".skill-tree/lib/installation.js",
        ".skill-tree/bin/install.js",
        ".skill-tree/tests/test-plugin-installation.js",
        ".skill-tree/documents/plugin-system-contract.md",
        ".skill-tree/documents/plugin-installation-contract.md"
      ],
      "parameters": {
        "test_path": ".skill-tree/tests/test-plugin-installation.js"
      },
      "assertion": "Exact external revisions, complete local resources and required sibling/native-tool dependencies resolve into an owned project-scoped plugin generation. Modified or unknown ownership, missing dependencies, unsupported host requirements, drift and interrupted replacement fail or recover without corrupting core packages and checkpoints. Enable, disable, update, uninstall and rollback follow the agreed consent/lifecycle contract; ordinary dry-run remains offline and no installation executes a skill. The canonical registry, owned package generation and configured hook bindings update or roll back atomically; install confirmation enables only displayed bindings and the registry supports downstream inventory views without requiring the management interface.",
      "timing": "immediate"
    }
  ]
}
```

Acceptance:
- Exact external revisions, complete local resources and required sibling/native-tool dependencies resolve into an owned project-scoped plugin generation.
- Modified or unknown ownership, missing dependencies, unsupported host requirements, drift and interrupted replacement fail or recover without corrupting core packages and checkpoints.
- Enable, disable, update, uninstall and rollback follow the agreed consent/lifecycle contract; ordinary dry-run remains offline and no installation executes a skill.
- The canonical registry, owned package generation and configured hook bindings update or roll back atomically; install confirmation enables only displayed bindings and the registry supports downstream inventory views without requiring the management interface.


Approved clarification decisions:
- Q3: Codex is the first verified plugin invocation host. The contract remains portable; invocation on other hosts is explicitly unqualified or unavailable until verified. Existing core installation support remains unchanged.
- Q9: Project defaults permit explicit temporary per-run overrides. The effective configuration is recorded and frozen across resume; persistent edits are explicit and never silently satisfy or replace parked-run obligations.
- Q11: The installation proposal displays exact versions, hook locations, enabled state and readiness effects. Actual confirmation installs and enables exactly the displayed configuration; skill execution occurs later in authorized workflows.
- Decision evidence: `.skill-tree/documents/plugin-workflow-decisions.md`; Q1-Q11 have actual owner approval. Final shared-understanding confirmation remains separate.

### Compose selected plugin hooks into standalone operations

```yaml
id: T-a9d7a827-fb25-4348-bcf7-867a449c58ef
priority: 119
status: Ready
parent_pending_ids: ["P-97789c00-ffd4-450f-a0ca-8cd5fd68f8de"]
processing_run_id: PR-e41ce0ec-099e-4072-ace9-59e7acb2ec45
root_task_id: T-a9d7a827-fb25-4348-bcf7-867a449c58ef
related_task_id: null
relation: main
depends_on: ["T-6f4500f7-91e2-410d-8172-a4c4cd232fc5"]
```

Goal:
- Extend canonical composition and bundled instructions with the agreed provider-neutral invocation and verified native capability routing.

Touch:
- `.skill-tree/lib/composer.js`
- `.skill-tree/config/resource-map.json`
- `.skill-tree/templates/operations.json`
- `.skill-tree/common/references/plugin-invocation.md`
- `.skill-tree/tests/test-plugin-composition.js`
- `.skill-tree/documents/plugin-system-contract.md`

Implementation constraints:
- Generate representative and installed resources only through canonical composition. Do not append unbounded external instructions to every skill.
- Separate context-scoped skill use from native host plugin bundles and decline unsupported invocation instead of claiming a nonexistent tool call. Core-only operations preserve current readiness. Enabled interview and review gates follow Q6/Q7; no mandatory global stage belongs to the core.

Validation:
- Strategy: test-first focused behavioral regressions.
```json
{
  "checks": [
    {
      "id": "standalone-plugin-composition",
      "recipe_id": "quality-node",
      "criteria": [
        "Configured plugins compose only into selected existing-operation hook points in deterministic order without replacing locked invariants.",
        "A copied installed operation retains the declared plugin resource closure without the source checkout or unrelated sibling packages; unsupported host capabilities return an explicit prerequisite.",
        "Plugin selection, revisions and content participate in profile/maintenance identities, freshness checks and stopped-handoff refresh behavior for general, web and unity.",
        "Core-only composition retains current readiness; selected interview and review hooks expose the approved holds, default placement and project/run configuration without creating a global mandatory stage."
      ],
      "sources": [
        ".skill-tree/lib/composer.js",
        ".skill-tree/config/resource-map.json",
        ".skill-tree/templates/operations.json",
        ".skill-tree/common/references/plugin-invocation.md",
        ".skill-tree/tests/test-plugin-composition.js",
        ".skill-tree/documents/plugin-system-contract.md"
      ],
      "parameters": {
        "test_path": ".skill-tree/tests/test-plugin-composition.js"
      },
      "assertion": "Configured plugins compose only into selected existing-operation hook points in deterministic order without replacing locked invariants. A copied installed operation retains the declared plugin resource closure without the source checkout or unrelated sibling packages; unsupported host capabilities return an explicit prerequisite. Plugin selection, revisions and content participate in profile/maintenance identities, freshness checks and stopped-handoff refresh behavior for general, web and unity. Core-only composition retains current readiness; selected interview and review hooks expose the approved holds, default placement and project/run configuration without creating a global mandatory stage.",
      "timing": "immediate"
    }
  ]
}
```

Acceptance:
- Configured plugins compose only into selected existing-operation hook points in deterministic order without replacing locked invariants.
- A copied installed operation retains the declared plugin resource closure without the source checkout or unrelated sibling packages; unsupported host capabilities return an explicit prerequisite.
- Plugin selection, revisions and content participate in profile/maintenance identities, freshness checks and stopped-handoff refresh behavior for general, web and unity.
- Core-only composition retains current readiness; selected interview and review hooks expose the approved holds, default placement and project/run configuration without creating a global mandatory stage.


Approved clarification decisions:
- Q1: Ponytail is an additional bounded review pass focused on unnecessary complexity and minimal complete changes; findings follow the ordinary authorized fix/re-review flow, and before/during/after placement remains configurable.
- Q3: Codex is the first verified plugin invocation host. The contract remains portable; invocation on other hosts is explicitly unqualified or unavailable until verified. Existing core installation support remains unchanged.
- Q5: Ponytail defaults to an additional bounded pass after the ordinary full review and before PR readiness; before/during/after placement remains configurable.
- Q9: Project defaults permit explicit temporary per-run overrides. The effective configuration is recorded and frozen across resume; persistent edits are explicit and never silently satisfy or replace parked-run obligations.
- Decision evidence: `.skill-tree/documents/plugin-workflow-decisions.md`; Q1-Q11 have actual owner approval. Final shared-understanding confirmation remains separate.

### Implement resumable plugin invocation and result receipts

```yaml
id: T-dae414c5-43e4-45db-a6f3-4ce4112440c5
priority: 118
status: Ready
parent_pending_ids: ["P-97789c00-ffd4-450f-a0ca-8cd5fd68f8de"]
processing_run_id: PR-e41ce0ec-099e-4072-ace9-59e7acb2ec45
root_task_id: T-dae414c5-43e4-45db-a6f3-4ce4112440c5
related_task_id: null
relation: main
depends_on: ["T-a9d7a827-fb25-4348-bcf7-867a449c58ef"]
```

Goal:
- Add prepare/invoke/record/reconcile semantics to the existing agent-driven workflow and review evidence protocols.

Touch:
- `.skill-tree/common/scripts/workflow-state.py`
- `.skill-tree/common/scripts/pr-review-state.py`
- `.skill-tree/common/scripts/run-workspaces.py`
- `.skill-tree/common/references/workflow-metadata.md`
- `.skill-tree/tests/test-plugin-workflow.py`
- `.skill-tree/scripts/agent-conformance.py`
- `.skill-tree/common/references/plugin-invocation.md`

Implementation constraints:
- Queue and review state mutations use ordinary guarded Skill Tree helpers; external instructions never mutate core state directly.
- Retain core-only readiness, immutable historical outcomes, exact selected-group scope and explicit permission boundaries. Enabled interview and review gates follow Q6/Q7. Optional existing-operation hooks need no unrelated new-stage approval. Actual model/provider execution uses a bounded reviewed plan and applicable scope.

Validation:
- Strategy: test-first focused behavioral regressions.
```json
{
  "checks": [
    {
      "id": "hook-state-regressions",
      "recipe_id": "quality-python",
      "criteria": [
        "Hook attempts and results bind task/operation, plugin revision, source/profile, review identities and frozen effective configuration with idempotent replay and stale-result rejection.",
        "Long invocation and owner questions occur outside the writer lock; waits, failure, rework and resume preserve the same task/run and mandatory acceptance boundaries.",
        "Explicit temporary overrides are recorded before invocation; later project-default changes or plugin removal never silently alter parked-run configuration or satisfy required interview/review gates."
      ],
      "sources": [
        ".skill-tree/common/scripts/workflow-state.py",
        ".skill-tree/common/scripts/pr-review-state.py",
        ".skill-tree/common/scripts/run-workspaces.py",
        ".skill-tree/common/references/workflow-metadata.md",
        ".skill-tree/tests/test-plugin-workflow.py",
        ".skill-tree/scripts/agent-conformance.py",
        ".skill-tree/common/references/plugin-invocation.md"
      ],
      "parameters": {
        "test_path": ".skill-tree/tests/test-plugin-workflow.py"
      },
      "assertion": "Hook attempts and results bind task/operation, plugin revision, source/profile, review identities and frozen effective configuration with idempotent replay and stale-result rejection. Long invocation and owner questions occur outside the writer lock; waits, failure, rework and resume preserve the same task/run and mandatory acceptance boundaries. Explicit temporary overrides are recorded before invocation; later project-default changes or plugin removal never silently alter parked-run configuration or satisfy required interview/review gates.",
      "timing": "immediate"
    },
    {
      "id": "installed-agent-hook-evidence",
      "recipe_id": "static-inspection",
      "criteria": [
        "Standalone installed fixtures and bounded approved agent observations establish hook routing, no-plugin behavior and stop/resume containment without implicit publication or scope expansion."
      ],
      "sources": [
        ".skill-tree/common/scripts/workflow-state.py",
        ".skill-tree/common/scripts/pr-review-state.py",
        ".skill-tree/common/scripts/run-workspaces.py",
        ".skill-tree/common/references/workflow-metadata.md",
        ".skill-tree/tests/test-plugin-workflow.py",
        ".skill-tree/scripts/agent-conformance.py",
        ".skill-tree/common/references/plugin-invocation.md"
      ],
      "parameters": {},
      "assertion": "Standalone installed fixtures and bounded approved agent observations establish hook routing, no-plugin behavior and stop/resume containment without implicit publication or scope expansion.",
      "timing": "immediate"
    }
  ]
}
```

Acceptance:
- Hook attempts and results bind task/operation, plugin revision, source/profile, review identities and frozen effective configuration with idempotent replay and stale-result rejection.
- Long invocation and owner questions occur outside the writer lock; waits, failure, rework and resume preserve the same task/run and mandatory acceptance boundaries.
- Standalone installed fixtures and bounded approved agent observations establish hook routing, no-plugin behavior and stop/resume containment without implicit publication or scope expansion.
- Explicit temporary overrides are recorded before invocation; later project-default changes or plugin removal never silently alter parked-run configuration or satisfy required interview/review gates.


Approved clarification decisions:
- Q1: Ponytail is an additional bounded review pass focused on unnecessary complexity and minimal complete changes; findings follow the ordinary authorized fix/re-review flow, and before/during/after placement remains configurable.
- Q2: An enabled post-processing interview is required before implementation; actual answers, revisions and rechecks are necessary. Core-only projects receive no mandatory global interview.
- Q3: Codex is the first verified plugin invocation host. The contract remains portable; invocation on other hosts is explicitly unqualified or unavailable until verified. Existing core installation support remains unchanged.
- Q5: Ponytail defaults to an additional bounded pass after the ordinary full review and before PR readiness; before/during/after placement remains configurable.
- Q6: Processing with an enabled interview creates a visible stable-ID T-task in a non-implementable clarification state; the same task becomes Ready only after actual answers, revisions, rechecks and owner confirmation.
- Q7: An enabled Ponytail pass must complete before PR readiness. Missing capability, failure or unavailability retains a visible block; explicit disabling never counts as successful execution.
- Q9: Project defaults permit explicit temporary per-run overrides. The effective configuration is recorded and frozen across resume; persistent edits are explicit and never silently satisfy or replace parked-run obligations.
- Decision evidence: `.skill-tree/documents/plugin-workflow-decisions.md`; Q1-Q11 have actual owner approval. Final shared-understanding confirmation remains separate.

### Expose the installed plugin registry and exact-ID removal

```yaml
id: T-10528edd-4542-4c26-b8b3-738ffc00d791
priority: 117
status: Ready
parent_pending_ids: ["P-50c04dfb-3cb6-4531-ae04-bd24bb232671"]
processing_run_id: PR-5420f7ac-ede8-4a34-bac5-a7d84f405fff
root_task_id: T-10528edd-4542-4c26-b8b3-738ffc00d791
related_task_id: null
relation: main
depends_on: ["T-6f4500f7-91e2-410d-8172-a4c4cd232fc5"]
```

Goal:
- Expose the owned installed-plugin registry and simple exact-ID removal, including every configured workflow integration location.

Current behavior:
- The current core installation profile records destination ownership and supports guarded uninstall. The current installer lists available core skills, but no external-plugin inventory or binding view exists.

Touch:
- `.skill-tree/installation/plugins.json`
- `.skill-tree/lib/plugins.js`
- `.skill-tree/lib/installation.js`
- `.skill-tree/bin/install.js`
- `.skill-tree/tests/test-plugin-management.js`
- `.skill-tree/documents/plugin-installation-contract.md`
- `.skill-tree/documents/install.md`

Implementation constraints:
- The lifecycle owns the canonical registry and atomic package/binding mutations. Registry views derive from the same owned state rather than maintaining another installed-plugin list.
- Project defaults and frozen per-run effective configuration remain distinguishable. Uninstall preserves recorded run configuration and reports missing requirements instead of silently rewriting a parked run.
- Removal selects an exact plugin ID, shows affected integration locations and rejects unresolved dependents instead of silently cascading to other plugins. The current project-local copy and ownership policy remains binding.

Validation:
- Strategy: test-first focused inventory and removal behavior in isolated installed projects.
```json
{
  "checks": [
    {
      "id": "plugin-management",
      "recipe_id": "quality-node",
      "criteria": [
        "A project-local installed-plugin registry has one canonical owner and records stable plugin ID, exact revision, installed destinations, dependencies and every configured operation/hook binding with enabled state.",
        "A read-only installed-plugin command exposes human-readable and machine-readable views by plugin and integration point, distinguishes installed packages from available catalog entries and reports ownership drift without network or mutation.",
        "One documented exact-ID removal command previews affected owned packages and bindings, then removes the selected plugin and bindings through the guarded lifecycle without deleting core packages, shared dependencies or unrelated files.",
        "Unknown or ambiguous IDs, dependent plugins, modified files and parked runs receive explicit safe outcomes; removal never rewrites historical receipts or marks an outstanding required invocation successful."
      ],
      "sources": [
        ".skill-tree/installation/plugins.json",
        ".skill-tree/lib/plugins.js",
        ".skill-tree/lib/installation.js",
        ".skill-tree/bin/install.js",
        ".skill-tree/tests/test-plugin-management.js",
        ".skill-tree/documents/plugin-installation-contract.md",
        ".skill-tree/documents/install.md"
      ],
      "parameters": {
        "test_path": ".skill-tree/tests/test-plugin-management.js"
      },
      "assertion": "A project-local installed-plugin registry has one canonical owner and records stable plugin ID, exact revision, installed destinations, dependencies and every configured operation/hook binding with enabled state. A read-only installed-plugin command exposes human-readable and machine-readable views by plugin and integration point, distinguishes installed packages from available catalog entries and reports ownership drift without network or mutation. One documented exact-ID removal command previews affected owned packages and bindings, then removes the selected plugin and bindings through the guarded lifecycle without deleting core packages, shared dependencies or unrelated files. Unknown or ambiguous IDs, dependent plugins, modified files and parked runs receive explicit safe outcomes; removal never rewrites historical receipts or marks an outstanding required invocation successful.",
      "timing": "immediate"
    }
  ]
}
```

Acceptance:
- A project-local installed-plugin registry has one canonical owner and records stable plugin ID, exact revision, installed destinations, dependencies and every configured operation/hook binding with enabled state.
- A read-only installed-plugin command exposes human-readable and machine-readable views by plugin and integration point, distinguishes installed packages from available catalog entries and reports ownership drift without network or mutation.
- One documented exact-ID removal command previews affected owned packages and bindings, then removes the selected plugin and bindings through the guarded lifecycle without deleting core packages, shared dependencies or unrelated files.
- Unknown or ambiguous IDs, dependent plugins, modified files and parked runs receive explicit safe outcomes; removal never rewrites historical receipts or marks an outstanding required invocation successful.

Approved clarification decisions:
- Q9: Project defaults permit explicit temporary per-run overrides. The effective configuration is recorded and frozen across resume; persistent edits are explicit and never silently satisfy or replace parked-run obligations.
- Q11: The installation proposal displays exact versions, hook locations, enabled state and readiness effects. Actual confirmation installs and enables exactly the displayed configuration; skill execution occurs later in authorized workflows.
- Decision evidence: `.skill-tree/documents/plugin-workflow-decisions.md`; Q1-Q11 have actual owner approval. Final shared-understanding confirmation remains separate.

### Integrate the pinned development-mode review pilot

```yaml
id: T-18db6175-499f-4679-bf8d-f815c7b42411
priority: 116
status: Ready
parent_pending_ids: ["P-468bf390-905d-43c5-a161-604eb1a41244"]
processing_run_id: PR-e41ce0ec-099e-4072-ace9-59e7acb2ec45
root_task_id: T-18db6175-499f-4679-bf8d-f815c7b42411
related_task_id: null
relation: main
depends_on: ["T-dae414c5-43e4-45db-a6f3-4ce4112440c5", "T-a5a738da-c182-4206-bb61-75ffa21946fb"]
```

Goal:
- Implement the supplied ponytail use case as an optional configurable review plugin with verified source and bounded activation.

Touch:
- `.skill-tree/config/plugins/ponytail.json`
- `.skill-tree/common/scripts/pr-review-state.py`
- `.skill-tree/common/references/pr-review-cycle.md`
- `.skill-tree/tests/test-plugin-review.py`
- `.skill-tree/documents/plugin-system-contract.md`
- `.skill-tree/documents/plugin-workflow-decisions.md`
- `.skill-tree/documents/plugin-system-research.md`

Implementation constraints:
- Reverify the supplied source revision and license/dependency facts before installation. The upstream skill is a session-wide coding mode, not an assumed isolated reviewer.
- The definition of during-review participation follows the actual owner decision rather than silently replacing the core reviewer.

Validation:
- Strategy: test-first focused behavioral regressions.
```json
{
  "checks": [
    {
      "id": "review-pilot-regressions",
      "recipe_id": "quality-python",
      "criteria": [
        "The pinned supplied development-mode skill defaults to an additional pass after ordinary full review and before PR readiness, with configurable before/during/after placement that preserves the full core review.",
        "Activation remains inside the agreed invocation context; resulting findings and rework retain current head/base identity and normal re-review behavior.",
        "Missing capability/dependency and session-mode leakage are covered by negative controls; the plugin cannot satisfy independent approval or authorize merge.",
        "An enabled review pass must complete for the current review identity before PR readiness; unavailable capabilities, failed execution or stale results retain a visible block, and explicit disabling is recorded without reporting execution success."
      ],
      "sources": [
        ".skill-tree/config/plugins/ponytail.json",
        ".skill-tree/common/scripts/pr-review-state.py",
        ".skill-tree/common/references/pr-review-cycle.md",
        ".skill-tree/tests/test-plugin-review.py",
        ".skill-tree/documents/plugin-system-contract.md",
        ".skill-tree/documents/plugin-workflow-decisions.md",
        ".skill-tree/documents/plugin-system-research.md"
      ],
      "parameters": {
        "test_path": ".skill-tree/tests/test-plugin-review.py"
      },
      "assertion": "The pinned supplied development-mode skill defaults to an additional pass after ordinary full review and before PR readiness, with configurable before/during/after placement that preserves the full core review. Activation remains inside the agreed invocation context; resulting findings and rework retain current head/base identity and normal re-review behavior. Missing capability/dependency and session-mode leakage are covered by negative controls; the plugin cannot satisfy independent approval or authorize merge. An enabled review pass must complete for the current review identity before PR readiness; unavailable capabilities, failed execution or stale results retain a visible block, and explicit disabling is recorded without reporting execution success.",
      "timing": "immediate"
    }
  ]
}
```

Acceptance:
- The pinned supplied development-mode skill defaults to an additional pass after ordinary full review and before PR readiness, with configurable before/during/after placement that preserves the full core review.
- Activation remains inside the agreed invocation context; resulting findings and rework retain current head/base identity and normal re-review behavior.
- Missing capability/dependency and session-mode leakage are covered by negative controls; the plugin cannot satisfy independent approval or authorize merge.
- An enabled review pass must complete for the current review identity before PR readiness; unavailable capabilities, failed execution or stale results retain a visible block, and explicit disabling is recorded without reporting execution success.


Approved clarification decisions:
- Q1: Ponytail is an additional bounded review pass focused on unnecessary complexity and minimal complete changes; findings follow the ordinary authorized fix/re-review flow, and before/during/after placement remains configurable.
- Q3: Codex is the first verified plugin invocation host. The contract remains portable; invocation on other hosts is explicitly unqualified or unavailable until verified. Existing core installation support remains unchanged.
- Q5: Ponytail defaults to an additional bounded pass after the ordinary full review and before PR readiness; before/during/after placement remains configurable.
- Q7: An enabled Ponytail pass must complete before PR readiness. Missing capability, failure or unavailability retains a visible block; explicit disabling never counts as successful execution.
- Q9: Project defaults permit explicit temporary per-run overrides. The effective configuration is recorded and frozen across resume; persistent edits are explicit and never silently satisfy or replace parked-run obligations.
- Decision evidence: `.skill-tree/documents/plugin-workflow-decisions.md`; Q1-Q11 have actual owner approval. Final shared-understanding confirmation remains separate.

### Integrate post-processing interviews and task rework

```yaml
id: T-657e5621-efb8-4c53-8ab9-bdd2a7e6ec69
priority: 115
status: Ready
parent_pending_ids: ["P-c9ec2d76-0e74-46cd-afd4-ce3f46a7a60b", "P-e5de6bf4-99d6-481e-b158-7d302efde259"]
processing_run_id: PR-595a7e56-0da2-4b81-afc6-f5cff249c1e2
root_task_id: T-657e5621-efb8-4c53-8ab9-bdd2a7e6ec69
related_task_id: null
relation: main
depends_on: ["T-dae414c5-43e4-45db-a6f3-4ce4112440c5", "T-a5a738da-c182-4206-bb61-75ffa21946fb", "T-f63559f1-4663-41b7-b085-f55ba7b47fe5"]
```

Goal:
- Implement the supplied `grill-me` interview use case after research processing, with an approved readiness guard and resumable owner interaction.

Touch:
- `.skill-tree/config/plugins/task-interview.json`
- `.skill-tree/common/scripts/workflow-state.py`
- `.skill-tree/common/references/future-workflow.md`
- `.skill-tree/tests/test-plugin-processing.py`
- `.skill-tree/documents/plugin-workflow-decisions.md`
- `.skill-tree/documents/plugin-system-research.md`

Implementation constraints:
- The current wrapper depends on `grilling` and a host-specific tool; unresolved dependencies are explicit prerequisites.
- Processing creates a visible stable-ID T-task under a clarification hold when the interview is enabled. The task remains non-implementable until actual answers, revisions, rechecks and current owner confirmation complete; core-only processing retains existing behavior.

Validation:
- Strategy: test-first focused behavioral regressions.
```json
{
  "checks": [
    {
      "id": "interview-loop-regressions",
      "recipe_id": "quality-python",
      "criteria": [
        "The pinned interview wrapper and delegated grilling resources resolve through the agreed supported invocation path.",
        "Processing with the interview enabled creates a visible non-implementable T-task; question/wait/answer/rework/recheck and owner confirmation retain the same ID and provenance before publishing Ready.",
        "Interrupted, stale, repeated and adverse interview outcomes preserve selection scope and standalone/controller handoff rules without inferring consent from silence.",
        "Semantic task changes reopen affected answers and final confirmation while formatting-only changes retain confirmation; unavailable interviews, silence or disabling never establish completed answers."
      ],
      "sources": [
        ".skill-tree/config/plugins/task-interview.json",
        ".skill-tree/common/scripts/workflow-state.py",
        ".skill-tree/common/references/future-workflow.md",
        ".skill-tree/tests/test-plugin-processing.py",
        ".skill-tree/documents/plugin-workflow-decisions.md",
        ".skill-tree/documents/plugin-system-research.md"
      ],
      "parameters": {
        "test_path": ".skill-tree/tests/test-plugin-processing.py"
      },
      "assertion": "The pinned interview wrapper and delegated grilling resources resolve through the agreed supported invocation path. Processing with the interview enabled creates a visible non-implementable T-task; question/wait/answer/rework/recheck and owner confirmation retain the same ID and provenance before publishing Ready. Interrupted, stale, repeated and adverse interview outcomes preserve selection scope and standalone/controller handoff rules without inferring consent from silence. Semantic task changes reopen affected answers and final confirmation while formatting-only changes retain confirmation; unavailable interviews, silence or disabling never establish completed answers.",
      "timing": "immediate"
    }
  ]
}
```

Acceptance:
- The pinned interview wrapper and delegated grilling resources resolve through the agreed supported invocation path.
- Processing with the interview enabled creates a visible non-implementable T-task; question/wait/answer/rework/recheck and owner confirmation retain the same ID and provenance before publishing Ready.
- Interrupted, stale, repeated and adverse interview outcomes preserve selection scope and standalone/controller handoff rules without inferring consent from silence.
- Semantic task changes reopen affected answers and final confirmation while formatting-only changes retain confirmation; unavailable interviews, silence or disabling never establish completed answers.


Approved clarification decisions:
- Q2: An enabled post-processing interview is required before implementation; actual answers, revisions and rechecks are necessary. Core-only projects receive no mandatory global interview.
- Q3: Codex is the first verified plugin invocation host. The contract remains portable; invocation on other hosts is explicitly unqualified or unavailable until verified. Existing core installation support remains unchanged.
- Q6: Processing with an enabled interview creates a visible stable-ID T-task in a non-implementable clarification state; the same task becomes Ready only after actual answers, revisions, rechecks and owner confirmation.
- Q8: Semantic changes reopen affected answers and final confirmation while preserving unrelated answers; formatting-only changes preserve confirmation. Semantic identity covers goal, scope, exclusions, dependencies, acceptance, validation and required plugin policy.
- Q9: Project defaults permit explicit temporary per-run overrides. The effective configuration is recorded and frozen across resume; persistent edits are explicit and never silently satisfy or replace parked-run obligations.
- Decision evidence: `.skill-tree/documents/plugin-workflow-decisions.md`; Q1-Q11 have actual owner approval. Final shared-understanding confirmation remains separate.

### Qualify shortlisted plugins against workflow baselines

```yaml
id: T-a583acd5-fc6b-4d37-97ec-02df969fea9e
priority: 114
status: Ready
parent_pending_ids: ["P-3f7df14a-88b7-48c8-ac14-eaef552d08aa"]
processing_run_id: PR-e41ce0ec-099e-4072-ace9-59e7acb2ec45
root_task_id: T-a583acd5-fc6b-4d37-97ec-02df969fea9e
related_task_id: null
relation: main
depends_on: ["T-dbebbff9-9d4f-42c6-9377-f9d00cf12b3d", "T-dae414c5-43e4-45db-a6f3-4ce4112440c5"]
```

Goal:
- Run the second stage of the detailed market research: bounded comparative candidate qualification and evidence-backed recommendation selection.

Touch:
- `.skill-tree/documents/plugin-system-research.md`
- `.skill-tree/history/research/plugin-market-map.json`
- `.skill-tree/history/research/plugin-comparison-results.json`
- `.skill-tree/documents/plugin-recommendation-evidence.md`
- `.skill-tree/scripts/agent-conformance.py`
- `.skill-tree/documents/plugin-system-contract.md`

Implementation constraints:
- Include the supplied pilots in the evaluated set without assuming favorable outcomes; source popularity alone never meets recommendation acceptance.
- Agree a concrete bounded plan and required runtime/cost scope before paid models or product tools. The report records actual executions, unavailable cases and evidence expiry. A missing policy or unsupported gated integration remains unqualified rather than forcing an unrelated workflow change. No universal efficacy ranking follows.

Validation:
- Strategy: exploratory comparative evaluation using justified baselines, independent review and exact contextual evidence.
```json
{
  "checks": [
    {
      "id": "comparative-evidence-review",
      "recipe_id": "static-inspection",
      "criteria": [
        "The approved comparison plan evaluates a justified candidate set against no-plugin baselines with positive/negative controls and actual activation evidence.",
        "Results bind candidate revision/dependencies, fixture, model/host configuration and measured task outcomes while keeping missing evidence and limitations explicit.",
        "The research records defended recommendations and alternatives or an explicit empty eligible set per integration location/flavor, distinguishing observed benefit from compatibility-only or unqualified discovery candidates."
      ],
      "sources": [
        ".skill-tree/documents/plugin-system-research.md",
        ".skill-tree/history/research/plugin-market-map.json",
        ".skill-tree/history/research/plugin-comparison-results.json",
        ".skill-tree/documents/plugin-recommendation-evidence.md",
        ".skill-tree/scripts/agent-conformance.py",
        ".skill-tree/documents/plugin-system-contract.md"
      ],
      "parameters": {},
      "assertion": "The approved comparison plan evaluates a justified candidate set against no-plugin baselines with positive/negative controls and actual activation evidence. Results bind candidate revision/dependencies, fixture, model/host configuration and measured task outcomes while keeping missing evidence and limitations explicit. The research records defended recommendations and alternatives or an explicit empty eligible set per integration location/flavor, distinguishing observed benefit from compatibility-only or unqualified discovery candidates.",
      "timing": "immediate"
    }
  ]
}
```

Acceptance:
- The approved comparison plan evaluates a justified candidate set against no-plugin baselines with positive/negative controls and actual activation evidence.
- Results bind candidate revision/dependencies, fixture, model/host configuration and measured task outcomes while keeping missing evidence and limitations explicit.
- The research records defended recommendations and alternatives or an explicit empty eligible set per integration location/flavor, distinguishing observed benefit from compatibility-only or unqualified discovery candidates.


Approved clarification decisions:
- Q3: Codex is the first verified plugin invocation host. The contract remains portable; invocation on other hosts is explicitly unqualified or unavailable until verified. Existing core installation support remains unchanged.
- Q4: Recommendations prioritize demonstrated task/review quality improvement, with explicit time/cost reporting and limitations; adoption alone supplies no outcome evidence.
- Q10: Recommended bundles require bounded comparison evidence in the target workflow. Untested or compatibility-only candidates remain manually selectable with explicit evidence status; no eligible candidate produces an explicit empty recommendation set.
- Decision evidence: `.skill-tree/documents/plugin-workflow-decisions.md`; Q1-Q11 have actual owner approval. Final shared-understanding confirmation remains separate.

### Implement the workflow-grouped catalog and evidence-backed bundles

```yaml
id: T-ea3d73b4-c312-4de9-9897-c97f380e4516
priority: 112
status: Ready
parent_pending_ids: ["P-336855cb-5271-40b9-a142-95ed6102889b"]
processing_run_id: PR-e41ce0ec-099e-4072-ace9-59e7acb2ec45
root_task_id: T-ea3d73b4-c312-4de9-9897-c97f380e4516
related_task_id: null
relation: main
depends_on: ["T-a583acd5-fc6b-4d37-97ec-02df969fea9e", "T-6f4500f7-91e2-410d-8172-a4c4cd232fc5"]
```

Goal:
- Implement the curated marketplace-style catalog and recommended/alternative bundles using the agreed plugin contract and research results.

Touch:
- `.skill-tree/config/plugin-catalog.json`
- `.skill-tree/lib/plugin-catalog.js`
- `.skill-tree/bin/install.js`
- `.skill-tree/tests/test-plugin-catalog.js`
- `.skill-tree/documents/plugin-recommendation-evidence.md`
- `.skill-tree/documents/plugin-system-contract.md`

Implementation constraints:
- A separate hosted marketplace is outside the established scope; a material delivery change requires owner discussion.
- Preserve source attribution and external licenses; recommendations retain provenance, freshness and explicit compatibility/evidence status.

Validation:
- Strategy: test-first focused behavioral regressions.
```json
{
  "checks": [
    {
      "id": "catalog-regressions",
      "recipe_id": "quality-node",
      "criteria": [
        "The canonical curated catalog lists every catalog entry grouped by agreed workflow integration points, with stable identity, source/revision, dependencies and host/flavor compatibility; available entries remain distinct from installed-registry views.",
        "Recommended bundles contain only candidates with bounded target-workflow comparison evidence; empty eligible sets are valid, and compatibility-only or unqualified candidates retain explicit status in manual selection.",
        "Deterministic listing/filtering and metadata validation reject unknown hooks, conflicting identity or unresolved recommendation dependencies and preserve a non-hosted project-local delivery."
      ],
      "sources": [
        ".skill-tree/config/plugin-catalog.json",
        ".skill-tree/lib/plugin-catalog.js",
        ".skill-tree/bin/install.js",
        ".skill-tree/tests/test-plugin-catalog.js",
        ".skill-tree/documents/plugin-recommendation-evidence.md",
        ".skill-tree/documents/plugin-system-contract.md"
      ],
      "parameters": {
        "test_path": ".skill-tree/tests/test-plugin-catalog.js"
      },
      "assertion": "The canonical curated catalog lists every catalog entry grouped by agreed workflow integration points, with stable identity, source/revision, dependencies and host/flavor compatibility; available entries remain distinct from installed-registry views. Recommended bundles contain only candidates with bounded target-workflow comparison evidence; empty eligible sets are valid, and compatibility-only or unqualified candidates retain explicit status in manual selection. Deterministic listing/filtering and metadata validation reject unknown hooks, conflicting identity or unresolved recommendation dependencies and preserve a non-hosted project-local delivery.",
      "timing": "immediate"
    }
  ]
}
```

Acceptance:
- The canonical curated catalog lists every catalog entry grouped by agreed workflow integration points, with stable identity, source/revision, dependencies and host/flavor compatibility; available entries remain distinct from installed-registry views.
- Recommended bundles contain only candidates with bounded target-workflow comparison evidence; empty eligible sets are valid, and compatibility-only or unqualified candidates retain explicit status in manual selection.
- Deterministic listing/filtering and metadata validation reject unknown hooks, conflicting identity or unresolved recommendation dependencies and preserve a non-hosted project-local delivery.


Approved clarification decisions:
- Q3: Codex is the first verified plugin invocation host. The contract remains portable; invocation on other hosts is explicitly unqualified or unavailable until verified. Existing core installation support remains unchanged.
- Q4: Recommendations prioritize demonstrated task/review quality improvement, with explicit time/cost reporting and limitations; adoption alone supplies no outcome evidence.
- Q10: Recommended bundles require bounded comparison evidence in the target workflow. Untested or compatibility-only candidates remain manually selectable with explicit evidence status; no eligible candidate produces an explicit empty recommendation set.
- Decision evidence: `.skill-tree/documents/plugin-workflow-decisions.md`; Q1-Q11 have actual owner approval. Final shared-understanding confirmation remains separate.

### Implement confirmed recommended and alternative plugin installation

```yaml
id: T-6ec57615-3512-4f91-98e8-efb12cde7d7f
priority: 110
status: Ready
parent_pending_ids: ["P-14584d76-6e8b-418a-b04b-8de586f10f0a"]
processing_run_id: PR-e41ce0ec-099e-4072-ace9-59e7acb2ec45
root_task_id: T-6ec57615-3512-4f91-98e8-efb12cde7d7f
related_task_id: null
relation: main
depends_on: ["T-2da07d09-0b1a-4407-b375-defd23720387", "T-ea3d73b4-c312-4de9-9897-c97f380e4516", "T-dae414c5-43e4-45db-a6f3-4ce4112440c5", "T-10528edd-4542-4c26-b8b3-738ffc00d791"]
```

Goal:
- Wire the grouped catalog, confirmed plugin acquisition and owned lifecycle into the existing installer according to the agreed interaction contract.

Touch:
- `.skill-tree/bin/install.js`
- `.skill-tree/lib/installation.js`
- `.skill-tree/lib/plugin-catalog.js`
- `.skill-tree/tests/test-plugin-installer.js`
- `.skill-tree/documents/plugin-installation-contract.md`
- `.skill-tree/documents/install.md`

Implementation constraints:
- Plugin installation never executes the selected skills or grants new workflow-stage/publication permission.
- Use existing provider destinations and ownership/transaction barriers; record truthful provider results and preserve unrelated files.

Validation:
- Strategy: test-first focused behavioral regressions.
```json
{
  "checks": [
    {
      "id": "plugin-installer-regressions",
      "recipe_id": "quality-node",
      "criteria": [
        "The installation flow presents exact recommended versions, hook locations, enabled state and readiness effects with actual install, skip or choose-other-plugin actions once per project; confirmation installs and enables exactly the displayed configuration.",
        "Choose-other lists the full available catalog grouped by integration points and installs only the confirmed compatible selection; skip preserves core-only behavior.",
        "Noninteractive, repeat, dry-run, provider-partial-failure and interrupted/rollback cases follow the agreed policy without hidden network, helper execution or inferred consent.",
        "An empty eligible recommendation set supports explicit manual selection or core-only skip; successful installation links to the installed registry and documented exact-ID removal command."
      ],
      "sources": [
        ".skill-tree/bin/install.js",
        ".skill-tree/lib/installation.js",
        ".skill-tree/lib/plugin-catalog.js",
        ".skill-tree/tests/test-plugin-installer.js",
        ".skill-tree/documents/plugin-installation-contract.md",
        ".skill-tree/documents/install.md"
      ],
      "parameters": {
        "test_path": ".skill-tree/tests/test-plugin-installer.js"
      },
      "assertion": "The installation flow presents exact recommended versions, hook locations, enabled state and readiness effects with actual install, skip or choose-other-plugin actions once per project; confirmation installs and enables exactly the displayed configuration. Choose-other lists the full available catalog grouped by integration points and installs only the confirmed compatible selection; skip preserves core-only behavior. Noninteractive, repeat, dry-run, provider-partial-failure and interrupted/rollback cases follow the agreed policy without hidden network, helper execution or inferred consent. An empty eligible recommendation set supports explicit manual selection or core-only skip; successful installation links to the installed registry and documented exact-ID removal command.",
      "timing": "immediate"
    }
  ]
}
```

Acceptance:
- The installation flow presents exact recommended versions, hook locations, enabled state and readiness effects with actual install, skip or choose-other-plugin actions once per project; confirmation installs and enables exactly the displayed configuration.
- Choose-other lists the full available catalog grouped by integration points and installs only the confirmed compatible selection; skip preserves core-only behavior.
- Noninteractive, repeat, dry-run, provider-partial-failure and interrupted/rollback cases follow the agreed policy without hidden network, helper execution or inferred consent.
- An empty eligible recommendation set supports explicit manual selection or core-only skip; successful installation links to the installed registry and documented exact-ID removal command.


Approved clarification decisions:
- Q3: Codex is the first verified plugin invocation host. The contract remains portable; invocation on other hosts is explicitly unqualified or unavailable until verified. Existing core installation support remains unchanged.
- Q4: Recommendations prioritize demonstrated task/review quality improvement, with explicit time/cost reporting and limitations; adoption alone supplies no outcome evidence.
- Q9: Project defaults permit explicit temporary per-run overrides. The effective configuration is recorded and frozen across resume; persistent edits are explicit and never silently satisfy or replace parked-run obligations.
- Q10: Recommended bundles require bounded comparison evidence in the target workflow. Untested or compatibility-only candidates remain manually selectable with explicit evidence status; no eligible candidate produces an explicit empty recommendation set.
- Q11: The installation proposal displays exact versions, hook locations, enabled state and readiness effects. Actual confirmation installs and enables exactly the displayed configuration; skill execution occurs later in authorized workflows.
- Decision evidence: `.skill-tree/documents/plugin-workflow-decisions.md`; Q1-Q11 have actual owner approval. Final shared-understanding confirmation remains separate.

## Backlog
