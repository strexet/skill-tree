# Parallel Ready preview

Use the read-only parallel Ready preview for an explicit preview request in the current project. Use the bundled helper with the exact source checkout root. The helper resolves the canonical queue for a linked worktree.

```sh
python3 -B <skill-directory>/scripts/parallel-preview.py <project-root> --workers 2
```

Omit task selectors to scan the prioritized queue. The default limit is two workers. Repeat `--id T-…` for an exact comparison. A selector absent from the prioritized queue stops the preview. Use the Director menu and the `project-read` route for a registered shared workspace, then preview one approved project at a time.

Review the snapshot, ordered selection and deferrals. The helper prefers higher priority and keeps queue order for ties. The preview holds uncertain scopes, unfinished or unverified prerequisites, and known conflicts with selected or active work. The comparison uses declared `Touch` paths, check and recipe inputs, mapped package outputs, and declared exclusive resources. Shared read inputs can be used by more than one worker. Repository-specific generators, implicit consumers, and runtime effects require source review.

After a scoped task completes, the preview verifies the owning controller receipt, exact Git commit and original task definition from the applied completion event. The verified review scope keeps affected writes, check inputs and generated outputs reserved through any pending reviewed local merge. Independent tasks can be selected while related work remains held. Missing proof or a recipe that no longer matches the accepted check keeps the affected review scope on hold. Completed delivery retires the review scope and named resource claims remain authoritative.

Report exact task IDs, overlap paths or resource names, and check assertions to rerun against the combined candidate. Include a cross-task scenario when the source exposes a shared consumer or entry point. When multiple tasks feed the same generated binding manifests, assign package regeneration to the integrator after merging the source changes. Report absent evidence as a limitation.

The preview reads the queue and returns recommendations. A separate implementation request selects the work, establishes run authority and follows the normal run and review contracts.
