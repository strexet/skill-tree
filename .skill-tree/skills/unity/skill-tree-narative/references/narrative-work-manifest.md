# Narrative work manifest

A project-owned JSON work manifest names one work and the exact context required for authoring. The convention is additive. Existing Markdown and sidecar records and snapshot identities remain valid.

| Field | Meaning |
| --- | --- |
| `schema_version` | Version of the project-owned work convention |
| `work_id` and `ip_id` | Stable identifiers for the work and the containing setting or IP |
| `continuity_id` | Continuity in which selected facts apply |
| `period` | Story period with a label and optional `anchor_event_id` and `elapsed` |
| `purpose` | Playable purpose and scope of the work |
| `canon_pin` | Object with `state` and `digest` |
| `predecessor` | Optional scoped continuation selection for an earlier work |

## Choose a baseline

- `empty` with a null digest is a deliberate first-work choice when no accepted baseline is required. Keep selected working drafts explicit and propose a first snapshot without a base.
- `accepted` requires the exact accepted snapshot digest. Resolve the digest through the existing context workflow and compare the snapshot continuity to the work continuity. Discover relevant records through the selected pin and normative dependencies. Do not infer a pin from recency.
- `unresolved` with a null digest records missing, unconfirmed or incompatible context. Retain the candidate digest and reason in review evidence when useful. Pause canon-dependent work and ask for the exact compatible pin. A working draft remains a separate candidate.

For a new work in an existing IP, retain established identities, choose the intended time and continuity, and pin only the verified accepted baseline. A predecessor selection may add `work_id`, `snapshot_digest`, `mode`, `outcome_ids` and `fact_refs`. A standalone work can omit predecessor selection. The manifest does not grant acceptance authority or replace the accepted snapshot.
