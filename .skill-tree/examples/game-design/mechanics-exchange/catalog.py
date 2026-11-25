"""Export Markdown pins and exercise an exact disposable catalog adoption."""
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
from tempfile import TemporaryDirectory
from unittest.mock import patch

FIXTURE = Path(".skill-tree/examples/game-design/mechanics-exchange")
MARKDOWN = Path(".skill-tree/common/references/game-design-patterns.md")
EDITORIAL = FIXTURE / "editorial-fixture.md"
SOURCES = (
    MARKDOWN, EDITORIAL, Path(".skill-tree/common/references/game-design-records.md"),
    Path(".skill-tree/common/references/game-design-mechanics.md"),
    Path(".skill-tree/tests/test-mechanics-catalog-exchange.py"),
    *(FIXTURE / name for name in ("README.md", "catalog.py", "expected.json")),
)
PIN = re.compile(r"[a-z0-9-]+/[a-z0-9-]+@[1-9][0-9]*")
DIGEST = re.compile(r"[0-9a-f]{64}")
BATCH_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
LEGACY = "paper-race-exchange/combined-boost@1"
DUPLICATE = "paper-race-exchange/reveal-duplicate@1"
RESERVE = "skill-tree-mechanics/bounded-reserve@1"
BOOST = "skill-tree-mechanics/hold-to-boost@1"
REVEAL = "skill-tree-mechanics/spend-to-reveal@1"
MEMBERS = ("catalog", "vocabulary", "overlay")


class ShapeError(ValueError):
    pass


class Conflict(ValueError):
    pass


