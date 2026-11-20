# Game Design records and revisions

Use readable entries in the consuming project's existing brief, rule documents, atlas, tuning table and evidence reports. A new project can begin with `design/game-brief.md`, `design/rules/`, `design/mechanics-atlas.md` and `design/studies/`. Keep project-specific descriptions, assets, scenes, save states and study inputs in the consuming project. The shared mechanics collection owns reusable patterns and sourced editorial records.

## Identity and ownership

Give each record a stable ID within the named project or shared collection and a revision for the content under review. Include the type, owner and locator. A reference such as `paper-race/boost-reserve@2` identifies one rule revision. A second project can use the same local ID under a distinct scope. An unqualified local ID resolves only within an explicitly identified project.

Pin a repository-relative path with a heading or record anchor and the exact Git commit. For a record outside Git, keep the reviewed copy and the SHA-256 digest of the retained bytes in the owning project. Identify the exact file or the delimited record bytes covered by a digest. Verify the scope, ID, revision and pin when reading a reference. An older pin identifies historical evidence even after a current revision moves. Report an unavailable pin with the missing source and the owner responsible for source access.

| Record | Owner and required context |
| --- | --- |
| Source | The curator records the collection scope, edition or version, locator, cited material, access and reuse terms. Unknown provenance or terms remain explicit. |
| Pattern | Mechanics records a reusable action or process, aliases, applicable conditions, control, clock and exact source references. A local proposal remains in the consuming project until editorial acceptance. |
| Rule | Game Design records the intended player experience, normal outcome, boundary case, exception, decision state and exact pattern references. Each parameter names one authoritative source, owner, unit and clock. |
| Placement | Mechanics records the exact rule revision, scene, mode or system, activation point, role, conditions, exception and applicable canon or asset pins. Record the observed evidence and unexamined locations. |
| Study | Balance records a distinct study ID and revision, decision question, rule and placement pins, baseline, candidate, method, measure, unit, clock, guardrail, stopping condition and check references. |
| Check | The assigned observer or test owner records a separate ID and revision, expected outcome, required inputs and start conditions. Executed checks add the attempt, actual environment, build or source revision, observed outcome, verdict and evidence locator. |

The rule owns behavior and the reference to the tuning authority. An approved value belongs in the rule when the rule owns the parameter. When an existing tuning table owns the value, record the exact table revision and parameter in the rule. Balance may quote versioned values as inputs to a comparison. The study identifies the effective configuration observed in each environment and directs discrepancies to the owner of the selected setting.

State time in the relevant clock and name the time unit. A rate per second of active control, a cost per action and a gain per minute of offline elapsed time describe different conditions. Include the denominator and eligible attempt count when the metric depends on exposure.

## Proposals and accepted changes

1. Record the proposal ID, proposer, exact reviewed base, candidate change, affected parameter authority, likely placements and reason. Retain the current approved revision as the baseline during exploration.
2. Record the actual owner decision with the selected proposal, decision reference and reason. On rejection or deferral, keep the proposal and decision in the study or design record. The accepted baseline continues to govern.
3. Apply the accepted change through one guarded update at the authoritative location. Use the owning system's conditional write against the exact reviewed revision or give one authorized writer exclusive access from rereading that revision through recording the durable change and proposal ID. Record the resulting rule and tuning revisions together. When the owning location supports neither guard, hold adoption until the owner establishes a single write path.
4. A base mismatch leaves the authority intact and preserves both proposals and the earlier acceptance. Hold the stale proposal for reconciliation against the new base and an owner decision on the resulting change. A repeated delivery checks the recorded proposal ID and resulting revisions before attempting a write. If a handoff stopped during adoption, keep that location held until the authorized writer reconciles the authoritative bytes and original proposal. Complete only the remaining update under the same revision guard.
5. Mark placements and checks that depend on the changed fact for review. Retain the exact earlier references and observations. Identify unknown consumers with a search area and owner. A revert creates a new reviewed change with matching rule, tuning and affected placement references.

## Evidence and handoffs

A planned check records the expected observation and target conditions. Add the actual environment and observed outcome only after execution. Preserve attempt IDs, unexpected results, unreached cases and unavailable evidence. Record the environment suitable for the claim, such as a paper calculation, inspected configuration, Editor session, player build or human observation. Re-execution adds an attempt linked to the earlier one.

The producer supplies the accepted record pin, relevant fact, affected placements and expected observation. The consumer returns the source actually used, the observed artifact or setting revision, the check attempt, environment and verdict. For a Director handoff, include the corresponding episode, assignment and child run identities when available. Compare expected and consumed bytes before accepting the dependent result. A changed consumed fact reopens the affected check. Standalone records use the same project references and evidence and can finish within the consuming project.
