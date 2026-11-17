#!/usr/bin/env python3
"""Coordinate revision-bound ArtWorkshop stages and scoped review repairs."""
import argparse
from copy import deepcopy
import importlib.util
from pathlib import Path
from math import isfinite
import sys
from uuid import uuid4
import json

source = Path(__file__).resolve()
spec = importlib.util.spec_from_file_location("art_workshop_stages", source.with_name("3d-workshop.py"))
workshop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workshop)
checks_spec = importlib.util.spec_from_file_location("art_workshop_stage_checks", source.with_name("3d-stage-checks.py"))
stage_checks = importlib.util.module_from_spec(checks_spec)
checks_spec.loader.exec_module(stage_checks)
require = workshop.require
digest = workshop.digest
def require_id(value):
    return workshop.matches(workshop.ID, value)

# Dependency order also determines the default dispatch order.
DEPENDENCIES = {
    "references": (), "clay": ("references",), "blockout": ("clay",),
    "detail": ("blockout", "clay"), "texture": ("detail", "references"),
    "motion": ("detail", "clay"), "export": ("texture",), "unity": ("export",),
    "delivery": ("unity",),
}
APPROVAL = {"references": "G1", "clay": "G2", "blockout": "G3", "texture": "G4", "unity": "G5"}
ARTIFACTS = {
    "references": "color", "clay": "clay", "blockout": "blend", "detail": "blend",
    "texture": "blend", "motion": "clip", "export": "export", "unity": "scene", "delivery": "delivery",
}
CHECKS = {
    "references": ("consistent-views",), "clay": ("matched-views", "clay-only"),
    "blockout": ("protected-form",), "detail": ("protected-form",),
    "texture": ("surface-only",), "motion": ("continuous-motion",),
    "export": ("round-trip",), "unity": ("playable-scene", "scene-artifacts"),
    "delivery": ("preserved-overrides",),
}
VISUAL = set(DEPENDENCIES) - {"export", "delivery"}
SURFACE_REVIEW = {"blockout", "detail", "motion"}
VIEW_NAMES = ("front", "side", "top")
SYMMETRY_STAGES = {"references", "clay", "blockout", "detail"}
NEUTRAL_POSES = {"humanoid-t", "humanoid-arms-down", "quadruped-square", "species-neutral", "object-neutral"}
COMMANDS = ("init", "inspect", "next", "begin", "submit", "review", "approve",
            "repair", "reconcile", "revise")


def dependencies(plan, stage):
    return DEPENDENCIES[stage] + (("motion",) if stage == "export" and "motion" in plan else ())


def load_pins(root, pins):
    require(isinstance(pins, dict) and pins, "A nonempty artifact map is required")
    for name, pin in pins.items():
        require(require_id(name) and isinstance(pin, dict) and set(pin) == {"path", "sha256"},
                "Artifact requires a named path and SHA-256 pin")
        path = workshop.rooted(root, pin["path"])
        require(path.is_file() and workshop.matches(workshop.SHA, pin["sha256"]) and
                workshop.file_hash(path) == pin["sha256"], f"Artifact bytes changed: {name}")


