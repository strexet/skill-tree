# Predecessor outcome policy

Choose continuation policy before creating a state that depends on an earlier ending. Record the earlier `work_id`, the exact `snapshot_digest` for imported material, the policy mode and the selected source references. Use a stable route or outcome ID when the predecessor defines an ID. Ask for a verified mapping when the earlier work records only labels.

| Mode | Effect |
| --- | --- |
| `fixed-outcome` | A named earlier ending determines the later starting conditions. |
| `imported-subset` | The later work imports explicitly selected outcomes from one compatible earlier route or saved state. |
| `common-facts` | The later work uses only facts verified across every allowed earlier route. |
| `separate-continuity` | The later work declares a different continuity and records explicitly adopted source material as proposals until approved. |

Use `outcome_ids` for chosen outcomes and `fact_refs` for exact supporting records or evidence. Match scope, event order and route conditions. Keep route-exclusive consequences separate from common facts. A missing source, incompatible route pair or unresolved policy prevents a settled predecessor state. Offer the author the smallest choice that would resolve the effect on the later work.

A selected policy governs the later work. Earlier authored works, route alternatives and accepted pins remain independently reproducible. The policy does not rewrite a predecessor or substitute for actual author approval.
