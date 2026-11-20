#!/usr/bin/env python3
"""Validate portable ArtWorkshop records and reconcile local staging attempts."""

import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import sys
from tempfile import NamedTemporaryFile
from unicodedata import normalize


ID = re.compile(r"[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*")
REVISION = re.compile(r"[a-z0-9][a-z0-9-]*")
SHA = re.compile(r"[a-f0-9]{64}")
LOCAL = "workshop-local"
MARKER = "complete.json"
MANIFEST = "manifest.json"


class WorkshopError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise WorkshopError(message)


def matches(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return sha256(raw.encode("utf-8")).hexdigest()


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def invalid_number(value):
    raise WorkshopError(f"Invalid JSON number: {value}")


def read_record(path, label):
    require(path.is_file() and not path.is_symlink(), f"Missing regular {label}: {path.name}")
    value = json.loads(path.read_bytes(), object_pairs_hook=unique_fields, parse_constant=invalid_number)
    require(isinstance(value, dict) and type(value.get("schema")) is int and value["schema"] == 1,
            f"Unsupported {label} schema")
    return value


def path_parts(relative, allow_root=False):
    if allow_root and relative == ".":
        return ()
    require(isinstance(relative, str) and relative and not any(c in relative for c in "\\:\0"),
            "A portable POSIX relative path is required")
    require(relative == normalize("NFC", relative), f"Portable path must use Unicode NFC: {relative}")
    parts = tuple(relative.split("/"))
    require(all(part not in {"", ".", ".."} for part in parts), f"Invalid portable path: {relative}")
    return parts


def rooted(root, relative, allow_root=False):
    path = root
    for part in path_parts(relative, allow_root):
        path /= part
        require(not path.is_symlink(), f"Symlink path component: {part}")
    return path


def text_list(value, label):
    require(isinstance(value, list) and all(isinstance(item, str) and item for item in value),
            f"{label} requires a list of strings")
    require(len(value) == len(set(value)), f"Duplicate {label}")
    return value


def prefix(parent, child):
    return child[:len(parent)] == parent


def overlaps(left, right):
    return prefix(left, right) or prefix(right, left)


def path_key(parts):
    return tuple(normalize("NFC", part.casefold()) for part in parts)


def portable_paths(value, label):
    paths = text_list(value, label)
    normalized = []
    prefixes = {}
    for path in paths:
        parts = path_parts(path)
        key = path_key(parts)
        require(all(not overlaps(key, previous) for previous in normalized), f"Overlapping {label}: {path}")
        for length in range(1, len(parts) + 1):
            spelling = parts[:length]
            previous = prefixes.setdefault(key[:length], spelling)
            require(previous == spelling, f"Ambiguous path spelling in {label}: {path}")
        normalized.append(key)
    return paths


def reference(row):
    require(isinstance(row, dict) and matches(ID, row.get("id")) and matches(REVISION, row.get("revision")),
            "Records require a stable ID and revision")
    return row["id"] + "@" + row["revision"]


def record_for(records, key, label):
    require(isinstance(key, str) and key in records, f"Unknown {label} revision: {key}")
    return records[key]


def index_records(value, label):
    require(isinstance(value, list), f"{label} requires records")
    records = {}
    for row in value:
        key = reference(row)
        require(key not in records, f"Duplicate {label} revision: {key}")
        records[key] = row
    return records


def profile_overlay(value):
    require(isinstance(value, dict) and set(value) <= {"requirements", "preferences"},
            "Profiles require separate requirements and preferences")
    require(all(isinstance(group, dict) for group in value.values()), "Profile groups must be objects")
    return value


def merge_profile(effective, provenance, overlay, source, prefix_name=""):
    for name, value in overlay.items():
        require(isinstance(name, str) and name and "." not in name, "Profile keys must be nonempty and omit dots")
        key = prefix_name + name
        previous = effective.get(name)
        if isinstance(value, dict):
            if not isinstance(previous, dict):
                effective[name] = {}
                provenance.pop(key, None)
            merge_profile(effective[name], provenance, value, source, key + ".")
        else:
            for child in list(provenance):
                if child.startswith(key + "."):
                    del provenance[child]
            effective[name] = deepcopy(value)
            provenance[key] = source


class Catalog:
    def __init__(self, root):
        document = read_record(rooted(root, "contracts/workshop.json"), "workshop catalog")
        self.project = document.get("project")
        self.project_ref = reference(self.project)
        self.families = index_records(document.get("families"), "family")
        self.assets = index_records(document.get("assets"), "asset")
        self.recipes = index_records(document.get("recipes"), "recipe")
        self.targets = index_records(document.get("targets"), "target")
        self.environments = index_records(document.get("environments"), "environment")
        self.dependencies = self.assets | self.recipes
        require(len(self.dependencies) == len(self.assets) + len(self.recipes), "Conflicting asset and recipe identity")
        merge_profile({}, {}, profile_overlay(self.project.get("defaults")), self.project_ref)
        for key, family in self.families.items():
            merge_profile({}, {}, profile_overlay(family.get("defaults")), key)
        for key, asset in self.assets.items():
            record_for(self.families, asset.get("family"), "family")
            merge_profile({}, {}, profile_overlay(asset.get("overrides")), key)
        for target in self.targets.values():
            require(matches(ID, target.get("repository_identity")), "A portable repository identity is required")
            require(text_list(target.get("roles"), "target roles"), "At least one target role is required")
            path_parts(target.get("project_subpath"), allow_root=True)
            require(portable_paths(target.get("allowed_roots"), "target roots"), "At least one target root is required")
        for environment in self.environments.values():
            record_for(self.targets, environment.get("target"), "target")
            path_parts(environment.get("scene"))
        self.closure(self.dependencies)

    def closure(self, roots):
        complete = set()
        active = set()

        def visit(key):
            require(key not in active, f"Dependency cycle at {key}")
            if key in complete:
                return
            row = record_for(self.dependencies, key, "asset or recipe")
            active.add(key)
            for dependency in text_list(row.get("dependencies"), f"dependencies of {key}"):
                visit(dependency)
            active.remove(key)
            complete.add(key)

        for key in roots:
            visit(key)
        return sorted(complete)

    def resolve(self, asset_ref):
        asset = record_for(self.assets, asset_ref, "asset")
        family = self.families[asset["family"]]
        effective = {}
        provenance = {}
        for row, field in ((self.project, "defaults"), (family, "defaults"), (asset, "overrides")):
            merge_profile(effective, provenance, row[field], reference(row))
        dependencies = sorted(set(self.closure([asset_ref])) - {asset_ref})
        result = {
            "asset": asset_ref,
            "effective": effective,
            "provenance": provenance,
            "dependencies": dependencies,
            "dependency_digests": {key: digest(self.dependencies[key]) for key in dependencies},
        }
        return {**result, "content_digest": digest(result)}


def outputs_of(rows):
    require(isinstance(rows, list) and rows, "At least one output is required")
    paths = []
    for row in rows:
        require(isinstance(row, dict) and matches(ID, row.get("role")), "An output role is required")
        path = row.get("path")
        parts = path_parts(path)
        require(parts[0].casefold() not in {MARKER, MANIFEST}, f"Reserved staging path: {path}")
        paths.append(path)
    portable_paths(paths, "output paths")
    return {row["path"]: row["role"] for row in rows}


def job_snapshot(catalog, job):
    require(matches(ID, job.get("id")), "A stable job ID is required")
    asset = record_for(catalog.assets, job.get("asset"), "asset")
    recipe = record_for(catalog.recipes, job.get("recipe"), "recipe")
    target = record_for(catalog.targets, job.get("target"), "target")
    environment = record_for(catalog.environments, job.get("environment"), "environment")
    require(environment["target"] == job["target"], "Environment belongs to a different target")
    writes = portable_paths(job.get("write_paths"), "write paths")
    for relative in writes:
        require(any(prefix(path_parts(allowed), path_parts(relative)) for allowed in target["allowed_roots"]),
                f"Write path is outside authorized roots: {relative}")
    deadline = job.get("deadline_utc")
    if deadline is not None:
        require(isinstance(deadline, str), "Deadline must be a timezone-aware ISO timestamp")
        require(datetime.fromisoformat(deadline.replace("Z", "+00:00")).utcoffset() is not None,
                "Deadline must be a timezone-aware ISO timestamp")
    inputs = {
        "schema": 1,
        "job_id": job["id"],
        "asset": reference(asset),
        "asset_digest": digest(asset),
        "recipe": reference(recipe),
        "recipe_digest": digest(recipe),
        "profile": catalog.resolve(job["asset"]),
        "target": reference(target),
        "target_digest": digest(target),
        "environment": reference(environment),
        "environment_digest": digest(environment),
        "dependencies": {key: digest(catalog.dependencies[key])
                         for key in catalog.closure([job["asset"], job["recipe"]])},
        "write_paths": sorted(writes),
        "outputs": outputs_of(job.get("outputs")),
    }
    if deadline is not None:
        inputs["deadline_utc"] = deadline
    return inputs, target


def local_binding(root, snapshot, target):
    if not snapshot["write_paths"]:
        return None, []
    record = read_record(rooted(root, LOCAL + "/bindings.json"), "local bindings")
    rows = record.get("bindings")
    require(isinstance(rows, list) and all(isinstance(row, dict) for row in rows), "Invalid local bindings")
    matching = [row for row in rows if row.get("target") == snapshot["target"]]
    require(len(matching) == 1, "Exactly one local binding for the target revision is required")
    row = matching[0]
    path = row.get("checkout_path")
    require(matches(ID, row.get("checkout_id")) and isinstance(path, str) and Path(path).is_absolute(),
            "Local binding requires a checkout ID and an absolute checkout locator")
    checkout = Path(path).resolve(strict=True)
    project = rooted(checkout, target["project_subpath"], allow_root=True)
    require(project.is_dir(), "The bound project directory is unavailable")
    return {"checkout_id": row["checkout_id"], "project_path": str(project)}, [
        str(rooted(project, relative)) for relative in snapshot["write_paths"]
    ]


def atomic_record(path, value, temporary_dir=None):
    temporary_path = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=temporary_dir or path.parent,
                                prefix="workshop-record-", delete=False) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(value, temporary, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


@contextmanager
def writer(root):
    local = rooted(root, LOCAL)
    local.mkdir(exist_ok=True)
    lock = rooted(local, "writer-lock")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(lock, flags, 0o600), "r+b") as handle:
        require(stat.S_ISREG(os.fstat(handle.fileno()).st_mode), "ArtWorkshop writer guard requires a regular file")
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise WorkshopError(f"ArtWorkshop local writer cannot acquire the file lock: {error.strerror}") from error
        yield


