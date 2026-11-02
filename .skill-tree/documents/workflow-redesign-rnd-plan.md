# Skill Tree Layout, Installation and Validation RND Plan

## Status and scope

Date: 2026-11-02. Status: approved implementation in progress; intermediate local commits are authorized.

The approved source implementation follows units U-01 through U-08. The implementation checkpoint preserves unit identities and required dependencies. Target migration, live installation and publication remain separate owner actions.

The requested outcomes are:

- Move the owned source and target-project directory from `.skill-tree/` to `.skill-tree/`.
- Install one selected Skill Tree flavor: `general`, `web` or `unity`.
- Compose the common contracts and the selected domain contracts during installation.
- Resolve stable project capabilities and version compatibility during installation; emit only applicable final instructions and refresh the profile after relevant environment changes.
- Require a concrete justification for application launches, with related checks collected at explicit group boundaries.
- Mark changes requiring runtime or visual validation explicitly and preserve pending verification across interruptions.
- Prefer testable Unity code and EditMode coverage; use PlayMode, Player and visual checks for suitable assertions.
- Make Red-Green-Refactor the default for suitable behavior changes and bug fixes, with explicit test validity, refactoring safety and fast feedback.
- Keep the common workflow consistent while expressing substantive Unity and Web differences.
- Provide a short manual update checklist for the single existing target repository. Automatic migration and legacy compatibility are excluded.

## Research evidence and limits

The inspected source baseline is commit `e844861`. Research covers all thirteen skill entry points, canonical workflow/safety/documentation contracts, the workflow-state helper, installation and resource generation, validators, provider configuration and behavioral tests.

Recorded source-baseline verification: synchronization, strict repository validation, 79 Python tests, 24 Node tests, installer listing and installer dry-run pass during the initial research. Tests use temporary repositories and installation destinations. Two additional installer controls use temporary directories and leave no installed packages. Document consistency review does not establish a new product-runtime qualification.

No Unity Editor, game UI, application server, browser qualification, Player build, device or external product service runs during research. Source contracts establish a validation-policy gap; source contracts alone cannot establish the frequency or justification of launches performed by agents in other repositories. Agent execution traces and actual launch-cost measurements remain uninspected.

## Confirmed findings

| ID | Priority | Evidence | Finding and consequence |
| --- | --- | --- | --- |
| F-01 | High | [Future workflow](../common/references/future-workflow.md), [Unity safety](../common/references/unity-safety.md) | Validation has authorization and evidence boundaries, but no explicit selection rule for the smallest sufficient check, application-launch rationale or group boundary. An agent has no common decision contract for choosing a focused test instead of a full product flow. |
| F-02 | High | [Workflow state](../common/scripts/workflow-state.py), `complete`, `next_task`, `finish` | Completion requires every acceptance criterion to pass before task removal; dependency scheduling recognizes terminal completion. No implemented-but-awaiting-verification state or validation-group entity exists. Adding a delayed-test flag alone creates premature completion or scheduling deadlock. |
| F-03 | High | [Installer](../bin/install.js), `selectedSkills`, `parseArgs`, `main` | Installation selects every available skill when no skill list is supplied. General and Unity variants coexist by default; no domain-flavor question or common/domain composition exists. Domain choice falls back to agent skill selection after installation. |
| F-04 | High | [Installer](../bin/install.js), `copyDir`, `symlinkDir`, `removeDir` | Replacement and uninstall check the destination type/name without checking an ownership receipt. A temporary-directory control confirms that `--force` deletes unowned content inside a same-name package directory. Composition and flavor replacement require stronger ownership handling. |
| F-05 | Medium | [Installer](../bin/install.js), `verifyInstall` | Verification checks entry-point/resource existence rather than package identity, content hashes or composed flavor. A temporary-directory control substitutes an unrelated entry point without references; `--verify` still exits successfully. Verification cannot currently prove the installed validation policy. |
| F-06 | Medium | [Unity safety](../common/references/unity-safety.md), [Unity documentation](repo-init-instructions.md), [Unity implementation entry point](../skills/skill-tree-unity-implement-next-future-task/SKILL.md) | Unity guidance distinguishes evidence and permissions but supplies no UTF lane-selection strategy, testability assessment or criteria for testability-refactoring tasks. Full game interaction remains an available tool without a documented preference for focused executable assertions. |
| F-07 | Medium | [Resource map](../config/resource-map.json), [Skill catalog](../../README.md) | Five Unity variants exist; no Web-specific variant or Web validation contract exists. The current split mainly adds Unity safety/evidence paragraphs instead of defining distinct development/testing workflows. |
| F-08 | Medium | [General audit](../skills/skill-tree-repo-documentation-audit/SKILL.md), [Unity audit](../skills/skill-tree-unity-repo-documentation-audit/SKILL.md) | The general audit entry point explicitly requires the metadata consistency validator and scoped prose diagnostics; the Unity audit entry point omits the explicit check step despite bundling the validator. Hand-maintained variants already exhibit instruction drift. |
| F-09 | Medium | [Workflow store](../common/scripts/workflow-state.py), [Metadata validator](../common/scripts/validate-repository-documentation.py), [Snapshot helper](../common/scripts/create-documentation-snapshot.py), [Root launcher](../../install.sh), [Package manifest](../../package.json) | Owned paths are hard-coded across source and installed helpers, transactions, history, snapshots, launchers and validation. A directory rename alone leaves broken commands and incompatible ownership checks. |
| F-10 | Low | [Future workflow](../common/references/future-workflow.md), [Workflow parser](../common/scripts/workflow-state.py), `SECTIONS`, `parse` | Guidance discourages boilerplate, but the parser requires thirteen named sections for every prioritized task. Small tasks receive the same structural burden as larger tasks; validation intent remains unstructured inside the required prose. |

No finding demonstrates unauthorized launches in an external project. F-01 and F-06 identify missing decision guidance rather than evidence of misconduct.

## Target architecture

### Design invariants and minimum scope

- One installation receipt owns resolved project facts and concrete recipes; task definitions own required acceptance/checks; the active checkpoint owns execution progress. Documentation links to the relevant owner instead of independently redefining the same data.
- Installation and refresh resolve stable compatibility. Task work still selects meaningful assertions and obeys current owner rules. No version question or generic stack-discovery tree runs inside the model's repeated test loop.
- Focused TDD checks run promptly. Grouping delays only compatible additional boundary checks; ordinary verified dependencies keep the existing meaning.
- The first implementation supports project-scoped copy installation for one explicitly selected project root, with a maintenance command included locally. Existing provider features receive regression coverage, but new watcher services, automatic refresh, global specialization and cross-project scheduling are outside the initial scope.
- Optional advanced practices remain focused references and conditional deliverables. Installed entry points contain a short relevant workflow, rather than the research tables, bibliography or every possible quality technique.

### Source families and installed flavors

The source architecture has three conceptual families: `common-skill-tree`, `web-skill-tree` and `unity-skill-tree`. The installer exposes the more familiar flavor names `general`, `web` and `unity`.

| Flavor | Composition | Resulting guidance |
| --- | --- | --- |
| `general` | Common workflow plus platform-neutral defaults | Source research, task/dependency orchestration, validation selection, group gates, evidence and repository-discovered tools. No Unity or Web assumptions. |
| `web` | Common workflow plus Web domain sections/resources | Browser/server boundaries, component/API tests, browser rendering, accessibility, storage, network and deployment distinctions. |
| `unity` | Common workflow plus Unity domain sections/resources | Unity compilation, UTF lanes, lifecycle/frame behavior, serialized identity, isolated persistence, native/platform qualification and Editor ownership. |

Recommended source layout:

```text
.skill-tree/
  common/                       # common-skill-tree canonical contracts/helpers
  domains/
    general/                    # optional platform-neutral additions
    web/                        # web-skill-tree sections/resources
    unity/                      # unity-skill-tree sections/resources
  templates/                    # entry-point section slots and UI metadata
  skills/                       # representative generated source packages
    general/<skill-name>/
    web/<skill-name>/
    unity/<skill-name>/
  config/
    flavors.json                # flavor registry and composition recipes
    capabilities.json           # versioned compatibility rules and probes
    providers.json              # provider destinations and discovery
    resource-map.json           # deterministic resource ownership
  scripts/
  bin/
  adapters/
  src/init-rules/
  tests/
  documents/
  history/
  artifacts/                    # ignored large evidence
```

Target repositories contain `.skill-tree/documents/`, manifests, active state, history and `.skill-tree/installation/`. The installation directory contains the generated profile/receipt and a self-contained maintenance bundle for the selected flavor. Generated staging/backups use ignored owned paths; no profile cross-product is committed. Provider discovery still uses provider-required locations such as `.agents/skills/`; `.skill-tree/` does not replace provider discovery directories. Root `README.md`, `AGENTS.md`, launchers, license and package manifests retain required locations/names. Source-versus-target role is explicit metadata, not inferred from a staging directory named `skills`.

The logical catalog retains the eight current general operations: documentation initialization, documentation audit, snapshot, intake, processing, single-task implementation, Work Through Next and Implement All. Every installed operation carries the selected flavor, including controllers and audit. Specialized duplicate entry points disappear from the installed default catalog; internal source modules remain distinct.

One repository receives one selected flavor and project root for a given installation scope. The final installed skill names retain the existing general `skill-tree-*` operation names, with flavor in description, UI metadata and the installation receipt. Source families do not require three competing installed command prefixes. A monorepo installation explicitly selects the covered root; work in another root requires a matching installation scope. General never supplies Unity/Web runtime qualification or weakens repository safety rules. Automatic mixed-flavor routing and colliding installations at the same provider destination are unsupported initially.

### Deterministic composition

Composition merges authored structured sections and resources, rather than concatenating complete Markdown files or asking a model to reconcile instructions.

