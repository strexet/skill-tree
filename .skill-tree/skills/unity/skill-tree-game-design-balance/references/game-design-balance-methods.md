# Balance methods by decision

Start from the [study contract](game-design-balance-study.md) and choose the smallest method that preserves the behavior under investigation. Name the rules, settings, starting state, clock and exposure. A deterministic paper check can establish outcomes under stated assumptions. Effective runtime settings, device response and participant behavior require matching observations.

| Research family | Question | Smallest useful output | Distinguishing check |
| --- | --- | --- | --- |
| Target and baseline | Which property matters under the selected mode and conditions? | Baseline measure, unit, scope, target and adverse outcome | Repeat the baseline from a comparable start and identify the result that would change the target. |
| Activity value and cost | When does the benefit justify effort, time, risk or forgone options? | One activity trace and a cost and benefit comparison | Compare matched opportunities and check a condition that changes the chosen option. |
| Chance and rare outcomes | How do typical rewards and long waits differ? | Distribution or enumeration tied to eligible attempts and an elapsed-time estimate when supported | Check a central outcome, a tail threshold and the effect of a guarantee or dependence between attempts. |
| PvE encounters | Can the player notice, respond and recover under the actual rules? | Encounter and input timeline with failure and restart points | Trace one normal response, one boundary and one legal alternative. Observe player responses before drawing a conclusion about readability. |
| Level difficulty and learning | Which ability must the player learn before the next demand? | First attempts, retries, hints and completion by practice stage | Compare eligible opportunities and distinguish a missing cue from a difficult execution. Observe unaided play for learning claims. |
| Pacing, pressure and respite | Does the schedule offer enough time for recovery and decisions? | Timeline of intensity, respite, cues and action opportunities | Compare a shifted or omitted event and observe whether the player uses the recovery interval. |
| Economy and resources | Which flows determine stock, affordability or shortage? | Stock and flow trace with caps and representative start balances | Compare typical and adverse event paths, rounding and saturation. For unattended gains check elapsed time, caps and resume behavior. |
| Progression and rewards | When does each eligible player obtain a useful new option? | Milestone and available-choice comparison across applicable save states | Check novice, stockpiled, returning and legacy-save states. Verify migration, cap behavior and one grant on replay when relevant. |
| Synergies and effect order | Which simultaneous or repeated effects change the outcome? | Event trace or combination table with the active ordering rule | Swap the order or repeat an action and compare state transitions and stacking limits. |
| Competition and metagame | Does a strategy or matchup advantage survive a matched comparison? | Matchup results indexed by side, initiative, map and experience when relevant | Swap sides or starting position, test a competing strategy and compare within skill strata. |
| Co-op and roles | Who can act, contribute or recover when another player is absent? | Per-participant opportunities, dependencies and waiting time | Change team composition or remove a participant and trace the next available decision and recovery. |
| Accessibility, controls and assists | Which input or cue condition affects access to the intended decision? | Cue, control, response and cancellation trace with candidate settings | Check just before, at and beyond the effective input boundary. Observe different devices or participants when responsiveness or comfort drives the decision. |
| Simulation and robustness | Does the result survive a different policy, start state or assumption? | Policy-specific results and held-out cases | Compare representative and adverse inputs under another plausible policy. Attribute simulated outcomes to the recorded policy. |
| Measurement and change validation | Did a measured difference survive comparable exposure after a change? | Event definitions, baseline and candidate cohorts, effect estimate, uncertainty and guardrail | Compare eligible denominators and matched strata. Examine conflicting aggregate and subgroup results before attributing a difference to the change. |

## Clock and exposure

For timing, identify the timestamp at the actual state writer, effective clock, pause and scaling behavior, resolution and inclusion rule. Test just below, at and just beyond the threshold. For discrete turns, record which transition consumes an opportunity. For unattended progress, compare elapsed time, rounding, pending effects and the saved reference time. An accelerated model shows behavior under the modeled clock. Verify the actual device or runtime when input sampling and update order matter.

For repeated observations, record the population with the opportunity to act, eligible attempts, numerator and denominator. Clustered attempts from the same player or match can change uncertainty. Compare cohorts with overlapping rules, start conditions and exposure. When the population mix shifts, report raw totals and within-group rates. A shared weighting can show whether composition explains an aggregate reversal. Preserve uncertainty and alternative explanations until suitable evidence supports attribution.

Keep paper calculations, observed settings, measured events and participant response linked to separate checks. Follow the method only as far as the available inputs support. A parameter sweep or telemetry workflow requires a separate project scope and available qualified inputs.

Use [design exercise routing](game-design-disciplines.md) when the requested artifact or lead operation needs clarification.
