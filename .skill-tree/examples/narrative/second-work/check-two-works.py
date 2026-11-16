"""Reproduce a Ridge Pack continuation in a disposable narrative project."""

from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory


FIXTURE = Path(__file__).resolve().parent
SCRIPT = FIXTURE.parents[2] / "common" / "scripts" / "narrative-state.py"
FIRST_RECORDS = FIXTURE.parent / "records"
SECOND_RECORDS = FIXTURE / "records"
STATE_ID = "state-ilya-ridge-after-lift"
ROLE_ID = "role-ilya-ridge-after-witness"
SCENE_ID = "scene-ridge-after-ledger"
IDENTITY_ID = "character-ilya"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def invoke(root, command, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), command, str(root), *args],
        capture_output=True, text=True, check=False, timeout=20,
    )


def run(root, command, *args):
    process = invoke(root, command, *args)
    if process.returncode:
        raise RuntimeError(process.stderr.strip())
    return json.loads(process.stdout)


def copy_records(source, destination):
    paths = sorted(path for path in source.iterdir() if path.suffix in {".json", ".md"})
    for path in paths:
        shutil.copyfile(path, destination / path.name)
    return [read_json(path)["id"] for path in paths if path.suffix == ".json"]


def accept_fixture(root, proposal, slug):
    proposal_path = root / f"fixture-{slug}-proposal.json"
    decision_path = root / f"fixture-{slug}-decision.json"
    write_json(proposal_path, proposal)
    write_json(decision_path, {
        "proposal_digest": proposal["proposal_digest"],
        "decision": "accepted",
        "author": "Synthetic fixture author",
        "reason": "Disposable two-work qualification.",
    })
    return run(
        root, "accept", "--proposal", str(proposal_path), "--expected-proposal",
        proposal["proposal_digest"], "--decision", decision_path.name,
    )["snapshot"]


def prepare_fixture(root):
    run(root, "init")
    records = root / ".narrative" / "records"
    first_ids = copy_records(FIRST_RECORDS, records)
    first_proposal = run(
        root, "propose", "--work", "work-ridge", "--continuity", "continuity-ridge",
        "--ids", *first_ids,
    )
    first_pin = accept_fixture(root, first_proposal, "first")
    first = run(root, "context", "--snapshot", first_pin)
    second_ids = copy_records(SECOND_RECORDS, records)
    manifest = read_json(FIXTURE / "work-ridge-after-manifest.json")
    manifest["predecessor"]["snapshot_digest"] = first_pin
    scene_file = records / f"{SCENE_ID}.json"
    scene = read_json(scene_file)
    origin = scene["adapted_from"]
    origin["snapshot_digest"] = first_pin
    origin["revision"] = first["entries"][origin["record_id"]]["revision"]
    write_json(scene_file, scene)
    return first, manifest, second_ids


def inspect_scope(first, manifest, state):
    predecessor = manifest["predecessor"]
    if predecessor["work_id"] != first["work"] or predecessor["snapshot_digest"] != first["snapshot"]:
        raise ValueError("The declared predecessor does not match the verified source pin.")
    if manifest["continuity_id"] != first["continuity"] or state["continuity_id"] != first["continuity"]:
        raise ValueError("The state and work require a compatible continuity.")
    if state["identity_id"] not in first["records"]:
        raise ValueError("The later state requires an accepted earlier identity.")
    required = state["requires_outcomes"]
    selected = predecessor["outcome_ids"]
    if predecessor["mode"] != "fixed-outcome" or len(selected) != 1:
        raise ValueError("The fixture requires one fixed predecessor outcome.")
    if set(required).issubset(selected):
        return None
    return {
        "code": "incompatible-predecessor-outcome",
        "work_id": manifest["work_id"],
        "state_id": state["id"],
        "source_record_id": predecessor["fact_refs"][0]["record_id"],
        "requires": required,
        "selected": selected,
    }


def qualify(root):
    first, manifest, second_ids = prepare_fixture(root)
    records = root / ".narrative" / "records"
    snapshots = root / ".narrative" / "snapshots"
    first_snapshot = snapshots / f'{first["snapshot"]}.json'
    original_bytes = first_snapshot.read_bytes()
    state = read_json(records / f"{STATE_ID}.json")
    if inspect_scope(first, manifest, state):
        raise ValueError("The selected lift continuation is incompatible.")

    adverse = read_json(FIXTURE / "adverse-predecessor.json")
    adverse_manifest = deepcopy(manifest)
    adverse_manifest["predecessor"]["outcome_ids"] = adverse["predecessor_outcome_ids"]
    finding = inspect_scope(first, adverse_manifest, state)
    expected = {
        **adverse["expected"], "work_id": adverse["work_id"], "state_id": adverse["state_id"],
    }
    if finding != expected or list(snapshots.glob("*.json")) != [first_snapshot]:
        raise ValueError("The adverse fixture must report an incompatible outcome without accepting a snapshot.")

    later_proposal = run(
        root, "propose", "--work", manifest["work_id"], "--continuity", manifest["continuity_id"],
        "--base", first["snapshot"], "--ids", *second_ids,
    )
    later_pin = accept_fixture(root, later_proposal, "later")
    manifest["canon_pin"] = {"state": "accepted", "digest": later_pin}
    later = run(root, "context", "--snapshot", later_pin)
    earlier_after = run(root, "context", "--snapshot", first["snapshot"])
    if earlier_after != first or first_snapshot.read_bytes() != original_bytes:
        raise ValueError("Preparing the later work changed the original pinned context.")
    revision = first["entries"][IDENTITY_ID]["revision"]
    if later["entries"][IDENTITY_ID]["revision"] != revision:
        raise ValueError("The later work changed the shared identity revision.")
    origin = json.loads(later["records"][SCENE_ID]["metadata"])["adapted_from"]
    if origin["snapshot_digest"] != first["snapshot"] or origin["revision"] != first["entries"]["scene-relay"]["revision"]:
        raise ValueError("Adaptation provenance does not resolve to the original scene.")
    return {
        "first_pin": first["snapshot"],
        "later_manifest": manifest,
        "shared_identity": {"id": IDENTITY_ID, "revision": revision},
        "later_state_id": STATE_ID,
        "later_role_id": ROLE_ID,
        "adapted_scene_id": SCENE_ID,
        "adaptation_origin": origin,
        "adverse_finding": finding,
    }


def main():
    with TemporaryDirectory(prefix="narrative-two-works-") as location:
        print(json.dumps(qualify(Path(location)), indent=2))


if __name__ == "__main__":
    main()