def symmetry_scope(root, request, plan, new_run):
    scope = request.get("neutral-symmetry")
    if scope is None:
        require(not new_run or request.get("fixture", False),
                "New live plans require resolved neutral symmetry intent")
        return None
    require(isinstance(scope, dict), "Neutral symmetry intent must be an object")
    kind = scope.get("kind")
    require(kind in {"mirrored", "asymmetric", "not-applicable"},
            "Resolve uncertain neutral symmetry intent with the owner before planning")
    load_pins(root, {"symmetry-basis": scope.get("basis")})
    if kind != "mirrored":
        if kind == "asymmetric":
            require(set(scope) == {"kind", "basis", "scope"} and isinstance(scope["scope"], str)
                    and bool(scope["scope"].strip()), "Asymmetry requires the exact owner scope")
            decision = workshop.read_record(workshop.rooted(root, scope["basis"]["path"]), "asymmetry decision")
            require(decision.get("origin") == "owner" and decision.get("choice") == "asymmetric"
                    and decision.get("scope") == scope["scope"] and isinstance(decision.get("observation"), str)
                    and bool(decision["observation"].strip()), "Asymmetry requires an observed owner instruction")
        else:
            require(set(scope) == {"kind", "basis", "asset_class"} and scope.get("asset_class") in {"location", "effect"},
                    "The not-applicable route is for location or effect layouts without a modeled subject")
        return scope
    require(set(scope) == {"kind", "basis", "scene", "symmetry_frame", "axes", "subjects",
                          "closed_subjects", "pose", "state"},
            "Mirrored intent requires a frame, planes, subject scope and neutral state")
    axes = workshop.text_list(scope["axes"], "symmetry axes")
    subjects = workshop.text_list(scope["subjects"], "symmetry subjects")
    closed = workshop.text_list(scope["closed_subjects"], "closed symmetry subjects")
    require(axes and set(axes) <= {"X", "Y", "Z"} and subjects and set(closed) <= set(subjects)
            and all(isinstance(scope[name], str) and scope[name].strip() for name in ("symmetry_frame", "scene")),
            "Freeze explicit reflection axes, coordinate frame, Blender scene and mesh names")
    require(scope["pose"] in NEUTRAL_POSES and require_id(scope["state"]), "Freeze a named neutral pose")
    states = plan["references"].get("requirements", {}).get("shot-states", {})
    require(set(VIEW_NAMES) <= set(states) and set(states.values()) == {scope["state"]},
            "Mirrored modeling references require front, side and top in the same neutral state")
    if "clay" in plan:
        require(set(plan["clay"]["shots"]) == set(states),
                "Mirrored clay requires the same neutral modeling shots as color")
    return scope


