"""Resolve declarative ArtWorkshop validation rules and protected motion scope."""

from copy import deepcopy
from math import isfinite
from pathlib import Path


CONFIG = "validation-rules.json"
FAMILIES = ("unclassified", "quadruped", "humanoid", "other-biological", "static-prop", "mechanical")
BIOLOGICAL = ("quadruped", "humanoid", "other-biological")
TASK_TYPES = ("creation", "revision")
PRECEDENCE = ("default", "stage", "task-type", "asset-family", "project", "asset")
LENGTH_RULE = "biological-segment-lengths"
LENGTH_ERROR_M = 0.000001

CATALOG = {
    "consistent-views": {
        "revision": 1, "lifecycle": "active", "stages": ("references",),
        "severity": "required", "evidence": {"observations": ["views"]},
        "parameters": {"minimum-anchors": 1},
    },
    "protected-form": {
        "revision": 1, "lifecycle": "active", "stages": ("blockout", "detail"),
        "severity": "required", "evidence": {"observations": ["protected"]},
        "parameters": {"minimum-features": 0},
        "family-parameters": {"static-prop": {"minimum-features": 1}},
    },
    LENGTH_RULE: {
        "revision": 1, "lifecycle": "active", "stages": ("motion",), "families": BIOLOGICAL,
        "severity": "required", "protected": True,
        "evidence": {"artifacts": ["blend", "clip"], "observation-pins": ["bone-bind-lengths", "bone-lengths"]},
        "parameters": {"numerical-error-m": LENGTH_ERROR_M},
    },
}


def context(request, motion, workshop):
    pose = (request.get("neutral-symmetry") or {}).get("pose")
    inferred = {"quadruped-square": "quadruped", "humanoid-t": "humanoid",
                "humanoid-arms-down": "humanoid", "species-neutral": "other-biological"}.get(pose)
    family = request.get("asset-family", inferred or "unclassified")
    task_type = request.get("task-type", "creation")
    workshop.require(family in FAMILIES and task_type in TASK_TYPES, "Unknown validation rule selector")
    workshop.require(inferred is None or family == inferred,
                     "Asset family conflicts with the resolved neutral pose")
    if motion:
        workshop.require(family != "static-prop", "A static prop cannot declare a motion stage")
        workshop.require(family != "unclassified" or request.get("fixture", False),
                         "Classify the moving asset before planning a live motion stage")
    return {"asset": request["asset"], "asset-family": family, "task-type": task_type}


def is_parameter(key, value):
    if key == "minimum-anchors":
        return type(value) is int and value > 0
    if key == "minimum-features":
        return type(value) is int and value >= 0
    return False


def read_configuration(root, workshop, stages):
    path = workshop.rooted(root, CONFIG)
    if not path.exists():
        return []
    config = workshop.read_record(path, "validation rule configuration")
    require = workshop.require
    require(set(config) == {"schema", "overrides"} and isinstance(config["overrides"], list),
            "Validation rule configuration requires an overrides list")
    choices = {"stage": tuple(stages), "task-type": TASK_TYPES, "asset-family": FAMILIES}
    seen = set()
    for row in config["overrides"]:
        require(isinstance(row, dict) and row.get("scope") in PRECEDENCE
                and isinstance(row.get("rule"), str) and row["rule"] in CATALOG,
                "Unknown validation rule or override scope")
        scope, name = row["scope"], row["rule"]
        definition = CATALOG[name]
        selector = row.get("selector")
        keys = {"scope", "rule"} | ({"selector"} if scope in choices or scope == "asset" else set())
        require(keys <= row.keys() and bool(row.keys() - keys)
                and row.keys() - keys <= {"enabled", "severity", "parameters"},
                "Validation rule override requires selector and supported settings")
        if scope in choices:
            require(selector in choices[scope], "Unknown validation rule selector")
            if scope == "stage":
                require(selector in definition["stages"], "Validation rule does not apply to the selected stage")
            if scope == "asset-family" and "families" in definition:
                require(selector in definition["families"], "Validation rule does not apply to the selected asset family")
        if scope == "asset":
            require(workshop.matches(workshop.ID, selector), "Invalid validation asset selector")
        key = (scope, selector, name)
        require(key not in seen, "Duplicate validation rule override")
        seen.add(key)
        require(not definition.get("protected"), "A protected validation rule cannot be overridden")
        require(definition["lifecycle"] != "retired" or row.get("enabled") is not True,
                "A retired validation rule cannot be enabled")
        require("enabled" not in row or type(row["enabled"]) is bool, "Rule enabled must be a boolean")
        require("severity" not in row or row["severity"] in ("required", "advisory"),
                "Unknown validation rule severity")
        parameters = row.get("parameters", {})
        require(isinstance(parameters, dict) and all(key in definition["parameters"] and is_parameter(key, value)
                                                    for key, value in parameters.items()),
                "Unknown or invalid validation rule parameter")
    return sorted(config["overrides"], key=lambda row: (PRECEDENCE.index(row["scope"]),
                                                       row.get("selector", ""), row["rule"]))