1. Resolve a versioned flavor recipe and selected operation IDs; inspect the target once to produce a concrete capability profile.
2. Load common mandatory sections, operation-specific sections and the selected domain/capability slots. Evaluate compatibility predicates in the composer and eliminate inactive branches.
3. Extend declared slots such as discovery, implementation constraints, validation selection and evidence requirements. Permit replacement only for explicitly declared replaceable slots.
4. Preserve non-replaceable shared invariants: owner authorization, exact selection, checkpoint integrity, evidence truthfulness, scope boundaries and commit/publication boundaries. Domain additions can tighten constraints; domain additions cannot silently relax shared constraints or repository-owner rules.
5. Resolve resource destinations from an explicit map. Identical-content duplicates deduplicate; conflicting content at the same destination fails unless the recipe declares the exact replacement.
6. Render one frontmatter block, one entry point, concrete applicable references/scripts and matching UI metadata. Validate every link, resource and allowed name. Final entry points and references contain no generic version-discovery or alternative-framework decision tree.
7. Record composer version, flavor, capability-profile identity, project input digests, source/recipe digests and generated output digests. Identical inputs produce identical output bytes; operation timestamps remain outside generated content hashes.

The installer composes packages in isolated staging using the same deterministic builder as source generation. Representative generated packages support review; temporary profile fixtures cover relevant compatibility combinations without maintaining every possible generated variant. Installation never runs generated workflow helpers or application code. Installed packages require no source checkout, sibling skill or runtime layer merge. A standalone controller includes the selected flavor's leaf contracts/helpers and loads detailed references progressively.

New domain flavors extend the registry, documented slots and contract tests. New flavors do not require copying the common workflow or adding domain conditionals throughout shared orchestration.

### Installation-time project specialization

Stable environment decisions belong to installation and profile refresh. Task-specific decisions such as the changed behavior, useful test cases, launch justification and current authorization remain part of task execution. An installer cannot precompute acceptance for future changes.

| Scope | Static installation evidence | Compiled result |
| --- | --- | --- |
| Unity | Exact project roots, `ProjectVersion.txt`, package manifest/lock, UTF/Input System/performance packages, test assemblies, UI framework usage and existing runner/profile configuration | Concrete compatible Unity/UTF recipes, relevant input/UI fixtures, existing harness paths and explicit unavailable lanes. |
| Web | Actual framework/runtime/package-manager versions, dependency locks, test scripts/configuration, component/browser runners, rendering mode, browser policy and existing server/build recipes | Concrete commands and references for the installed stack; applicable component/API/browser checks and support policy. |
| General | Actual languages, compiler/test/lint tools, owned project roots and existing validation commands | Project-specific test/static-check recipes without importing unrelated platform assumptions. |

The capability resolver uses versioned, inspectable compatibility rules with supporting documentation. Probe results have known, absent, ambiguous or unsupported states. A package declaration alone does not establish an exact resolved version or a working runner. Conflicting locks, an unresolved project root or an unknown required version produce one installation-time question or a clear noninteractive error. Prefer declared scripts and owned configuration; unsupported executable configuration needs an explicit static recipe rather than guessed commands.

Discovery reads source/configuration as data. Installation does not evaluate arbitrary project configuration code or launch an Editor, compiler, application server or project test suite. Static compatibility and executed runner qualification remain distinct. Missing tests, documentation or an optional test package do not prevent installing the flavor: emit the concrete available workflow, a truthful capability gap and the relevant setup guidance. A task needing an unavailable mandatory check remains validation-blocked until scoped setup or another accepted check resolves the gap. Installation fails only when the selected root, safe composition or essential format compatibility cannot be established; missing test infrastructure must not prevent installing the tools needed to organize setup.

### Missing foundational test framework

A missing suitable foundational test framework requires a concrete setup task, not merely a reported limitation. At the post-install handoff, use normal Add Pending to create or reuse one task for the covered project root. Assign very high priority: the highest open task priority plus one, unless an explicit developer priority instruction takes precedence. Research and promotion still follow Process Pending; Pending priority never authorizes queue-only implementation.

The task covers selection when necessary, compatible installation/configuration, one meaningful executable smoke test, documented focused commands and profile refresh. Research existing project conventions, pinned toolchain compatibility, required test lanes, maintenance and iteration cost. Recommend a concrete framework with a short rationale and alternatives only when a material choice remains; ask the developer only for an unresolved consequential choice. Reuse/configure a suitable existing framework rather than installing another framework solely because tests or a test assembly are missing.

The installer preserves the finding in the installation receipt without running workflow helpers. An initialized target materializes the task during the normal post-install intake; a target without a queue retains the finding until explicitly requested documentation setup creates the queue, then captures the task before implementation selection. Return the Pending ID after capture. Reinstallation/refresh deduplicates the same unresolved foundation gap instead of generating repeated tasks. Missing optional mutation, property-testing or specialized UI packages do not automatically create top-priority work.

When selected behavior cannot be accepted without the foundation, link the researched setup task as a required dependency through the existing intake/process/controller flow. Documentation and other independently verifiable work remain eligible. The setup task supplies no implicit package-upgrade, Editor, Player/device or external-service authorization. No target setup task is created during the current plan-only work.

### Examples of resulting packages

- Unity 6.0 with uGUI and UTF: the installed references contain the concrete existing UTF/uGUI workflow; UI Toolkit 6.3-only guidance is absent.
- A compatible Unity UI Toolkit project with the UI testing package: the installed references include the supported panel simulation recipe, without asking the agent to rediscover the Editor version during every task.
- A Web project with an existing component runner and browser suite: emitted commands use the detected package manager, configuration paths and installed runner; alternative-runner setup instructions are absent.
- A General project with a Python harness: the package exposes the actual scoped commands; JavaScript and Unity test setup branches are absent.

The same specialization rule applies to package-specific async conventions, persistence adapters, DI, asset loading, accessibility tools, mutation/property testing and performance tools. Source research tables describe available practices; a compiled target package contains only the selected project-relevant instructions. Missing future capability becomes a concrete setup decision followed by profile refresh, rather than a repeated capability questionnaire.

### Profile freshness and dependency upgrades

The installation receipt at `.skill-tree/installation/profile.json` owns resolved facts, concrete recipe IDs, source/input/output digests and owned provider destinations. Human documentation links to the generated summary. Separate Skill Tree recipe identity, target environment identity and emitted package identity: unchanged generated bytes do not establish current runtime qualification.

The profile records the bounded input set used for specialization: Editor version, dependency declarations/locks, relevant runner/UI/assembly configuration, commands, browser/build policy and referenced validation profiles. Include absent optional paths and configuration-file inventories to detect added capabilities. A known upgrade/setup operation marks the profile dirty. The first implementation uses input-digest checks at invocation/resume; no background watcher or whole-repository scan is required.

Use the following lifecycle:

```text
installed/current
    -> relevant input change -> refresh-required
    -> inspect and compose in staging -> review/verify delta
    -> activate new profile -> installed/current
```

The installer includes a self-contained maintenance bundle at `.skill-tree/installation/manager.js`, with the composer and selected flavor's source modules/compatibility rules. The manager locates the target from the bundle location and validates receipt ownership; caller working directory never selects a different repository implicitly. Installation into a target never assumes the source repository's `.skill-tree/bin/install.js` exists locally. The proposed local refresh reuses recorded selections, repeats static discovery and displays changed facts, instructions, commands and qualification gaps:

```sh
node .skill-tree/installation/manager.js --refresh-profile --dry-run
node .skill-tree/installation/manager.js --refresh-profile
```

Profile refresh has the following behavior:

1. Detect changed inputs and reject unsupported/ambiguous combinations before replacing any package. Never upgrade project dependencies to satisfy a recipe. A new version unsupported by bundled rules needs an explicit Skill Tree source/bundle update; do not silently fetch network content.
2. Stage the complete new generation and validate ownership, composition, references and content digests. Local modifications produce a reviewable conflict. Use the new recoverable installation transaction specified in U-04; the current installer has no such transaction.
3. If emitted packages remain identical, record a verified no-op package refresh with the new environment fingerprint. Each check declares relevant source, recipe and environment inputs; invalidate only affected results. An unrelated lockfile change does not automatically invalidate every task, while unknown impact invalidates the affected lane conservatively.
4. If instructions or commands change, activate the verified owned generation together with the matching receipt/bridge pointers. Report exact changes and outstanding qualification; installation performs no product execution.
5. Preserve task IDs, acceptance, grouping and checkpoint progress. Keep task check IDs stable; resolve the corresponding recipe against the new profile. Removed/incompatible recipes leave explicit validation-blocked obligations until the task's validation plan is reviewed. Never replace a required check with a weaker alternative.
6. A failed refresh leaves the previous generation intact but stale. A reviewed rollback restores the package/receipt generation only; project dependency rollback is a separate action. Matching old project inputs can restore profile compatibility, while current source/evidence requirements still apply.

Freshness checking belongs to deterministic helper admission, outside the model's repeated reasoning loop. Top-level Implement Next, Work Through Next and Implement All compare relevant input digests once, then pin the profile identity in the current controller/checkpoint. Nested calls and Red/Green iterations reuse the admission result without a separate token protocol. Resume repeats admission; an upgrade performed within the flow ends the current admission. Read-only inspection, intake and maintenance remain available when implementation admission is blocked. A stale profile causes one actionable refresh result, not repeated model-led version discovery.

Profile activation never rewrites instructions during an executed operation. The controller checkpoints and reaches a bounded cleanup/handoff point before replacement. No background refresh daemon or waiting installer is needed. A controller-requested refresh resumes the same authorized flow after reloading changed instructions and re-admitting the profile; a standalone refresh leaves the existing checkpoint stopped. Stored state alone never starts implementation. Preserve standing authorization and task IDs; no unrelated process is terminated and no checkpoint is recreated.

