"""Evaluate source, geometry, motion and receiver observations for an ArtWorkshop stage."""
from fractions import Fraction
import json
from math import hypot, isclose, isfinite
from pathlib import Path
import subprocess

LOCK_SECTIONS = {"geometry", "uv", "weights", "rig", "pose", "animation", "material_assignments"}
ROUND_TRIP = {"scale", "axes", "pivot", "skin", "animation", "dependencies"}
MOTION_VIEWS = {"left", "right", "underside", "oblique"}
MOTION_SAMPLE_STEP = {"normal": 4, "slow": 1}
MOTION_VIDEO_SUFFIXES = {".mkv", ".mov", ".mp4", ".webm"}
BLEND_POINTS = {"0.25", "0.5", "0.75"}


def named_map(value, names):
    return isinstance(value, dict) and set(value) == set(names)


def number(value):
    try:
        return type(value) in {int, float} and isfinite(value)
    except OverflowError:
        return False


def verified_pin(root, workshop, pin):
    if not named_map(pin, ("path", "sha256")) or not workshop.matches(workshop.SHA, pin["sha256"]):
        return False
    path = workshop.rooted(root, pin["path"])
    return path.is_file() and workshop.file_hash(path) == pin["sha256"]


def consistent_views(shots, expected, observations, minimum=1):
    rows = observations.get("views")
    if not named_map(rows, shots):
        return False
    states = {}
    for shot, row in rows.items():
        if not isinstance(row, dict):
            return False
        state = row.get("state")
        expression = row.get("expression")
        anchors = row.get("anchors")
        if state != expected[shot] or not isinstance(expression, str) or not expression:
            return False
        if not isinstance(anchors, dict) or len(anchors) < minimum:
            return False
        for feature in anchors.values():
            if not named_map(feature, {"side", "contact", "anchor"}) or feature["side"] not in {
                    "left", "right", "center", "none"} or type(feature["contact"]) is not bool:
                return False
            if not isinstance(feature["anchor"], str) or not feature["anchor"]:
                return False
        comparable = (expression, anchors)
        previous = states.setdefault(state, comparable)
        if previous != comparable:
            return False
    return True


def matches_clay(shots, observations, supplied):
    rows = observations.get("pairs")
    if not named_map(rows, shots):
        return {"matched-views": False, "clay-only": False}
    matched, volume = True, True
    for shot, row in rows.items():
        if not named_map(row, ("color", "registered", "texture-like")):
            return {"matched-views": False, "clay-only": False}
        matched &= row["registered"] is True and row["color"] == supplied.get(shot) and row["color"] is not None
        volume &= row["texture-like"] == []
    return {"matched-views": matched, "clay-only": volume}


def protected_form(packet, observations, minimum=0):
    rows = observations.get("protected")
    if not named_map(rows, packet["protected"]) or len(rows) < minimum:
        return False
    expected = packet.get("requirements", {}).get("protected-values", {})
    for name, row in rows.items():
        rule = expected[name]
        if not isinstance(row, dict) or row.get("baseline") != rule["value"] or "candidate" not in row:
            return False
        if "tolerance" in rule:
            baseline, actual, tolerance = rule["value"], row["candidate"], rule["tolerance"]
            if (not all(number(value) for value in (baseline, actual, tolerance))
                    or rule["unit"] not in {"m", "mm", "deg", "px"} or row.get("unit") != rule["unit"]
                    or not 0 <= abs(baseline - actual) <= tolerance):
                return False
        elif rule["value"] is None or type(row["candidate"]) is not type(rule["value"]) or row["candidate"] != rule["value"]:
            return False
    return True


def load_observation(root, workshop, pin):
    if verified_pin(root, workshop, pin):
        return workshop.read_record(workshop.rooted(root, pin["path"]), "stage observation")
    return {}


