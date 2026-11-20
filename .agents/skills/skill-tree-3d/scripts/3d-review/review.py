#!/usr/bin/env python3
"""Assemble ArtWorkshop evidence and evaluate revision-bound decisions."""

import argparse
import importlib.util
import json
from pathlib import Path
import sys

from evidence import verify_evidence
import visual


SOURCE = Path(__file__).resolve()
CONTRACT = SOURCE.parent.parent / "3d-workshop.py"
if not CONTRACT.is_file():
    CONTRACT = SOURCE.parents[4] / "common/scripts/3d-workshop.py"
SPEC = importlib.util.spec_from_file_location("art_workshop_contract", CONTRACT)
workshop = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workshop)

STAGES = {"GP", *(f"{prefix}{stage}" for prefix in ("G", "S", "V") for stage in range(1, 7))}
CONTEXT_STAGES = {"G5", "G6", "S5", "S6", "V5", "V6"}
PRODUCERS = {"unity", "blender", "technical", "agent"}
GATES = {"detail": "G3", "final-import": "G4"}
REFERENCE_GATES = {"clay-reference": "G1", "blockout": "G2"}
TERMINAL = {"pass", "not_applicable"}


def require(condition, message):
    workshop.require(condition, message)


def digest(value):
    return workshop.digest(value)


def mapping(value, label):
    require(isinstance(value, dict), f"{label} must be an object")
    return value


def entries(value, label):
    require(isinstance(value, list) and all(isinstance(item, dict) for item in value),
            f"{label} must be a list of objects")
    return value


def identifier(value, label):
    require(workshop.matches(workshop.ID, value), f"Invalid {label} identity")
    return value


def revision(value, label):
    require(workshop.matches(workshop.REVISION, value), f"Invalid {label} revision")
    return value


def hash_value(value, label):
    require(workshop.matches(workshop.SHA, value), f"Invalid {label} digest")
    return value


def strings(value, label):
    return workshop.text_list(value, label)


def document_file(root, path, label):
    return workshop.read_record(workshop.rooted(root, path), label)


def require_scope(candidate):
    require(isinstance(candidate, dict) and candidate.get("stage") in STAGES, "Invalid candidate review stage")
    identifier(candidate.get("asset_id"), "asset")
    revision(candidate.get("revision"), "asset")
    target = mapping(candidate.get("target"), "target")
    identifier(target.get("id"), "target")
    revision(target.get("revision"), "target")
    identifier(target.get("checkout_id"), "checkout")
    if "reference_workflow" in candidate:
        require(candidate["reference_workflow"] == visual.ORTHOGRAPHIC_REFERENCE and
                candidate["stage"] in {"G1", "G2", "G3", "G4", "G5", "G6"}, "Invalid neutral reference workflow")
    return digest({"asset_id": candidate["asset_id"], "target": target})


def input_fingerprints(candidate):
    result = {}
    for source in ("components", "dependencies"):
        for key, value in mapping(candidate.get(source), source).items():
            identifier(key, "review input")
            require(key not in result, f"Duplicate component or dependency: {key}")
            result[key] = hash_value(value, key)
    require(result, "Review requires at least one source input digest")
    return result


def assignment(candidate):
    environments = {}
    for environment in entries(candidate.get("environments", []), "environments"):
        key = identifier(environment.get("id"), "environment")
        require(key not in environments, f"Duplicate environment: {key}")
        revision(environment.get("revision"), "environment")
        path = environment.get("scene_path")
        parts = workshop.path_parts(path)
        require(len(parts) > 1 and parts[0] == "Assets" and parts[-1].endswith(".unity"), "Invalid environment scene path")
        hash_value(environment.get("scene_sha256"), "scene")
        workshop.path_parts(environment.get("camera_path"))
        workshop.path_parts(environment.get("anchor_path"))
        require(type(environment.get("neutral")) is bool, "Environment neutral flag must be explicit")
        strings(environment.get("risks", []), "environment risks")
        if "capture_profile" in environment:
            mapping(environment["capture_profile"], "capture profile")
        environments[key] = environment
    selected = candidate.get("primary_environment_id")
    if selected is not None:
        require(isinstance(selected, str) and selected in environments, "Unknown primary environment")
    primary = selected if selected is not None else next(iter(environments), None)
    origin = "selected" if selected is not None else "single-assignment" if len(environments) == 1 else "stable-fallback"
    return environments, primary, origin