Admission does not replace launch safeguards: verify the actual tool/process identity, exact checkout, authorization and save/service isolation when establishing the execution session. Source/test evidence remains current for each check. Concurrent out-of-band toolchain edits during an admitted session are unsupported; unexpected mismatch stops the affected operation. Invocation/resume checks catch missed changes at the next boundary; continuous mid-session detection is not claimed.

Source upgrades and target-environment upgrades are distinct triggers. A source/bundle update explicitly replaces the selected flavor's maintenance materials and packages under the same ownership checks. Local profile refresh uses the already installed materials. Automatic downloads, refresh watchers and source-update scheduling are outside the initial scope.

Profile refresh updates generated packages and receipts within the supported metadata schema. An incompatible Skill Tree queue/checkpoint schema stops with the manual update checklist; profile refresh contains no migration handler or format converter.

Required lifecycle fixtures cover: Unity 6.0 to 6.3 capability changes; a UTF/Input System package change; a Web runner/framework major change; adding a previously absent tool; changed inputs with identical output; unsupported versions; locally edited packages; an out-of-band change caught at admission; interruption/rollback; and an active run awaiting validation during refresh. Fixture assertions include no compatibility-discovery branches in emitted instructions and no repeated version probes during a focused test loop.

## Installation UX and integrity

### Selection flow

1. Resolve target, provider and scope separately from domain flavor. Existing provider profiles remain provider profiles; the new option uses `--flavor`.
2. A fresh interactive installation asks: `Which Skill Tree set should be installed? General / Web / Unity`. Static repository signals can suggest a choice with a reason; suggestions never submit the answer.
3. Explicit `--flavor general|web|unity` selects the flavor without another question. Noninteractive fresh installation requires the flag and gives a concise usage error when absent. `--yes` never invents a flavor. Selection of a flavor authorizes the ordinary reviewed install plan; no second routine confirmation is required.
4. `--list` reports flavors and logical operations without selection or writes. Dry-run with a specified flavor shows composition, exact destinations, replacement conflicts, bridge edits and policy summary without writes. Missing flavor in noninteractive dry-run produces the same actionable selection error.
5. A repeat installation can retain the recorded flavor without repeated questions. An explicit flavor switch displays the affected owned packages; active controllers must be stopped before replacement. Installation never changes queue semantics during an active operation.
6. Installation resolves the concrete project profile, then reports the selected flavor, detected versions/capabilities, emitted package identities, unavailable lanes, input fingerprints, verification results and the separate documentation-setup command. No Editor, server, browser, package upgrade, full documentation initialization or test execution follows automatically.

Example future source-installer command; the target is explicit:

```sh
node <skill-tree-source>/.skill-tree/bin/install.js --target <target-repository> --only codex --project --flavor unity --copy
```

### Receipts, replacement and recovery

- Add a scoped ownership/composition receipt with package digests, selected flavor, detected capabilities, relevant input digests, schema/composer versions and provider destinations. Keep mutable workflow state separate from install metadata.
- Stage and validate the complete selected package set before changing destinations. Use an install lock, journal/backups and recoverable per-destination replacement; a multi-provider result reports individual success/failure rather than claiming a filesystem-wide atomic operation.
- Existing matching owned packages produce a verified no-op. Existing unknown or locally modified packages cause an explicit conflict; `--force` does not turn an unowned directory into installer-owned content.
- Uninstall removes only receipt-owned matching packages and marker-owned bridge content. Preserve unrelated packages, edits, queues, checkpoints, evidence and generated packages referenced by another installation.
- `--verify` checks flavor, profile freshness, package identity, complete resource inventory, content digests and bridge identity. Existence-only verification is insufficient.
- Copy installation is the required initial path. An existing symlink option must either use a verified stable composed output or report unsupported specialization before writes. Do not build a shared generation-cache service merely to retain symlink mode. Source templates are never exposed as installed runnable packages.
- Project-specialized packages use project scope. A shared global package cannot freeze one target repository's versions for unrelated repositories. Do not add a new portable global flavor or global precedence resolver to the initial implementation. Preserve existing provider behavior where compatible; unsupported specialized/global combinations fail clearly rather than silently installing conflicting packages.
- Remote/upstream installation must receive the composed standalone packages. If an upstream path cannot preserve flavor composition and verification, report the unsupported path and use a supported local install route; never silently install the uncomposed catalog.

## Validation policy

### Selection rule

Every executable task records observable acceptance, affected boundaries and the smallest sufficient validation lane. A launch is justified by a specific unverified assertion, not by task count, code volume, available tools or a routine final checklist.

| Change or assertion | Preferred evidence | Application launch policy |
| --- | --- | --- |
| Documentation, metadata or installer changes | Static checks and temporary repository/package fixtures | No product launch. |
| Pure logic, transformations, rules or state transitions | Existing unit tests; Unity logic normally uses UTF EditMode | No full game/browser flow. Unity EditMode still needs an authorized Editor execution. |
| Several coupled components sharing an integration boundary | Focused integration checks over the combined changes | Collect at a declared group boundary when intermediate work remains safe. |
| Rendered layout, visual states, focus, input or accessibility | Relevant rendered assertions and scoped visual inspection | Flag explicitly and run for the affected surface; one small visual change can justify a launch. |
| Unity frame order, lifecycle, physics or coroutine behavior | Focused UTF PlayMode fixtures | Run before dependent work when the assertion determines a later design decision; otherwise collect at group end. |
| Browser-only behavior, hydration, routing or service-worker lifecycle | Focused browser checks using the correct server/build fixture | Start the required fixture once for the scoped boundary; mocks alone do not prove the integration. |
| AOT/native/platform/runtime difference | Suitable Player, browser-engine or physical-device lane | Use only when the target-specific assertion requires the lane and authorization covers the operation. |

The policy distinguishes two dimensions: process startup and executed validation. Reusing an authorized matching Editor/server session can reduce startup cost, but a cached process is not current test evidence. Cheap appropriate checks remain timely; batching never delays a mandatory safety/security/data-integrity check or a prerequisite assertion.

### Task fields

Optional additions to the existing task header:

```yaml
validation_group_id: VG-<uuid>
boundary_validation: group-end
```

The installation profile supplies flavor and covered project root; ordinary tasks do not repeat the same environment fields. `validation_group_id` is omitted for independent tasks. `boundary_validation` is `not-required`, `group-end` or `before-dependent-work`; omission resolves to `not-required` only after the normal task validation assessment finds no additional boundary obligation.

The flag schedules additional integration/rendering qualification; ordinary unit, EditMode and focused PlayMode TDD tests remain immediate even when the flag is `not-required`. Every actual external execution still obeys authorization and launch safeguards. A task without a useful multi-task group validates directly; no artificial singleton group record is required. Process Pending infers the choice from acceptance without a routine questionnaire; implementation checks actual impact and escalates when necessary. An unresolved mandatory validation decision blocks readiness.

The task's Validation section is the single editable owner of required check IDs, acceptance mapping and task-specific parameters. Reference concrete profile recipe IDs instead of copying commands, version rules and fixture boilerplate. For a boundary check, include the assertion and short reason cheaper evidence is insufficient; detailed authorization/deadline defaults come from the existing execution profile. Small tasks need only acceptance, the scoped check and a concise rationale. UI/runtime changes trigger impact reassessment; file extensions alone cannot settle the decision.

Examples:

- Score calculation plus boundary conditions: focused EditMode coverage; no full game UI walkthrough.
- Independent inventory-screen changes with compatible fixtures: one related group with immediate lower-level tests and combined scoped PlayMode/visual assertions. Verified implementation prerequisites complete earlier; the parent owns the final shared flow.
- A one-line coroutine scheduling fix: an immediate focused PlayMode regression; `before-dependent-work` only for an additional qualification obligation needed before later work.
- A responsive Web navigation change: grouped browser checks at affected widths, keyboard behavior and visual state; a screenshot alone cannot prove focus behavior.
- A server-only parsing correction: unit/API fixtures; browser launch requires a separate browser assertion.

### Launch decision and evidence

Before an executed launch, the helper resolves task/check IDs, source/test fingerprints, environment and the applicable authorization/deadline/cleanup profile. The agent supplies only task-specific assertions and missing rationale. Reuse a justified owned Editor/server session for compatible focused checks; no repeated prose approval packet is required for each Red/Green iteration. Reasons such as `run everything to be safe` do not qualify.

After execution, the helper records actual lane, applicable counts, result artifacts, failures/skips, environment/build identity and cleanup. Test runners require nonzero expected test discovery; static/visual/harness checks require the corresponding assertions and artifacts instead of invented test counts. Missing evidence or unexpected skipped required checks cannot pass. Reuse evidence only when the check's relevant source, tests, configuration and environment match; unknown impact invalidates the affected evidence.

A failed acceptance check prevents acceptance. An expected failing test can establish TDD Red without representing failed final acceptance. Targeted repairs remain within the current task/checkpoint. Preserve executed-control, prerequisite-wait, transport-uncertainty and host-policy-rejection classifications; only repeated unresolved executed failures without new evidence count toward the two-control circuit breaker.

## Validation groups and completion semantics

### Group definition

Task headers in `future.md` are the sole editable source of group membership; task Validation sections own check requirements. No separate `validation-groups.json` or duplicated editable member list is needed. `future.json.task_progress` stores in-progress implementation/check state, including standalone attempts; `active_run` stores controller scope and the frozen in-scope group member IDs. Terminal history owns completed receipts. Derived views never overwrite authoritative progress during refresh.

A nonempty group uses a stable `VG-` identity. Process Pending records a short shared-boundary rationale in the relevant task context. The helper derives members and required checks from the current task definitions; the controller freezes only authorized member IDs. Profile identity comes from the run admission, not duplicated group-specific compatibility policy. Group identity remains separate from task/dependency IDs.