def plan_for(root, request, *, new_run=True):
    goal = request.get("goal", "delivery")
    require(goal in DEPENDENCIES, "Unknown goal stage")
    motion = request.get("motion", goal == "motion")
    require(type(motion) is bool and (goal != "motion" or motion), "Invalid motion route")
    routes = dict(DEPENDENCIES)
    if motion:
        routes["export"] += ("motion",)
    selected = set()

    def include(stage):
        if stage not in selected:
            selected.add(stage)
            for predecessor in routes[stage]:
                include(predecessor)

    include(goal)
    plan = request["stages"]
    require(isinstance(plan, dict) and set(plan) == selected, "Plan must cover the exact dependency closure")
    for stage, row in plan.items():
        require(isinstance(row, dict) and {"inputs", "allowed", "protected", "shots"} <= set(row)
                and not set(row) - {"inputs", "allowed", "protected", "shots", "requirements"},
                f"Invalid stage scope: {stage}")
        inputs = row["inputs"]
        require(isinstance(inputs, dict), "Inputs require a named artifact map")
        if inputs:
            load_pins(root, inputs)
        for key in ("allowed", "protected", "shots"):
            require(isinstance(row[key], list), f"Invalid stage field: {key}")
            workshop.text_list(row[key], key)
        require(row["allowed"] and not set(row["allowed"]) & set(row["protected"]),
                f"Allowed and protected changes overlap or describe no writable scope: {stage}")
        require(all(require_id(shot) for shot in row["shots"]) and (stage not in VISUAL or row["shots"])
                and not set(row["shots"]) & {*ARTIFACTS.values(), "review-input"},
                f"Visual stage requires distinct named shots: {stage}")
        requirements = row.get("requirements", {})
        require(isinstance(requirements, dict), "Stage requirements must be an object")
        permitted = {"references": {"shot-states"}, "motion": {"clips", "temporal-review"},
                     "unity": {"controls", "unity-motion-review"},
                     "blockout": {"protected-values"}, "detail": {"protected-values"}}.get(stage, set())
        if stage in SURFACE_REVIEW:
            permitted.add("diagnostic-shots")
            if (new_run and not request.get("fixture", False)) or "diagnostic-shots" in requirements:
                diagnostic = workshop.text_list(requirements.get("diagnostic-shots"), "diagnostic shots")
                require(len(diagnostic) >= 2 and set(diagnostic) < set(row["shots"]),
                        "Surface review needs at least two additional diagnostic shots and a presentation shot")
        require(set(requirements) <= permitted, f"Unknown requirement for {stage}")
        if stage in {"references", "clay", "blockout", "detail", "texture"} and request.get("orthographic"):
            require(set(VIEW_NAMES) <= set(row["shots"]), "Primary orthographic coverage is missing")
        if stage == "references":
            states = requirements.get("shot-states", {})
            require(isinstance(states, dict) and set(states) == set(row["shots"])
                    and all(require_id(value) for value in states.values()), "Freeze a state for every reference shot")
            if request.get("orthographic"):
                require(len({states[shot] for shot in VIEW_NAMES}) == 1,
                        "The primary orthographic set requires a single neutral state")
        if stage in {"blockout", "detail"}:
            constraints = requirements.get("protected-values", {})
            require(isinstance(constraints, dict) and set(constraints) == set(row["protected"]),
                    "Freeze the baseline for every protected feature")
            for rule in constraints.values():
                require(isinstance(rule, dict) and (set(rule) == {"value"}
                        or set(rule) == {"value", "tolerance", "unit"}), "Invalid protected feature baseline")
        if stage == "motion":
            clips = requirements.get("clips")
            require(isinstance(clips, dict) and clips, "Freeze the required motion clips")
            for name, limits in clips.items():
                require(isinstance(name, str) and name and isinstance(limits, dict)
                        and set(limits) == {"minimum-samples", "max-slip-m"}
                        and type(limits["minimum-samples"]) is int and limits["minimum-samples"] > 1
                        and type(limits["max-slip-m"]) in {int, float} and isfinite(limits["max-slip-m"])
                        and limits["max-slip-m"] >= 0, "Motion clip requires checked coverage and slip limits")
            temporal = requirements.get("temporal-review")
            if (new_run and not request.get("fixture", False)) or "temporal-review" in requirements:
                require(stage_checks.temporal_scope_valid(temporal, clips, row["shots"]),
                        "Motion requires a frozen full clip range and left, right, underside and oblique playback")
        if stage == "unity":
            controls = requirements.get("controls", [])
            require(isinstance(controls, list), "Unity controls require a list")
            workshop.text_list(controls, "Unity controls")
            require(not motion or controls, "Animated Unity review needs required controls")
            scope = requirements.get("unity-motion-review")
            require(not (motion and new_run and not request.get("fixture", False)) or scope is not None,
                    "Animated Unity review requires frozen movement scenarios")
            if scope is not None:
                clips = plan.get("motion", {}).get("requirements", {}).get("clips", {})
                require(stage_checks.unity_motion_scope(scope, clips, row["shots"])
                        and all(require_id(name) for name in scope["cases"]),
                        "Unity motion requires clips, scenario ranges, diagnostic views, regions and contact policy")
    scope = symmetry_scope(root, request, plan, new_run)
    if scope is not None:
        plan = deepcopy(plan)
        for stage in SYMMETRY_STAGES & set(plan):
            plan[stage].setdefault("requirements", {})["neutral-symmetry"] = deepcopy(scope)
    return {stage: plan[stage] for stage in DEPENDENCIES if stage in selected}


def stage_status(root, state, stage):
    slot = state["stages"].get(stage, {})
    current = slot.get("current")
    if current is None:
        return "pending"
    try:
        sealed_inputs = current["packet"]["inputs"]
        if sealed_inputs:
            load_pins(root, sealed_inputs)
        scope = current["packet"].get("requirements", {}).get("neutral-symmetry")
        if scope is not None:
            load_pins(root, {"symmetry-basis": scope["basis"]})
        for dep, seal in current["packet"]["predecessors"].items():
            if stage_status(root, state, dep) != "accepted" or state["stages"][dep]["current"]["seal"] != seal:
                return "stale"
        candidate = current.get("candidate")
        if candidate:
            load_pins(root, candidate["artifacts"])
            load_pins(root, {"technical": candidate["technical"]})
            if current.get("observation_pins"):
                load_pins(root, current["observation_pins"])
        if current.get("review"):
            load_pins(root, {"review": current["review"]})
        if current.get("proof"):
            load_pins(root, current["proof"])
    except (OSError, ValueError):
        return "stale"
    return current["status"]


