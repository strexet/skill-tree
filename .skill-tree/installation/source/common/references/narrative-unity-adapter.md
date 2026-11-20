# Ink and Unity Adapter

Choose one writer for every state key. Ink owns exact authored dialogue, flow-local evidence and short-lived choices. A Unity host owns persistent game-system results when configured. An adapter translates a stable narrative choice to a typed host request, then records the acknowledged result as input to later story decisions.

## Request and result

- Bind work, quest, scene and choice IDs to a stable command or query ID. Name argument types, authorized caller, owner and save version.
- Give a unique effect a stable transaction key that includes the campaign occurrence. A repeated command returns the recorded result without writing a second effect.
- Apply gameplay writes only on the host acknowledgement. Ink displays an explicit pending, unavailable or failed result when the host cannot complete a command.
- Bind save, adapter and story versions at a checkpoint. An absent saved key requires explicit migration. An incompatible save offers informed restart or preserves the original for a compatible build.
- Obtain the exact editor, packages, host event contract and target save system before an actual Unity implementation.

The fixture is declarative and proposes a host ownership split. Standalone Ink test results establish behavior of the standalone pilot.

When a host result differs from the accepted rule, compare the exact adapter, rule and placement pins, configured source and applied overrides. Record each candidate writer in order, the ordinary choice or action, acknowledgement and initial and final state. Report the first divergent write or missing acknowledgement and the subsequent unexecuted assertions. Pin save versions and selected host bindings. A proposed design change uses the design owner's decision. A competing writer or stale import binding returns to Unity.

A project-owned episode check drives the same input, adapter request, acknowledgement and authoritative write used in the selected scene. For an expected one-time effect, record the occurrence key and count before input, after first success and after the replay or restored checkpoint. Record the first violated prerequisite or wrong writer and report later unexecuted checks. A passing declared Narrative trace supplies the expected route and state pins for the selected check.
