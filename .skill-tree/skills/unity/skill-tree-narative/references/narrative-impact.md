# Narrative Change Impact

Select exact proposed record IDs in the working drafts or in an accepted snapshot. Ordinary impact output reports the transitive reverse reach of normative dependencies and unresolved required edges. Set `NARRATIVE_HELPER` to the installed skill's `scripts/narrative-state.py` and `PROJECT` to the selected project root. Set `CANDIDATE` to the exact accepted snapshot digest for a pin comparison.

```sh
python3 "$NARRATIVE_HELPER" impact "$PROJECT" --drafts --ids law-pack --extended
python3 "$NARRATIVE_HELPER" impact "$PROJECT" --snapshot "$CANDIDATE" --work-pin works/work-ridge.json
python3 "$NARRATIVE_HELPER" impact "$PROJECT" --snapshot "$CANDIDATE" --ids law-pack \
  --work-pin works/work-ridge.json --dramatic review/intent.json --suspected review/suspected.json
```

The three optional input flags are repeatable and resolve repository-relative files in the target project. Any input flag enables extended output. Reports remain read-only. Omit `--ids` for a pin-only comparison between accepted snapshots. Dramatic and suspected relationships require selected IDs. The helper can compare a snapshot whose records are all retired.

| Output | Meaning |
| --- | --- |
| `normative` | Selected change candidates, transitive dependents and closure validity. A missing required edge makes the extended command exit with status 1 after printing the report. |
| `optional` | Recorded sidecar relationships incident to the selected or dependent records, with provenance, declared scope and target status. An unresolved optional target remains a review question. |
| `dramatic` | Explicit authoring intent records incident to the affected set. Endpoint status reports scene membership in the selected records. The helper marks work, continuity and route scope unverified. Specified beat IDs require source review and carry the same unverified status. |
| `suspected` | Reviewer annotations remain unverified, with prose evidence and unanswered questions. Suspected links do not join normative traversal. |
| `work_pins` | Exact current work pins and hypothetical comparison to the selected accepted snapshot or provisional draft scope. The current accepted snapshot remains available. |

A work pin input follows the work manifest. An accepted pin resolves the full historical snapshot and must match the work continuity. Incompatible continuities are reported without comparison. For a proposed move between accepted snapshots, compare the full compositions. Include changed, added and removed records, as well as changes to retirement status, even when the records fall outside the selected impact IDs. Identify unchanged reverse dependents from both snapshots. A draft set has no established continuity. The provisional draft comparison stays scoped to the selected IDs and relevant dependents. A record absent from a partial draft scope is unavailable for comparison. The report identifies dependents that require review and leaves work pins intact.

A dramatic input is one JSON intent object from the dramatic-link contract. The input supplies source and target scene IDs, an optional beat at each endpoint, relation and scope. A suspected input is an object with a `links` array. Each annotation supplies stable `source` and `target` IDs, a short `evidence` locator or observation, a `question` and optional `scope`. Report missing context as a question. A recorded link supplies a review lead and no authority to rewrite canon.