def reference_symmetry(root, workshop, observations, scope, shots, artifacts, primary):
    record = load_observation(root, workshop, observations.get("neutral-reference-symmetry"))
    if (record.get("kind") != "neutral-reference-symmetry" or record.get("state") != scope["state"]
            or record.get("symmetry_frame") != scope["symmetry_frame"] or record.get("axes") != scope["axes"]
            or record.get("primary") != artifacts[primary]
            or record.get("shots") != {shot: artifacts[shot] for shot in shots}
            or not named_map(record.get("checks"), scope["axes"])):
        return False
    source_digests = {artifacts[shot]["sha256"] for shot in (*shots, primary)}
    for check in record["checks"].values():
        if not named_map(check, {"views", "comparison", "unmatched_landmarks", "unmatched_outline_regions"}):
            return False
        views = check["views"]
        if (not isinstance(views, list) or not views or not all(isinstance(view, str) and view in shots for view in views)
                or len(views) != len(set(views)) or check["unmatched_landmarks"] != []
                or check["unmatched_outline_regions"] != []):
            return False
        comparison = check["comparison"]
        if (comparison not in artifacts.values() or not verified_pin(root, workshop, comparison)
                or comparison["sha256"] in source_digests):
            return False
    return True


def zero_counts(record, names):
    return all(type(record.get(name)) is int and record[name] == 0 for name in names)


def neutral_geometry_symmetry(root, workshop, observations, scope, blend):
    record = load_observation(root, workshop, observations.get("neutral-geometry-symmetry"))
    if (record.get("kind") != "neutral-geometry-symmetry" or record.get("asset_sha256") != blend["sha256"]
            or record.get("scene") != scope["scene"] or record.get("symmetry_frame") != scope["symmetry_frame"]
            or record.get("axes") != scope["axes"]
            or record.get("subjects") != scope["subjects"] or record.get("closed_subjects", []) != scope["closed_subjects"]
            or record.get("passed") is not True
            or not named_map(record.get("checks"), {"bind", "evaluated-neutral"})):
        return False
    for phase in record["checks"].values():
        if (not isinstance(phase, dict) or phase.get("passed") is not True
                or type(phase.get("vertices")) is not int or phase["vertices"] <= 0
                or type(phase.get("faces")) is not int or phase["faces"] <= 0
                or not zero_counts(phase, ("invalid_vertices",))
                or not named_map(phase.get("axes"), scope["axes"])
                or not named_map(phase.get("integrity"), scope["closed_subjects"])):
            return False
        for axis in phase["axes"].values():
            if (not isinstance(axis, dict) or axis.get("passed") is not True
                    or not zero_counts(axis, ("unmatched_vertices", "unmatched_faces", "unmatched_edges"))):
                return False
        for subject in phase["integrity"].values():
            if (not isinstance(subject, dict) or subject.get("passed") is not True or not zero_counts(
                    subject, ("boundary_edges", "nonmanifold_edges", "duplicate_center_vertices", "degenerate_faces"))):
                return False
    return True


def locked_texture(root, workshop, observations, packet, artifacts):
    baseline = load_observation(root, workshop, observations.get("baseline-lock"))
    candidate = load_observation(root, workshop, observations.get("candidate-lock"))
    original_source = packet["supplied"].get("detail", {}).get("blend")
    for record, source in ((baseline, original_source), (candidate, artifacts["blend"])):
        if not source or record.get("source", {}).get("sha256") != source["sha256"]:
            return False
        if (record.get("status") != "passed" or not record.get("blender_build") or
                not named_map(record.get("fingerprints"), LOCK_SECTIONS) or
                not all(workshop.matches(workshop.SHA, value) for value in record["fingerprints"].values())):
            return False
    return (baseline["blender_build"] == candidate["blender_build"]
            and baseline["fingerprints"] == candidate["fingerprints"])


def motion_checks(observations, expected):
    clips = observations.get("clips")
    if not named_map(clips, expected):
        return False
    for name, clip in clips.items():
        if not isinstance(clip, dict):
            return False
        n = clip.get("sample_count")
        if not (type(n) is int and n >= expected[name]["minimum-samples"] and clip.get("between_keys") is True and clip.get("loop_ok") is True):
            return False
        if not all(type(clip.get(key)) is int and clip[key] == 0 for key in ("intersections", "penetrations")):
            return False
        slip, maximum = clip.get("max_slip_m"), expected[name]["max-slip-m"]
        if not (number(slip) and number(maximum) and 0 <= slip <= maximum):
            return False
    return True


