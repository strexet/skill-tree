# Future Work

## Pending Task Format

Fixed metadata records task identity and dependency scope.

## Pending Queue

## Prioritized Next Changes

### U-02 Relocate owned source and target paths

```yaml
id: T-69b96cac-72c3-4a69-9969-9775ea457877
priority: 107
status: Ready
parent_pending_ids: ["P-d5ffb35c-ee83-4ba6-9f6b-89f647b869b8"]
processing_run_id: PR-7e6c556f-e261-441b-bd21-caf2f656050d
root_task_id: T-69b96cac-72c3-4a69-9969-9775ea457877
related_task_id: null
relation: main
depends_on: ["T-257487e7-a192-4b6a-a2bf-634106432f67"]
```

Goal:
- All owned paths use .skill-tree while provider discovery locations retain required names.

Current behavior:
- The baseline uses thirteen source skills and the existing workflow schema.

Desired behavior:
- All owned paths use .skill-tree while provider discovery locations retain required names.

Touch:
- Source contracts, helpers, installer, fixtures and current documentation as required by the selected unit.

Discovery allowance:
- The selected unit follows the approved redesign scope.

Out of scope:
- Live target installation, publication, Unity execution and existing target migration.

Implementation constraints:
- The selected unit follows the approved redesign scope.

Questions and required clarifications:
- [Resolved - owner request] The approved plan authorizes implementation and intermediate local commits.

Validation:
- Run relevant static and temporary-fixture checks with operation deadlines.

Acceptance:
- All owned paths use .skill-tree while provider discovery locations retain required names.

Documentation updates:
- Update current contracts and implementation status.

Risks:
- Preserve exact task identities, ownership and unrelated content.

### U-03 Compose project-specialized packages

```yaml
id: T-25e8ef8b-6545-4c82-ab91-f1e8bd28605f
priority: 106
status: Ready
parent_pending_ids: ["P-d5ffb35c-ee83-4ba6-9f6b-89f647b869b8"]
processing_run_id: PR-7e6c556f-e261-441b-bd21-caf2f656050d
root_task_id: T-25e8ef8b-6545-4c82-ab91-f1e8bd28605f
related_task_id: null
relation: main
depends_on: ["T-69b96cac-72c3-4a69-9969-9775ea457877"]
```

Goal:
- Deterministic standalone packages implement eight operations for general, web and unity profiles.

Current behavior:
- The baseline uses thirteen source skills and the existing workflow schema.

Desired behavior:
- Deterministic standalone packages implement eight operations for general, web and unity profiles.

Touch:
- Source contracts, helpers, installer, fixtures and current documentation as required by the selected unit.

Discovery allowance:
- The selected unit follows the approved redesign scope.

Out of scope:
- Live target installation, publication, Unity execution and existing target migration.

Implementation constraints:
- The selected unit follows the approved redesign scope.

Questions and required clarifications:
- [Resolved - owner request] The approved plan authorizes implementation and intermediate local commits.

Validation:
- Run relevant static and temporary-fixture checks with operation deadlines.

Acceptance:
- Deterministic standalone packages implement eight operations for general, web and unity profiles.

Documentation updates:
- Update current contracts and implementation status.

Risks:
- Preserve exact task identities, ownership and unrelated content.

### U-04 Install and maintain owned project packages

```yaml
id: T-9bada49a-808a-48c5-a5da-ed44b71f00df
priority: 105
status: Ready
parent_pending_ids: ["P-d5ffb35c-ee83-4ba6-9f6b-89f647b869b8"]
processing_run_id: PR-7e6c556f-e261-441b-bd21-caf2f656050d
root_task_id: T-9bada49a-808a-48c5-a5da-ed44b71f00df
related_task_id: null
relation: main
depends_on: ["T-25e8ef8b-6545-4c82-ab91-f1e8bd28605f"]
```

Goal:
- Receipts, static profile refresh, ownership conflicts and recovery work without source access.

Current behavior:
- The baseline uses thirteen source skills and the existing workflow schema.

Desired behavior:
- Receipts, static profile refresh, ownership conflicts and recovery work without source access.

Touch:
- Source contracts, helpers, installer, fixtures and current documentation as required by the selected unit.

Discovery allowance:
- The selected unit follows the approved redesign scope.

Out of scope:
- Live target installation, publication, Unity execution and existing target migration.

Implementation constraints:
- The selected unit follows the approved redesign scope.

Questions and required clarifications:
- [Resolved - owner request] The approved plan authorizes implementation and intermediate local commits.

Validation:
- Run relevant static and temporary-fixture checks with operation deadlines.

Acceptance:
- Receipts, static profile refresh, ownership conflicts and recovery work without source access.

Documentation updates:
- Update current contracts and implementation status.

Risks:
- Preserve exact task identities, ownership and unrelated content.

### U-05 Persist task progress and validation groups

```yaml
id: T-98e59352-ec61-46da-bb16-73754fb836fc
priority: 104
status: Ready
parent_pending_ids: ["P-d5ffb35c-ee83-4ba6-9f6b-89f647b869b8"]
processing_run_id: PR-7e6c556f-e261-441b-bd21-caf2f656050d
root_task_id: T-98e59352-ec61-46da-bb16-73754fb836fc
related_task_id: null
relation: main
depends_on: ["T-9bada49a-808a-48c5-a5da-ed44b71f00df"]
```

Goal:
- Profile admission, immediate checks, bounded groups and stale evidence prevent premature completion.

Current behavior:
- The baseline uses thirteen source skills and the existing workflow schema.

Desired behavior:
- Profile admission, immediate checks, bounded groups and stale evidence prevent premature completion.