def frontier(root, state):
    pending = []
    for stage in DEPENDENCIES:
        if stage not in state["plan"]:
            continue
        status = stage_status(root, state, stage)
        if status == "accepted":
            continue
        if all(stage_status(root, state, dep) == "accepted" for dep in dependencies(state["plan"], stage)):
            pending.append({"stage": stage, "status": status})
    return pending


def owner_proof(root, state, stage, attempt, request):
    if state["fixture"]:
        proof = request["decision"]
        require(proof == {"origin": "fixture", "candidate": attempt["candidate_digest"], "answer": "accept"},
                "Fixture approval must match this candidate")
        return proof, {}
    package_review = source.parent / "3d-review" / "review.py"
    review_script = package_review if package_review.is_file() else (
        source.parents[2] / "examples/3d/workshop/review/review.py")
    sys.path.insert(0, str(review_script.parent))
    try:
        review_spec = importlib.util.spec_from_file_location("art_workshop_stage_review", review_script)
        review = importlib.util.module_from_spec(review_spec)
        review_spec.loader.exec_module(review)
    finally:
        sys.path.remove(str(review_script.parent))
    review_input = attempt["candidate"]["artifacts"]["review-input"]
    host = request["trusted_host"]
    pins = {"review-input": review_input, "trusted-host": host}
    load_pins(root, pins)
    doc = workshop.read_record(workshop.rooted(root, review_input["path"]), "review input")
    candidate = doc["candidate"]
    require(doc["operation"] == "owner-decision" and candidate["asset_id"] == state["asset"]
            and candidate["revision"] == attempt["candidate"]["revision"]
            and candidate["stage"] == APPROVAL[stage] and candidate["target"] == state["target"],
            "Approval refers to a different stage candidate")
    sealed_artifacts = {name: pin for name, pin in attempt["candidate"]["artifacts"].items()
                        if name != "review-input"}
    require(candidate["components"].get("workflow-artifacts") == digest(sealed_artifacts)
            and "workflow-artifacts" in candidate["stage_inputs"][candidate["stage"]],
            "Owner packet does not bind the exact stage artifacts")
    context = review.trusted_context(root, host["path"], host["sha256"], False, review_input["path"])
    required = {"clay": ("references",), "blockout": ("clay",), "texture": ("clay", "blockout"),
                "unity": ("clay", "blockout", "texture")}.get(stage, ())
    for predecessor in required:
        require(stage_status(root, state, predecessor) == "accepted", "An approved predecessor is stale")
        previous = state["stages"][predecessor]["current"]["owner"]
        require(any(row.get("stage") == APPROVAL[predecessor] and
                    all(row.get(key) == previous[key] for key in ("packet_digest", "stage_fingerprint"))
                    for row in context.get("previous", [])), "Host history does not match the accepted graph predecessor")
    proof = review.transition(root, doc, context, False)
    require(proof["status"] == "owner-decision-verified", proof.get("reason", "Owner approval remains open"))
    return proof, pins


def read_pin(root, pin, name):
    load_pins(root, {name: pin})
    return workshop.read_record(workshop.rooted(root, pin["path"]), name)