def temporal_scope_valid(scope, clips, shots):
    """Validate the frozen coverage for a new live motion attempt."""
    if not named_map(scope, {"views", "ranges"}) or not named_map(scope["views"], MOTION_VIEWS):
        return False
    views = list(scope["views"].values())
    if not all(isinstance(view, str) and view in shots for view in views) or len(set(views)) != len(views):
        return False
    if not named_map(scope["ranges"], clips):
        return False
    return all(named_map(span, {"start", "end", "fps", "loop"})
               and type(span["start"]) is int and type(span["end"]) is int and span["end"] > span["start"]
               and number(span["fps"]) and span["fps"] > 0 and type(span["loop"]) is bool
               for span in scope["ranges"].values())


def video_timing(path, frames, fps):
    """Decode the captured stream and compare presentation timestamps with the sample grid."""
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-select_streams", "v:0",
             "-show_frames", "-show_entries", "stream=time_base:frame=best_effort_timestamp",
             "-of", "json", str(path)], capture_output=True, timeout=30, check=True)
        if probe.stderr:
            return False
        decoded = json.loads(probe.stdout)
        time_base = Fraction(decoded["streams"][0]["time_base"])
        timestamps = [int(frame["best_effort_timestamp"]) for frame in decoded["frames"]]
        period = 1 / Fraction(str(fps))
        return len(timestamps) == frames and 0 < time_base <= period and all(
            left < right for left, right in zip(timestamps, timestamps[1:])) and all(
            abs((stamp - timestamps[0]) * time_base - index * period) <= time_base
            for index, stamp in enumerate(timestamps))
    except (OSError, ValueError, ArithmeticError, KeyError, IndexError, subprocess.SubprocessError):
        return False


def camera_forward(camera):
    if not named_map(camera, {"name", "forward"}) or not isinstance(camera["name"], str) or not camera["name"].strip():
        return False
    forward = camera["forward"]
    return (isinstance(forward, list) and len(forward) == 3 and all(number(axis) and abs(axis) <= 1 for axis in forward)
            and isclose(sum(axis * axis for axis in forward), 1, abs_tol=0.0001))


def camera_dot(first, second):
    return sum(a * b for a, b in zip(first, second))


def temporal_media(root, workshop, record, scope, artifacts, *, verify_media):
    """Bind each ordered video capture to the exact animated source and sampling grid."""
    blend = artifacts.get("blend")
    if (record.get("kind") != "temporal-motion-capture" or not blend
            or Path(blend["path"]).suffix.lower() != ".blend" or record.get("blend") != blend
            or not isinstance(record.get("scene"), str) or not record["scene"].strip()
            or record.get("clip") != artifacts["clip"]):
        return False
    return ordered_playback(root, workshop, record.get("clips"), scope, artifacts, verify_media=verify_media)


