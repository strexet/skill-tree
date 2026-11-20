# Game Design brief and rule decisions

Start with the requested design decision and the intended player experience. Inspect existing design, rule and tuning records for the selected scope. Use the [shared record contract](game-design-records.md) for revision, authority and evidence. Treat an approved rule, an observed build and a proposed change as separate records with exact references.

## Brief from a sparse concept

Write a short premise, audience and explicit constraints. Name the activity the player repeats, the system response, the goal and the next decision. Identify the core mechanics that cause the response and the reward or pressure that makes the loop worth repeating. Mark missing design facts as assumptions. Ask the author when an unresolved objective or constraint prevents a useful draft.

When a decision needs alternatives, compare at least two feasible directions under the same audience and constraint. Include retaining the current feature or removing a proposed feature when feasible. Explain the distinct player decisions, implementation cost and likely failure conditions. Choose one representative interaction and an observation that would change the recommendation. Use an illustrative sketch, paper sequence or small prototype question suited to the unresolved design issue.

## GDD views

Choose the views that answer the request. Use a single new or revised page when one page contains the necessary decision.

| Design question | Working view |
| --- | --- |
| What experience does the concept promise? | Audience, intended feeling, activity, important constraint and comparable concept slices |
| What occupies the player and what occurs between inputs? | Core activities, system processes, session goals and progression |
| How does the rule operate? | Trigger, conditions, state transition, clock, example and exception |
| Where does the player learn or use the rule? | Introduction, safe practice, complication, combination and rest |
| What earns a reward and what can the player afford? | Sources, costs, pacing, returning-player conditions and failure pressure |
| What makes the controls understandable and responsive? | Cue, input, response, cancellation, recovery and retry timeline |
| What observation would resolve the decision? | Hypothesis, competing explanation, setup and a decision threshold |
| What did the owner decide and why? | Revision, selected and declined options, rationale, affected placements and open questions |
| What belongs in the playable slice? | Essential experience, provisional assets, effort and the most consequential assumption |

## Repair an ambiguous or conflicting rule

Locate the current rule, decision owner and tuning authority. Identify the exact conflicting statements, the placements at risk and any valid exceptions. Preserve adjacent rules. Reconcile unambiguous wording within the approved intent. Record an alternative as a proposal and route a change of intent or approved value to the owner.

Write the initial state, trigger, guard, state change and observable result. Specify when feedback appears and how repeated, cancelled or simultaneous actions resolve when relevant. Give one normal trace and one boundary trace with concrete inputs. Include an unchanged control when the claim concerns a difference. A technical observation outside the accepted behavior goes to the owner of the effective configuration.

Choose the clock for each behavior. Continuous controls use active play time and name pause and time-scale behavior. Discrete actions use the relevant turn, tick or event and name ordering when multiple events coincide. Unattended progress uses elapsed time under the project's persistence, cap and resume rules. A hybrid rule identifies the clock at each transition. Name the unit and authoritative parameter reference. Keep copied numeric values in traces tied to the referenced revision.

Ask an independent reader to derive the normal and boundary results from the same inputs. Resolve divergent predictions by locating the omitted condition, ambiguous term or owner decision. Record the agreed observable outcome and the cheapest suitable check.

## Deliver the selected document

Return the brief or revised rule, exact decision and supporting assumptions, open questions, expected observation and owner. A placement handoff names the rule revision, scene or system and the application question. A balance handoff names the rule or placement revision, the tuning authority and the parameter and evidence question. Verified configurations, acceptance decisions and runtime results require matching evidence. Standalone document work ends with the requested document and current decision state.

Use [design exercise routing](game-design-disciplines.md) to choose a focused activity, artifact and check for the requested design question.

Use the [focused playtest protocol](game-design-playtest.md) for a design decision about comprehension, route discovery or game feel.
