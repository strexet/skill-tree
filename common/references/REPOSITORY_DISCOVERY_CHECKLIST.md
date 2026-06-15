# Repository Discovery Checklist

Use this checklist before writing documentation.

## Repository Shape

- Repository root and Git status.
- Source directories and language/framework boundaries.
- Entry points for apps, services, packages, tools, jobs, or libraries.
- Package manifests, lock files, dependency managers, and runtime versions.
- Build scripts, release scripts, CI workflows, containers, deployment files, and generated artifacts.

## Current Behavior Evidence

- Main features and their owning files.
- State, storage, persistence, migrations, and data contracts.
- External APIs, SDKs, services, queues, analytics, billing, auth, or platform integrations.
- CLI commands, environment variables, configuration files, and secrets handling.
- Error handling, retry behavior, cancellation, recovery, logging, telemetry, and observability.

## Validation Evidence

- Unit, integration, end-to-end, smoke, lint, static analysis, and manual validation commands.
- Test fixtures and representative data.
- Known skipped or disabled tests.
- Build and release constraints.

## Documentation Evidence

- Existing README and docs.
- Agent instructions and repository rules.
- Current task queues, roadmaps, inline task comments, and issue notes.
- Stale claims, unsupported assumptions, duplicated docs, and missing source references.

## Exclusions

- Do not treat generated, vendored, cache, build output, coverage, dependency, or local-only files as source-of-truth unless the repository explicitly owns them.
- Do not infer behavior from names alone; verify with code, tests, configs, or docs.
