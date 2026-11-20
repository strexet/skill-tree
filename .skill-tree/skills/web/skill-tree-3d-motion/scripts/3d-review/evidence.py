"""Bind ArtWorkshop review evidence to exact producer records and artifact bytes."""

from hashlib import file_digest, sha256
import json
import math
from pathlib import Path
import re
from unicodedata import normalize
from zlib import crc32


SHA256 = re.compile(r"[a-f0-9]{64}")
REVISION = re.compile(r"[a-z0-9][a-z0-9.-]*")
TARGET_PINS = ("editor_version", "manifest_sha256", "packages_lock_sha256")
CAPTURE_FIELDS = {
    "quality": "quality", "pipeline": "pipeline", "graphics_api": "graphics_api",
    "color_space": "color_space", "width": "capture_width", "height": "capture_height",
}
PRODUCERS = {
    "unity-capture": "unity", "unity-motion": "unity", "blender-render": "blender",
    "technical": "technical", "agent": "agent",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest_value(value):
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate evidence field: {key}")
        result[key] = value
    return result


def invalid_constant(value):
    raise ValueError(f"Invalid evidence number: {value}")


def parse_record(raw, label):
    value = json.loads(raw, object_pairs_hook=unique_fields, parse_constant=invalid_constant)
    require(isinstance(value, dict) and type(value.get("schema")) is int and value["schema"] == 1,
            f"Unsupported {label} schema")
    return value


def relative_parts(value):
    require(isinstance(value, str) and value == normalize("NFC", value) and
            not any(char in value for char in "\\:\0"), "Evidence requires a portable relative path")
    parts = value.split("/")
    require(all(part not in {"", ".", ".."} for part in parts), "Evidence path escapes the reviewed root")
    return parts


def evidence_file(root, value):
    path = root
    for part in relative_parts(value):
        require(part in {entry.name for entry in path.iterdir()}, "Evidence path is missing or uses an alias")
        path = path / part
        require(not path.is_symlink(), "Evidence path contains a symbolic link")
    require(path.is_file() and path.stat().st_size > 0, "Evidence requires a nonempty regular file")
    return path


def hash_file(path):
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def match(record, expected, label):
    for field, value in expected.items():
        require(field in record and record[field] == value, f"{label} {field} differs from the exact review scope")


def target_scope(candidate):
    target = candidate["target"]
    return {"target_id": target["id"], "target_revision": target["revision"], "checkout_id": target["checkout_id"]}


def scene_scope(environment):
    return {
        "environment_id": environment["id"], "environment_revision": environment["revision"],
        "scene_path": environment["scene_path"], "scene_sha256": environment["scene_sha256"],
        "camera_path": environment["camera_path"], "anchor_path": environment["anchor_path"],
    }


def candidate_scope(candidate):
    return {**target_scope(candidate), "asset_id": candidate["asset_id"], "asset_revision": candidate["revision"]}


def capture_profile(environment):
    profile = environment.get("capture_profile", {}) if environment else {}
    require(isinstance(profile, dict) and set(profile) <= set(CAPTURE_FIELDS), "Invalid capture profile fields")
    return {CAPTURE_FIELDS[field]: value for field, value in profile.items()}


def validate_profile(receipt, environment):
    for field in ("quality", "pipeline", "graphics_api", "color_space"):
        value = receipt.get(field)
        require(isinstance(value, str) and value.strip(), f"Capture receipt is missing actual {field}")
    require(receipt["graphics_api"].casefold() != "null", "Capture receipt has no graphics device")
    for field in ("capture_width", "capture_height"):
        require(type(receipt.get(field)) is int and 16 <= receipt[field] <= 4096, f"Invalid actual {field}")
    match(receipt, capture_profile(environment), "Capture profile")


def read_receipt(root, evidence, expected_hash=False):
    raw = evidence_file(root, evidence.get("receipt_path")).read_bytes()
    digest = sha256(raw).hexdigest()
    if expected_hash or "receipt_sha256" in evidence:
        require(digest == evidence.get("receipt_sha256"), "Evidence receipt SHA-256 differs")
    return parse_record(raw, "evidence receipt"), digest


def verify_artifact(root, evidence, digest):
    path = evidence_file(root, evidence.get("artifact_path"))
    require(digest_value(digest) and hash_file(path) == digest, "Captured artifact SHA-256 differs")
    if "artifact_sha256" in evidence:
        require(evidence["artifact_sha256"] == digest, "Declared evidence artifact SHA-256 differs")
    return path


def png_dimensions(path):
    with path.open("rb") as stream:
        require(stream.read(8) == b"\x89PNG\r\n\x1a\n", "Capture artifact is not a PNG")
        size = path.stat().st_size
        image_size = None
        data_bytes = 0
        while True:
            header = stream.read(8)
            require(len(header) == 8, "Capture PNG is truncated")
            length, kind = int.from_bytes(header[:4], "big"), header[4:]
            if image_size is None:
                require(kind == b"IHDR" and length == 13, "Invalid capture PNG header")
            require(length <= size - stream.tell() - 4, "Capture PNG chunk is truncated")
            digest = crc32(kind)
            if kind == b"IHDR":
                require(image_size is None, "Capture PNG repeats the image header")
                data = stream.read(length)
                image_size = int.from_bytes(data[:4], "big"), int.from_bytes(data[4:8], "big")
                require(all(dimension > 0 for dimension in image_size), "Capture PNG has invalid dimensions")
                digest = crc32(data, digest)
            else:
                for offset in range(0, length, 1024 * 1024):
                    digest = crc32(stream.read(min(1024 * 1024, length - offset)), digest)
            require(int.from_bytes(stream.read(4), "big") == digest, "Capture PNG has an invalid chunk checksum")
            if kind == b"IDAT":
                data_bytes += length
            if kind == b"IEND":
                require(length == 0 and data_bytes > 0 and not stream.read(1), "Capture PNG has incomplete image data")
                return image_size


def gif_dimensions(path):
    def take(stream, count):
        result = stream.read(count)
        require(len(result) == count, "Motion GIF is truncated")
        return result

    def blocks(stream):
        total = 0
        while length := take(stream, 1)[0]:
            take(stream, length)
            total += length
        return total

    with path.open("rb") as stream:
        require(take(stream, 6) in {b"GIF87a", b"GIF89a"}, "Motion artifact is not a GIF")
        screen = take(stream, 7)
        size = int.from_bytes(screen[:2], "little"), int.from_bytes(screen[2:4], "little")
        require(all(dimension > 0 for dimension in size), "Motion GIF has invalid dimensions")
        if screen[4] & 0x80:
            take(stream, 3 * (2 << (screen[4] & 7)))
        frames = 0
        while True:
            kind = take(stream, 1)
            if kind == b";":
                require(frames >= 2 and not stream.read(1), "Motion GIF requires multiple complete frames")
                return size
            if kind == b"!":
                take(stream, 1)
                blocks(stream)
                continue
            require(kind == b",", "Invalid motion GIF image block")
            descriptor = take(stream, 9)
            left, top = int.from_bytes(descriptor[:2], "little"), int.from_bytes(descriptor[2:4], "little")
            width, height = int.from_bytes(descriptor[4:6], "little"), int.from_bytes(descriptor[6:8], "little")
            require(width > 0 and height > 0 and left + width <= size[0] and top + height <= size[1],
                    "Invalid motion GIF frame dimensions")
            if descriptor[8] & 0x80:
                take(stream, 3 * (2 << (descriptor[8] & 7)))
            require(2 <= take(stream, 1)[0] <= 8 and blocks(stream) > 0, "Motion GIF frame has no image data")
            frames += 1


def motion_artifact_dimensions(path):
    suffix = path.suffix.casefold()
    if suffix == ".png":
        return png_dimensions(path)
    if suffix == ".gif":
        return gif_dimensions(path)
    raise ValueError("Unity motion evidence requires a PNG contact sheet or animated GIF")


def finite_time(value):
    return type(value) in {int, float} and math.isfinite(value) and value >= 0


def clip_index(values):
    require(isinstance(values, list) and values, "Motion proof requires clip intervals")
    result = {}
    for value in values:
        require(isinstance(value, dict) and isinstance(value.get("id"), str) and value["id"] and
                value["id"] not in result and finite_time(value.get("start")) and finite_time(value.get("end")) and
                value["end"] > value["start"], "Invalid motion clip interval")
        result[value["id"]] = value
    return result


def verify_motion(proof, expected, native):
    require(isinstance(proof, dict), "Motion evidence requires measured coverage")
    coverage = expected.get("coverage")
    actual_coverage = proof.get("coverage")
    require(coverage in {"full", "representative"} and actual_coverage in {"full", "representative"} and
            (coverage != "full" or actual_coverage == "full"), "Motion coverage is incomplete")
    actual_clips = clip_index(proof.get("clips"))
    for clip_id, required in clip_index(expected.get("clips")).items():
        clip = actual_clips.get(clip_id)
        require(clip is not None and clip["start"] <= required["start"] and clip["end"] >= required["end"],
                f"Motion clip {clip_id} does not cover the required interval")
        if native:
            samples = clip.get("sample_times")
            minimum = 3 if coverage == "full" else 2
            require(isinstance(samples, list) and len(samples) >= minimum and all(finite_time(value) for value in samples) and
                    samples == sorted(set(samples)) and clip["start"] <= samples[0] <= required["start"] and
                    required["end"] <= samples[-1] <= clip["end"], f"Motion clip {clip_id} lacks measured time samples")
    actual_contacts = proof.get("contacts", [])
    required_contacts = expected.get("contacts", [])
    require(isinstance(actual_contacts, list) and isinstance(required_contacts, list), "Motion contacts require a list")
    for contact in required_contacts:
        if native:
            expected_contact = contact if isinstance(contact, dict) else {"id": contact}
            require(any(isinstance(actual, dict) and actual.get("result") == "pass" and finite_time(actual.get("time")) and
                        any(clip["start"] <= actual["time"] <= clip["end"] for clip in actual_clips.values()) and
                        all(key in actual and actual[key] == value for key, value in expected_contact.items())
                        for actual in actual_contacts), "Required measured motion contact is missing")
        else:
            require(contact in actual_contacts, "Required motion contact is missing")


def fixture_evidence(evidence, check, candidate, environment):
    match(evidence, target_scope(candidate), "Fixture")
    if environment is not None:
        expected = {"environment_id": environment["id"], "environment_revision": environment["revision"],
                    "scene_sha256": environment["scene_sha256"]}
        for field in ("scene_path", "camera_path", "anchor_path"):
            if field in evidence:
                expected[field] = environment[field]
        match(evidence, expected, "Fixture scene")
    if check.get("motion") is not None:
        verify_motion(evidence.get("motion"), check["motion"], native=False)
    roles = check.get("view_roles")
    if roles is not None:
        match(evidence, {"view_roles": roles}, "Fixture view")
    return {"source": "fixture", "native": False, "evidence_key": evidence["check_key"],
            **({"view_roles": roles} if roles is not None else {})}


def producer_revision(record):
    revision = record.get("asset_revision")
    require(isinstance(revision, str) and REVISION.fullmatch(revision), "Producer evidence lacks an original asset revision")
    return revision


def unity_binding(root, evidence, candidate, receipt_hash, request_hash):
    raw = evidence_file(root, evidence.get("binding_path")).read_bytes()
    digest = sha256(raw).hexdigest()
    require(digest == evidence.get("binding_sha256"), "Producer review binding SHA-256 differs")
    binding = parse_record(raw, "producer review binding")
    match(binding, {"source": "unity-capture", "check_id": evidence["check_id"], "check_key": evidence["check_key"],
                    "asset_id": candidate["asset_id"], "stage": candidate["stage"],
                    "receipt_sha256": receipt_hash, "request_sha256": request_hash}, "Producer review binding")
    return producer_revision(binding), digest


def unity_capture(root, evidence, candidate, environment):
    require(environment is not None, "Unity capture requires an exact environment assignment")
    request_raw = evidence_file(root, evidence.get("request_path")).read_bytes()
    request = parse_record(request_raw, "frozen Unity request")
    request_hash = sha256(request_raw).hexdigest()
    receipt, receipt_hash = read_receipt(root, evidence)
    original_revision, binding_hash = unity_binding(root, evidence, candidate, receipt_hash, request_hash)
    match(receipt, {"action": "capture", "status": "captured", "request_sha256": request_hash}, "Unity capture receipt")
    expected = {**candidate_scope(candidate), "asset_revision": original_revision, **scene_scope(environment)}
    match(request, expected, "Frozen Unity request")
    # The receipt binds the placement through the exact request hash.
    match(receipt, {key: value for key, value in expected.items() if key != "anchor_path"}, "Unity capture receipt")
    if "anchor_path" in receipt:
        match(receipt, {"anchor_path": environment["anchor_path"]}, "Unity capture receipt")
    pins = {key: request.get(key) for key in (*TARGET_PINS, "operation_id", "project_root", "plan_digest")}
    require(all(isinstance(value, str) and value for value in pins.values()) and
            all(digest_value(pins[key]) for key in ("manifest_sha256", "packages_lock_sha256", "plan_digest")),
            "Frozen Unity request is missing its exact execution pins")
    match(receipt, pins, "Unity capture receipt")
    match(request, {key: candidate["target"][key] for key in TARGET_PINS if key in candidate["target"]}, "Unity target")
    validate_profile(receipt, environment)
    dimensions = {key: receipt[key] for key in ("capture_width", "capture_height")}
    match(request, dimensions, "Frozen Unity request")
    require(digest_value(environment["scene_sha256"]), "Environment lacks a saved scene SHA-256")
    capture_path = relative_parts(receipt.get("capture_path"))
    require(capture_path[:-1] == ["Library", "SkillTreeArtWorkshop", "operations", pins["operation_id"]] and
            capture_path[-1].startswith("capture-") and capture_path[-1].endswith(".png"),
            "Unity capture path is outside the recorded operation")
    artifact_hash = receipt.get("capture_sha256")
    artifact = verify_artifact(root, evidence, artifact_hash)
    require(png_dimensions(artifact) == (dimensions["capture_width"], dimensions["capture_height"]),
            "Unity capture PNG dimensions differ from the receipt")
    return {"artifact_sha256": artifact_hash, "request_sha256": request_hash, "receipt_sha256": receipt_hash,
            "binding_sha256": binding_hash, "original_asset_revision": original_revision}


def native_capture(root, evidence, check, candidate, environment):
    source = evidence["source"]
    receipt, receipt_hash = read_receipt(root, evidence, expected_hash=True)
    original_revision = producer_revision(receipt)
    expected = {**candidate_scope(candidate), "asset_revision": original_revision, "stage": candidate["stage"],
                "source": source, "producer": PRODUCERS[source], "status": "captured",
                "check_id": evidence["check_id"], "check_key": evidence["check_key"]}
    if environment is not None:
        expected.update(scene_scope(environment))
    match(receipt, expected, "Native capture receipt")
    if environment is not None:
        match(receipt, capture_profile(environment), "Native capture profile")
    tool = receipt.get("tool")
    require(isinstance(tool, dict) and isinstance(tool.get("version"), str) and tool["version"],
            "Native capture requires a producer tool identity")
    tool_pins = candidate.get("tool_pins", {}).get(PRODUCERS[source], {})
    match(tool, tool_pins, "Native capture tool")
    if source == "unity-motion":
        require(environment is not None and check.get("motion") is not None, "Unity motion requires an assigned motion check")
        require(tool["version"] == receipt.get("editor_version") and
                all(digest_value(receipt.get(key)) for key in ("manifest_sha256", "packages_lock_sha256")),
                "Unity motion requires exact Editor and package pins")
        match(receipt, {key: candidate["target"][key] for key in TARGET_PINS if key in candidate["target"]}, "Unity motion target")
        verify_motion(receipt.get("motion"), check["motion"], native=True)
    else:
        require(isinstance(tool.get("build_hash"), str) and tool["build_hash"], "Blender render requires a build hash")
    artifact_hash = receipt.get("artifact_sha256")
    artifact = verify_artifact(root, evidence, artifact_hash)
    if source == "unity-motion":
        dimensions = motion_artifact_dimensions(artifact)
    else:
        require(artifact.suffix.casefold() == ".png", "Blender render evidence requires a PNG")
        dimensions = png_dimensions(artifact)
    for index, key in enumerate(("capture_width", "capture_height")):
        if key in receipt:
            require(type(receipt[key]) is int and receipt[key] == dimensions[index], "Capture artifact dimensions differ")
    roles = check.get("view_roles")
    if roles is not None:
        require(source == "blender-render" and isinstance(roles, list) and len(roles) == 1,
                "A native Blender render declares one exact stage view")
        match(receipt, {"view_roles": roles}, "Native capture view")
    return {"artifact_sha256": artifact_hash, "receipt_sha256": receipt_hash, "original_asset_revision": original_revision,
            **({"view_roles": roles} if roles is not None else {})}


def performance_measurements(receipt, check):
    required = check.get("performance", {}).get("required_metrics")
    measurements = receipt.get("measurements")
    require(isinstance(required, dict) and required and isinstance(measurements, dict) and
            set(measurements) == set(required), "Performance receipt requires the exact measured metrics")
    for metric_id, spec in required.items():
        require(isinstance(spec, dict) and set(spec) == {"type", "unit"} and spec["type"] in {"number", "integer"} and
                isinstance(spec["unit"], str) and spec["unit"], f"Invalid performance metric contract: {metric_id}")
        observed = measurements[metric_id]
        require(isinstance(observed, dict) and set(observed) == {"value", "unit"} and observed["unit"] == spec["unit"],
                f"Performance measurement unit or fields differ: {metric_id}")
        value = observed["value"]
        types = {int} if spec["type"] == "integer" else {int, float}
        require(type(value) in types and math.isfinite(value), f"Invalid actual performance measurement: {metric_id}")
    return measurements


def check_receipt(root, evidence, check):
    receipt, digest = read_receipt(root, evidence, expected_hash=True)
    match(receipt, {key: evidence[key] for key in ("source", "check_id", "check_key", "result")}, "Bound check receipt")
    if check["kind"] == "performance":
        require(evidence["source"] == "technical", "Performance requires actual technical measurements")
        return {"receipt_sha256": digest, "measurements": performance_measurements(receipt, check)}
    if check["kind"] == "visual-sheet":
        roles = check.get("view_roles", [])
        require(isinstance(roles, list), "A visual sheet declares its exact stage views")
        match(receipt, {"view_roles": roles}, "Visual sheet view")
        artifact_hash = receipt.get("artifact_sha256")
        artifact = verify_artifact(root, evidence, artifact_hash)
        require(artifact.suffix.casefold() in {".svg", ".png"}, "A visual sheet must be SVG or PNG")
        if artifact.suffix.casefold() == ".png":
            png_dimensions(artifact)
        return {"receipt_sha256": digest, "visual_artifact_sha256": artifact_hash, "view_roles": roles}
    return {"receipt_sha256": digest}


def verify_evidence(root: Path, evidence: dict, check: dict, candidate: dict,
                    environment: dict | None, fixture: bool) -> dict:
    """Validate a matched passing check without promoting simulated evidence."""
    try:
        source = evidence.get("source")
        match(evidence, {"check_id": check["id"], "result": "pass"}, "Evidence")
        require(digest_value(evidence.get("check_key")), "Evidence requires an exact check key")
        if source == "fixture":
            require(fixture is True, "Fixture evidence cannot establish actual review evidence")
            return fixture_evidence(evidence, check, candidate, environment)
        require(source in PRODUCERS and PRODUCERS[source] == check.get("producer"), "Wrong evidence producer for this check")
        kind = check["kind"]
        require((source != "unity-capture" or kind == "capture") and
                (source != "unity-motion" or kind == "motion") and
                (source != "blender-render" or kind in {"capture", "render"}) and
                (source not in {"technical", "agent"} or kind not in {"capture", "render", "motion"}),
                "Evidence source cannot establish this check kind")
        require(check.get("motion") is None or source == "unity-motion", "Still evidence cannot establish motion coverage")
        root = root.resolve(strict=True)
        if source == "unity-capture":
            verified = unity_capture(root, evidence, candidate, environment)
        elif source in {"unity-motion", "blender-render"}:
            verified = native_capture(root, evidence, check, candidate, environment)
        else:
            verified = check_receipt(root, evidence, check)
        return {"source": source, "native": not fixture and "artifact_sha256" in verified,
                "evidence_key": evidence["check_key"], **verified}
    except (OSError, KeyError, TypeError, AttributeError, OverflowError) as error:
        raise ValueError(f"Invalid review evidence: {error}") from error
