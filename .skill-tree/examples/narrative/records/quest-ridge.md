# Emergency Selector

| Field | Scope |
| --- | --- |
| Identity | `quest-ridge` in the `work-ridge` standalone pilot. |
| Purpose | Let the player prioritize rescue, medicine or a risky attempt under a single-cycle power limit. |
| Entry | Enter the lift house during the night-shift emergency. The reserve pack, selector and Ilya are present. |
| Optional stage | `scene-relay` reveals the trip cause through the relay log. Skipping the log preserves the same three selector actions. |
| Decision | Power the lift, power the cooler or try the refuge heater. The heater can isolate the pack. |
| Exit | Every implemented outcome reaches `scene-report`. Closing the logbook ends the standalone pilot. |
| Evidence | `quest.ink` owns current dialogue and outcomes. Review of player comprehension remains a future observation. |

| Action | Immediate effect | Visible consequence |
| --- | --- | --- |
| Lift rescue | The pack is spent and the crew reaches safety. | Night workers step down and the nurse removes warmed vials. |
| Clinic cooling | The pack is spent and the medicine stays cold. | The clinic thermometer turns green and the crew waits in the refuge. |
| Refuge heater | The damaged lead isolates the pack. | The fuse blows and the refuge stays dark. |

The card describes implemented behavior. A dedicated refusal and a longer story continuation are possible design questions outside the current standalone scope. The optional log adds knowledge of the trip cause. The log changes a later line from Ilya and supplies no mechanical prerequisite to selecting a circuit.