Group related work by shared feature flow, component boundary, fixture and compatible environment. Similar priority or nearby queue position alone is insufficient. Do not combine incompatible save/service contexts or unrelated product surfaces merely to reduce launch count.

Work Through Next contains only the selected root and required descendants; Implement All contains only the initial snapshot and required descendants. Group membership never expands the scope. Checks can verify implemented in-scope members only when the checks do not require unfinished out-of-scope work; otherwise report the exact missing prerequisite. Do not manufacture a subgroup and silently weaken a shared acceptance criterion. Standalone Implement Next never implements other members or starts a controller to close a group.

New required descendants can extend the active group through the existing intake/process/controller flow with a recorded reason. Nonblocking findings stay deferred. Validate grouping feasibility before execution: verified dependencies between members can require earlier checks, and a shared final check cannot depend on a later step requiring the same check to pass. Reject or split such an invalid grouping during research. No task-count threshold or cumulative root time pool is introduced.

### State machine

```text
not-started -> implementing -> awaiting-validation -> completed
                   |                 |
                   +-> blocked <-----+
                         -> resume the recorded implementation or validation step
```

Queue `Ready` describes research/readiness; authoritative task progress prevents reimplementing an already implemented unit. Awaiting-validation tasks retain the full specification and stay outside terminal history. Passing verification is computed from matching check results and finalized transactionally; no separately editable `verified` state is needed. A task with sufficient immediate evidence completes directly.

Keep the single existing `depends_on` graph, with verified completion as the prerequisite. Do not introduce `implementation_depends_on` or a second scheduling graph. Batch compatible eligible tasks while prerequisites hold; validate an upstream task early when a dependency requires completion. A shared final flow can belong to the parent task after lower-level child acceptance is complete. Launch savings never justify weakening dependency semantics.

The controller selects implementation-ready in-scope units by the existing priority/tie rules and never selects an awaiting-validation unit for implementation again. For Implement All, another initial root can join the active batch only as a declared eligible member of the same group; unrelated roots do not bypass an unresolved selected root. Material questions and recorded execution stops retain the existing stop semantics. When no further group member can safely proceed, run due checks or return the exact validation blocker. Progress detection includes implementation-stage transitions and newly resolved check obligations; repeated logs, timestamps and unchanged attempts do not count as progress.

At the boundary, deduplicate checks only when recipe, parameters, environment and relevant source match; keep the task/criterion coverage mapping. Execute the required combined set and preserve distinct unit/runtime/visual obligations. One shared green report cannot automatically cover unrelated criteria. A failed member/check does not erase unaffected passing evidence, but every affected required criterion must pass before completion.

`complete` accepts only matching passed evidence for every required criterion; write the terminal receipt before queue/progress removal. `finish` refuses success while a required check remains pending, failed, stale or unavailable. Persist group results and finalize members through recoverable writes; resume uses existing results without repeating implementation or issuing duplicate terminal outcomes. No separate group outcome ledger is required.

A source change after a passed check invalidates affected verification. Group changes require an updated membership/check-set fingerprint. Required unrun checks never become optional during completion. Missing authorization leaves a concise validation-blocked checkpoint with exact uncovered owner-run commands; valid standing authorization avoids repeated prompts.

## Unity domain

### Testability and lane choice

Installation/profile refresh resolves the pinned Editor/UTF packages, UI framework, test assemblies and existing harness recipes. The installed Unity flavor uses the concrete workflow. Task execution inspects task-relevant code, fixture/save/service boundaries and authorization without generic compatibility discovery. A missing foundational framework follows the very-high-priority setup-task contract; installation remains available and never upgrades project packages.

The implementation contract favors deterministic domain logic with explicit inputs and dependencies. Separate clocks, random sources, persistence and service adapters from rules/state transitions when the selected change requires a test seam. Keep MonoBehaviour lifecycle adapters small without forcing a new dependency-injection framework or opportunistic architecture rewrite. Preserve serialized fields, GUIDs and package pins.

Keep a minimal task-scoped test seam in the current change. Capture a separate evidence-backed refactoring task only for a durable independently actionable change: exact coupling, blocked assertion, minimal intended seam and behavior-preservation checks. Necessary broader refactoring becomes a required descendant; an optional improvement stays nonblocking. Existing meaningful tests can establish preservation without duplicate characterization tests. Alternative runtime coverage qualifies a behavior only when the acceptance contract permits the substitution; missing required tests never disappear into backlog.

| Lane | Suitable assertions | Qualification boundary |
| --- | --- | --- |
| Static inspection | Source contracts, references, serialization compatibility and configuration | No compilation or execution claim. |
| UTF EditMode | Rules, calculations, state transitions, configuration, serialization helpers and Editor tools | Primary executable default for suitable assertions; runs inside Unity Editor. |
| UTF PlayMode in Editor | Awake/OnEnable/Start ordering, frame/coroutine behavior, physics, scene lifecycle and runtime bindings | Focused isolated fixture; full normal-level traversal requires a separate scenario justification. |
| UTF PlayMode in a Player | Runtime/backend/native/platform differences beyond Editor evidence | Builds and runs a Player; build/platform/device permissions remain separate. |
| Visual/gameplay/device scenario | Actual rendering, touch, safe areas, platform interaction and intended game flows | Assertions state the exact surface and environment; Editor screenshots cannot prove device behavior. |