def submit(root, state, stage, attempt, request):
    candidate = request["candidate"]
    require(isinstance(candidate, dict) and set(candidate) == {"revision", "artifacts", "technical"},
            "Candidate requires a revision, artifacts and technical report")
    require(workshop.matches(workshop.REVISION, candidate["revision"]), "Invalid candidate revision")
    artifacts = candidate["artifacts"]
    load_pins(root, artifacts)
    if stage in {"motion", "unity"}:
        failed_media = {item for prior in state["stages"][stage]["history"]
                        for item in prior.get("failed_playback", [])}
        require(not failed_media.intersection(pin["sha256"] for pin in artifacts.values()),
                "Previously rejected playback must be recaptured after repair")
    require(ARTIFACTS[stage] in artifacts, "The stage output artifact is missing")
    require(state["fixture"] or stage not in APPROVAL or "review-input" in artifacts,
            "Live owner gate requires the ArtWorkshop review input")
    packet = attempt["packet"]
    require(stage not in VISUAL or set(packet["shots"]) <= set(artifacts),
            "The candidate is missing planned visual artifacts")
    diagnostic = set(packet.get("requirements", {}).get("diagnostic-shots", ()))
    if diagnostic:
        diagnostic_digests = {artifacts[shot]["sha256"] for shot in diagnostic}
        presentation_digests = {artifacts[shot]["sha256"] for shot in set(packet["shots"]) - diagnostic}
        require(len(diagnostic_digests) == len(diagnostic) and not diagnostic_digests & presentation_digests,
                "Diagnostic shots require distinct captured evidence")
    check = read_pin(root, candidate["technical"], "technical")
    require(check.get("attempt") == attempt["id"] and check.get("stage") == stage
            and check.get("artifacts") == digest(artifacts), "Technical report refers to another candidate")
    results = check.get("checks", {})
    require(isinstance(results, dict) and set(CHECKS[stage]) <= set(results)
            and all(type(value) is bool for value in results.values()), "The stage checks are incomplete")
    analysis = review_checks(root, stage, attempt, candidate, check, verify_media=not state["fixture"])
    pin_keys = {"texture": ("baseline-lock", "candidate-lock"), "unity": ("scene-receipt",)}.get(stage, ())
    pin_keys += tuple(key for key in ("neutral-reference-symmetry", "neutral-geometry-symmetry",
                                      "temporal-motion-capture", "unity-motion-capture")
                      if key in analysis)
    observation_pins = {key: check["observations"][key] for key in pin_keys if key in check.get("observations", {})}
    if all(analysis.values()) and observation_pins:
        load_pins(root, observation_pins)
        attempt["observation_pins"] = observation_pins
    failed = sorted({name for outcome in (results, analysis) for name, ok in outcome.items() if not ok})
    attempt["candidate"] = candidate
    attempt["candidate_digest"] = digest(candidate)
    previous = [
        item["candidate"]["revision"] for item in state["stages"][stage]["history"] if "candidate" in item
    ]
    require(candidate["revision"] not in previous, "Use a new candidate revision after a rejected attempt")
    if failed:
        findings(attempt, ["technical-" + name for name in failed])
        attempt["motion_findings"] = sorted(name for name in attempt["failures"]
                                             if name.startswith(("technical-unity-contact-", "technical-unity-hold-")))
    elif stage in VISUAL:
        attempt["status"] = "review"
    elif stage in APPROVAL:
        attempt["status"] = "owner-review"
    else:
        accept(attempt)


def review_checks(root, stage, attempt, candidate, check, *, verify_media):
    return stage_checks.evaluate(root, stage, attempt["packet"], candidate, check, workshop, verify_media=verify_media)


def findings(attempt, failures):
    attempt["failures"] = sorted(failures)
    attempt["status"] = "repair"


def accept(attempt):
    attempt["seal"] = digest({"packet": attempt["packet"], "candidate": attempt["candidate"],
                              "review": attempt.get("review"), "owner": attempt.get("owner")})
    attempt["status"] = "accepted"