def ordered_playback(root, workshop, sequences, scope, artifacts, *, verify_media):
    if not named_map(sequences, scope["ranges"]):
        return False
    used = {artifacts[shot]["sha256"] for shot in scope["views"].values()}
    for clip, rows in sequences.items():
        span = scope["ranges"][clip]
        if not named_map(rows, {"action", "fps", "views"}) or rows["fps"] != span["fps"]:
            return False
        if (not isinstance(rows["action"], str) or not rows["action"].strip()
                or not named_map(rows["views"], scope["views"])):
            return False
        start, end = span["start"] * 4, span["end"] * 4
        directions = {}
        cameras = set()
        for role, view in rows["views"].items():
            if not named_map(view, {"shot", "camera", *MOTION_SAMPLE_STEP}) or view["shot"] != scope["views"][role]:
                return False
            camera = view["camera"]
            if not camera_forward(camera) or camera["name"] in cameras or any(
                    camera_dot(camera["forward"], other) > 0.999 for other in directions.values()):
                return False
            cameras.add(camera["name"])
            directions[role] = camera["forward"]
            for speed, step in MOTION_SAMPLE_STEP.items():
                capture = view[speed]
                if not named_map(capture, {"video", "ticks"}) or not isinstance(capture["ticks"], list):
                    return False
                ticks = capture["ticks"]
                if len(ticks) != (end - start) // step + 1 or any(
                        type(tick) is not int or tick != start + index * step for index, tick in enumerate(ticks)):
                    return False
                pin = capture["video"]
                if (pin not in artifacts.values() or not verified_pin(root, workshop, pin)
                        or Path(pin["path"]).suffix.lower() not in MOTION_VIDEO_SUFFIXES or pin["sha256"] in used):
                    return False
                if verify_media and not video_timing(workshop.rooted(root, pin["path"]), len(ticks), span["fps"]):
                    return False
                used.add(pin["sha256"])
        if (camera_dot(directions["left"], directions["right"]) > -0.75
                or any(abs(camera_dot(directions["underside"], directions[side])) > 0.75 for side in ("left", "right"))):
            return False
    return True


def temporal_review(record, scope, capture, require, require_id, *, unity=False):
    """Return blocking findings from independently reviewed continuous playback."""
    clips = record.get("playback")
    require(named_map(clips, scope["ranges"]), "Playback review must cover every required clip")
    rejected = []
    rejected_media = set()
    for clip, views in clips.items():
        require(named_map(views, scope["views"]), "Playback review must cover every required camera")
        span = scope["ranges"][clip]
        for role, speeds in views.items():
            require(named_map(speeds, MOTION_SAMPLE_STEP), "Playback review requires both normal and slow speed")
            for speed, row in speeds.items():
                captured = capture["clips"][clip]["views"][role][speed]
                media = captured["video"]
                require(isinstance(row, dict) and row.get("video") == media
                        and row.get("result") in {"pass", "fail"} and row.get("full_playback") is True
                        and (not span["loop"] or row.get("loop_boundary_reviewed") is True)
                        and isinstance(row.get("observation"), str) and row["observation"].strip(),
                        f"Playback review lacks a current complete observation: {clip}/{role}/{speed}")
                if unity:
                    aspects = row.get("aspects")
                    require(named_map(aspects, {"surface", "trajectory", "contact"})
                            and all(isinstance(note, str) and note.strip() for note in aspects.values()),
                            "Unity playback needs separate surface, trajectory and contact observations")
                if row["result"] == "fail":
                    tick = row.get("tick")
                    require(require_id(row.get("finding")) and type(tick) is int and tick in captured["ticks"]
                            and isinstance(row.get("region"), str) and row["region"].strip(),
                            "A playback finding needs an identity, frame tick and region")
                    rejected.append(row["finding"])
                    rejected_media.add(media["sha256"])
    return rejected, rejected_media


def unity_motion_scope(scope, clips, shots):
    fields = {"views", "ranges", "cases", "regions"}
    if (not isinstance(scope, dict) or not fields <= set(scope) <= fields | {"blend-holds"}
            or not isinstance(scope["cases"], dict)):
        return False
    cases = scope["cases"]
    regions = scope["regions"]
    if (not cases or not temporal_scope_valid({"views": scope["views"], "ranges": scope["ranges"]}, cases, shots)
            or not isinstance(regions, list) or not regions
            or not all(isinstance(region, str) and region.strip() for region in regions)
            or len(set(regions)) != len(regions)):
        return False
    pure = set()
    for case in cases.values():
        if (not named_map(case, {"kind", "sequence", "contact"})
                or case["kind"] not in {"clip", "transition", "control", "hold"}
                or not isinstance(case["sequence"], list) or not case["sequence"]
                or not all(isinstance(step, str) and step.strip() for step in case["sequence"])):
            return False
        if case["kind"] == "clip":
            if len(case["sequence"]) != 1:
                return False
            pure.add(case["sequence"][0])
        elif len(case["sequence"]) < 2:
            return False
        contact = case["contact"]
        if named_map(contact, {"max-slip-m", "max-penetration-m"}):
            if not all(number(limit) and limit >= 0 for limit in contact.values()):
                return False
        elif not (isinstance(contact, dict) and set(contact) in
                  ({"no-plant-reason"}, {"no-plant-reason", "max-penetration-m"})
                  and isinstance(contact["no-plant-reason"], str) and contact["no-plant-reason"].strip()
                  and number(contact.get("max-penetration-m", 0)) and contact.get("max-penetration-m", 0) >= 0):
            return False
    return bool(pure) and set(clips) <= pure and valid_blend_intervals(scope, pure)


