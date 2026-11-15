# Development Practices

Keep behavioral slices small and verify domain examples, boundaries and failure paths before connecting broader adapters. Isolate clocks, randomness, filesystem/network effects and persistence through established project seams. Preserve architecture and pins; missing testability justifies only the scoped seam or one researched required descendant.

Review three distinct questions: the test executes, the test detects a relevant defect, and the oracle represents the intended acceptance. Derive cases from requirements or trusted references rather than exclusively from new implementation. Prefer small real collaborators and controlled adapters; mock external/time-dependent boundaries deliberately and contract-test consequential assumptions.

Use existing property-testing tools for suitable round-trip, idempotency or equivalence invariants and preserve failing seeds. Targeted mutation or explicit negative controls can test critical changed guards when value justifies cost; controlled temporary copies or guaranteed restoration protect task-owned work. No universal coverage percentage, mutation-score quota or optional-package installation follows automatically.

Persistence/interface changes include task-relevant compatibility, duplicate requests, interrupted writes, original-result recovery and cancellation/cleanup assertions. A transport timeout never proves a mutation failed. Existing static/type/lint/dependency checks provide actionable file/rule diagnostics; new infrastructure requires a concrete recurring defect.

Record first failures, environment and repeatability; diagnose flakiness instead of retrying until a pass appears. Golden/screenshot changes require review against intended behavior. Another model's approval, prompt parsing or helper fixtures never establish an independent oracle or actual agent-behavior qualification. Qualified core governance uses the declared resolver, critic and arbiter roles. Additional unrelated agents, external services and lifecycle hooks require a concrete declared workflow purpose and applicable authorization.

## Direct replacement

When the installed `direct-replacement` policy is enabled, trace the affected consumer from the normal entry point during planning. Switch the affected consumers to the intended implementation and retire the superseded path in the same scope. Verify the normal entry point and check the current registration, configuration and callers for aliases, fallbacks and competing active paths introduced or retained by the change.

Explicit owner instructions and matching API locks can require scoped coexistence. Record the affected consumers, supporting evidence and retirement condition for an authorized transition. Use the separate API lock gate for protected contracts. Keep historical ArtWorkshop bundles and explicit rollback under the ArtWorkshop contracts.

In PR review, a version-like name prompts source inspection. Record a blocking observation when the current changed behavior has a verified active path that violates the rule. Record the missing fact when evidence is inconclusive.

## Recurring network refresh

When the installed `network-polling` policy is enabled, establish the required freshness and the mechanisms available from the source before choosing a recurring request. Use a user-triggered or lifecycle request when a single request meets the freshness target. Use a suitable existing subscription when the consumer needs continuous updates.

For justified polling, record the freshness target, the interval, the responsible owner and the start and stop conditions. Verify that errors allow recovery, shutdown stops refresh and slow requests cannot overlap. A timer prompts inspection of the caller and request path. A recurring network request with a verified policy violation blocks review. Record the missing fact when evidence is inconclusive.

The rule applies to changed behavior. Bounded local process waits, on-demand Director status requests and local 3D cleanup follow the applicable workflow lifecycle checks.