def route_unity_motion_repair(root, state, attempt, resolution):
    """Reopen the earliest source with a reproduced defect and preserve dependent attempts."""
    diagnosis = read_pin(root, resolution["evidence"], "unity-motion-diagnosis")
    require(diagnosis.get("kind") == "unity-motion-diagnosis" and diagnosis.get("attempt") == attempt["id"]
            and diagnosis.get("candidate") == attempt["candidate_digest"]
            and diagnosis.get("findings") == attempt["motion_findings"], "Diagnosis must match the current failures")
    blender = diagnosis.get("blender-stage")
    require(blender in {"detail", "motion"} and blender in state["plan"], "Choose the evaluated Blender source stage")
    records = {"unity": attempt["candidate"]["artifacts"]["scene"]}
    for stage, key in ((blender, "blender"), ("references", "references")):
        require(stage_status(root, state, stage) == "accepted", "Repair source is stale or unavailable")
        records[key] = state["stages"][stage]["current"]["candidate"]["artifacts"][ARTIFACTS[stage]]
    for source, pin in records.items():
        row = diagnosis.get(source)
        require(isinstance(row, dict) and row.get("artifact") == pin
                and row.get("result") in {"pass", "fail"} and (source != "unity" or row["result"] == "fail")
                and isinstance(row.get("observation"), str) and row["observation"].strip(),
                "Compare the exact references, evaluated Blender source and Unity candidate")
        load_pins(root, {"diagnostic-comparison": row.get("comparison")})
    earliest = ("references" if diagnosis["references"]["result"] == "fail" else
                blender if diagnosis["blender"]["result"] == "fail" else "unity")
    resolution["return-to"] = earliest
    if earliest != "unity":
        slot = state["stages"][earliest]
        previous = slot.pop("current")
        previous["resolution"] = {**resolution, "reported-by": "unity", "unity-attempt": attempt["id"]}
        previous["failures"] = attempt["motion_findings"]
        slot["history"].append(previous)
    return earliest


