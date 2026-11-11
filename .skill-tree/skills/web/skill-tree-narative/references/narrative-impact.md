# Narrative Change Impact

Select exact proposed record IDs in the working drafts or in an accepted snapshot. Ordinary impact output reports the transitive reverse reach of normative dependencies and unresolved required edges.

```sh
python3 .skill-tree/common/scripts/narrative-state.py impact PROJECT --drafts --ids law-pack --extended
python3 .skill-tree/common/scripts/narrative-state.py impact PROJECT --snapshot DIGEST --ids law-pack \
  --work-pin works/work-ridge.json --dramatic review/intent.json --suspected review/suspected.json
```

The three optional input flags are repeatable and resolve repository-relative files in the target project. Any input flag enables extended output. Reports remain read-only.

| Output | Meaning |
| --- | --- |
| `normative` | Selected change candidates, transitive dependents and closure validity. A missing required edge makes the extended command exit with status 1 after printing the report. |
| `optional` | Recorded sidecar relationships incident to the selected or dependent records, with provenance, declared scope and target status. An unresolved optional target remains a review question. |
| `dramatic` | Explicit authoring intent records incident to the affected set. Endpoint status reports scene membership in the selected records. Work, continuity and route scope remain unverified. A beat is unverified when the selected record metadata does not establish the beat. |
| `suspected` | Reviewer annotations remain unverified, with prose evidence and unanswered questions. Suspected links do not join normative traversal. |
| `work_pins` | Exact current work pins and a hypothetical comparison if a work moved to the selected record scope. The existing accepted revision remains available. |

A work pin input follows the work manifest. An accepted pin resolves the full historical snapshot and must match the work continuity. Incompatible continuities are reported without comparison. A draft set has no established continuity and the comparison remains provisional. A record absent from a partial draft scope is unavailable for comparison. Compare revisions for both current and historical reverse dependents. The report identifies unchanged dependents that still require review and does not update a work pin.

A dramatic input is one JSON intent object from the dramatic-link contract. The input supplies source and target scene IDs, an optional beat at each endpoint, relation and scope. A suspected input is an object with a `links` array. Each annotation supplies stable `source` and `target` IDs, a short `evidence` locator or observation, a `question` and optional `scope`. Report missing context as a question. A recorded link supplies a review lead and no authority to rewrite canon.
