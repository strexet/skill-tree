# Narrative review criteria

## Evidence and findings

Review the exact proposal and relevant source material for the selected work, continuity, period, routes and accepted snapshot. Record the proposal hash, snapshot ID, reviewed artifact paths and hashes, relevant routes, reviewer identity and outcome. A review of substantial changes uses an independent reviewer with the actual proposal, source records and diff. If the independent pass is unavailable, record the prerequisite for the affected acceptance.

Record each finding with severity, category, affected record or scene, exact sources, scope, why the issue matters, and a concrete fix or decision. Distinguish formal error, evidenced contradiction, causal or knowledge gap, motivational risk, intentional or unresolved ambiguity, and editorial advice. A strict world rule can establish a contradiction. An unusual action by a cautious character may require motivation. A contradictory witness account may be deliberate. Confirm each claim and scope before classifying a conflict.

Keep three evidence levels separate.

- **Structural checks** cover supported schema, ID uniqueness, path and link resolution, exact source versions, and approved normative dependencies in the candidate composition. Keep explicit test scope for any modeled state or route checks.
- **Semantic review** evaluates world rules, causality, knowledge, motivation, voice, gameplay implications and craft. The review records evidence and distinguishes observed defects from hypotheses.
- **Playthrough observations** record the build or prototype revision, start state, choices, observed effects, and player feedback. Player comprehension, pacing, fairness and emotional effect require observation. A presented clue, a selected interpretation and a player explaining the implication are three different observations.

## Canon and continuity

- Resolve the complete candidate composition, including unchanged records affected by a changed normative dependency. Mutually dependent candidates can be evaluated together. An approved scene cannot depend normatively on a draft, retired or missing rule outside the accepted candidate package. A mention of a superseded account has a different meaning from a normative dependency.
- Compare facts only within overlapping continuity, time, territory and outcome conditions. Separate established world facts, character beliefs, rumors, deliberate ambiguity and unresolved author decisions. Identify what evidence a character could know by a particular scene. Check player and player-character knowledge separately.
- Review world chronology, disclosure order and playable route conditions as separate structures. Check causal order, participant availability, and consequences on each applicable route. Moving a flashback can alter suspense and player knowledge while leaving the event time unchanged.
- Derive transitive reverse impact from normative links and search likely affected prose for unrecorded references. Check changes to setup, payoff, obligations, relationships and implementation. Preserve historical snapshots and record which works, if any, are explicitly moving to the candidate.
- Resolve blockers inside the accepting scope before approval. Record dismissed findings with reasons. Link open work outside the candidate to the affected records or works. Repeat the affected checks and review on changed sources or proposal bytes.

## Dramaturgy and gameplay

Use the [dramaturgy card catalog](narrative-craft-catalog.md) after identifying a concrete scene need. Read the selected card and directly relevant alternatives. Retain a scene whose observed function already serves the work. Treat the catalog as guidance outside canon.

Start with the author's intended experience and the episode's actual function. Check what the player does, understands, changes or carries forward. Examine choice wording, the price of alternatives, feedback, the reliability of clues, and whether optional content hides required information. Check both the route with a setup and the route that skips the setup. Preserve meaningful differences where branches converge.

Select a technique for a demonstrated need. Use setup and payoff when a consequential turn lacks support, environmental evidence when exposition can become investigation, and dramatic irony when different knowledge can create playable tension. Use subtext when the underlying motive is established. A quiet scene may support pacing or atmosphere without a reversal. A stable character can stay compelling under pressure. Keep technique references outside canon.

For an editorial suggestion, name the observation and intended effect, present two or three useful options when warranted, recommend one, and give a way to test the effect. Separate a small craft improvement from a change that adds production cost or requires canon approval. Retain the current scene when the scene serves the intended purpose.

## Interactive handoff

Keep the design intent, scene or quest ID, expected behavior and implementation reference in the narrative records. The ink source owns exact interactive dialogue and local branching after handoff. The Unity project owns game systems. Define one owner for each shared variable, including read and write events, allowed values, initial or missing value policy, and save behavior. Record one authoritative ink location. A JSON sidecar describes the expected behavior and integration points. Test the executable behavior in the chosen runtime.

Record the relevant main route, optional skip, alternative outcome, failure or refusal, and repeat-entry path. Add save and restore coverage when supported by the runtime. Check inaccessible or mutually exclusive outcomes, unintended prerequisites, inaccessible participants, and duplicate unique rewards. Record the exact runtime and content version, covered paths, and remaining assumptions. Report an ink compilation, an executed route, an observed human playthrough and a Unity integration check separately.

## Research behind the criteria

- Availability and effects give small narrative units a playable structure. [Emily Short, Storylets](https://emshort.blog/2019/11/29/storylets-you-want-them/)
- Reachability and the routes by which a player may encounter information are separate questions worth recording. [Otto, Chen and Smith, DendryScope](https://ojs.aaai.org/index.php/AIIDE/article/view/27527)
- Automated route probes and human playthrough transcripts support different observations. [Choice of Games testing guide](https://www.choiceofgames.com/make-your-own-games/testing-choicescript-games-automatically/), [Emily Short, Suggestions for Testing](https://emshort.blog/how-to-play/writing-if/my-articles/suggestions-for-testing/)
- ink documents runtime integration, external functions and saved story state. [inkle runtime integration guide](https://github.com/inkle/ink/blob/master/Documentation/RunningYourInk.md)