EditMode tests are Editor executions; PlayMode tests can run in Editor or Player contexts. UTF supports frame/coroutine assertions, so a frame-related change does not automatically require manual game traversal. Sources: [Unity test modes](https://docs.unity3d.com/Packages/com.unity.test-framework@1.4/manual/edit-mode-vs-play-mode-tests.html), [Player test workflow](https://docs.unity3d.com/Packages/com.unity.test-framework@1.4/manual/workflow-run-playmode-test-standalone.html).

The runner selects assemblies/categories/tests explicitly and parses NUnit XML plus logs, rather than treating launch/transport success as a passed suite. UTF command-line selectors distinguish `EditMode`, `PlayMode` and target-specific Player execution. Multi-frame tests require compatible runner options; a synchronous filtered run cannot silently omit required fixtures. Source: [UTF command-line reference](https://docs.unity3d.com/Packages/com.unity.test-framework@1.4/manual/reference-command-line.html).

The cited UTF 1.4 documentation establishes the lane concepts. The installer resolves concrete flags, attributes and platform support against the target's pinned UTF/Editor versions and emits only supported instructions; the plan does not select or upgrade a project package version.

### Execution discipline

- Prefer deterministic NUnit assertions for logic and `[UnityTest]` only for required frame/lifecycle behavior. Use explicit frame/condition bounds rather than arbitrary waits.
- Reuse suitable isolated scenes/prefabs and existing harnesses. Restore changed state, static/event subscriptions, time settings and temporary objects; avoid save resets and backend calls outside verified scope.
- Batch compatible EditMode suites and later scoped PlayMode checks in one authorized owned Editor lifecycle when feasible. Do not start a second Editor against the same checkout or create an uncontrolled fresh checkout to evade a recorded stop.
- Respect current preflight process ownership, exact checkout/version, unrelated Editors, hard operation deadlines and cleanup reserve. An EditMode fixture that enters PlayMode needs the corresponding scope despite the fixture label.
- Keep headless-compatible assertions distinct from rendering assertions. A headless pass cannot settle GPU/layout/device acceptance.
- Prefer project UTF/harness evidence over generated solution builds. No `dotnet build`, Player/device operation or external-service access follows from ordinary Editor-test scope.
- Use only the project conventions and package-specific instructions selected in the admitted installation profile. Apply the concrete convention to current task code without re-detecting alternative packages.

## Web domain

Installation/profile refresh resolves the actual Web framework, language, package manager, test runner, server/build commands, API/storage adapters, browser support and existing rendering recipes. The installed Web flavor contains the resulting concrete instructions. Task execution identifies changed boundaries and appropriate assertions without re-detecting the stack. A Web flavor does not imply a JavaScript-only stack or compulsory Playwright installation.

Prefer pure unit tests, component/DOM tests, in-process API/contract tests and isolated storage fixtures when the assertion fits. A component runner using a real browser counts as browser execution even when the framework labels the suite a unit test. Framework terminology never overrides actual operation cost or effects.

Use scoped browser checks for real layout, CSS, responsive behavior, focus/accessibility interactions, hydration, navigation, service workers, browser storage and relevant engine differences. Visual changes carry explicit runtime checks where rendering matters; semantic assertions complement screenshots. Network/auth/provider integration uses controlled fixtures and separates mocked, local, hosted and live-service claims.

Start an owned server once for a compatible group, with the correct source/build identity, bind address, isolated port, readiness condition, environment, deadline and cleanup. Verify an existing server's identity before reuse; a responding port is insufficient. Distinguish a development server from production-build preview and hosted deployment. Service-worker/storage persistence scenarios need explicit isolated profiles and cannot always use a new empty browser context for every step.

Playwright can start and reuse configured servers, and supports timeout/cleanup settings; the domain policy adds repository/build identity checks before reuse. The composer includes Playwright instructions only for an installation profile with the compatible runner. Source: [Playwright web server configuration](https://playwright.dev/docs/test-webserver).

A local browser pass does not qualify deployed caching, redirects, TLS, provider behavior, installed PWA behavior or a physical mobile browser. Schedule only the affected browser/viewport/platform matrix and record unqualified environments. Keep required correctness checks even for small high-impact changes; cosmetic grouping cannot postpone an unsafe data/auth change.

## End-to-end agent UX

| Stage | Agent behavior | Developer-visible result |
| --- | --- | --- |
| Install | Select/retain flavor; compose and verify packages | Selected flavor, operation list, destinations and actual verification. |
| Initialize/audit | Use admitted project facts; inspect current source claims and domain evidence | Current documentation and confirmed gaps; mark newly discovered capability drift for refresh without repeating stack discovery on every task. |
| Add Pending | Capture intent without a full validation questionnaire | Stable Pending ID and useful known context. |
| Process Pending | Research acceptance, testability, boundary flag and useful grouping | Ready/blocked tasks, concise check/group summary and next-action handoff. Standalone processing still waits for selection. |
| Implement | Make scoped changes; run appropriate immediate checks; update actual impact | Implemented IDs, immediate evidence and explicit pending verification. |
| Validate boundary | Execute justified scoped checks over the combined source | Check results, covered criteria, source/environment identity and remaining gaps. |
| Complete/resume | Finalize only verified tasks; persist pending obligations | Honest completed/awaiting-validation/blocked/deferred counts and exact next action. |

Keep the everyday interface compact: one flavor choice, one short validation classification per task and a readable group summary. Expand detail only for unknown testability, conflicting scope, failed checks or an actual launch. Do not ask the same authorization question after a prerequisite wait when valid scope already covers continuation.

The ordinary task path is selected-task research, the concrete focused test loop, due checks and completion. Grouping is an optional optimization, not a prerequisite for every task. Helpers maintain hashes, recipes and progress; the agent does not regenerate installation metadata or fill an execution form on every iteration. Existing adequate tests and matching evidence are reused; new checks address a real uncovered assertion.

Small prioritized tasks retain meaningful goal, scope, acceptance and validation without mandatory empty sections. Optional risks/discovery/documentation sections appear only when substantive. Validators enforce observable acceptance and structured validation fields instead of section-count boilerplate. Large tasks retain the detailed template.

## Modern development practices research

### Research method and confidence

Research date: 2026-11-02. The source register contains official product documentation and standards, engineering reports and developer-authored articles, an observational conference paper and a recent research preprint. Dated agentic-development sources concentrate on 2025-2026. Older foundational guidance remains relevant when the current maintained tool or standard still supports the principle. Publication date, documentation maintenance and target-version compatibility are separate checks.

The recommendations below are proposed Skill Tree adaptations. The supporting sources establish mechanisms, tool contracts or reported experience; the sources do not demonstrate a measured productivity improvement for the current Skill Tree repository. Practitioner reports, survey associations and controlled experiments have different evidential strength. The research does not establish a universal best testing pyramid, a fixed test ratio or a guaranteed TDD speedup.

Important qualifications:

- The 2026 test-driven LLM survey distinguishes genuine Red-Green-Refactor from generation conditioned on existing tests and evaluation performed only after coding. The survey is a preprint; passing tests alone cannot establish behavioral equivalence or adherence to TDD. [R-09](https://arxiv.org/abs/2609.12012)
- The MSR 2026 study observes more mock additions in agent-authored test commits across JavaScript, TypeScript and Python repositories. Commit attribution and mock-detection methods limit interpretation. The observation does not prove that every mock is harmful or that the same rates apply to Unity/C#. [R-08](https://andrehora.github.io/pub/2026-msr-agents-over-mocked-tests.pdf)
- METR's February 2026 update identifies selection and measurement problems in the later productivity experiment. Early-2025 slowdown findings are not a current universal estimate; later results do not establish a reliable universal speedup either. Measure local workflow outcomes instead. [R-07](https://metr.org/blog/2026-02-24-uplift-update/)
- Current Claude documentation explicitly supersedes the older best-practices article. The useful portable principles are runnable verification, concise contextual instructions and deterministic enforcement for invariants; provider-specific defaults, hooks, permissions and model advice are not common Skill Tree requirements. [R-02](https://code.claude.com/docs/en/best-practices)

### Main recommendation: two feedback loops

Use a small change-and-test loop for implementation and a separate boundary-validation loop for expensive integration/rendering checks. DORA warns that collecting small changes into a large downstream testing batch delays feedback. Therefore, a validation group collects only compatible expensive obligations; a validation group never withholds cheap behavioral feedback or permits a large unreviewed feature dump. [R-05](https://dora.dev/capabilities/working-in-small-batches/)

```text
Acceptance examples and baseline
    -> failing focused test -> minimal behavior -> passing test -> refactor
    -> repeat for the next small behavior
    -> affected regressions and static checks
    -> justified group-boundary runtime/rendering checks
    -> verified acceptance and completion
```

Group closure follows a coherent testable boundary and the current authorized scope. Reuse expensive process setup where safe, while executing focused assertions promptly. A slow or unavailable test loop becomes a concrete harness/testability problem to investigate; delaying all feedback until a large group is finished is not the remedy.

### Proposed TDD protocol

The user-selected development default is test-first development for meaningful executable behavior. Red/green TDD is a documented agentic technique because observing failure before implementation checks whether the test exercises the intended missing behavior. [R-01](https://simonwillison.net/guides/agentic-engineering-patterns/red-green-tdd/)

The following protocol is the proposed Skill Tree design:

1. Establish the intended behavior from researched acceptance, concrete examples, boundary conditions and relevant failure paths. Run an appropriate existing baseline or reference recent matching baseline evidence. Identify pre-existing failures separately.
2. Add the smallest meaningful test before implementing the behavior. Assert externally relevant outcomes or domain invariants. Avoid testing private call order unless call order is the actual contract.
3. Execute Red and inspect the reason. The expected missing behavior must cause the failure. Wrong filters, zero tests, a broken runner, unrelated compilation errors, credentials or unavailable infrastructure do not establish Red. A missing new API can be an intermediate compiler failure; establish a runnable behavioral failure after adding the minimal API seam where feasible.
4. Implement the smallest coherent change and execute the focused test until Green. Keep the accepted behavioral oracle stable. A legitimate test correction records the reason and receives a test-diff review; removing assertions, broadening expected output or updating a golden file solely to obtain Green is invalid.
5. Refactor while relevant tests remain Green. Re-run the affected regression set after a meaningful structural change, then perform the required static/contract checks and any due group checks. Keep unrelated cleanup outside the selected task.
6. Let the helper retain the useful Red/Green report references, failure category and source/test/runner fingerprints in the existing task progress. Checkpoint at meaningful handoffs or interruptions, not after every assertion. Keep code, test and acceptance changes reviewable without requiring separate commits or another TDD event ledger.

An expected failing assertion is an executed control that successfully establishes the Red phase; the expected Red observation is not an unresolved operational failure. Unexpected repeated failures still follow the unchanged-failure circuit breaker. TDD never excuses an infinite repair loop, a weakened assertion or bypassing a recorded execution stop.

Resolve the test strategy from the task: test-first for meaningful new behavior/bugs, characterization for uncovered existing behavior, exploratory for an unknown hypothesis, and not-applicable for suitable nonbehavioral changes. The Validation section needs an explicit strategy override only when the default does not fit. Use existing partial-work/next-action fields for a paused Red/Green step; no mandatory `test_strategy` header or separate `tdd_phase` state is required. Unrelated pre-existing failures remain reported limitations; relevant mandatory failures block qualification without authorizing unrelated repairs.

| Situation | Strategy | Acceptance boundary |
| --- | --- | --- |
| New deterministic behavior or a reproducible bug | Test-first | Observe the intended Red failure, implement Green, refactor with regressions. |
| Existing behavior needs refactoring | Existing meaningful tests, then characterization for uncovered behavior | Establish preservation before structural change. Characterization does not prove that existing behavior is desirable; distinguish intentional bug fixes from preserved behavior. |
| Legacy coupling prevents a useful test | Small testability seam plus required refactoring task where necessary | Add the minimal seam and verify preserved behavior; do not rewrite the architecture merely to satisfy a test tool. |
| Visual exploration, unknown engine behavior or a performance hypothesis | Bounded exploratory check followed by a repeatable regression where useful | Record the hypothesis and actual observation. Do not call an exploratory success test-first evidence. |
| Documentation, simple configuration or generated-resource update | Not applicable, with appropriate validators | No artificial unit tests that restate prose or copy the implementation. |

Unity TDD can use repeated focused tests in the same authorized Editor lifecycle. The batching policy primarily reduces restarts and broad gameplay traversal; the batching policy does not defer every EditMode Red/Green result. A supported test loop must remain inside the exact checkout, save/service isolation and toolchain scope.

### Test quality and refactoring confidence

Use three separate questions: does the test run, can the test detect a relevant defect, and does the expected result represent the intended requirement? Coverage helps locate unexecuted code; coverage does not answer the last two questions. Thoughtworks' 2026 sensor report illustrates assertion gaps despite high coverage and describes the cost of mutation testing. [R-04](https://martinfowler.com/articles/sensors-for-coding-agents.html)

Proposed safeguards:

- Derive representative cases and invariants from requirements, domain examples or a trusted reference, not exclusively from the newly written implementation. Review the test oracle for high-impact behavior and verify the final code against the acceptance text.
- Prefer real small collaborators and controlled in-memory adapters when practical. Mock external/time-dependent boundaries deliberately; contract-test assumptions that matter. Neither mocking every collaborator nor banning mocks is a useful default.
- Add property-based checks for suitable invariants such as serialization round trips, idempotent updates and equivalent algorithms. Preserve failing examples/seeds for replay. Adopt an existing compatible property-testing tool conditionally; the approach does not imply installing Hypothesis into non-Python projects. [R-10](https://hypothesis.readthedocs.io/en/latest/tutorial/introduction.html)
- Use targeted mutation tests or explicit negative controls for critical changed logic when the value justifies the cost. Check that a plausible wrong comparison or missing guard is detected. Review equivalent mutants; require no universal mutation-score target. [R-11](https://stryker-mutator.io/docs/)
- Run mutation experiments only in controlled temporary copies or with guaranteed task-owned restoration. Unity uses a compatible UTF/harness route; Stryker.NET availability does not authorize generated-solution builds or establish Unity compatibility.
- Keep golden/screenshot baselines reviewable. Record the intended visual change before approving a baseline replacement. A comparison against a newly accepted baseline is not independent evidence of correctness.
- Diagnose flakiness rather than increasing retries until a pass appears. Record first-failure evidence and repeatability; a flaky required assertion remains a qualification issue.

Fresh-context review can reduce shared assumptions, but another model or session is not an independent ground-truth oracle. Delegation remains conditional on owner/provider policy. No extra agent, model call or external service is required by the default test loop.

### General flavor: recommended practices

The common foundation combines small behavioral slices, explicit boundaries and executable feedback. The agent-specific benefit is less rediscovery and a more reliable correction loop. The table contains proposed adaptations; stable project/tool applicability is resolved during installation, while task-specific risk and assertions remain execution decisions.

| Practice | Application and agentic adaptation | Default or trigger | Evidence |
| --- | --- | --- | --- |
| Small vertical slices with acceptance examples | Select one coherent outcome, test the domain/API boundary, then connect required adapters. Keep requirements short enough to verify; avoid generating a complete subsystem before feedback. | Default for behavioral work. | [R-05](https://dora.dev/capabilities/working-in-small-batches/) |
| Functional core and explicit side-effect boundaries | Put rules/transforms behind explicit inputs; isolate filesystem, network, clocks and randomness. Reuse the established project architecture instead of imposing a new framework. | Changed behavior needs deterministic tests. | [R-03](https://martinfowler.com/articles/harness-engineering.html); proposed architectural adaptation. |
| Executable architecture and static checks | Run relevant formatting, compiler/type checks, lint and dependency-boundary rules. Return file/rule/action diagnostics; start with valuable existing rules rather than arbitrary complexity quotas. | Existing tools by default; new rules need a concrete recurring defect. | [R-04](https://martinfowler.com/articles/sensors-for-coding-agents.html) |
| Repeatable test recipes | Document exact single-test, affected-suite and boundary commands, required pins, fixtures and report format. Reuse dependency caches only with matching inputs; avoid opportunistic upgrades. | Initialization and harness changes. | [R-02](https://code.claude.com/docs/en/best-practices) |
| Contract checks at owned boundaries | Verify consumer/provider schemas, error cases and version assumptions. Prefer simple schema fixtures for a monolith; consumer-driven tooling is conditional on control of both sides. | An integration boundary changes. | [R-12](https://docs.pact.io/getting_started/what_is_pact_good_for) |
| Retry-safe state changes | Test duplicate requests, partial failures and recovery. Retrieve the original operation result when uncertain; a tool timeout never proves that a mutation failed. Do not assume an idempotency key has identical semantics across services. | Persistent/external mutations. | [R-13](https://docs.stripe.com/api/idempotent_requests); proposed portable adaptation. |
| Observability designed with failure paths | Expose bounded error categories and useful structured diagnostics without secrets. Verify cancellation and cleanup as part of the changed resource lifecycle. | Async/resource/service work; avoid unrelated instrumentation. | [R-03](https://martinfowler.com/articles/harness-engineering.html); proposed portable adaptation. |
| Tool-enforced completion invariants | Make metadata/check receipts reject stale or missing evidence. Optional provider hooks invoke the same portable checks; shared rules never depend solely on a prompt being followed. | Completion and installation infrastructure. | [R-02](https://code.claude.com/docs/en/best-practices) |
| Agent-behavior evaluation | Test observable workflow failures: skipped checks, invalid completion, scope expansion and unintended launch. Keep fixtures separate from actual model-driven evaluations. | Skill/controller/composer behavior changes. | [R-14](https://developers.googleblog.com/en/the-anatomy-of-harness-engineering-how-to-evaluate-iterate-and-guard-ai-coding-agents/) |

For database/file-format changes in an application, include task-relevant compatibility, atomicity and interrupted-write tests. Application data-compatibility testing is distinct from Skill Tree migration support; automatic Skill Tree migration remains excluded.

### Unity flavor: recommended practices

Typical Unity work spans domain C#, engine lifecycle/adapters, serialized content and platform builds. A pure logic test cannot qualify lifecycle, rendering or native runtime behavior. The Unity flavor makes the boundaries explicit and uses the lowest suitable lane.

| Practice | Application and agentic adaptation | Default or trigger | Evidence |
| --- | --- | --- | --- |
| EditMode-first domain design | Keep calculations/state transitions callable without normal-level startup. Treat ScriptableObjects as a project-specific data/configuration tool, with explicit runtime-state ownership; no forced migration to ScriptableObjects. | Rules, economy, inventory, scoring and deterministic configuration. | [R-17](https://unity.com/resources/create-modular-game-architecture-scriptableobjects-unity-6) |
| Focused test assemblies and dependencies | Separate runtime, Editor and test assemblies where useful; inspect the dependency graph and serialization impact before moving code. Reduce the compilation blast radius without creating an assembly per class. | Measured iteration cost or missing test boundary. | [R-15](https://docs.unity3d.com/6000.0/Documentation/Manual/assembly-definitions-intro.html) |
| Deterministic simulation inputs | Inject or adapt time, randomness and commands for domain tests. Use repeatable seeds and bounded frame conditions; keep actual engine/physics timing assertions in PlayMode. | Randomized rules, timers, turns, replayable bugs. | Proposed adaptation of the TDD and isolation contracts; no cross-platform deterministic-physics claim. |
| Safe warm-Editor iteration | Reuse the exact authorized Editor. Qualify static fields, event subscriptions and fixture cleanup before considering disabled domain reload. Keep a required cold-start regression when startup semantics matter. | Repeated test-loop cost; configuration changes remain separate scope. | [R-16](https://docs.unity3d.com/6000.0/Documentation/Manual/domain-reloading.html) |
| Simulated input fixtures | Use the installed Input System's test fixtures for commands and device events. Register required layouts explicitly and preserve fixture setup/teardown. Simulated touch does not qualify a physical device. | Input System exists and changed input behavior requires assertions. | [R-18](https://docs.unity3d.com/Packages/com.unity.inputsystem@1.11/manual/Testing.html) |
| UI-framework-specific checks | Resolve uGUI, UI Toolkit or IMGUI during installation. Emit concrete presenter/binding and rendering/interaction recipes for the detected framework instead of a universal game UI macro. | UI changes use the admitted profile. | [R-19](https://discussions.unity.com/t/ui-toolkit-test-framework-is-available-in-6-3/1698228), [R-20](https://docs.unity3d.com/Packages/com.unity.ui.test-framework@6.3/manual/test-fixtures/trigger-and-update-ui.html) |
| Scoped performance regressions | Identify the changed hot path and representative workload; measure relevant allocations, profiler markers, timing and retained resources. Preserve environment/build metadata and compare like-for-like samples. | Performance fix, repeated gameplay loop or known mobile budget. | [R-21](https://docs.unity3d.com/Packages/com.unity.test-framework.performance@3.0/manual/index.html) |
| Platform qualification for platform claims | Use Editor tests for fast feedback, then the justified target Player/device lane for AOT, native integration or real performance. Profile the actual target rather than inferring mobile results from Editor timings. | Target-specific acceptance. | [R-22](https://docs.unity.com/en-us/engine/6000.0/manual/analysis/profiler/profiling-applications/profiling-target-device), [R-23](https://docs.unity3d.com/6000.0/Documentation/Manual/scripting-backends-il2cpp.html) |
| Mobile lifecycle and ownership scenarios | Cover task-relevant pause/resume, cancellation, scene unload, event cleanup, save interruption and repeated initialization. Keep backend/native adapters isolated and record remaining device evidence. | Changed lifecycle, persistence or SDK adapter; fixtures do not replace physical validation. | Proposed domain acceptance derived from the existing Unity safety boundaries. |

A relevant modern option is the UI Toolkit Test Framework, announced for Unity 6.3 in December 2025. The package documentation describes `PanelSimulator` control of the UI update loop and simulated time. The installer includes the recipe only for a compatible UI Toolkit profile; the Unity 6.0/uGUI output omits the recipe entirely. Refresh after an applicable project upgrade can select the recipe without adding runtime compatibility branches. The official Unite 2025 talk is listed as further viewing; only the talk metadata and linked documentation were inspected. [R-19](https://discussions.unity.com/t/ui-toolkit-test-framework-is-available-in-6-3/1698228), [R-20](https://docs.unity3d.com/Packages/com.unity.ui.test-framework@6.3/manual/test-fixtures/trigger-and-update-ui.html), [R-31](https://www.youtube.com/watch?v=7Sfev9fcr3s)

Modern documentation does not erase target-version limits. Unity 6.0 domain-reload documentation and later release documentation describe different capabilities/defaults. Never copy a newer static-cleanup API, UTF option or sample package version into an older pinned project without compatibility evidence.

Performance-testing package examples also need qualification: the inspected 3.0 documentation describes measurement metadata and notes development-Player behavior under UTF. Such results are not automatically release-build performance evidence. Existing project package pins and platform restrictions govern the exact runner. [R-21](https://docs.unity3d.com/Packages/com.unity.test-framework.performance@3.0/manual/index.html)

### Web flavor: recommended practices

Typical Web work spans domain/server behavior, HTTP/storage contracts, component interaction and browser rendering. Server versus client execution, asynchronous requests, caching and supported browsers introduce boundaries that differ from Unity's frame/lifecycle and serialized-asset model.

| Practice | Application and agentic adaptation | Default or trigger | Evidence |
| --- | --- | --- | --- |
| Behavior-first component tests | Exercise forms, validation and state via semantic roles/labels. Prefer visible behavior over component internals or brittle CSS selectors. Keep a real-browser obligation for behavior absent from a simulated DOM. | UI behavior changes. | [R-25](https://testing-library.com/docs/guiding-principles/) |
| Accessible design as acceptance | Include relevant keyboard, focus, names, error messaging, zoom/reflow and contrast assertions. Combine automated checks with scoped interaction review; an automated audit alone cannot establish accessibility conformance. | Changed interactive/visual surfaces. | [R-27](https://www.w3.org/TR/WCAG22/), [R-26](https://playwright.dev/docs/accessibility-testing) |
| Stable browser automation | Use isolated contexts/data, semantic locators and condition-based assertions. Collect relevant traces on failure; avoid arbitrary sleeps and indiscriminate full-browser matrices. | Required browser lane. | [R-24](https://playwright.dev/docs/best-practices) |
| API contracts and negative server tests | Test schema validation, authorization boundaries, malformed input and useful error responses in a controlled API fixture. Verify both sides of a changed owned integration; a mocked response alone proves neither provider behavior nor persistence effects. | Server/API boundary changes. | [R-12](https://docs.pact.io/getting_started/what_is_pact_good_for), [R-30](https://asvs.owasp.org/) |
| Explicit asynchronous UI states | Test loading, empty, error, retry and stale-result states. Use controlled deferred responses/clock fixtures to reproduce races; assert the final user outcome and cleanup after navigation. | Fetching, optimistic updates or cancellation changes. | Proposed TDD adaptation using [R-24](https://playwright.dev/docs/best-practices). |
| Server/client responsibility boundaries | Keep trusted authorization and sensitive operations on the server; validate untrusted input at boundaries. Inspect actual framework SSR/hydration/cache behavior instead of assuming a universal rendering architecture. | Auth, server actions, SSR or cache changes. | [R-30](https://asvs.owasp.org/); framework-specific details require target documentation. |
| Measured user-experience performance | Use affected-route bundle/request checks and reproducible lab measurements during development; qualify field outcomes separately. Current Core Web Vitals are LCP, INP and CLS, assessed at the 75th percentile; a single Lighthouse score cannot prove real-user results. | Affected loading, interactivity or layout budget. | [R-28](https://web.dev/articles/vitals) |
| Compatibility and progressive fallback | Check feature support against the actual audience/browser policy; use Baseline as a compatibility signal, not a replacement for project support requirements. Prefer native semantic controls and a suitable fallback where required. | New platform API/CSS behavior or browser-specific defect. | [R-29](https://web.dev/baseline); proposed fallback policy. |
| Build/cache/storage-aware qualification | Use the relevant build fixture for routing, assets, service-worker updates and persistent storage. Verify the existing server's identity; keep dedicated isolated persistent profiles for multi-session scenarios. | PWA, caching, offline, storage or deployment-sensitive changes. | Existing Web-domain contract plus conditional [R-24](https://playwright.dev/docs/best-practices) isolation principles. |

Use a small representative viewport/browser set for the changed assertion, then the declared release matrix at the relevant gate. Include reduced motion, localization, long text and touch target concerns when the product/surface requires the cases. Avoid automatic dependency upgrades, framework replacement or a new end-to-end framework merely because a practice appears in a recent article.

For backend-only Web tasks, browser testing remains conditional. For browser-only behavior, a passing in-process API test is insufficient. A shared schema reduces duplication but does not automatically validate untrusted runtime data or business-level authorization.

### Practices excluded from the defaults

- Testing every change through the full product UI, or postponing every test until a large group closes.
- Requiring a fixed unit/integration/end-to-end percentage, 100% coverage or a global mutation-score target regardless of risk.
- Generating exhaustive mocks, snapshots or tests that simply reproduce production implementation details.
- Treating AI-generated tests, a second agent's approval or a high benchmark score as an independent correctness oracle.
- Applying a large new specification framework to a small change. Use just enough acceptance/design context to make the next check meaningful.
- Automatically disabling Unity reload, installing the newest testing package, replacing uGUI with UI Toolkit or imposing DOTS/ECS/DI without project evidence.
- Turning every Web UI check into a hosted deployment, or treating browser emulation as physical-device evidence.
- Adding hooks that automatically launch Editors, servers, external models or full suites on every edit/stop.
- Adopting test-and-commit/revert automation. Existing commit authorization and preservation of unrelated work remain binding.

The purpose of the exclusions is a shorter reliable feedback loop, with escalation determined by actual assertions and risk. Research labels such as harness engineering and spec-driven development supply vocabulary; labels alone do not justify additional infrastructure.

### Changes required in the planned skills and installer

U-01, U-03 and U-05 implement strategy defaults, test-oracle review and immediate-versus-boundary timing in the existing task/progress model. A focused required Red/Green check cannot move to group end merely to avoid execution.

Each flavor contains a short common TDD/refactoring contract and relevant profile recipes/examples. The generated installation profile owns resolved commands/capabilities. `testing.md` owns human validation policy and links to the profile summary; avoid a second editable command/capability inventory. Refresh updates generated facts without overwriting human policy or initializing missing product documents.

The installer flavor summary explains the test-loop policy and selected capabilities. Flavor installation neither adds project test dependencies nor enables lifecycle hooks. A missing foundational framework creates the very-high-priority setup task described above through the post-install intake. Other newly required capabilities produce scoped setup/testability tasks during research; refresh follows approved setup. Readiness and authorization rules determine execution.

Verification has two distinct layers:

1. Deterministic repository/temporary-fixture checks cover parsing, composition, scope boundaries, state transitions, ownership and evidence enforcement. Existing Python/Node tests belong to the first layer.
2. Optional actual agent-behavior evaluations measure whether a composed skill performs the intended observable actions in sandboxed fixtures. Prompt parsing or helper tests alone cannot prove model adherence. Use safe mock Editor/server tools for default scenarios; actual model calls require separately applicable account/cost scope. Avoid exact transcript/tool-order matching when multiple valid solutions exist. [R-14](https://developers.googleblog.com/en/the-anatomy-of-harness-engineering-how-to-evaluate-iterate-and-guard-ai-coding-agents/)

Required deterministic fixtures cover state/recipe enforcement: no scheduled product launch for documentation, invalid evidence rejection, scoped grouping, dependency-driven early validation, profile specialization and interruption recovery. Optional model-driven evaluations additionally observe intended Red before Green, acceptance stability, sensible testability findings and correct launch escalation. A mocked helper scenario proves only the helper contract, never actual model adherence.

Evaluate local outcomes using time to the first useful check, focused-loop duration, cold/warm startup time, flake rate, diagnostic usefulness, rework and escaped regressions. Record qualified environment and task type. A lower launch count is valuable only when verification quality and end-to-end task latency remain acceptable. No unmeasured speedup, model-token estimate or telemetry collection is implied. DORA's 2026 analysis describes verification overhead; the proposed metrics investigate the local cost rather than assuming that faster code generation means faster delivery. [R-06](https://dora.dev/insights/balancing-ai-tensions/)

### Adoption order

First adopt behavioral acceptance, focused TDD/characterization, explicit testability findings, repeatable commands and honest evidence. Next add group-state enforcement and selected-flavor composition. Add architecture checks, property testing and contract checks where actual boundaries justify the investment. Add targeted mutation/performance/real-agent evaluations after the basic loop is reliable. Target-specific visual, Player and device qualification follows the relevant acceptance need and authorization.

### Research source register

Source checks occurred during research on 2026-11-02: thirty primary pages/documents and one official talk metadata record. Video retrieval has the explicit limitation recorded below. Living documentation may change. The register records publication/version information visible in the inspected source; an undated living page is not presented as a newly published 2026 article.

| ID | Source and date/version | Evidence type and contribution |
| --- | --- | --- |
| R-01 | [Simon Willison: Red/green TDD](https://simonwillison.net/guides/agentic-engineering-patterns/red-green-tdd/), Agentic Engineering Patterns, 2026 guide | Practitioner guidance on observing failure before implementation. |
| R-02 | [Claude Code current best practices](https://code.claude.com/docs/en/best-practices), living documentation | Vendor guidance on runnable checks, concise context and deterministic enforcement. No portable permission/model defaults inferred. |
| R-03 | [Birgitta Böckeler: Harness engineering for coding agent users](https://martinfowler.com/articles/harness-engineering.html), 2026-04-02 | Engineering framework for guides and feedback sensors; not a controlled productivity study. |
| R-04 | [Birgitta Böckeler: Maintainability sensors for coding agents](https://martinfowler.com/articles/sensors-for-coding-agents.html), 2026-05-27 | Reported application experiment with static rules, dependency checks and mutation testing. |
| R-05 | [DORA: Working in small batches](https://dora.dev/capabilities/working-in-small-batches/), maintained capability guidance | Fast feedback and explicit warning against regrouping small changes into delayed testing batches. |
| R-06 | [DORA: Balancing AI tensions](https://dora.dev/insights/balancing-ai-tensions/), 2026-03-10 | Qualitative analysis of 1,110 Google developer responses from Q3 2025; verification overhead and contextual limits. |
| R-07 | [METR: Developer productivity experiment update](https://metr.org/blog/2026-02-24-uplift-update/), 2026-02-24 | Empirical-method update explaining why later results cannot supply a reliable current universal effect. |
| R-08 | [Hora and Robbes: Are Coding Agents Generating Over-Mocked Tests?](https://andrehora.github.io/pub/2026-msr-agents-over-mocked-tests.pdf), MSR 2026 | Observational repository study; inspected abstract, implications and validity limitations. |
| R-09 | [Liang et al.: Test-Driven Approaches to Software Engineering with LLMs](https://arxiv.org/abs/2609.12012), 2026-09-10 | Preprint survey; inspected abstract and method summary. Separates test validity, feedback and evaluation independence. |
| R-10 | [Hypothesis introduction](https://hypothesis.readthedocs.io/en/latest/tutorial/introduction.html), maintained documentation | Tool contract and examples of useful properties; conditional tool adoption. |
| R-11 | [Stryker: Mutation testing](https://stryker-mutator.io/docs/), maintained documentation | Mechanism for checking whether assertions detect altered behavior; no Unity runner compatibility implied. |
| R-12 | [Pact: When to use Pact](https://docs.pact.io/getting_started/what_is_pact_good_for), maintained page, revision 2022-04-13 | Boundary-contract use cases and limits; no universal replacement of integration tests. |
| R-13 | [Stripe: Idempotent requests](https://docs.stripe.com/api/idempotent_requests), current API documentation | Concrete retry/recovery semantics, including API-version differences; portable policy is an adaptation. |
| R-14 | [Google Developers: Anatomy of Harness Engineering](https://developers.googleblog.com/en/the-anatomy-of-harness-engineering-how-to-evaluate-iterate-and-guard-ai-coding-agents/), 2026-09-09 | Vendor engineering article on focused observable agent-behavior evaluations. |
| R-15 | [Unity: Introduction to assemblies](https://docs.unity3d.com/6000.0/Documentation/Manual/assembly-definitions-intro.html), Unity 6.0 | Compilation and dependency boundaries. |
| R-16 | [Unity: Domain reload disabled](https://docs.unity3d.com/6000.0/Documentation/Manual/domain-reloading.html), Unity 6.0 | Persistent static/event state and required reset behavior. |
| R-17 | [Unity: Modular architecture with ScriptableObjects](https://unity.com/resources/create-modular-game-architecture-scriptableobjects-unity-6), 2025-08-22 | Official Unity 6 resource overview and sample direction; the full downloadable book was not reviewed. |
| R-18 | [Unity Input System testing](https://docs.unity3d.com/Packages/com.unity.inputsystem@1.11/manual/Testing.html), package 1.11 | Isolated input state and fixture setup/teardown requirements. |
| R-19 | [Unity: UI Toolkit Test Framework announcement](https://discussions.unity.com/t/ui-toolkit-test-framework-is-available-in-6-3/1698228), 2025-12-02 | Official release announcement establishes Unity 6.3 availability. |
| R-20 | [Unity UI Test Framework: Trigger and update UI](https://docs.unity3d.com/Packages/com.unity.ui.test-framework@6.3/manual/test-fixtures/trigger-and-update-ui.html), 6.3 documentation | Controlled UI update loop/time; not proof of uGUI or Unity 6.0 support. |
| R-21 | [Unity Performance Testing package](https://docs.unity3d.com/Packages/com.unity.test-framework.performance@3.0/manual/index.html), 3.0 documentation | Measurements, environment metadata and development-Player qualification limit. |
| R-22 | [Unity: Profile a target platform](https://docs.unity.com/en-us/engine/6000.0/manual/analysis/profiler/profiling-applications/profiling-target-device), Unity 6.0 | Platform-specific profiling workflow; device performance remains separate evidence. |
| R-23 | [Unity: IL2CPP scripting backend](https://docs.unity3d.com/6000.0/Documentation/Manual/scripting-backends-il2cpp.html), Unity 6.0 | AOT/native runtime boundary. |
| R-24 | [Playwright best practices](https://playwright.dev/docs/best-practices), maintained documentation | User-visible behavior, isolation, semantic locators and retrying assertions. |
| R-25 | [Testing Library guiding principles](https://testing-library.com/docs/guiding-principles/), maintained page, revision 2020-11-04 | Durable user-oriented testing principle; not a newly invented agentic practice. |
| R-26 | [Playwright accessibility testing](https://playwright.dev/docs/accessibility-testing), maintained documentation | Automated accessibility checks and explicit manual-testing limitations. |
| R-27 | [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/), Recommendation 2024-12-12 | Accessibility requirements; project scope selects relevant criteria, without an automatic compliance claim. |
| R-28 | [web.dev: Web Vitals](https://web.dev/articles/vitals), maintained page, revision 2024-10-31 | Current metric set and percentile-based field interpretation. |
| R-29 | [web.dev: Baseline](https://web.dev/baseline), maintained documentation | Browser support signal and availability stages. |
| R-30 | [OWASP ASVS](https://asvs.owasp.org/), 5.0.0 published 2025-05-30 | Security verification requirements framework; a task-specific subset replaces a generic security slogan. |
| R-31 | [Unity: UI testing made easy, Unite 2025](https://www.youtube.com/watch?v=7Sfev9fcr3s), recording published 2025-12-16 | Official talk metadata/further viewing. Video retrieval was throttled; no transcript or full-talk inspection claimed. |

## Implementation sequence and acceptance

Implementation starts only under a subsequent implementation request. The following units are proposed work packages, not newly created queue entries.

| Unit | Dependency | Deliverable | Acceptance |
| --- | --- | --- | --- |
| U-01 | None | Minimal task/check ownership, progress transitions, composition slots and flavor/capability contracts | General/Web/Unity examples resolve; defaults avoid redundant headers; one dependency graph and one editable group-membership source prevent phase deadlocks. |
| U-02 | U-01 | `.skill-tree/` source/target path update | Launchers, npm commands, source resolution, ownership checks, locks/transactions, snapshots, history, bridges, validators, tests, ignores and portable metadata use the new path. Root/provider discovery locations remain valid. |
| U-03 | U-01, U-02 | Deterministic composer and self-contained project-specialized packages | All operations build for supported profiles in all three flavors; inactive compatibility branches are absent from all emitted references; conflicting slots/resources fail; output is deterministic and standalone. |
| U-04 | U-03 | Project installer, local maintenance bundle, refresh and integrity fixes | Projects without tests install; a missing foundation produces one very-high-priority setup intake, including framework selection when needed; absent queues preserve the finding; refresh, ownership and recovery work without source access or product execution. |
| U-05 | U-01, U-02, U-03, U-04 | Task progress and scoped group scheduler | Admission pins the profile once; standalone progress persists; dependencies force timely checks; no repeated implementation or invented subgroup acceptance; stale/pending checks prevent completion. |
| U-06 | U-03, U-05 | Unity domain guidance and capability inventory | EditMode-first TDD, justified runtime lanes, testability-refactor intake, version-gated UI fixtures, reload isolation and performance evidence limits have contract fixtures. |
| U-07 | U-03, U-05 | Web domain guidance and capability inventory | Behavior/component/API/browser distinctions, accessibility, server identity, failure states, compatibility and performance/deployment evidence boundaries have fixtures. |
| U-08 | U-04, U-05, U-06, U-07 | Controller UX, docs and source qualification | Standalone/controller handoffs remain correct; selected flavor appears consistently; deterministic fixtures prove gates; optional agent-behavior evaluations have separate scope and truthful qualification. |

U-02 inventories references with hidden-file-aware searches. Update `.gitignore` narrowly for artifacts/locks/staging; do not ignore the entire `.skill-tree/` tree. Check generated resource notices, package discovery, source-role detection, `installed_catalog`, schema/name validators, snapshot relevance and root shell/PowerShell entry points. Regenerate copies through the canonical builder only. Existing historical evidence never becomes fresh evidence merely because paths move.

Source verification uses the relocated equivalents of `npm run sync:check`, `npm run validate`, `npm run test:py`, `npm run test:node`, installer list/dry-run and `git diff --check`. Fixtures cover composition, local maintenance without source access, missing infrastructure, deduplicated high-priority foundation intake with/without an existing queue, ownership/recovery, pending validation, single-graph dependencies, group-scope limits, stale evidence and false-positive verification. Shared audit requirements receive cross-flavor parity checks. Generated outputs omit inactive framework/version branches; loop fixtures prevent repeated discovery. No policy expectation substitutes for an actual model-behavior evaluation.

Repository fixtures establish workflow behavior. An actual target-project UTF or browser scenario becomes a separate justified qualification unit only after the source implementation is ready and applicable owner scope exists. No live provider installation, game launch, app server or Player build belongs in the routine Skill Tree source test suite.

## Manual update checklist for the single existing target repository

No automatic migration, format converter, legacy alias or compatibility handler is planned. Future repositories receive the new format directly. The existing target repository is updated later, after the owner supplies the repository.

1. Inspect current status, owned Skill Tree files, queue/checkpoint/history, installed packages and repository rules; stop the active controller and preserve a reviewable backup.
2. Move the owned directory to `.skill-tree/`; update root pointers, owned commands and ignore entries without touching unrelated content.
3. Review and park/remove exact superseded packages/owned bridge blocks before installing colliding new package names. Install the chosen flavor and local maintenance bundle; verify receipts/content. Old packages without receipts require manual ownership review, never automatic adoption through `--force`.
4. Manually adapt the current queue/checkpoint/group metadata to the new documented schema, preserving task/run identities, required/deferred scope, stop reasons and outstanding acceptance. Reconcile unsupported state explicitly; never reset state to make validation pass.
5. Preserve original historical receipts and evidence. Record relocated reference mapping in a short update note; rebuild derived navigation/index data and mark unavailable/stale evidence honestly.
6. Run metadata/package/source consistency checks, review the diff and report the preserved next action. Resume work or execute product checks only under a later applicable request.

The checklist is documentation only. No existing target repository is updated during RND or source implementation.

## Decisions retained for implementation review

The design selects install-time project specialization, explicit dependency-driven profile refresh, one flavor per installation scope, stable logical operation names, focused TDD/characterization, explicit launch scheduling, bounded validation groups and UTF EditMode-first coverage. Stable compatibility predicates stay in the resolver/composer; final instructions contain concrete applicable recipes. Fast behavioral feedback continues inside a group; expensive compatible qualification closes the group. The exact recipe serialization and human-friendly rendering of validation sections remain implementation details subject to behavioral acceptance.

Mixed-domain automatic routing, cross-repository groups, launch-count quotas, automatic package upgrades, migration support, refresh watchers and extra TDD/group ledgers remain excluded. Grouping reduces redundant launches while preserving required evidence, developer scope and truthful completion.

Suggested documentation commit message: `docs: reconcile and simplify Skill Tree workflow plan`