def blend_cycles(scope, interval):
    looping_clips = {row["sequence"][0] for case, row in scope["cases"].items()
                     if row["kind"] == "clip" and scope["ranges"][case]["loop"]}
    return tuple(interval[end] in looping_clips for end in ("from", "to"))


def valid_blend_intervals(scope, pure):
    intervals = scope.get("blend-holds", {})
    if not isinstance(intervals, dict):
        return False
    covered = set()
    for name, interval in intervals.items():
        if (not isinstance(name, str) or not name.strip()
                or not named_map(interval, {"basis", "from", "to", "samples"})
                or interval["basis"] not in {"weight", "control"}
                or any(not isinstance(interval[key], str) or interval[key] not in pure for key in ("from", "to"))
                or interval["from"] == interval["to"]):
            return False
        points = interval["samples"]
        if not isinstance(points, dict) or "0.5" not in points or not set(points) <= BLEND_POINTS:
            return False
        looping = any(blend_cycles(scope, interval))
        for case in points.values():
            if not isinstance(case, str) or case in covered:
                return False
            definition = scope["cases"].get(case, {})
            if (definition.get("kind") != "hold" or definition.get("sequence") != [interval["from"], interval["to"]]
                    or scope["ranges"][case]["loop"] is not looping):
                return False
            covered.add(case)
    return covered == {case for case, row in scope["cases"].items() if row["kind"] == "hold"}


def unity_motion_checks(root, workshop, artifacts, observations, packet, *, verify_media):
    scope = packet["requirements"]["unity-motion-review"]
    capture = load_observation(root, workshop, observations.get("unity-motion-capture"))
    evidence = capture.get("checks")
    bound = (capture.get("kind") == "unity-motion-capture" and capture.get("scene") == artifacts["scene"]
             and capture.get("export") == packet["supplied"]["export"]["export"]
             and capture.get("target") == packet["target"] and capture.get("play-mode") is True
             and named_map(evidence, scope["cases"]))
    if not bound:
        return {"unity-motion-capture": False}
    media = ordered_playback(root, workshop, capture.get("clips"), scope, artifacts, verify_media=verify_media)
    traces = {}
    held = {}
    for case, row in evidence.items():
        media = media and (
            isinstance(row, dict) and named_map(row.get("regions"), scope["regions"])
            and all(isinstance(note, str) and note.strip() for note in row["regions"].values())
            and row.get("trace") in artifacts.values() and verified_pin(root, workshop, row.get("trace")))
        if media:
            trace = load_observation(root, workshop, row["trace"])
            media = (trace.get("kind") == "unity-motion-trace" and trace.get("scene") == artifacts["scene"]
                     and trace.get("case") == case)
            traces[case] = unity_contact_metrics(trace.get("frames"), scope["ranges"][case])
            media = media and traces[case] is not None
            held[case] = trace.get("held")
    if not media:
        return {"unity-motion-capture": False}
    result = {"unity-motion-capture": True}
    for case, stats in traces.items():
        contact = scope["cases"][case]["contact"]
        result[f"unity-contact-{case}"] = contact_passes(stats, contact)
    for interval in scope.get("blend-holds", {}).values():
        for value, case in interval["samples"].items():
            settled = settled_blend(held[case], scope["ranges"][case], float(value),
                                    interval["basis"], blend_cycles(scope, interval))
            if settled is None:
                return {"unity-motion-capture": False}
            result[f"unity-hold-{case}"] = settled
    return result