def context_identity(environment):
    return {key: value for key, value in environment.items() if key != "risks"}


def fingerprints_for(candidate, checks):
    scope = require_scope(candidate)
    inputs = input_fingerprints(candidate)
    environments, _, _ = assignment(candidate)
    index = {}
    for check in entries(checks, "checks"):
        check_id = identifier(check.get("id"), "check")
        identifier(check.get("kind"), "check kind")
        require(check_id not in index and check.get("producer") in PRODUCERS and type(check.get("required")) is bool,
                "Invalid or duplicate review check")
        producer = check["producer"]
        if check["kind"] == "capture":
            require(producer in {"blender", "unity"}, "Capture checks require a matching native graphics producer")
        if check["kind"] == "motion":
            require(producer == "unity", "Motion checks require a matching Unity producer")
        if check["kind"] == "performance":
            require(producer == "technical", "Measured performance requires a technical profiling receipt")
            performance = mapping(check.get("performance"), "performance scope")
            metrics = mapping(performance.get("required_metrics"), "required performance metrics")
            require(metrics, "Performance metrics must be explicit")
            for metric, constraint in metrics.items():
                identifier(metric, "performance metric")
                require(isinstance(constraint, dict) and constraint.get("type") in {"number", "integer"}
                        and isinstance(constraint.get("unit"), str) and constraint["unit"].strip(),
                        f"Performance metric {metric} requires a type and unit")
        selected = strings(check.get("inputs"), "check inputs")
        require(selected and all(item in inputs for item in selected), f"Check has unknown or empty inputs: {check_id}")
        environment_id = check.get("environment_id")
        require(environment_id is None or isinstance(environment_id, str) and environment_id in environments,
                f"Check has an unknown environment: {check_id}")
        environment = environments.get(environment_id)
        identity = {
            "scope": scope, "stage": candidate["stage"], "check": check,
            "inputs": {item: inputs[item] for item in selected},
            "environment": context_identity(environment) if environment is not None else None,
        }
        index[check_id] = digest(identity)
    require(index and any(check["required"] for check in checks), "Review requires an explicit required check set")
    return index


def stage_fingerprints(candidate, scope, inputs):
    result = {}
    for stage, keys in mapping(candidate.get("stage_inputs", {}), "stage inputs").items():
        require(stage in STAGES, f"Unknown predecessor stage: {stage}")
        names = strings(keys, f"{stage} source inputs")
        require(names and all(name in inputs for name in names), f"Missing applicable source inputs for {stage}")
        stage_input = {"scope": scope, "stage": stage, "inputs": {name: inputs[name] for name in names}}
        if "reference_workflow" in candidate:
            stage_input["reference_workflow"] = candidate["reference_workflow"]
        result[stage] = digest(stage_input)
    return result


def motion_scope(check, environment, primary):
    motion = mapping(check.get("motion"), "motion scope")
    requested = motion.get("coverage")
    require(requested in {"full", "representative"}, "Unknown motion coverage")
    if environment == primary:
        require(requested == "full", "Primary motion checks require the complete cycle")
    clips = entries(motion.get("clips"), "required motion clips")
    ids = set()
    for clip in clips:
        name = identifier(clip.get("id"), "clip")
        require(name not in ids and type(clip.get("start")) is int and type(clip.get("end")) is int
                and clip["start"] < clip["end"], "Invalid clip frame scope")
        ids.add(name)
    require(ids, "Motion coverage requires explicit clips")
    strings(motion.get("contacts", []), "required contacts")
    return ids