def encode(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()


def digest(data):
    return sha256(data).hexdigest()


def locator(path, heading, section):
    return {"path": path.as_posix(), "heading": heading, "sha256": digest(section.encode())}


def alias_rows(description):
    aliases = []
    for match in re.finditer(r"(English|Spanish) (.*?)(?= Spanish | English |$)", description):
        language = {"English": "en", "Spanish": "es"}[match[1]]
        for term in re.finditer(r"`([^`]+)`([^`]*)", match[2]):
            suffix = term[2].strip(" ,.")
            aliases.append({"language": language, "label": term[1], "context": suffix.removeprefix("in ")})
    return aliases


def extract_records(root, path, source, selected):
    text = (root / path).read_bytes().decode()
    headings = list(re.finditer(r"^## (.+)$", text, re.M))
    preamble = text[:headings[0].start()]
    if f"`{source}`" not in preamble:
        raise Conflict("Source record revision is unavailable")
    records = [{"pin": source, "kind": "source", "source": None, "aliases": [],
                "body": preamble.strip(), "locator": locator(path, preamble.splitlines()[0][2:], preamble)}]
    for index, heading in enumerate(headings):
        stop = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        section = text[heading.start():stop]
        identity = re.search(r"^\| Identity \| `([^`]+)` \|", section, re.M)
        if identity is None or identity[1] not in selected:
            continue
        aliases = re.search(r"^\| Aliases \| (.+) \|$", section, re.M)
        rule = re.search(r"^\| Rule \| (.+) \|$", section, re.M)
        if not aliases or not rule:
            raise Conflict("Incomplete selected Markdown record")
        records.append({"pin": identity[1], "kind": "pattern", "source": source,
                        "aliases": alias_rows(aliases[1]), "body": rule[1],
                        "locator": locator(path, heading[1], section)})
    if {record["pin"] for record in records[1:]} != set(selected):
        raise Conflict("Selected Markdown record revision is unavailable")
    return records


def initial_batch(root):
    records = extract_records(root, MARKDOWN, "skill-tree-mechanics/original-seed@1", (RESERVE, BOOST, REVEAL))
    records += extract_records(root, EDITORIAL, "paper-race-exchange/editorial-fixture@1", (LEGACY, DUPLICATE))
    return {
        "schema": 1, "batch_id": "seed-v1", "records": records, "redirects": [],
        "vocabulary": [{"term": "boost with reserve", "record_pin": LEGACY}],
        "overlay": {"project": "paper-race", "placements": [{"id": "bridge-boost", "record_pin": LEGACY}]},
    }


def migration_batch():
    return {
        "schema": 1, "batch_id": "editorial-v2", "records": [],
        "redirects": [
            {"from": DUPLICATE, "kind": "merge", "targets": [REVEAL], "decision": None},
            {"from": LEGACY, "kind": "split", "targets": [RESERVE, BOOST], "decision": BOOST},
        ],
        "vocabulary": [{"term": "bounded reserve", "record_pin": RESERVE},
                       {"term": "sustained movement", "record_pin": BOOST}],
        "overlay": {"project": "paper-race", "placements": [{"id": "bridge-boost", "record_pin": LEGACY}]},
    }


def fields(value, expected):
    if type(value) is not dict or value.keys() != expected.keys():
        raise ShapeError("invalid-shape: unexpected members")
    for name, allowed in expected.items():
        types = allowed if isinstance(allowed, tuple) else (allowed,)
        if type(value[name]) not in types:
            raise ShapeError(f"invalid-shape: {name}")


def validate_structure(batch):
    fields(batch, {"schema": int, "batch_id": str, "records": list, "redirects": list, "vocabulary": list, "overlay": dict})
    if batch["schema"] != 1:
        raise ShapeError("invalid-shape: unsupported schema")
    if not BATCH_ID.fullmatch(batch["batch_id"]):
        raise ShapeError("invalid-shape: batch identity")
    for record in batch["records"]:
        fields(record, {"pin": str, "kind": str, "source": (str, type(None)),
                        "body": str, "aliases": list, "locator": dict})
        fields(record["locator"], {"path": str, "heading": str, "sha256": str})
        for alias in record["aliases"]:
            fields(alias, {"language": str, "label": str, "context": str})
    for redirect in batch["redirects"]:
        fields(redirect, {"from": str, "kind": str, "targets": list, "decision": (str, type(None))})
        if any(type(target) is not str for target in redirect["targets"]):
            raise ShapeError("invalid-shape: redirect target")
    fields(batch["overlay"], {"project": str, "placements": list})
    for row in batch["overlay"]["placements"]:
        fields(row, {"id": str, "record_pin": str})
    for row in batch["vocabulary"]:
        fields(row, {"term": str, "record_pin": str})


def require_pattern(records, pin):
    if pin not in records or records[pin]["kind"] != "pattern":
        raise Conflict(f"invalid-revision: {pin}")


def staged_catalog(current, batch, batch_hash):
    records = dict(current["records"])
    redirects = dict(current["redirects"])
    for record in batch["records"]:
        pin = record["pin"]
        path = PurePosixPath(record["locator"]["path"])
        if not PIN.fullmatch(pin) or record["kind"] not in {"source", "pattern"}:
            raise Conflict(f"invalid-revision: {pin}")
        if path.is_absolute() or ".." in path.parts or not DIGEST.fullmatch(record["locator"]["sha256"]):
            raise Conflict(f"invalid-revision: source locator for {pin}")
        if pin in records and records[pin] != record:
            raise Conflict(f"record-revision-conflict: {pin}")
        records[pin] = record
    for pin, record in records.items():
        source = records.get(record["source"])
        if record["kind"] == "pattern" and (source is None or source["kind"] != "source"):
            raise Conflict(f"invalid-revision: source for {pin}")
        if record["kind"] == "source" and record["source"] is not None:
            raise Conflict(f"invalid-revision: source record {pin}")

    for redirect in batch["redirects"]:
        origin, targets = redirect["from"], redirect["targets"]
        require_pattern(records, origin)
        for target in targets:
            require_pattern(records, target)
        if origin in targets or len(set(targets)) != len(targets) or origin in redirects:
            raise Conflict(f"invalid-redirect: {origin}")
        if redirect["kind"] == "split":
            if len(targets) < 2 or redirect["decision"] not in targets:
                raise Conflict(f"ambiguous-split: {origin}")
        elif redirect["kind"] != "merge" or len(targets) != 1 or redirect["decision"] is not None:
            raise Conflict(f"invalid-redirect: {origin}")
        redirects[origin] = redirect

    for row in batch["overlay"]["placements"] + batch["vocabulary"]:
        require_pattern(records, row["record_pin"])
    receipts = {**current["receipts"], batch["batch_id"]: batch_hash}
    return {"records": records, "redirects": redirects, "receipts": receipts}


def recommended_pin(state, pin):
    require_pattern(state["catalog"]["records"], pin)
    redirect = state["catalog"]["redirects"].get(pin)
    if redirect is None:
        return pin
    return redirect["decision"] if redirect["kind"] == "split" else redirect["targets"][0]


def member_bytes(state):
    return {name: encode(state[name]) for name in MEMBERS}


def version_digest(files):
    return digest(encode({name: digest(contents) for name, contents in files.items()}))


def active_version(store):
    pointer = store / "active"
    if not pointer.exists():
        return None
    reply = pointer.read_text().strip()
    if not DIGEST.fullmatch(reply):
        raise Conflict("Invalid active version pointer")
    return reply


def load_version(store, active):
    if not DIGEST.fullmatch(active):
        raise Conflict("Invalid version identity")
    directory = store / "versions" / active
    files = {name: (directory / (name + ".json")).read_bytes() for name in MEMBERS}
    if version_digest(files) != active:
        raise Conflict("Disposable version set has inconsistent bytes")
    return {name: json.loads(content) for name, content in files.items()}


def switch_pointer(store, active, staging):
    pointer = staging / "active"
    pointer.write_text(active + "\n")
    os.replace(pointer, store / "active")


def import_batch(store, batch, *, expected_active):
    validate_structure(batch)
    active = active_version(store)
    current = load_version(store, active)["catalog"] if active else {"records": {}, "redirects": {}, "receipts": {}}
    batch_hash = digest(encode(batch))
    previous_batch = current["receipts"].get(batch["batch_id"])
    if previous_batch is not None:
        if previous_batch != batch_hash:
            raise Conflict("batch-content-conflict")
        return {"status": "replayed", "active": active, "batch_id": batch["batch_id"]}
    if active != expected_active:
        raise Conflict("stale-active-version")
    staged = {"catalog": staged_catalog(current, batch, batch_hash),
              "vocabulary": batch["vocabulary"], "overlay": batch["overlay"]}
    files = member_bytes(staged)
    version = version_digest(files)
    destination = store / "versions" / version
    destination.parent.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=store) as temporary:
        staging = Path(temporary)
        candidate = staging / "version"
        candidate.mkdir()
        for name, contents in files.items():
            (candidate / (name + ".json")).write_bytes(contents)
        if destination.exists():
            load_version(store, version)
        else:
            os.replace(candidate, destination)
        switch_pointer(store, version, staging)
    return {"status": "applied", "active": version, "batch_id": batch["batch_id"]}


