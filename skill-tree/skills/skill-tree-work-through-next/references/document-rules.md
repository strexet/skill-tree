<!-- GENERATED FILE; Source: skill-tree/common/references/document-rules.md; generator: skill-tree/scripts/sync-skill-references.py -->

# Document Rules

All Skill Tree-owned prose uses English. Exact identifiers, API symbols, file paths and code retain required syntax. Informal task requests become concise English intent without altering constraints.

Live documents describe current project entities, responsibilities, behavior and limitations declaratively. Planned outcomes reside in future.md. Remove historical commentary, previous-version comparisons and changelog narratives from live documents. Structured history records remain permitted evidence.

Replace pronouns with explicit subjects and references: developer, agent, target repository, selected task, queue, audit, validation profile or named component. Avoid ambiguous referents. Current source evidence outranks stale documentation. Mark unknown facts and validation gaps explicitly.

Use lowercase kebab-case owned filenames/directories. Required discovery filenames, package manifests and technical identifiers retain prescribed spelling. Keep one canonical owner for each contract. Avoid repeated instructions, empty sections and speculative detail.

The document validator reports rule, severity, file, line, column and offending source excerpt. Definite language, naming, personal-pronoun and historical-narrative violations are errors. Potentially ambiguous demonstratives and unquoted title-case labels receive review warnings; grammatical relative/complement clauses containing `that` and current-purpose constructions such as `may be used to` remain valid. Quoted labels, code, identifiers, comments and link destinations retain exact syntax. Default prose lint fails on errors; `--warnings-as-errors` and strict repository checks also fail on warnings. Source review resolves warning context and remains required for semantic correctness and English prose beyond character checks.