def validate_context(candidate, checks, environments, primary):
    if candidate["stage"] in {"G3", "G4"}:
        require(any(check["required"] and check["kind"] == "capture" and check["producer"] == "blender" for check in checks),
                "G3 and G4 require a declared Blender capture")
    if candidate["stage"] not in CONTEXT_STAGES:
        return
    require(environments, "Contextual review requires assigned environments")
    primary_clips = set()
    for environment in environments:
        contextual = [check for check in checks if check.get("environment_id") == environment and check["required"]]
        require(any(check["kind"] in {"capture", "motion"} and check["producer"] == "unity" for check in contextual),
                f"Missing required Unity contextual evidence plan for {environment}")
        if candidate["stage"] == "G6":
            motion_checks = [check for check in contextual if check["kind"] == "motion"]
            require(motion_checks, f"Motion review requires a declared check for {environment}")
            for check in motion_checks:
                clips = motion_scope(check, environment, primary)
                if environment == primary:
                    primary_clips.update(clips)
    if candidate["stage"] == "G6":
        clips = candidate.get("required_clips")
        if clips is not None:
            require(set(strings(clips, "all required clips")) <= primary_clips,
                    "A required clip is missing from the primary environment")


def review_state(root, document, keys, result_by_id, fixture):
    review = document.get("agent_review")
    if review is None:
        return {"state": "pending", "findings": []}
    mapping(review, "agent review")
    require(review.get("state") == "reviewed", "Unknown agent review state")
    identifier(review.get("reviewer"), "reviewer")
    reviewed = strings(review.get("reviewed_checks"), "reviewed check IDs")
    require(reviewed and all(check in keys for check in reviewed), "Agent review must reference current checks")
    findings = entries(review.get("findings", []), "agent findings")
    for finding in findings:
        require(finding.get("severity") in {"note", "changes-required"} and isinstance(finding.get("summary"), str)
                and finding["summary"].strip(), "Invalid review finding")
        references = strings(finding.get("checks", []), "finding check IDs")
        require(set(references) <= set(reviewed), "Review finding references unreviewed checks")
    if not fixture:
        path = workshop.rooted(root, review.get("receipt_path"))
        recorded = workshop.read_record(path, "actual agent review receipt")
        hash_value(review.get("receipt_sha256"), "agent review receipt")
        require(workshop.file_hash(path) == review["receipt_sha256"]
                and recorded.get("reviewer") == review["reviewer"]
                and recorded.get("check_keys") == {check: keys[check] for check in reviewed}
                and recorded.get("evidence_keys") == {check: result_by_id[check]["evidence_digest"] for check in reviewed}
                and recorded.get("findings") == findings, "The agent review receipt is stale")
    actual = all(result_by_id[check]["state"] in TERMINAL for check in reviewed)
    blocking = any(finding["severity"] == "changes-required" for finding in findings)
    return {"state": "reviewed" if actual else "stale", "reviewer": review["reviewer"], "findings": findings,
            "reviewed_checks": reviewed, "changes_required": blocking,
            **({"receipt_sha256": review["receipt_sha256"]} if not fixture else {})}


def read_evidence(root, check, key, candidate, environment, items, fixture):
    candidates = [item for item in items if item.get("check_key") == key]
    if not candidates:
        return {"state": "stale" if items else "missing"}
    if len(candidates) != 1:
        return {"state": "invalid", "reason": "Conflicting evidence records identify the same current check"}
    item = candidates[0]
    if item.get("result") != "pass":
        return {"state": "failed"}
    try:
        evidence = verify_evidence(root, item, check, candidate, environment, fixture)
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {"state": "invalid", "reason": str(error)}
    return {"state": "pass", "evidence": evidence}


