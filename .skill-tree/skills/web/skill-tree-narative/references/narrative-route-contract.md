# Declarative Quest Route Contract

The v1 JSON contract describes expected behavior for a finite set of named traces. Select an explicit draft or canon pin before review. The runtime remains authoritative for executable behavior.

## Document and route records

- Set `schema_version` to `1`, declare `work_id`, `continuity_id`, and one source identity. Use `source.draft_id` for an explicit synthetic or working draft. Use `source.snapshot_sha256` for an exact accepted snapshot. Record the portable `state_registry` locator.
- Define an `entry` node and a map of `nodes`. Keys use lowercase portable narrative IDs. A node declares `actions` by stable ID. Each action has one `target`, an optional `when` predicate and optional typed `effects` assignments. A terminal or playable continuation node declares `exit` as `terminal` or `continuation` and has no actions.
- A node may declare `on_enter_once` assignments. The checker applies the declared assignments once per node per trace after transition effects. A route budget counts entries independently of effects. A legitimate revisit must be declared in `visit_limits`, which maps node IDs to positive maximum counts. The default is one visit.
- Each trace declares `id`, `initial_state`, `steps`, `expected_state` and `expected_exit`. Every step declares `node` and the set of expected `offered` actions. A nonfinal step selects one `action`. A final step reaches the expected exit. Extra state claims outside the registry have unknown coverage and are excluded from a passing assertion.
- The trace can name `exposure` sources and `interpretation` decisions for editorial review. Neither field changes routing. Chronology and authorial truth remain with the selected story records. A playback trace expresses player order only.

## Predicates and state

An optional predicate contains exactly one form. A leaf has `key`, `op` and `value` fields. The supported operations are `eq`, `ne`, `lt`, `lte`, `gt` and `gte`. Ordering applies only to integer keys. A compound predicate has a single nonempty `all` or `any` array. A predicate containing both operators is malformed. `all` requires every member and `any` requires at least one. Every operand needs a known value even when another operand determines the Boolean result.

Use declared Boolean, enum or bounded integer values. Explicit `false` differs from an absent key. A missing key needed by a predicate produces unavailable state. A key omitted from all assertions can remain outside the observed scope. Trace expected state names exactly the values under test, and a contradictory expected value produces a failing route result.

Begin with the `route-contract.example.json` sample. The sample records the log discovery and the lift. Add a separate trace that skips the relay log and selects the cooler to compare exposure and ending state without revising the earlier trace. The log may affect Ilya's line without changing the available selector actions. A scene omitted from a route is neither shown nor interpreted by implication.
