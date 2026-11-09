# Technical Architecture

The source is a Node.js installer/composer and Python workflow helpers with Markdown instruction packages. [Installation architecture](installation-architecture.md) owns the composition, activation, receipts and local-manager design.

The composer combines `.skill-tree/templates/operations.json`, locked invariants, common resources and domain sections through `.skill-tree/config/flavors.json`. The generator emits standalone representative packages under `.skill-tree/skills/<flavor>/`. The installer composes project-specific profiles and copies packages to provider destinations.

The installed `SKILL.md` entrypoint routes an agent to bundled contracts and helpers. Helpers select work, validate supplied evidence and record state; agents inspect source, make authorized edits and execute checks. Helpers do not establish actual model adherence.

Task definitions reside in `.skill-tree/documents/future.md`. The derived index, authoritative progress and retained controllers reside in `future.json`. [Workflow metadata](../common/references/workflow-metadata.md) owns schemas and helper payloads. [Run workspaces](../common/references/run-workspaces.md) owns canonical queue routing and machine-local locators.

The installer profile contains machine-bound project identity. A copied profile requires explicit verified `manager.js --rebind` before ordinary verification. A retained schema-3 queue requires explicit recovery of the matching machine-local locator. Completed delivery locators can be omitted while every unfinished mapping remains required. [Installation](install.md) owns the bootstrap commands and boundaries.
