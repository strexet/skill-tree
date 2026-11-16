# Compact Evidence Retention

`.skill-tree/history/task-outcomes.jsonl` retains compact completed/cancelled/superseded/merged outcomes, task provenance, acceptance results, limitations, followups, source fingerprints, commit references, evidence availability and timestamps. Record terminal evidence before queue removal. Queue absence never proves completion. Full specifications, plans and task bodies remain excluded.

Keep the latest ten audit records and ten finished-run summaries. Retention counts and explicit pins reside in skill-tree.json. Active-run references and unresolved findings protect relevant older records. Stable finding IDs prevent repeated findings from becoming independent issues; compare only compatible scopes. Historical checks establish behavior solely on the recorded source. Evidence availability and source freshness remain separate from recorded verdicts.

Large logs/screenshots/reports reside in ignored artifacts. Keep failure evidence until the associated issue resolves or developer-directed disposition permits removal. Pruning removes owned unpinned summaries only; task outcomes remain. Expired evidence is marked unavailable. Ordinary skills never silently delete evidence or Git history.

Exclude transcripts, internal reasoning, routine tool events, repeated snapshots, environment dumps, credentials and unmeasured token claims. Current rules remain the authority for permissions. Confirmed product decisions belong in current rules or requirements; history can reference the current decision owner.

Terminal outcomes retain optional topic and intake batch IDs from the completed task. Portable run events can carry compact original intake receipts for changed task lineage. Replay validates the original Pending membership and rejects a conflicting receipt. Missing historical receipt evidence supplies no batch timestamp or authorization. Keep immutable intake receipts under `.skill-tree/history/intake-batches/` while support for exact intake retry remains available. Ordinary summary pruning preserves intake receipts.
