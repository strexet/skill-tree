<!-- GENERATED FILE; Source: skill-tree/common/references/documentation-output-contract.md; generator: skill-tree/scripts/sync-skill-references.py -->

# Documentation Output Contract

Required root discovery files: README.md and AGENTS.md. Preserve unrelated instruction content.

Required documents under skill-tree/documents/: project.md, technical.md, features.md, future.md, rules.md, repository-map.md, build-and-release.md, testing.md and dependencies.md. Create optional ux-ui-manifest.md, platform-integrations.md, backend-and-networking.md, data-and-persistence.md, analytics-and-monetization.md, localization.md, security.md, troubleshooting.md, references.md, decisions.md or glossary.md only when repository evidence justifies the subject.

Project documentation owns purpose, users, scope and constraints. Technical documentation owns architecture, startup, data flow and boundaries. Features owns current implemented/partial/configured/disabled behavior. Future owns planned work. Rules owns workflow and editing policy. Repository map owns physical layout. Build/release, testing and dependencies own the corresponding toolchain/validation/package contracts. Specialized subjects receive one canonical owner.

Documentation initialization explicitly creates the required queue, metadata manifest and index. Ordinary intake never initializes the complete documentation set. Audit verifies claims against implementation/configuration/tests, repairs drift in place and recreates missing required documents from evidence. Audits capture confirmed issues in Backlog with B- IDs, evidence, impact and acceptance direction; validation/implementation findings use Add Pending under the applicable workflow. No implicit promotion or implementation.

Read document-rules.md, workflow-metadata.md and applicable Unity safety before generation. Keep Pending Task Format before Pending Queue. Record unknowns, checks run and checks omitted. Persist compact audit coverage/findings through the helper; update manifest freshness. Snapshots remain an explicit separate operation.