def patch(root, path, state, action, request):
    stage = request.get("stage")
    require(stage in state["plan"], "Stage is outside the selected plan")
    temporal = state["plan"][stage].get("requirements", {}).get("temporal-review")
    unity_motion = state["plan"].get("unity", {}).get("requirements", {}).get("unity-motion-review")
    if stage == "motion" and not state["fixture"] and action in {"begin", "submit", "review"}:
        require(temporal is not None, "Replan unfinished live motion with frozen temporal review coverage")
    if stage in {"export", "unity", "delivery"} and not state["fixture"] and action in {
            "begin", "submit", "review", "approve"}:
        motion = state["stages"].get("motion", {}).get("current")
        require(motion is None or "temporal-motion-capture" in motion.get("observation_pins", {}),
                "Requalify legacy live motion with temporal playback before downstream execution")
        if stage in {"unity", "delivery"} and "motion" in state["plan"]:
            require(unity_motion is not None, "Replan unfinished animated Unity review with frozen motion scenarios")
    slot = state["stages"].setdefault(stage, {"history": []})
    status = stage_status(root, state, stage)
    current = slot.get("current")
    if action == "begin":
        if status == "building":
            require(request["actor"] == current["packet"]["producer"], "Original producer must reconcile the attempt")
            return {"status": "existing", "attempt": current}
        require(status == "pending", "Reconcile, repair or revise the original attempt before beginning")
        require(all(stage_status(root, state, dep) == "accepted"
                    for dep in dependencies(state["plan"], stage)), "Required predecessor is missing or stale")
        actor = request["actor"]
        require(require_id(actor), "Producer needs a stable actor identity")
        scope = state["plan"][stage]
        if scope["inputs"]:
            load_pins(root, scope["inputs"])
        symmetry = scope.get("requirements", {}).get("neutral-symmetry")
        if symmetry is not None:
            load_pins(root, {"symmetry-basis": symmetry["basis"]})
        preds = {dep: state["stages"][dep]["current"] for dep in dependencies(state["plan"], stage)}
        supplied = {}
        for dep, item in preds.items():
            artifacts = item["candidate"]["artifacts"]
            if stage in {"blockout", "detail", "motion"}:
                if dep == "clay":
                    keys = {"clay", *item["packet"]["shots"]}
                else:
                    keys = {"blend"}
                supplied[dep] = {key: artifacts[key] for key in keys}
            else:
                supplied[dep] = {key: pin for key, pin in artifacts.items() if key != "review-input"}
        packet = {"asset": state["asset"], "target": state["target"], "stage": stage, "producer": actor,
                  **deepcopy(scope), "predecessors": {dep: item["seal"] for dep, item in preds.items()},
                  "supplied": supplied}
        if slot["history"]:
            previous = slot["history"][-1]
            packet["repair"] = previous.get("resolution")
            packet["findings"] = previous.get("failures", [])
            if previous.get("review"):
                packet["review"] = previous["review"]
        attempt = {"id": "attempt-" + uuid4().hex, "packet": packet, "status": "building"}
        slot["current"] = attempt
    else:
        require(current is not None and request.get("attempt") == current["id"], "Use the exact current attempt")
        attempt = current
        if action == "submit":
            require(status == "building" and request["actor"] == attempt["packet"]["producer"],
                    "Candidate must come from the original producer in the current attempt")
            submit(root, state, stage, attempt, request)
        elif action == "review":
            require(status == "review", "Candidate is not ready for visual review")
            record = read_pin(root, request["review"], "review")
            reviewer = record["reviewer"]
            require(require_id(reviewer) and reviewer != attempt["packet"]["producer"], "Independent reviewer required")
            require(record["attempt"] == attempt["id"] and record["candidate"] == attempt["candidate_digest"],
                    "Visual review refers to another candidate")
            require(set(record["shots"]) == set(attempt["packet"]["shots"]), "Visual review must cover every planned shot")
            rejected = []
            for shot, row in record["shots"].items():
                require(isinstance(row, dict) and row.get("result") in {"pass", "fail"}
                        and isinstance(row.get("observation"), str) and row["observation"].strip()
                        and row.get("artifact") == attempt["candidate"]["artifacts"][shot],
                        f"Visual review lacks a current observation: {shot}")
                if row["result"] == "fail":
                    require(all(isinstance(row.get(key), str) and row[key].strip()
                                for key in ("region", "expected")) and require_id(row.get("finding")),
                            "A failed shot needs a location, expected result and stable finding identity")
                    rejected.append(row["finding"])
            if temporal is not None:
                capture = read_pin(root, attempt["observation_pins"]["temporal-motion-capture"], "temporal-motion-capture")
                playback_findings, failed_media = stage_checks.temporal_review(
                    record, temporal, capture, require, require_id)
                rejected.extend(playback_findings)
                if failed_media:
                    attempt["failed_playback"] = sorted(failed_media)
            if stage == "unity" and unity_motion is not None:
                capture = read_pin(root, attempt["observation_pins"]["unity-motion-capture"], "unity-motion-capture")
                playback_findings, failed_media = stage_checks.temporal_review(
                    record, unity_motion, capture, require, require_id, unity=True)
                rejected.extend(playback_findings)
                attempt["motion_findings"] = sorted(set(playback_findings))
                if failed_media:
                    attempt["failed_playback"] = sorted(failed_media)
            attempt["review"] = request["review"]
            if rejected:
                findings(attempt, sorted(set(rejected)))
            elif stage in APPROVAL:
                attempt["status"] = "owner-review"
            else:
                accept(attempt)
        elif action == "approve":
            require(status == "owner-review", "Only a reviewed candidate can advance an owner gate")
            proof, pins = owner_proof(root, state, stage, attempt, request)
            attempt["owner"], attempt["proof"] = proof, pins
            accept(attempt)
        elif action in {"repair", "reconcile", "revise"}:
            allowed = {"repair": {"repair"}, "reconcile": {"building", "stale"},
                       "revise": {"owner-review", "accepted"}}
            require(status in allowed[action], "The selected attempt does not admit this action")
            resolution = request["resolution"]
            require(isinstance(resolution, dict) and require_id(resolution.get("method"))
                    and isinstance(resolution.get("reason"), str) and resolution["reason"].strip(),
                    "A bounded resolution method and reason are required")
            if action == "reconcile":
                read_pin(root, resolution["evidence"], "reconciliation")
                require(request.get("actor") == attempt["packet"]["producer"],
                        "Original producer must reconcile a pending side effect")
            if action == "repair":
                recurring = [past for past in slot["history"]
                             if set(past.get("failures", [])) & set(attempt["failures"])]
                if recurring and recurring[-1].get("resolution", {}).get("method") == resolution["method"]:
                    require(False, "Unchanged finding requires a distinct repair method")
                if len(recurring) >= 2:
                    diagnostic = resolution.get("evidence")
                    require(diagnostic not in [past["resolution"].get("evidence") for past in recurring],
                            "Repeated finding needs distinct diagnostic evidence or an owner decision")
                    read_pin(root, diagnostic, "repair-diagnostic")
                if stage == "unity" and attempt.get("motion_findings"):
                    route_unity_motion_repair(root, state, attempt, resolution)
            if "inputs" in resolution:
                require(action != "repair", "Replan changed authority or source inputs explicitly")
                load_pins(root, resolution["inputs"])
                state["plan"][stage]["inputs"] = resolution["inputs"]
            attempt["resolution"] = resolution
            slot["history"].append(attempt)
            del slot["current"]
        else:
            require(False, "Unsupported stage command")
    workshop.atomic_record(path, state)
    outcome = {"status": stage_status(root, state, stage), "attempt": attempt}
    if stage == "unity" and action == "repair" and attempt.get("motion_findings"):
        outcome["return-to"] = attempt["resolution"]["return-to"]
        outcome["steps"] = frontier(root, state)
    return outcome