def effective(stage, selectors, overrides, workshop):
    family = selectors["asset-family"]
    lookup = {**selectors, "stage": stage}
    rows = {}
    applied = []
    for name, definition in CATALOG.items():
        if stage not in definition["stages"] or family not in definition.get("families", FAMILIES):
            continue
        parameters = deepcopy(definition["parameters"])
        origins = {"enabled": "catalog", "severity": "catalog",
                   "parameters": dict.fromkeys(parameters, "catalog")}
        for parameter, value in definition.get("family-parameters", {}).get(family, {}).items():
            parameters[parameter] = value
            origins["parameters"][parameter] = f"catalog:asset-family:{family}"
        row = {"definition-revision": definition["revision"], "lifecycle": definition["lifecycle"],
               "enabled": True, "severity": definition["severity"], "parameters": parameters,
               "evidence": deepcopy(definition["evidence"]), "origins": origins}
        for override in overrides:
            scope, selector = override["scope"], override.get("selector")
            target = lookup[scope] if scope in ("stage", "task-type", "asset-family", "asset") else None
            if override["rule"] != name or selector != target:
                continue
            applied.append(override)
            origin = scope if selector is None else f"{scope}:{selector}"
            for key in ("enabled", "severity"):
                if key in override:
                    row[key] = override[key]
                    origins[key] = origin
            for key, value in override.get("parameters", {}).items():
                parameters[key] = value
                origins["parameters"][key] = origin
        if definition["lifecycle"] == "retired":
            workshop.require(not definition.get("protected"), "A protected rule cannot be retired")
            row["enabled"] = False
            origins["enabled"] = "retirement"
        rows[name] = row
    snapshot = {"schema": 1, "stage": stage, "context": selectors, "rules": rows,
                "configuration-revision": workshop.digest(applied)}
    if rows:
        folder = Path(__file__).resolve().parent
        snapshot["implementation"] = {name: workshop.file_hash(folder / name) for name in
                                      ("3d-validation-rules.py", "3d-stage-checks.py")}
    return {**snapshot, "revision": workshop.digest(snapshot)}


def positive_length(value):
    try:
        return type(value) in (int, float) and value > 0 and isfinite(value)
    except OverflowError:
        return False


def segments_for(requirements, workshop):
    segments = requirements.get("bone-segments")
    workshop.require(isinstance(segments, dict) and bool(segments)
                     and all(workshop.matches(workshop.ID, segment) and isinstance(spec, dict)
                             and set(spec) == {"bone", "head", "tail", "bind-length-m"}
                             and all(isinstance(spec[k], str) and spec[k].strip() for k in ("bone", "head", "tail"))
                             and spec["head"] != spec["tail"] and positive_length(spec["bind-length-m"])
                             for segment, spec in segments.items()),
                     "Protected motion requires named bones, anatomical endpoints and fixed bind lengths")
    workshop.require(len({spec["bone"] for spec in segments.values()}) == len(segments),
                     "Protected segments require distinct anatomical bones")
    return segments


def motion_exceptions(root, requirements, asset, workshop, load_pins):
    segments = segments_for(requirements, workshop)
    clips = requirements.get("clips", {})
    pins = requirements.get("bone-length-exceptions", [])
    workshop.require(isinstance(pins, list), "Bone length exceptions require a list of owner evidence pins")
    allowed = set()
    for pin in pins:
        load_pins(root, {"bone-length-exception": pin})
        evidence = workshop.read_record(workshop.rooted(root, pin["path"]), "bone length exception")
        selected_segments, selected_clips = evidence.get("segments"), evidence.get("clips")
        workshop.require(evidence.get("kind") == "bone-length-exception" and evidence.get("origin") == "owner"
                         and evidence.get("asset") == asset
                         and isinstance(selected_segments, list) and bool(selected_segments)
                         and all(isinstance(name, str) and name in segments for name in selected_segments)
                         and isinstance(selected_clips, list) and bool(selected_clips)
                         and all(isinstance(name, str) and name in clips for name in selected_clips)
                         and all(isinstance(evidence.get(k), str) and evidence[k].strip()
                                 for k in ("instruction", "reference")), "A bone length exception requires exact observed owner scope")
        pairs = {(clip, segment) for clip in selected_clips for segment in selected_segments}
        workshop.require(len(pairs) == len(selected_segments) * len(selected_clips) and not pairs & allowed,
                         "Overlapping bone length exception scope")
        allowed.update(pairs)
    return sorted(allowed)
