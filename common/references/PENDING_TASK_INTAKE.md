# Pending Task Intake

This is lightweight intake before `Process pending`. Its output captures a goal that can later be researched, not a ready implementation specification.

## Understanding gate

Write only when the subject, requested change and intended outcome are understood from the user and light repository context. A brief paraphrase should be specific enough for the user to recognize the request.

Ask before writing when an ambiguous pronoun, unspecified screen/system, conflicting outcome or unexplained term would produce materially different tasks. Ask the smallest useful set of questions, preferably together with concrete choices grounded in context. Wait for required answers. Never treat silence as an answer or add a placeholder task for unclear intent.

Do not require implementation-ready details at intake. Clear goals can defer exact code ownership, architecture, layout, APIs, persistence strategy or detailed tests. Record a relevant deferred question only if it helps later processing; do not turn it into a long clarification checklist.

Example: “make that thing nicer” with multiple plausible screens needs a question about the subject and desired improvement. “add a replay button to the loss screen” has a clear goal even if its component and scene wiring are unknown.

## Context budget

Read local rules, the local pending template and relevant current-state documentation. Inspect the existing queue titles and any apparently overlapping entries. Follow one or two relevant document references rather than auditing the repository. A narrow source lookup is appropriate if docs cannot identify the subject or appear contradictory. Do not run the app, enumerate all assets, investigate dependencies or research implementation approaches.

Distinguish user requirements from documented context and inference. Cite real repository paths only when found; say “documentation states” when code was not verified. `Process pending` owns deeper verification and promotion.

## Priority and placement

Priority describes intake order, not implementation readiness. Always record both the priority and why the new entry lands where it does. Never move the new entry straight into Prioritized Next Changes.

| User input | Entry priority | Placement |
|---|---|---|
| No priority/placement stated | Highest — default | First task in Pending Queue |
| “urgent”, “top priority”, “do this first” | Highest/high using local terminology; preserve wording | First, unless user specifies another location |
| “low priority”, “later”, “not urgent”, “when there is time” | Low, with the user's wording | Last, unless a different relative position is requested |
| Explicit normal/medium priority | Preserve local label and user's reason | After higher-priority tasks and before lower-priority tasks when groups are clear |
| Explicit numeric/local priority | Preserve the stated value; use the repository's known scale | In its corresponding group; do not invent scale direction |
| “after X”, “before Y”, “at the bottom” | Preserve explicit priority if given; otherwise Highest — default plus explicit placement override | At the exact requested location |

Within an explicit priority group, place after existing peers while preserving their order, unless the user requests otherwise. The no-priority default and explicit top/urgent requests insert first.

Honor an unambiguous relative placement without asking again. If an anchor is absent/duplicated, priority wording conflicts, or normal/numeric placement cannot be determined from existing conventions, ask where it should land before writing. Offer meaningful choices such as first, last or after a named task. Do not infer low priority from vague uncertainty about the feature itself.

Interpret “later” or “first” as priority only when they describe task urgency/order. A requested UI label such as “Later”, or “show the first dice”, does not set task priority.

Preserve all existing tasks' relative order. Queue ordering applies only to Pending Queue; `Process pending` later researches readiness and preserves explicit priority intent when promoting work.

## Output contract

Use the local nested Markdown pending format. Extend it with a nested `Priority` field if absent. Minimum content: action-oriented title, Priority, Description, Expected behavior and Source. Add Current context when it helped interpret the request. Source should preserve the original informal wording and material clarifications so refinement does not erase intent.

Include only useful optional fields from the pending template: Requirements, Runtime/product behavior, Data/model behavior, Edge cases, Acceptance criteria, Documentation updates or Details to verify during processing. Do not generate empty sections, `Status: Ready`, the full questions section, `Touch`, implementation alternatives, migration plans or exhaustive tests. A simple observable criterion is appropriate; a detailed acceptance specification belongs to `Process pending`.

Use the repository's document language unless the user requests otherwise; preserve exact technical identifiers and original request wording. Keep descriptions concise without deleting supplied exact values, sequences or constraints. Do not encode a guessed solution as a confirmed requirement.

### Default priority example

User: “add replay on the screen when you lose so you can start another game there”. Repository docs identify a game-over screen; source wiring has not been inspected.

```markdown
- Add replay from the game-over screen
  - Priority
    - Highest — default; first in Pending Queue.
  - Description
    - Let the player start another game directly from the loss screen.
  - Current context
    - FEATURES.md documents a game-over screen; its replay wiring has not been verified.
  - Expected behavior
    - A replay action on the loss screen starts another game.
  - Source
    - User request: “add replay on the screen when you lose so you can start another game there”.
```

### Explicit low priority example

User: “not urgent, let me turn off the dice shake in settings”.

```markdown
- Add a setting to disable dice shake
  - Priority
    - Low — user said “not urgent”; last in Pending Queue.
  - Description
    - Add a player setting that disables the dice shake effect.
  - Expected behavior
    - With dice shake disabled, dice outcomes still display without the shake effect.
  - Source
    - User request: “not urgent, let me turn off the dice shake in settings”.
```

This example assumes context establishes that “dice shake” means the visual effect. If it could mean vibration or animation and docs do not resolve that distinction, ask before inserting. Persistence/default values can be deferred unless the user supplied them.

## Preservation and handoff

If an obvious equivalent task exists, identify it rather than adding another. Do not rewrite, merge, reprioritize or remove it without an explicit update request. Preserve differences that make a related request distinct.

Edit only the intended Pending Queue entry. Do not change the pending template, other queues, current-state docs, code or configuration as part of ordinary intake. If document structure is missing or malformed, report the specific issue rather than rebuilding it silently.

After writing, review queue boundaries and the diff. Briefly report the task title, chosen priority/position, documents used and any intentionally deferred details. The next command is `Process pending`; never invoke it automatically merely because intake succeeded.