def assemble(root, document, fixture=False):
    candidate = document.get("candidate")
    scope = require_scope(candidate)
    inputs = input_fingerprints(candidate)
    environments, primary, primary_origin = assignment(candidate)
    checks = entries(document.get("checks"), "checks")
    keys = fingerprints_for(candidate, checks)
    validate_context(candidate, checks, environments, primary)
    mode = document.get("mode")
    require(mode in {"quick", "final"}, "Review mode must be quick or final")
    risks = set(strings(document.get("changed_risks", []), "changed risks"))
    applicable = set(environments) if candidate["stage"] in CONTEXT_STAGES else {
        check["environment_id"] for check in checks if check.get("environment_id") is not None
    }
    if primary not in applicable:
        primary = next((key for key in environments if key in applicable), None)
        primary_origin = "stable-fallback" if primary else "not-applicable"
    required = [
        key for key, environment in environments.items() if key in applicable
        and (mode == "final" or key == primary or risks.intersection(environment.get("risks", [])))
    ]
    deferred = [key for key in environments if key in applicable and key not in required]
    evidence = {check_id: [] for check_id in keys}
    for item in entries(document.get("evidence", []), "evidence records"):
        check_id = item.get("check_id")
        require(isinstance(check_id, str) and check_id in evidence, "Evidence references an unknown check")
        evidence[check_id].append(item)

    results = []
    for check in checks:
        check_id = check["id"]
        environment_id = check.get("environment_id")
        environment = environments.get(environment_id)
        row = {"id": check_id, "key": keys[check_id], "kind": check["kind"], "producer": check["producer"],
               "environment_id": environment_id, "required": check["required"]}
        if environment_id in deferred:
            row["state"] = "deferred"
        elif environment is not None and environment["neutral"] and check["kind"] == "style":
            row["state"] = "not_applicable"
        else:
            row.update(read_evidence(root, check, keys[check_id], candidate, environment, evidence[check_id], fixture))
        row["evidence_digest"] = digest({"state": row["state"], "evidence": row.get("evidence")})
        results.append(row)

    result_by_id = {row["id"]: row for row in results}
    review = review_state(root, document, keys, result_by_id, fixture)
    reviewed_ids = set(review.get("reviewed_checks", []))
    coverage = []
    for environment_id, environment in environments.items():
        required_checks = [row for row in results if row["environment_id"] == environment_id and row["required"]]
        if environment_id not in applicable:
            state = "not_applicable"
        elif environment_id in deferred:
            state = "deferred"
        else:
            state = "complete" if required_checks and all(row["state"] in TERMINAL for row in required_checks) else "incomplete"
        style_checks = [row for row in required_checks if row["kind"] == "style"]
        style_inputs = style_checks or [row for row in required_checks if row["kind"] in {"capture", "motion"}]
        if environment["neutral"] or state == "not_applicable":
            style = "not_applicable"
        elif state == "complete" and style_inputs and review["state"] == "reviewed" and all(
            row["id"] in reviewed_ids and row["state"] == "pass" for row in style_inputs
        ):
            style = "reviewed"
        else:
            style = "pending"
        coverage.append({"id": environment_id, "state": state, "style": style})
    selected_complete = all(row["state"] in TERMINAL for row in results if row["required"] and row["environment_id"] not in deferred)
    full_coverage = not deferred and selected_complete and all(row["state"] in {"complete", "not_applicable"} for row in coverage)
    visual_checks = [row["id"] for row in results if row["required"] and row["producer"] in {"unity", "blender"}
                     and row["state"] != "not_applicable"]
    review_required = set(visual_checks) | {row["id"] for row in results if row["required"]
        and row["kind"] == "style" and row["state"] != "not_applicable"}
    reviewed_visual = review_required <= reviewed_ids
    native = (bool(visual_checks) and not fixture and all(
        result_by_id[check].get("evidence", {}).get("native") is True for check in visual_checks))
    technical = [row for row in results if row["producer"] == "technical" and row["kind"] != "performance"]
    performance = [row for row in results if row["kind"] == "performance"]
    question = document.get("question")
    recommendation = document.get("recommendation")
    summary = document.get("change_summary")
    for key, value in (("question", question), ("recommendation", recommendation), ("change summary", summary)):
        require(isinstance(value, str) and value.strip(), f"Review {key} must be explicit")
    visual_policy = visual.evaluate(root, document.get("visual_policy"), mode, candidate, scope, result_by_id,
                                    review, environments, fixture, digest)
    packet = {
        "schema": 1, "fixture": fixture, "asset_id": candidate["asset_id"], "revision": candidate["revision"],
        "stage": candidate["stage"], "target": candidate["target"], "scope_digest": scope,
        "candidate_digest": digest(candidate), "dependencies": candidate["dependencies"],
        "mode": mode, "changes": summary, "question": question, "recommendation": recommendation,
        "stage_fingerprints": stage_fingerprints(candidate, scope, inputs),
        "coverage": {"primary": primary, "primary_origin": primary_origin, "required": required, "deferred": deferred,
                     "complete": full_coverage, "selected_complete": selected_complete, "environments": coverage},
        "checks": results, "agent_visual_review": review,
        "technical_qa": {"state": category(technical), "check_ids": [row["id"] for row in technical]},
        "target_performance": {"state": category(performance), "check_ids": [row["id"] for row in performance]},
        "human_decision": {"state": "pending"},
        "native_evidence_complete": native,
        "approval_ready": mode == "final" and full_coverage and review["state"] == "reviewed"
                          and reviewed_visual and not review.get("changes_required", False)
                          and (fixture or not visual_checks or native)
                          and (visual_policy is None or visual_policy["state"] == "verified"),
    }
    if visual_policy is not None:
        packet["visual_policy"] = visual_policy
    return {**packet, "packet_digest": digest(packet)}


