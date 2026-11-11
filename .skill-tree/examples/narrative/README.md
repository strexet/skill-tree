# The Ridge Pack

The Ridge Pack is a synthetic fixture for the Skill Tree narrative workflow. The setting and characters belong only to the example. The example supplies a baseline for a scripted canon acceptance. The open decision remains a proposal.

## Author brief

The player takes over an emergency selector in a mountain lift house. The playable question is what the player protects when one limited supply serves a lift crew and a clinic. The desired experience is an informed tradeoff under time pressure. The reachable episode should take a few minutes. One optional inspection changes what the player and Ilya understand.

One creative question remains open for the author. Should the episode introduce responsibility for the damaged heater lead?

- Keep the cause mechanical. The fixture gives the player a legible choice and a focused operational mystery. The scene stays focused on competing responsibilities. The first cut uses the mechanical cause.
- Add a privately attributable work order. A named decision-maker gives the clinic and crew conflict a sharper edge. The choice needs another believable reason for leaving the lead in service and a follow-up scene for the accountability thread.
- Make the work order disputed by two witnesses. Conflicting testimony supports a longer investigation. The author would need to decide what evidence future scenes can expose and which point remains intentionally unresolved.

A review can proceed on the existing fixture. Attributing responsibility for the fault requires an author decision.

## Canon and exposure

| Stable ID | Type | Fixture content |
| --- | --- | --- |
| `ip-ridge` | IP | Emergency logistics under constrained infrastructure |
| `work-ridge` | Work | The Ridge Pack, continuity `continuity-ridge` |
| `law-pack` | Accepted fixture rule | A reserve pack runs one high-draw cycle or sustains a low-draw heater. A short can isolate the pack before either service runs. |
| `event-trip` | Accepted fixture event | The heater lead failed at 06:12. Maintenance replaced the blown fuse at 06:24 and left the selector neutral. The pack passed the capacity check at 06:32. The first lightning occurred at 06:40. |
| `character-ilya` | Accepted fixture identity and initial belief | Ilya prioritizes crew safety and believes the storm cooked the pack. The world event contradicts that belief. |
| `quest-ridge` | Fixture quest | Select a circuit after optional relay-log inspection. Choice changes crew rescue and clinic stock. |
| `scene-relay` | Optional scene | The dated log reveals the order of events. Ilya reads the log on the inspection route and corrects the initial belief. |
| `scene-report` | Repeatable scene | A ledger receipt is recorded once. Revisiting the scene does not issue a second receipt. |

The blue seal in `ridge_station` prepares the payoff in `relay_log`. The log reveals why the reserve is usable and why the heater remains unsafe. A player who skips the log sees a green reserve gauge and exposed copper and can still reach either recovery outcome. A skip path never receives the explanation from Ilya as if the inspection occurred.

## Path contract

| Path | Ink entry sequence | Visible result | Expected final state |
| --- | --- | --- | --- |
| Discover and rescue | `ridge_station → relay_log → selector → lift → report` | Crew disembarks. Clinic staff discard warmed vials. | Cause known, pack spent, crew safe, medicine warm, one ledger entry |
| Skip and preserve | `ridge_station → selector → cooler → report` | Medicine stays chilled. Crew waits in the refuge until dawn. | Cause unknown, pack spent, crew waiting, medicine cold, one ledger entry |
| Risk the heater and fail | `ridge_station → relay_log → selector → heater → report` | The short isolates the pack. Crew and clinic lose both services. | Cause known, pack isolated, crew waiting, medicine warm, one ledger entry |
| Save, restore, revisit | Save after the first ledger entry. Reload the same compiled story and choose the revisit option. | The existing entry is acknowledged. | Pack and outcome unchanged, one ledger entry |

Ink owns the five variables in the standalone story. The stock and crew flags model game-system effects. The save check uses Ink JSON with the same compiled story. A Unity adapter owns external stock and rescue effects and handles repeated events without duplicating effects. The fixtures do not qualify integration or cross-version saves. The optional scene is accessible before the selector choice. Starting a new story creates a fresh playthrough.

The Ink source is authoritative for exact text and transitions. The path contract defines context and expected behavior. A review should report mechanical path evidence, continuity findings, and untested player experience separately. For a human playtest, ask the player what each choice risked and what appeared to cause the fault before explaining the reveal.

## Try the authoring flow

Use a new throwaway project with the installed `skill-tree-narative` operation. Initialize the narrative store and copy the sample `records/` pairs into the empty `.narrative/records/` directory. Ask the agent to set up `work-ridge` in `continuity-ridge`, review `quest-ridge` and help decide how much the player can learn on the skip route. The first proposed baseline contains `law-pack`, `event-trip` and `character-ilya`. The authoring example uses a scripted fixture decision only during qualification.

To examine revision isolation, use the exact accepted snapshot for the first work, edit a working record and compare the accepted and draft views. The [authoring workflow](../../common/references/narrative-workflow.md) describes the commands and package review.

## Run the pilot

Use the macOS universal archive from the [official inklecate v1.2.1 release](https://github.com/inkle/ink/releases/tag/v1.2.1). The archive includes the matching Ink runtime DLL. Automated paths use the .NET 8 SDK, the release compiler and that DLL.

```sh
mkdir -p .tooling/inklecate
gh release download v1.2.1 --repo inkle/ink --pattern inklecate_mac.zip --dir .tooling
printf '%s  %s\n' 200aae0b4471b38142465559a0640baf143e87fc9a236c68d08e1adde48053cf .tooling/inklecate_mac.zip | shasum -a 256 -c
unzip -q .tooling/inklecate_mac.zip -d .tooling/inklecate

./run-paths.sh
.tooling/inklecate/inklecate -p quest.ink
```

`run-paths.sh` builds and tests in a temporary directory and deletes the output when finished. For tools installed elsewhere, set `INKLECATE` and `INK_RUNTIME` to absolute paths. [Inkle CLI instructions](https://github.com/inkle/ink/tree/v1.2.1#advanced-using-inklecate-on-the-command-line)

The source profile declares the `narrative-ink-replay` integration recipe. After changing recipe inputs, stop at the owned profile-refresh handoff, refresh the installation and re-admit the exact worktree before preparing the run. The controller records an execution deadline, cleanup reserve, tool fingerprints and the current story source. Run without network dependency resolution.

The harness verifies the macOS release compiler and matching runtime DLL before allocating scratch output. Exit 66 reports a prerequisite. Compilation diagnostics, a failed build and failed route assertions are execution failures. A passing report identifies nonzero named runtime cases separately from compilation and records scratch cleanup.

The runtime harness reads the declared `ridge-pilot` cases in `route-traces.json`, selects active choices by Ink tags and compares offered IDs, presented cues, terminal exits and final state. The restore trace reloads the same build before two report revisits. The six selector traces cover discovery or skip crossed with all three actions. A negative control sets `NARRATIVE_INK_NEGATIVE_CONTROL=duplicate-choice` and expects a nonzero runtime result with trace, beat and action context.

See `stable-route-evidence.md` for the current replay evidence scope. The historical pilot receipt remains in `evidence.md`.

## Qualify a continuation

Run the two-work fixture to reproduce an earlier pin and a scoped continuation without editing the example project.

```sh
python3 .skill-tree/examples/narrative/second-work/check-two-works.py
```

The disposable fixture accepts the original work, applies the lift outcome to a later role for Ilya, and rejects a cooling-outcome control before accepting the later work. The fixture then resolves the original pin again. See `second-work/README.md` for the exact evidence scope.
