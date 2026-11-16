# Narrative relationship semantics

Use `depends_on` for a record that supplies a required normative fact or condition. The candidate snapshot must contain the required target. Keep optional relationships in a `relationships` list with `kind`, `target`, and optional `scope` and source locator. Existing sidecars without the list retain the current normative model.

| Kind | Source to target | Review use |
| --- | --- | --- |
| mentions | A record names another record | Candidate for wording, visibility or provenance review |
| features | A scene or work includes an entity | Inspect role, availability or expected appearance |
| occurs-at | An event or scene takes place at a location | Inspect spatial and period constraints |
| causes | A source event contributes to a later event or state | Review causal implications and uncertainty |
| precedes | A source event occurs earlier in world chronology | Review temporal order within compatible scope |
| adapted-from | A revised scene or work derives from an earlier source | Preserve identity and compare both contexts |

Optional targets can be historical, retired or missing. Report unresolved optional targets as review evidence with scope and reason. The review assigns normative edges explicitly when a missing target invalidates candidate canon. Keep craft links in the dramatic link contract and guessed prose references in the review report. An optional link can be meaningful while the normative dependency remains unsatisfied.