def category(rows):
    if not rows:
        return "not_required"
    return "complete" if all(row["state"] in TERMINAL for row in rows) else "incomplete"


def invalidation(document):
    before = document.get("previous")
    after = document.get("candidate")
    checks = entries(document.get("checks"), "checks")
    require(require_scope(before) == require_scope(after) and before["stage"] == after["stage"],
            "Compare the same asset, target and review stage")
    previous = input_fingerprints(before)
    current = input_fingerprints(after)
    old_environments, _, _ = assignment(before)
    new_environments, _, _ = assignment(after)
    require(set(old_environments) == set(new_environments), "Changing assignments requires a fresh coverage plan")
    changed = {key for key in previous.keys() | current.keys() if previous.get(key) != current.get(key)}
    scene_changes = {key for key in old_environments
                     if context_identity(old_environments[key]) != context_identity(new_environments[key])}
    referenced = {key for check in checks for key in strings(check.get("inputs"), "check inputs")}
    unknown = changed - referenced
    old_keys = fingerprints_for(before, checks)
    new_keys = fingerprints_for(after, checks)
    invalidated = [key for key in new_keys if unknown or old_keys[key] != new_keys[key]]
    return {"changed_inputs": sorted(changed | {f"environment:{key}" for key in scene_changes}),
            "invalidated": invalidated, "reusable": [key for key in new_keys if key not in invalidated],
            "check_keys": new_keys, "previous_accepted": document.get("previous_accepted")}


def trusted_context(root, path, expected_hash, fixture, review_input):
    if path is None:
        require(expected_hash is None, "Trusted host digest requires the separate trusted input")
        return None
    hash_value(expected_hash, "trusted host context")
    source = workshop.rooted(root, path)
    require(source.is_file() and workshop.file_hash(source) == expected_hash, "Trusted host context digest changed")
    require(not source.samefile(workshop.rooted(root, review_input)), "Trusted host context must be a separate file")
    data = workshop.read_record(source, "trusted host context")
    origin = "fixture" if fixture else "skill-tree-host"
    require(data.get("origin") == origin, "Trusted host context has the wrong authority origin")
    if not fixture:
        require(isinstance(data.get("receipt_reference"), str) and data["receipt_reference"].strip(),
                "Actual host authority needs an observed receipt reference")
    return data


def accepted_stage(host, candidate, scope, stage, fingerprints):
    expected = fingerprints.get(stage)
    if expected is None:
        return None
    rows = [row for row in entries(host.get("previous", []), "accepted stage history")
            if row.get("status") == "accepted" and row.get("asset_id") == candidate["asset_id"]
            and row.get("stage") == stage and row.get("scope_digest") == scope
            and row.get("stage_fingerprint") == expected and workshop.matches(workshop.SHA, row.get("packet_digest"))]
    return rows[0] if len(rows) == 1 else None


def accepted_reference(host, candidate, scope, stage, fingerprints):
    if visual.orthographic_input(stage) not in candidate.get("stage_inputs", {}).get(stage, []):
        return None
    return accepted_stage(host, candidate, scope, stage, fingerprints)