def execute(root, run, action, request):
    require(require_id(run), "Run requires an exact stable ID")
    path = workshop.rooted(root, f"{workshop.LOCAL}/stages/{run}.json")
    if action in {"inspect", "next"}:
        state = workshop.read_record(path, "stage workflow")
        next_steps = frontier(root, state)
        if action == "next":
            status = "continue" if next_steps else "complete"
            return {"status": status, "steps": next_steps}
        return {"state": state, "stages": {stage: stage_status(root, state, stage) for stage in state["plan"]},
                "steps": next_steps}
    with workshop.writer(root):
        if action == "init":
            require(require_id(request.get("asset")), "Asset requires a stable ID")
            require(type(request.get("fixture", False)) is bool, "Invalid fixture mode")
            target = request.get("target")
            if request.get("fixture", False):
                require(require_id(target), "Fixture target requires a stable ID")
            else:
                require(isinstance(target, dict) and set(target) == {"id", "revision", "checkout_id"}
                        and require_id(target["id"]) and require_id(target["checkout_id"])
                        and workshop.matches(workshop.REVISION, target["revision"]),
                        "Live target requires the exact ID, revision and checkout")
            plan = plan_for(root, request, new_run=not path.exists())
            state = {"schema": 1, "run": run, "asset": request["asset"], "target": target,
                     "fixture": request.get("fixture", False), "plan": plan, "stages": {}}
            if path.exists():
                previous = workshop.read_record(path, "stage workflow")
                require({**previous, "stages": {}} == state, "Run already belongs to another plan")
                return {"status": "existing", "steps": frontier(root, previous)}
            path.parent.mkdir(exist_ok=True)
            workshop.atomic_record(path, state)
            return {"status": "created", "steps": frontier(root, state)}
        state = workshop.read_record(path, "stage workflow")
        return patch(root, path, state, action, request)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--run", required=True)
    parser.add_argument("action", choices=COMMANDS)
    parser.add_argument("--input")
    args = parser.parse_args()
    try:
        root = args.root.resolve(strict=True)
        require(root.is_dir(), "Workshop root must be an existing directory")
        request = workshop.read_record(workshop.rooted(root, args.input), "operation input") if args.input else {}
        print(json.dumps(execute(root, args.run, args.action, request), sort_keys=True))
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        print(f"3D stages: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
