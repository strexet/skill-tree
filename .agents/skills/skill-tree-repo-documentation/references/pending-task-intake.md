# Pending Intake

## Invocation boundary

An Add Pending invocation captures future work. Imperatives and conditional actions inside the future task description remain task requirements, including requests to find, inspect, implement or fix an entity. Descriptive verbs never supply immediate execution authorization. Necessary intake reading and duplicate checks remain permitted.

For a Figma request, capture node lookup, a missing-node stop/report condition and a found-node design-implementation/current-version-fix condition together. Intake preserves both branches without searching Figma or executing either branch. Clear intake-only intent requires no question about starting the described implementation.

A separate explicit owner instruction such as `Create Pending, then process and implement the task` supplies scope for the subsequent requested workflow. Capture first, report the Pending identity, then invoke the requested processing/controller operation under existing selection and authorization rules. The intake helper only creates Pending work; a source field or embedded imperative never dispatches another operation. Missing material subject, change or outcome still requires clarification.

## Request understanding

Establish the subject, target component, requested change and observable outcome from the request and relevant current documentation. Clarify material ambiguity with contextual choices and a recommendation. Required answers precede insertion; silence never supplies an answer.

Keep intake brief. Deep implementation research, detailed alternatives and complete acceptance planning belong to Process Pending. Preserve constraints and exact technical examples; translate request prose into English. Check existing Pending/Prioritized/Backlog entries for duplicates. Explicit update/reuse requests permit scoped changes; ambiguous duplicates require clarification.

Return the Pending identity, title, priority, relationship and deferred details. Intake neither promotes tasks nor grants execution/commit permission. Transient lock waits, transport probes, alternate controls and targeted repairs stay in the active checkpoint. Pending intake requires durable work remaining independently actionable after the current operation.

## Semantic classification and priority

Before translating or summarizing the original request, classify the requested work by meaning. Reports of a bug, issue, critical problem, `баг`, `ошибка` or `дефект` describe a defect when existing behavior fails or produces an incorrect result. Recognize obvious misspellings such as `issuee`. Keyword presence alone is insufficient: negated defect claims, issue-management features and requests to add a bug classifier remain ordinary requests when the requested work introduces a capability rather than repairs failing behavior.

Agents pass `classification` with `kind` equal to `defect` or `other` and a concise English `reason` recording the semantic decision. The deterministic helper validates and retains the decision, then enforces numeric priority. The helper does not perform natural-language inference or call a model. Existing programmatic callers without classification retain existing defaults; Add Pending agents always supply classification for owner requests. Local reviewed classification fixtures qualify the payload/priority contract rather than actual model adherence.

An owner-specified numeric `priority` or `relative_priority` wins over the defect default. Supply numeric priority only for an explicit owner override; never pass the ordinary default 100 as an implicit override. Relative placement uses an exact open task ID and an `above` or `below` direction, producing the anchor priority plus or minus one. Competing numeric and relative instructions require clarification before helper invocation. Explicit `low_priority: true` gives defect reports priority 25 when no numeric/relative override exists.

A defect report without an explicit owner priority receives the maximum current integer priority among open Pending, Prioritized and Backlog entries plus one, including blocked prioritized tasks and excluding terminal history. An empty queue uses the existing default-100 baseline and produces 101. Existing negative priorities remain valid. Ordinary requests retain current default, low-priority and relationship-specific rules. The policy applies during new intake and never retroactively reprioritizes existing work.

```json
{
  "title": "Preserve saved edits after restart",
  "description": "Saving loses the last edit after restart.",
  "expected_behavior": "The saved edit survives restart.",
  "classification": {
    "kind": "defect",
    "reason": "Existing saved state fails to survive restart."
  }
}
```