def settled_blend(record, span, target, basis, cyclic=None):
    """Return None for incomplete evidence and a verdict for a complete hold trace."""
    if cyclic is None:
        cyclic = (span["loop"], span["loop"])
    if not named_map(record, {"basis", "samples"}) or record["basis"] != basis:
        return None
    start, end = 4 * span["start"], 4 * span["end"]
    samples = record["samples"]
    if not isinstance(samples, list) or len(samples) != end - start + 1:
        return None
    phases, values = [], []
    for tick, row in enumerate(samples, start):
        if (not named_map(row, {"tick", "value", "phases"}) or type(row["tick"]) is not int or row["tick"] != tick
                or not number(row["value"])):
            return None
        values.append(row["value"])
        pair = row["phases"]
        if any(cyclic):
            if (not isinstance(pair, list) or len(pair) != 2
                    or any(not (number(phase) if loop else phase is None) for loop, phase in zip(cyclic, pair))):
                return None
            phases.append(pair)
        elif pair is not None:
            return None
    if any(abs(value - target) > .01 for value in values):
        return False
    if not any(cyclic):
        return True
    for loop, track in zip(cyclic, zip(*phases)):
        if loop and (track[-1] - track[0] < 2 - 1e-6
                     or any(not 0 <= cur - prev < 1 for prev, cur in zip(track, track[1:]))):
            return False
    return not all(cyclic) or all(abs((right - left) - (phases[0][1] - phases[0][0])) <= .02
                                  for left, right in phases)


def contact_passes(stats, contact):
    if stats["max-penetration-m"] > contact.get("max-penetration-m", 0):
        return False
    if "no-plant-reason" in contact:
        return stats["support-samples"] == 0
    return stats["planted-pairs"] > 0 and stats["max-slip-m"] <= contact["max-slip-m"]


def unity_contact_metrics(frames, span):
    """Measure the largest support drift from touchdown and between adjacent samples."""
    start, end = 4 * span["start"], 4 * span["end"]
    if not isinstance(frames, list) or len(frames) != end - start + 1:
        return None
    anchors, previous = {}, {}
    slip, penetration, pairs, supported = 0.0, 0.0, 0, 0
    for tick, frame in enumerate(frames, start):
        if (not named_map(frame, {"tick", "support", "floor-clearance-m"})
                or type(frame["tick"]) is not int or frame["tick"] != tick
                or not number(frame["floor-clearance-m"]) or not isinstance(frame["support"], dict)):
            return None
        current = frame["support"]
        supported += bool(current)
        for foot, uv in current.items():
            if not isinstance(foot, str) or not foot or not isinstance(uv, list) or len(uv) != 2 or not all(map(number, uv)):
                return None
            if foot in previous:
                pairs += 1
                slip = max(slip, *(hypot(uv[0] - sample[0], uv[1] - sample[1])
                                   for sample in (anchors[foot], previous[foot])))
        anchors = {foot: anchors.get(foot, uv) for foot, uv in current.items()}
        previous = current
        penetration = max(penetration, -frame["floor-clearance-m"])
    return {"planted-pairs": pairs, "support-samples": supported,
            "max-slip-m": slip, "max-penetration-m": penetration}


def matching_blend_scope(receipt, scope):
    expected = {name: {key: interval[key] for key in ("from", "to", "basis")}
                for name, interval in scope.get("blend-holds", {}).items()}
    return receipt.get("continuous-blends") == expected


def verified_scene(root, workshop, artifacts, observations, packet):
    scene = artifacts["scene"]
    receipt = load_observation(root, workshop, observations.get("scene-receipt"))
    preview = receipt.get("preview")
    controls = receipt.get("controls")
    valid = (Path(scene["path"]).suffix == ".unity" and receipt.get("scene") == scene
             and receipt.get("target") == packet["target"] and receipt.get("opened") is True
             and receipt.get("export") == packet["supplied"]["export"]["export"]
             and verified_pin(root, workshop, preview)
             and preview in [value for name, value in artifacts.items() if name != "scene"]
             and isinstance(receipt.get("open_instructions"), str) and bool(receipt["open_instructions"].strip())
             and isinstance(controls, list) and all(isinstance(row, dict) and isinstance(row.get("name"), str)
                                                    and row["name"].strip() and row.get("verified") is True
                                                    for row in controls)
             and set(packet.get("requirements", {}).get("controls", [])) <= {row["name"] for row in controls})
    return {"playable-scene": valid, "scene-artifacts": valid and receipt.get("unresolved") == []}