def state(root):
    path = rooted(root, LOCAL + "/attempts.json")
    value = read_record(path, "local attempts") if path.exists() else {"schema": 1, "attempts": {}}
    require(isinstance(value.get("attempts"), dict), "Invalid local attempts index")
    require(isinstance(value.setdefault("retired_attempts", {}), dict), "Invalid retired attempts index")
    return path, value


def stage_paths(root, entry):
    snapshot = entry["job"]
    asset, revision = snapshot["asset"].split("@")
    return (
        rooted(root, f"{LOCAL}/staging/{snapshot['job_id']}/{entry['attempt_id']}"),
        rooted(root, f"{LOCAL}/staged/{asset}/{revision}"),
    )


def receipt(entry, status=None):
    return {
        "job_id": entry["job"]["job_id"],
        "attempt_id": entry["attempt_id"],
        "job_digest": entry["job_digest"],
        "status": status or entry["status"],
        **({"manifest_sha256": entry["manifest_sha256"]} if "manifest_sha256" in entry else {}),
    }


def start(root, job_path, attempt):
    require(matches(ID, attempt), "A stable attempt ID is required")
    job = read_record(rooted(root, job_path), "job")
    snapshot, target = job_snapshot(Catalog(root), job)
    checkout, writes = local_binding(root, snapshot, target)
    job_id = snapshot["job_id"]
    entry = {
        "job": snapshot, "job_digest": digest(snapshot), "attempt_id": attempt,
        "checkout": checkout, "physical_writes": writes, "status": "staging",
    }
    with writer(root):
        state_path, book = state(root)
        entries = book["attempts"]
        original = entries.get(job_id)
        if original is not None:
            require(all(original[key] == entry[key] for key in ("job_digest", "attempt_id", "checkout", "physical_writes")),
                    f"Original attempt must be reconciled for {job_id}")
            original = attempt_for(book, job_id, attempt)
            stage, destination = stage_paths(root, original)
            if original["status"] == "staging":
                stage.mkdir(parents=True, exist_ok=True)
            elif original["status"] == "staged":
                verify_stage(destination, original, marker_required=True)
            return receipt(original)
        require(attempt not in book["retired_attempts"].get(job_id, {}), "Use a new ID after an attempt is retired")
        stage, destination = stage_paths(root, entry)
        require(not destination.exists(), "The immutable staged revision already exists")
        require(not stage.exists(), "The staging directory has no matching attempt owner")
        for other_id, other in entries.items():
            _, other_destination = stage_paths(root, other)
            require(path_key(destination.parts) != path_key(other_destination.parts),
                    f"Staged revision is claimed by {other_id}")
            if other["status"] == "staged":
                continue
            for left in writes:
                left_parts = path_key(Path(left).parts)
                for right in other["physical_writes"]:
                    right_parts = path_key(Path(right).parts)
                    require(not overlaps(left_parts, right_parts), f"Target write overlaps original attempt {other_id}")
        entries[job_id] = entry
        atomic_record(state_path, book)
        stage.mkdir(parents=True)
        return receipt(entry)


