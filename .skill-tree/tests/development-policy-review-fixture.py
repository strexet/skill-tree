import importlib.util
import json
from pathlib import Path
import sys

root = Path.cwd()
package = root / ".agents/skills/skill-tree-pr-review-cycle/scripts"
spec = importlib.util.spec_from_file_location("fixture_pr", package / "pr-review-state.py")
pr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pr)
wf = pr.owned_module("fixture_workflow", package / "workflow-state.py")
store = wf.Store(root, allow_unselected=True, neutral=True)
case = json.load(sys.stdin)
snapshot = {
    "repo_id": "fixture", "remote": "origin", "source_branch": "feature",
    "target_branch": "develop", "head": case["head"], "base_oid": case["base"],
    "changed_files": case.get("files", ["app.js"]), "state": "OPEN",
    "pr": {"id": "fixture", "url": "https://example.invalid/pull/1"},
    "checks_known": True, "checks": case.get("checks", []),
}
record = case["previous"] or pr.new_record(snapshot, pr.parameters("feature", {}))
payload = {
    "head": snapshot["head"], "base_oid": snapshot["base_oid"],
    "target_branch": snapshot["target_branch"], "files": snapshot["changed_files"],
    "context_inspected": True, "checks_inspected": True, "discussions_inspected": True,
    "development_policy_observations": case["observations"], "findings": case["findings"],
}
result = {}
try:
    if not case.get("ready_only"):
        record = pr.reviewed(record, snapshot, payload, store=store)
    result["record"] = record
    if not record.get("review_requirements"):
        prepared = pr.review_requirement_plan(store, snapshot, record=record,
                                              publication_id=record.get("publication_id"))
        if prepared:
            record["review_requirements"] = pr._frozen_review_requirements(store, prepared)
    result["ready"] = pr.ready(record, snapshot, store=store)
except pr.ReviewError as error:
    result["error"] = str(error)
json.dump(result, sys.stdout)