def rollback(store, *, expected_active, restore):
    if active_version(store) != expected_active:
        raise Conflict("stale-active-version")
    load_version(store, restore)
    with TemporaryDirectory(dir=store) as temporary:
        switch_pointer(store, restore, Path(temporary))


def exercise(root, store):
    batch = initial_batch(root)
    initial = import_batch(store, batch, expected_active=None)
    before = active_version(store)
    replay = import_batch(store, batch, expected_active=None)
    invalid = {}

    def capture(name, attempt, expected, error=Conflict):
        try:
            import_batch(store, attempt, expected_active=expected)
        except error as failure:
            invalid[name] = str(failure)
        else:
            raise AssertionError(f"Fixture control unexpectedly passed: {name}")
        if active_version(store) != before:
            raise AssertionError(f"Rejected fixture changed active version: {name}")

    capture("invalid-shape", dict(batch, records={}), before, ShapeError)
    foreign = migration_batch()
    foreign["overlay"]["placements"][0]["record_pin"] = "paper-race-exchange/combined-boost@9"
    capture("invalid-revision", foreign, before)
    changed = {**batch["records"][0], "body": "Conflicting bytes at the original revision."}
    capture("record-revision-conflict", dict(batch, batch_id="changed", records=[changed]), before)
    capture("batch-content-conflict", dict(batch, records=[changed]), before)
    ambiguous = migration_batch()
    ambiguous["redirects"][1]["decision"] = None
    capture("ambiguous-split", ambiguous, before)
    migration = migration_batch()
    capture("stale-active-version", migration, "0" * 64)
    original_replace = os.replace

    def fail_pointer(src, dest):
        if dest == store / "active":
            raise OSError("Fixture interruption before active version switch")
        return original_replace(src, dest)

    with patch.object(os, "replace", fail_pointer):
        capture("failed-publish", migration, before, OSError)
    migrated = import_batch(store, migration, expected_active=before)["active"]
    current = load_version(store, migrated)
    rollback(store, expected_active=migrated, restore=before)
    restored = load_version(store, active_version(store))
    return {
        "initial_pins": sorted(restored["catalog"]["records"]),
        "initial_import": initial,
        "initial_replay": replay,
        "merge_redirect": recommended_pin(current, DUPLICATE),
        "split_redirect": recommended_pin(current, LEGACY),
        "historical_placement_pin": current["overlay"]["placements"][0]["record_pin"],
        "migration_vocabulary": [row["term"] for row in current["vocabulary"]],
        "invalid_controls": invalid,
        "migrated_version": migrated,
        "rolled_back_version": active_version(store),
        "restored_member_sha256": {name: digest(content) for name, content in member_bytes(restored).items()},
    }


def make_report(root):
    with TemporaryDirectory() as temporary:
        observed = exercise(root, Path(temporary))
    return {
        "schema": 1,
        "task_id": "T-07e60e24-7fe7-4acf-9a20-1d8308657df2",
        "scope": "One disposable Markdown-backed catalog, vocabulary and project overlay",
        "environment": {"python": platform.python_version(), "execution": "local-temporary-storage-standard-library"},
        "source_sha256": {path.as_posix(): digest((root / path).read_bytes()) for path in SOURCES},
        "output_sha256": digest(encode(observed)),
        "expected": json.loads((root / FIXTURE / "expected.json").read_text()),
        "observed": observed,
        "omissions": ["Canonical migration, external project access and concurrent writers are outside the fixture."],
    }


if __name__ == "__main__":
    print(json.dumps(make_report(Path(__file__).resolve().parents[4]), indent=2, sort_keys=True))
