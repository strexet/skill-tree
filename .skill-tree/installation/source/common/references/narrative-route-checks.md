# Bounded Narrative Route Checks

Set `NARRATIVE_ROUTE_CHECK` to the installed skill's `scripts/narrative-route-check.py` and `ROUTE_CONTRACT` to the selected project JSON file.

```sh
python3 "$NARRATIVE_ROUTE_CHECK" "$ROUTE_CONTRACT"
```

The checker accepts a single v1 contract or a corpus wrapper. Corpus case definitions reuse the base state registry and can override the model for a narrow adverse fixture. The Skill Tree source checkout supplies the example corpus at `.skill-tree/examples/narrative/route-traces.json`.

The checker reads JSON and evaluates declared actions, predicates, assignments and visit limits. Effects are typed assignments. A key marked `unique_effect` permits one grant during the trace. An `on_enter_once` effect applies only on the first entry to a node. Re-entry remains legal within the declared budget.

| Exit | Result |
| --- | --- |
| 0 | All traces match declared expectations, including expected adverse diagnostics. |
| 1 | At least one trace reaches an unexpected route result. |
| 2 | The input or contract cannot be interpreted. |

Inspect route and step IDs in diagnostic output. `unavailable-state` means a guard or required output lacks a value. `unavailable-action` means the action is missing from the observed available set. `offered-mismatch` compares the actual and expected offered sets. `state-mismatch` identifies a conflicting final value. `missing-exit` flags a non-playable stop. `visit-limit` and `repeated-unique-effect` distinguish excess revisits from repeated grants.

The checker preserves inputs and reports `declared-traces-only`. Engine behavior, narrative interpretation, complete graph reachability and canon authority remain separate claims.

## Prepare the producer replay record

Freeze the required case and trace IDs from the accepted plan before execution. Label normal cases and expected adverse controls. Record the exact work and continuity, accepted snapshot and applicable record revisions. Verify the accepted archive through the owning Narrative project and compare the work and continuity against the selected request. Retain any draft or foreign source identity with the narrower evidence boundary.

Record the checker version or content digest, attempt, invocation, environment, exit and exact retained output digest. Pin the bytes actually read for the base contract or model, the state registry and the traces or corpus wrapper. A case override also needs the exact case and selected model bytes. The checker reports declared-trace outcomes. The producer record supplies the input provenance and accepted-source verification.

Compare the returned case and trace IDs against the frozen required set. Name missing, unreached, unexpected or duplicate IDs as applicable. For each row retain the expected and observed diagnostic, the first known divergent step and later steps left unexecuted. An expected adverse diagnostic must match the planned code and applicable step. A missing required case holds coverage even when every returned row passed. Keep a separate consumer check for any Unity behavior.