def preserved_delivery(observations):
    return (observations.get("rollback") is True and observations.get("repeat_import") is True
            and observations.get("local_edits_preserved") is True
            and observations.get("conflict_detected") is True)


def evaluate(root, stage, packet, candidate, report, workshop, *, verify_media=True):
    """Evaluate measured or reviewed records from the named producer and exact stage."""
    observations = report.get("observations", {})
    if not isinstance(observations, dict):
        raise ValueError("Stage observations must be an object")
    artifacts = candidate["artifacts"]
    scope = packet.get("requirements", {}).get("neutral-symmetry", {})
    symmetry = {}
    if scope.get("kind") == "mirrored":
        if stage in {"references", "clay"}:
            primary = "color" if stage == "references" else "clay"
            symmetry["neutral-reference-symmetry"] = reference_symmetry(root, workshop, observations, scope,
                                                                       packet["shots"], artifacts, primary)
        elif stage in {"blockout", "detail"}:
            symmetry["neutral-geometry-symmetry"] = neutral_geometry_symmetry(root, workshop, observations, scope,
                                                                             artifacts["blend"])
    managed = packet.get("validation-rules", {}).get("rules", {})
    if stage == "references":
        if "consistent-views" not in managed:
            symmetry["consistent-views"] = consistent_views(packet["shots"], packet["requirements"]["shot-states"],
                                                            observations)
        return symmetry
    if stage == "clay":
        return {**matches_clay(packet["shots"], observations, packet["supplied"]["references"]), **symmetry}
    if stage in {"blockout", "detail"}:
        if "protected-form" not in managed:
            symmetry["protected-form"] = protected_form(packet, observations)
        return symmetry
    if stage == "texture":
        return {"surface-only": locked_texture(root, workshop, observations, packet, artifacts)}
    if stage == "motion":
        results = {"continuous-motion": motion_checks(observations, packet["requirements"]["clips"])}
        temporal = packet["requirements"].get("temporal-review")
        if temporal is not None:
            capture = load_observation(root, workshop, observations.get("temporal-motion-capture"))
            results["temporal-motion-capture"] = temporal_media(
                root, workshop, capture, temporal, artifacts, verify_media=verify_media)
        return results
    if stage == "export":
        result = observations.get("round-trip")
        return {"round-trip": named_map(result, ROUND_TRIP) and all(value is True for value in result.values())}
    if stage == "unity":
        result = verified_scene(root, workshop, artifacts, observations, packet)
        if "unity-motion-review" in packet["requirements"]:
            result.update(unity_motion_checks(root, workshop, artifacts, observations, packet, verify_media=verify_media))
            if verify_media:
                receipt = load_observation(root, workshop, observations.get("scene-receipt"))
                result["unity-blend-scope"] = matching_blend_scope(receipt, packet["requirements"]["unity-motion-review"])
        elif verify_media:
            receipt = load_observation(root, workshop, observations.get("scene-receipt"))
            result["unity-animation-scope"] = receipt.get("animated") is False
        return result
    if stage == "delivery":
        return {"preserved-overrides": preserved_delivery(observations)}
    raise ValueError(f"No observation policy for {stage}")


def biological_bind_lengths(packet, record, tolerance):
    """Compare planned anatomical coverage and lengths with the admitted detail source."""
    source = packet["supplied"].get("detail", {}).get("blend")
    segments = packet["requirements"]["bone-segments"]
    lengths = record.get("rest-lengths-m")
    if (source is None or record.get("kind") != "biological-bind-lengths" or record.get("source") != source
            or not named_map(lengths, (spec["bone"] for spec in segments.values()))):
        return False
    for segment in segments.values():
        actual = lengths[segment["bone"]]
        if (not number(actual) or actual <= 0
                or abs(actual - segment["bind-length-m"]) > tolerance):
            return False
    return True