def attempt_for(book, job_id, attempt):
    require(matches(ID, job_id) and matches(ID, attempt), "Exact job and attempt IDs are required")
    entry = book["attempts"].get(job_id)
    require(isinstance(entry, dict) and entry.get("attempt_id") == attempt, "The exact original attempt is required")
    require(entry["status"] in {"staging", "sealing", "staged"} and entry["job_digest"] == digest(entry["job"]),
            "Invalid original attempt state or changed job snapshot")
    require(entry["job"]["job_id"] == job_id, "Attempt state identifies another job")
    if entry["status"] in {"sealing", "staged"}:
        require(matches(SHA, entry.get("manifest_sha256")), "Journaled attempt requires the original manifest SHA-256")
    return entry


def file_hash(path):
    digest_bytes = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest_bytes.update(block)
    return digest_bytes.hexdigest()


def staged_files(directory):
    seen = set()
    for path in directory.rglob("*"):
        mode = path.lstat().st_mode
        require(stat.S_ISDIR(mode) or stat.S_ISREG(mode), f"Unsupported stage entry: {path.name}")
        if stat.S_ISREG(mode):
            seen.add(path.relative_to(directory).as_posix())
    return seen


def verify_stage(directory, entry, marker_required=False):
    manifest_path = rooted(directory, MANIFEST)
    manifest = read_record(manifest_path, "staging manifest")
    job = entry["job"]
    require((manifest.get("job_id"), manifest.get("attempt_id"), manifest.get("job_digest"))
            == (job["job_id"], entry["attempt_id"], entry["job_digest"]), "Staging manifest identifies another attempt")
    files = manifest.get("files")
    require(outputs_of(files) == job["outputs"], "Staging manifest does not cover the expected outputs")
    marker_path = rooted(directory, MARKER)
    declared = set(job["outputs"]) | {MANIFEST}
    if marker_path.exists():
        declared.add(MARKER)
    require(staged_files(directory) == declared, "Staging package inventory differs from the manifest")
    for item in files:
        path = rooted(directory, item["path"])
        require(matches(SHA, item.get("sha256")) and file_hash(path) == item["sha256"],
                f"Staging artifact digest mismatch: {item['path']}")
    manifest_sha = file_hash(manifest_path)
    if "manifest_sha256" in entry:
        require(manifest_sha == entry["manifest_sha256"], "Staging manifest differs from the original sealed attempt")
    marker = {
        "schema": 1,
        "job_id": job["job_id"],
        "attempt_id": entry["attempt_id"],
        "job_digest": entry["job_digest"],
        "manifest_sha256": manifest_sha,
    }
    if marker_required or marker_path.exists():
        require(read_record(marker_path, "completion marker") == marker, "Staging completion marker is stale")
    return marker