Touch:
- Source contracts, helpers, installer, fixtures and current documentation as required by the selected unit.

Discovery allowance:
- The selected unit follows the approved redesign scope.

Out of scope:
- Live target installation, publication, Unity execution and existing target migration.

Implementation constraints:
- The selected unit follows the approved redesign scope.

Questions and required clarifications:
- [Resolved - owner request] The approved plan authorizes implementation and intermediate local commits.

Validation:
- Run relevant static and temporary-fixture checks with operation deadlines.

Acceptance:
- Profile admission, immediate checks, bounded groups and stale evidence prevent premature completion.

Documentation updates:
- Update current contracts and implementation status.

Risks:
- Preserve exact task identities, ownership and unrelated content.

### U-06 Qualify Unity domain contracts

```yaml
id: T-0277c075-52e4-41a3-8f7b-ab79bd7bf019
priority: 103
status: Ready
parent_pending_ids: ["P-d5ffb35c-ee83-4ba6-9f6b-89f647b869b8"]
processing_run_id: PR-7e6c556f-e261-441b-bd21-caf2f656050d
root_task_id: T-0277c075-52e4-41a3-8f7b-ab79bd7bf019
related_task_id: null
relation: main
depends_on: ["T-98e59352-ec61-46da-bb16-73754fb836fc"]
```

Goal:
- Concrete pinned Unity recipes preserve EditMode-first feedback, lifecycle isolation and platform evidence limits.

Current behavior:
- The baseline uses thirteen source skills and the existing workflow schema.

Desired behavior:
- Concrete pinned Unity recipes preserve EditMode-first feedback, lifecycle isolation and platform evidence limits.

Touch:
- Source contracts, helpers, installer, fixtures and current documentation as required by the selected unit.

Discovery allowance:
- The selected unit follows the approved redesign scope.

Out of scope:
- Live target installation, publication, Unity execution and existing target migration.

Implementation constraints:
- The selected unit follows the approved redesign scope.

Questions and required clarifications:
- [Resolved - owner request] The approved plan authorizes implementation and intermediate local commits.

Validation:
- Run relevant static and temporary-fixture checks with operation deadlines.

Acceptance:
- Concrete pinned Unity recipes preserve EditMode-first feedback, lifecycle isolation and platform evidence limits.

Documentation updates:
- Update current contracts and implementation status.

Risks:
- Preserve exact task identities, ownership and unrelated content.

### U-07 Qualify Web domain contracts

```yaml
id: T-2a154c49-75e0-4b67-b564-ea65b0291f8b
priority: 102
status: Ready
parent_pending_ids: ["P-d5ffb35c-ee83-4ba6-9f6b-89f647b869b8"]
processing_run_id: PR-7e6c556f-e261-441b-bd21-caf2f656050d
root_task_id: T-2a154c49-75e0-4b67-b564-ea65b0291f8b
related_task_id: null
relation: main
depends_on: ["T-98e59352-ec61-46da-bb16-73754fb836fc"]
```

Goal:
- Concrete Web recipes distinguish unit, API, browser, accessibility and deployment assertions.

Current behavior:
- The baseline uses thirteen source skills and the existing workflow schema.

Desired behavior:
- Concrete Web recipes distinguish unit, API, browser, accessibility and deployment assertions.

Touch:
- Source contracts, helpers, installer, fixtures and current documentation as required by the selected unit.

Discovery allowance:
- The selected unit follows the approved redesign scope.

Out of scope:
- Live target installation, publication, Unity execution and existing target migration.

Implementation constraints:
- The selected unit follows the approved redesign scope.

Questions and required clarifications:
- [Resolved - owner request] The approved plan authorizes implementation and intermediate local commits.

Validation:
- Run relevant static and temporary-fixture checks with operation deadlines.

Acceptance:
- Concrete Web recipes distinguish unit, API, browser, accessibility and deployment assertions.

Documentation updates:
- Update current contracts and implementation status.

Risks:
- Preserve exact task identities, ownership and unrelated content.

### U-08 Qualify the redesigned source workflow

```yaml
id: T-bae05f34-57a2-4bbe-9a3f-07f835d4e3c1
priority: 101
status: Ready
parent_pending_ids: ["P-d5ffb35c-ee83-4ba6-9f6b-89f647b869b8"]
processing_run_id: PR-7e6c556f-e261-441b-bd21-caf2f656050d
root_task_id: T-bae05f34-57a2-4bbe-9a3f-07f835d4e3c1
related_task_id: null
relation: main
depends_on: ["T-0277c075-52e4-41a3-8f7b-ab79bd7bf019", "T-2a154c49-75e0-4b67-b564-ea65b0291f8b"]
```

Goal:
- Controllers, installation and documentation pass source fixtures without product execution.

Current behavior:
- The baseline uses thirteen source skills and the existing workflow schema.

Desired behavior:
- Controllers, installation and documentation pass source fixtures without product execution.

Touch:
- Source contracts, helpers, installer, fixtures and current documentation as required by the selected unit.

Discovery allowance:
- The selected unit follows the approved redesign scope.

Out of scope:
- Live target installation, publication, Unity execution and existing target migration.

Implementation constraints:
- The selected unit follows the approved redesign scope.

Questions and required clarifications:
- [Resolved - owner request] The approved plan authorizes implementation and intermediate local commits.

Validation:
- Run relevant static and temporary-fixture checks with operation deadlines.

Acceptance:
- Controllers, installation and documentation pass source fixtures without product execution.

Documentation updates:
- Update current contracts and implementation status.

Risks:
- Preserve exact task identities, ownership and unrelated content.

## Backlog
