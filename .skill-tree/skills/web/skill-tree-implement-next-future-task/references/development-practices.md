# Development Practices

Keep behavioral slices small and verify domain examples, boundaries and failure paths before connecting broader adapters. Isolate clocks, randomness, filesystem/network effects and persistence through established project seams. Preserve architecture and pins; missing testability justifies only the scoped seam or one researched required descendant.

Review three distinct questions: the test executes, the test detects a relevant defect, and the oracle represents the intended acceptance. Derive cases from requirements or trusted references rather than exclusively from new implementation. Prefer small real collaborators and controlled adapters; mock external/time-dependent boundaries deliberately and contract-test consequential assumptions.

Use existing property-testing tools for suitable round-trip, idempotency or equivalence invariants and preserve failing seeds. Targeted mutation or explicit negative controls can test critical changed guards when value justifies cost; controlled temporary copies or guaranteed restoration protect task-owned work. No universal coverage percentage, mutation-score quota or optional-package installation follows automatically.

Persistence/interface changes include task-relevant compatibility, duplicate requests, interrupted writes, original-result recovery and cancellation/cleanup assertions. A transport timeout never proves a mutation failed. Existing static/type/lint/dependency checks provide actionable file/rule diagnostics; new infrastructure requires a concrete recurring defect.

Record first failures, environment and repeatability; diagnose flakiness instead of retrying until a pass appears. Golden/screenshot changes require review against intended behavior. Another model's approval, prompt parsing or helper fixtures never establish an independent oracle or actual agent-behavior qualification. No extra agent, external service or lifecycle hook is part of the default loop.
