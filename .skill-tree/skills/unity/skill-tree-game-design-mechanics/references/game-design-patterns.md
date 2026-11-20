# Mechanics collection and source coverage

The seed collection contains three original design examples. Source `skill-tree-mechanics/original-seed@1` records the Skill Tree editorial material, `game-design-patterns.md` and the applicable Skill Tree repository license. The descriptions represent reusable concepts. Concrete game settings and observations belong to the consuming project. Follow the [record contract](game-design-records.md) for new IDs and citations.

## Bounded reserve

| Field | Record |
| --- | --- |
| Identity | `skill-tree-mechanics/bounded-reserve@1` |
| Aliases | English `limited reserve`, `charge` in resource vocabulary. Spanish `reserva limitada`. |
| Rule | A resource grant raises a stock up to a ceiling. Spending lowers the stock and frees capacity. The grant and spend can be triggered by an action or an autonomous update. |
| Control and clock | Follow the grant or spend event in the host rule. A cap can apply in continuous, discrete or unattended systems. |
| Feedback and prerequisites | Expose the current stock and capacity at the decision point. Define the source, eligible spend and overflow treatment. |
| Limitation and counterexample | A persistent full reserve can remove a reason to seek more grants. An uncapped score can increase indefinitely and lacks the capacity decision. |
| Source | Original seed, [bounded reserve record](#bounded-reserve). |

## Hold to boost

| Field | Record |
| --- | --- |
| Identity | `skill-tree-mechanics/hold-to-boost@1` |
| Aliases | English `hold boost`, `charge` in sustained movement vocabulary. |
| Rule | Holding an eligible control starts a movement increase. Continuing the hold consumes a reserve on the active clock. Release or depletion ends the increase. |
| Control and clock | Continuous hold with active play time. Start, release and depletion produce explicit state boundaries. |
| Feedback and prerequisites | Need a sustained control, a movement change and the available reserve. Indicate active boost and the end of the effect. Haptic feedback remains an unspecified option. |
| Limitation and counterexample | A long hold can close access for some players. A one-shot dash triggered on press follows a different rule with an independent end condition. |
| Source | Original seed, [hold to boost record](#hold-to-boost). |

## Spend to reveal information

| Field | Record |
| --- | --- |
| Identity | `skill-tree-mechanics/spend-to-reveal@1` |
| Aliases | English `paid reveal`, `hint token`. |
| Rule | An eligible request spends a limited resource and reveals a fact that changes a following decision. A rejected request preserves the prior state. |
| Control and clock | Discrete interaction at a defined decision point. Specify any concurrent request ordering in the project rule. |
| Feedback and prerequisites | Show the cost, available stock and revealed information. Define the information boundary and the effect of repeating a request. |
| Limitation and counterexample | A reveal with limited decision value can waste a scarce resource. A fixed free tutorial prompt has no resource choice. |
| Source | Original seed, [spend to reveal record](#spend-to-reveal-information). |

## Documented sample

The coverage ledger contains two primary examples per interaction group. Overlap entries describe additional facets of the same example. Versioned rules and mode names identify the examined editions. For live documentation, each `@1` source record identifies the named page and section inspected on 2026-11-19. Shared entries contain original generic descriptions and source links. Source text, images, assets and project materials remain in the source publications or consuming projects. The sample establishes documented behavior in the named case.

| Interaction group | Source record and edition | Examined section | Overlap and claim scope |
| --- | --- | --- | --- |
| Continuous control | `car-racing@1`, Farama Car Racing v3 continuous | Action Space | Signed steering and separate accelerator and brake inputs. [Farama Car Racing](https://gymnasium.farama.org/environments/box2d/car_racing/#action-space) |
| Continuous control | `lunar-lander@1`, Farama Lunar Lander v3 continuous | Arguments and Notes | Main and lateral thrust controls. Orientation-dependent torque is a caveat of the documented implementation. [Farama control arguments](https://gymnasium.farama.org/environments/box2d/lunar_lander/#arguments), [Farama implementation notes](https://gymnasium.farama.org/environments/box2d/lunar_lander/#notes) |
| Timed execution | `mania-hold@1`, osu!mania with the documented lazer default | Gameplay and Judgement | Press and release times plus sustained state. Continuous hold overlaps the execution clock. [osu!mania hold notes](https://osu.ppy.sh/wiki/en/Gameplay/Hit_object/Hold_note) |
| Timed execution | `osu-slider@1`, osu! standard slider | Slider description and ticks | Pointer tracking and held input at checkpoints. Continuous spatial control overlaps timing. [osu! sliders](https://osu.ppy.sh/wiki/en/Gameplay/Hit_object/Slider) |
| Discrete decisions | `fide-standard@1`, FIDE Laws effective January 2023 | Articles 1 and 3 | Alternating moves and legal positions in over-the-board chess. [FIDE Laws of Chess](https://handbook.fide.com/chapter/e012023) |
| Discrete decisions | `catan-base-2020@1`, CATAN base rules English 2020 | Resource Production, Trade and Build | Turn order and shared roll-based production followed by resource decisions. [CATAN base rulebook](https://www.catan.com/sites/default/files/2021-06/catan_base_rules_2020_200707.pdf#page=4) |
| Simultaneous play | `diplomacy-orders@1`, Renegade rulebook file revision 6 | Overview, Order Writing and Order Resolution | Private orders revealed together and resolved as a batch. Resolution is a discrete phase. [Renegade Diplomacy rulebook](https://renegadegamestudios.com/content/File%20Storage%20for%20site/Rulebooks/Diplomacy/DiplomacyRGS_Rulebook_v6_LR.pdf#page=6) |
| Simultaneous play | `frozen-synapse@1`, Mode 7 PC release listing | `About This Game` | Preview before committing and simultaneous execution of both plans. Resolution follows a discrete turn. [Mode 7 Frozen Synapse](https://store.steampowered.com/app/98200/Frozen_Synapse/) |
| Asynchronous play | `lichess-correspondence@1`, Lichess correspondence mode | Time Control and returning to ongoing games | Turn-based play spread over hours or days. The move sequence remains discrete. [Lichess mode guide](https://lichess.org/page/blind-mode-tutorial) |
| Asynchronous play | `trackmania-ghost@1`, Trackmania leaderboard ghosts | Leaderboard ghosts | Load a recorded performance in a later session. The documented in-game feature requires active Club Access. Live driving overlaps continuous control. [Trackmania leaderboard ghosts](https://doc.trackmania.com/play/watch-replays/#leaderboard-ghosts) |
| Autonomous systems | `factorio-belt-signal@1`, Factorio circuit-enabled transport belts | Devices and pulse and hold options | Sensor transitions follow simulation ticks without fresh control input. [Factorio circuit network](https://wiki.factorio.com/Circuit_network#Devices) |
| Autonomous systems | `openttd-load-orders@1`, OpenTTD Orders manual for 0.7.0 and later | Giving Orders and Full load | A vehicle follows the route and waits for a cargo condition. The condition combines a discrete check with autonomous execution. [OpenTTD orders](https://wiki.openttd.org/en/Manual/Orders#full-load) |

Continuous samples leave assisted or alternative input modes open. Timed execution samples leave audiovisual and haptic accessibility open. Discrete samples leave solo planning and uneven turn schedules open. Simultaneous samples leave live cooperative control open. Asynchronous samples leave shared-world contributions and unattended progression open. Autonomous samples leave forecasting, unattended recovery and persistent player economy effects open.

## Reusable patterns from the sample

Each ID belongs to `skill-tree-mechanics` and uses revision 1. The source column refers to the coverage ledger. The clock and contrast describe conditions for a useful match.

| Pattern ID and search terms | Action or process and observable result | Condition and contrast | Source |
| --- | --- | --- | --- |
| `analog-course-correction`, steer and pace | Apply signed steering and propulsion to correct a heading while controlling speed. The resulting path and speed show whether the correction worked. | Continuous input during movement. A choice between fixed routes changes the decision unit. | `car-racing@1` |
| `thrust-and-attitude`, orientation control | Adjust main thrust and lateral thrust to approach a target while controlling orientation. Track position and rotation together. | Continuous input with direction-dependent motion. A steering axis constrained to the ground has a different consequence. | `lunar-lander@1` |
| `timed-hold-release`, long note | Start the held action at a cue, maintain the held state and judge the release against an end cue. | Timed event windows. An action that ends automatically lacks a judged release. | `mania-hold@1` |
| `follow-timed-path`, moving checkpoint | Maintain control while following a target. Evaluate the held state and position at timed checkpoints. | Timed continuous tracking. Holding one fixed control can succeed without following the spatial target in a nearby rule. | `osu-slider@1` |
| `alternating-legal-action`, sequential turn | An eligible actor commits one legal state change and passes the decision to the other actor. | Discrete eligibility. Joint submissions can reveal both intentions after each decision is committed. | `fide-standard@1` |
| `supply-before-spend`, production phase | Resolve the resource grant at turn start, then allow eligible exchange and purchase. Updated holdings inform the spending decision. | Discrete phases with a defined supply rule. An independent periodic grant can arrive outside a player's decision turn. | `catan-base-2020@1` |
| `sealed-joint-resolution`, hidden orders | Accept private decisions and reveal the submitted orders for joint resolution. The resolution exposes outcomes and conflicts. | Shared discrete order boundary. Revealing one actor's result before another actor chooses changes the information available. | `diplomacy-orders@1` |
| `preview-then-commit`, simultaneous plan preview | Let a player preview a draft order before committing. Resolve the committed plans together and show the observed outcome. | Discrete planning followed by simultaneous execution. A draft preview has a different evidence status from the committed result. | `frozen-synapse@1` |
| `delayed-turn-handoff`, correspondence turn | Carry the current game state and actor eligibility across sessions until the eligible actor replies. | Discrete move sequence with elapsed-time scheduling. The immediate session uses a different participation window. | `lichess-correspondence@1` |
| `recorded-run-reference`, replay benchmark | Load a previous performance as a reference during a new run. Compare current action with a recorded path or timing. | Asynchronous evidence on a shared course or task. A live opponent can respond to the current action. | `trackmania-ghost@1` |
| `arrival-pulse`, entry event | Emit a brief signal when an item arrives. A later update with the item still present has no new arrival. | Autonomous ticks and a defined entry event. An occupancy signal follows continuing presence. | `factorio-belt-signal@1` |
| `occupancy-level`, presence signal | Maintain the signal for the duration of occupancy. A reader can observe the state after the arrival tick. | Autonomous ticks and a stable observed condition. An arrival pulse can disappear while occupancy continues. | `factorio-belt-signal@1` |
| `conditioned-departure`, full-load gate | Hold the current transport order until eligible cargo meets the selected loading condition. Continue the route after the gate opens. | Autonomous vehicle orders and a local inventory criterion. A scheduled departure may advance after elapsed time with spare capacity. | `openttd-load-orders@1` |

## Editorial decisions

The initial batch admits the original patterns listed above. The Frozen Synapse order phase also provides additional evidence for joint resolution. The source supports the distinct `preview-then-commit` pattern because preview changes the decision information before commitment. The Lichess sample adds asynchronous scheduling to a known alternating decision, preserving the separate chess move and participation concepts. Claims about active opponent reactions are excluded from recorded ghosts.

The disputed Factorio merge compares two ticks with one item on the belt. The arrival tick emits a pulse. The next tick with the item still present supplies continuing occupancy and no new pulse. The editorial review keeps two pattern IDs under `factorio-belt-signal@1`. A repeat inspection of the same source revision retains the source ID and both dispositions, with zero duplicate sources or pattern records.

Review novelty against the inspected patterns and ask whether a returned pattern helps resolve the selected design question. The coverage counts describe the editorial sample. Additional modes, player preferences and actual project behavior require matching evidence.