def biological_lengths(root, workshop, packet, artifacts, record, observations, tolerance):
    """Check exact clip coverage and two evaluated length observations per segment."""
    requirements = packet["requirements"]
    segments = requirements["bone-segments"]
    ranges = requirements["temporal-review"]["ranges"]
    clips = record.get("clips")
    if (record.get("kind") != "biological-segment-lengths"
            or any(name not in artifacts or record.get(name) != artifacts[name] for name in ("blend", "clip"))
            or record.get("segments") != segments or not named_map(clips, ranges)):
        return False
    capture = load_observation(root, workshop, observations.get("temporal-motion-capture"))
    if (not named_map(capture.get("clips"), ranges) or not isinstance(capture.get("scene"), str)
            or not capture["scene"].strip() or record.get("scene") != capture["scene"]):
        return False
    allowed = {tuple(pair) for pair in packet["validation-rules"]["motion-exceptions"]}
    for clip, row in clips.items():
        span = ranges[clip]
        first, last = 4 * span["start"], 4 * span["end"]
        recorded_clip = capture["clips"][clip]
        if (not isinstance(recorded_clip, dict) or not named_map(row, ("action", "samples"))
                or not isinstance(row["action"], str) or not row["action"].strip()
                or row["action"] != recorded_clip.get("action")):
            return False
        samples = row["samples"]
        if not isinstance(samples, list) or len(samples) != last - first + 1:
            return False
        for tick, sample in enumerate(samples, first):
            if (not named_map(sample, ("tick", "lengths")) or type(sample["tick"]) is not int
                    or sample["tick"] != tick or not named_map(sample["lengths"], segments)):
                return False
            for segment, values in sample["lengths"].items():
                if not named_map(values, ("joint-m", "bone-m")) or any(
                        not number(value) or value <= 0 for value in values.values()):
                    return False
                if (clip, segment) not in allowed:
                    baseline = segments[segment]["bind-length-m"]
                    if any(abs(value - baseline) > tolerance for value in values.values()):
                        return False
    return True


def evaluate_managed(root, packet, candidate, report, workshop):
    """Evaluate enabled definitions against candidate-bound evidence."""
    observations = report.get("observations", {})
    artifacts = candidate["artifacts"]
    outcomes, pins = {}, {}
    for name, row in packet["validation-rules"]["rules"].items():
        outcome = {"severity": row["severity"], "definition-revision": row["definition-revision"],
                   "result": "disabled"}
        outcomes[name] = outcome
        if not row["enabled"]:
            continue
        evidence = row["evidence"]
        outcome["evidence"] = {"technical": candidate["technical"]}
        records = {}
        ready = all(key in artifacts for key in evidence.get("artifacts", ()))
        ready &= all(key in observations for key in evidence.get("observations", ()))
        for key in evidence.get("observation-pins", ()):
            pin = observations.get(key)
            try:
                record = load_observation(root, workshop, pin)
            except (OSError, ValueError):
                record = {}
            if record:
                records[key] = record
                outcome["evidence"][key] = pins[key] = pin
            else:
                ready = False
        passed = False
        parameters = row["parameters"]
        if ready and name == "consistent-views":
            passed = consistent_views(packet["shots"], packet["requirements"]["shot-states"], observations,
                                      parameters["minimum-anchors"])
        elif ready and name == "protected-form":
            passed = protected_form(packet, observations, parameters["minimum-features"])
        elif ready and name == "biological-segment-lengths":
            tolerance = parameters["numerical-error-m"]
            passed = (biological_bind_lengths(packet, records["bone-bind-lengths"], tolerance)
                      and biological_lengths(root, workshop, packet, artifacts, records["bone-lengths"],
                                             observations, tolerance))
        outcome["result"] = "pass" if passed else "fail"
    return outcomes, pins