def transition(root, document, host, fixture):
    candidate = document.get("candidate")
    scope = require_scope(candidate)
    stage = candidate["stage"]
    stages = stage_fingerprints(candidate, scope, input_fingerprints(candidate))
    action = document.get("operation")
    require(action in {*GATES, *REFERENCE_GATES, "early-proxy", "owner-decision"}, "Unknown review transition")
    if host is None:
        return {"status": "blocked", "reason": "Exact owner or accepted stage evidence is required"}
    orthographic = candidate.get("reference_workflow") == visual.ORTHOGRAPHIC_REFERENCE
    if action in REFERENCE_GATES:
        require(orthographic, "A declared neutral orthographic reference workflow is required")
        expected = REFERENCE_GATES[action]
        predecessor = accepted_reference(host, candidate, scope, expected, stages)
        if predecessor is None:
            return {"status": "blocked", "reason": f"Exact current {expected} orthographic approval is missing"}
        return {"status": "fixture-route-pass" if fixture else "eligible", "predecessor": predecessor}
    if action in GATES:
        expected = GATES[action]
        predecessor = accepted_stage(host, candidate, scope, expected, stages)
        if predecessor is None:
            return {"status": "blocked", "reason": f"Exact current {expected} acceptance is missing"}
        if action == "final-import" and accepted_stage(host, candidate, scope, "G3", stages) is None:
            return {"status": "blocked", "reason": "Exact current G3 acceptance is missing"}
        if orthographic and accepted_reference(host, candidate, scope, "G2", stages) is None:
            return {"status": "blocked", "reason": "Exact current G2 orthographic approval is missing"}
        return {"status": "fixture-route-pass" if fixture else "eligible", "predecessor": predecessor}
    if action == "early-proxy":
        expected = {"asset_id": candidate["asset_id"], "revision": candidate["revision"], "scope_digest": scope,
                    "authorized": True}
        proof = host.get("proxy")
        if not isinstance(proof, dict) or any(proof.get(key) != value for key, value in expected.items()):
            return {"status": "blocked", "reason": "Exact early proxy authorization is missing"}
        return {"status": "proxy-only", "final_import_eligible": False, "fixture": fixture}

    packet = assemble(root, document, fixture)
    require(stage in stages, "Declare current source inputs for the stage decision")
    expected = {key: packet[key] for key in ("asset_id", "revision", "stage", "scope_digest", "packet_digest")}
    expected["stage_fingerprint"] = stages[stage]
    decision = host.get("decision")
    if not isinstance(decision, dict) or any(decision.get(key) != value for key, value in expected.items()):
        return {"status": "blocked", "reason": "The owner decision does not identify the displayed packet"}
    if decision.get("answer") == "revise":
        return {"status": "changes-requested", "packet_digest": packet["packet_digest"], "fixture": fixture}
    if decision.get("answer") != "accept" or not packet["approval_ready"]:
        return {"status": "blocked", "reason": "The exact final review and owner decision are required"}
    if "visual_policy" in packet and not visual.presentation_matches(host, decision, packet):
        return {"status": "blocked", "reason": "The exact current preview must be shown before the approval prompt"}
    if orthographic and stage != "G1":
        expected = "G1" if stage == "G2" else "G2"
        if accepted_reference(host, candidate, scope, expected, stages) is None:
            return {"status": "blocked", "reason": f"Exact current {expected} orthographic approval is missing"}
    prerequisites = {"G4": ("G3",), "G5": ("G3", "G4"), "G6": ("G3", "G4")}
    for predecessor in prerequisites.get(stage, ()):
        if accepted_stage(host, candidate, scope, predecessor, stages) is None:
            return {"status": "blocked", "reason": f"Exact current {predecessor} acceptance is missing"}
    return {"status": "fixture-route-pass" if fixture else "owner-decision-verified",
            "packet_digest": packet["packet_digest"], "stage_fingerprint": stages[stage]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    actions = parser.add_subparsers(dest="action", required=True)
    for name in ("assemble", "invalidation", "transition"):
        command = actions.add_parser(name)
        command.add_argument("--input", required=True)
        command.add_argument("--fixture", action="store_true")
        if name == "transition":
            command.add_argument("--trusted-host")
            command.add_argument("--trusted-host-sha256")
    args = parser.parse_args()
    try:
        root = args.root.resolve(strict=True)
        require(root.is_dir(), "An existing review root is required")
        document = document_file(root, args.input, "review input")
        if args.action == "assemble":
            result = assemble(root, document, args.fixture)
        elif args.action == "invalidation":
            result = invalidation(document)
        else:
            context = trusted_context(root, args.trusted_host, args.trusted_host_sha256, args.fixture, args.input)
            result = transition(root, document, context, args.fixture)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Review packet: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