def stage_check(root, job_id, attempt):
    _, book = state(root)
    entry = attempt_for(book, job_id, attempt)
    stage, destination = stage_paths(root, entry)
    if entry["status"] == "staged":
        verify_stage(destination, entry, marker_required=True)
        return receipt(entry)
    verify_stage(stage, entry)
    return receipt(entry, "ready")


def reconcile_seal(root, entry):
    stage, destination = stage_paths(root, entry)
    if destination.exists():
        require(not stage.exists(), "Competing staging and staged directories require exact recovery")
        verify_stage(destination, entry, marker_required=True)
        return
    marker = verify_stage(stage, entry)
    marker_path = rooted(stage, MARKER)
    if not marker_path.exists():
        atomic_record(marker_path, marker, temporary_dir=stage.parent)
    verify_stage(stage, entry, marker_required=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    require(not destination.exists(), "The immutable staged revision already exists")
    stage.rename(destination)
    verify_stage(destination, entry, marker_required=True)


def retire(root, job_id, attempt):
    require(matches(ID, job_id) and matches(ID, attempt), "Exact job and attempt IDs are required")
    with writer(root):
        state_path, book = state(root)
        archive = book["retired_attempts"].get(job_id, {})
        if attempt in archive:
            return receipt(archive[attempt])
        entry = attempt_for(book, job_id, attempt)
        require(entry["status"] == "staging", "Only an unsealed original attempt can be retired")
        stage, destination = stage_paths(root, entry)
        require(not destination.exists() and not rooted(stage, MARKER).exists(),
                "A completed package or marker requires reconciliation")
        entry["status"] = "retired"
        book["retired_attempts"].setdefault(job_id, {})[attempt] = entry
        del book["attempts"][job_id]
        atomic_record(state_path, book)
        return receipt(entry)


def seal_or_recover(root, job_id, attempt, action):
    with writer(root):
        state_path, book = state(root)
        entry = attempt_for(book, job_id, attempt)
        stage, destination = stage_paths(root, entry)
        if entry["status"] == "staged":
            verify_stage(destination, entry, marker_required=True)
            return receipt(entry)
        if entry["status"] == "staging":
            if action == "recover":
                return receipt(entry, "incomplete")
            require(not destination.exists(), "The immutable staged revision already exists")
            require(not rooted(stage, MARKER).exists(), "The stage has an unowned completion marker")
            marker = verify_stage(stage, entry)
            entry.update(status="sealing", manifest_sha256=marker["manifest_sha256"])
            atomic_record(state_path, book)
        reconcile_seal(root, entry)
        entry["status"] = "staged"
        atomic_record(state_path, book)
        return receipt(entry)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("validate")
    actions.add_parser("resolve").add_argument("--asset", required=True)
    launch = actions.add_parser("start")
    launch.add_argument("--job", required=True)
    launch.add_argument("--attempt", required=True)
    for action in ("stage-check", "seal", "recover", "retire"):
        command = actions.add_parser(action)
        command.add_argument("--id", required=True)
        command.add_argument("--attempt", required=True)
    args = parser.parse_args()
    try:
        root = args.root.resolve(strict=True)
        require(root.is_dir(), "An existing workshop directory is required")
        if args.action == "validate":
            catalog = Catalog(root)
            result = {"schema": 1, "status": "valid", "project": catalog.project_ref,
                      "assets": len(catalog.assets), "recipes": len(catalog.recipes)}
        elif args.action == "resolve":
            result = Catalog(root).resolve(args.asset)
        elif args.action == "start":
            result = start(root, args.job, args.attempt)
        elif args.action == "stage-check":
            result = stage_check(root, args.id, args.attempt)
        elif args.action == "retire":
            result = retire(root, args.id, args.attempt)
        else:
            result = seal_or_recover(root, args.id, args.attempt, args.action)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, RecursionError) as error:
        print(f"ArtWorkshop: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
