#!/usr/bin/env python3
"""Prepare and inspect exact, file-based narrative canon snapshots."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import sys
from tempfile import NamedTemporaryFile


TYPED_ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)+")
KIND = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
SHA256 = re.compile(r"[a-f0-9]{64}")


class NarrativeError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise NarrativeError(message)


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")


def digest(content):
    return hashlib.sha256(content).hexdigest()


def unique_fields(pairs):
    fields = {}
    for key, value in pairs:
        require(key not in fields, f"Duplicate JSON field: {key}")
        fields[key] = value
    return fields


def invalid_constant(value):
    raise NarrativeError(f"Unsupported JSON constant: {value}")


def parse_json(content):
    return json.loads(
        content, object_pairs_hook=unique_fields, parse_constant=invalid_constant,
    )


def valid_id(identifier, prefix=""):
    return isinstance(identifier, str) and bool(TYPED_ID.fullmatch(identifier)) and identifier.startswith(prefix)


def ids(value):
    require(isinstance(value, list) and all(valid_id(item) for item in value), "Expected typed kebab-case IDs")
    require(len(set(value)) == len(value), "Duplicate record ID")
    return value


def valid_digest(value):
    return isinstance(value, str) and bool(SHA256.fullmatch(value))


def relative_parts(relative):
    require(
        isinstance(relative, str) and "\\" not in relative and "\0" not in relative
        and not PureWindowsPath(relative).drive and relative
        and all(part not in {"", ".", ".."} for part in relative.split("/")),
        "Repository-relative path required",
    )
    return relative.split("/")


def read_text(path):
    require(not path.is_symlink(), f"Symlinks are unsupported: {path.name}")
    require(path.is_file(), f"Required regular file is missing: {path.name}")
    return path.read_bytes().decode("utf-8")


def metadata_for(identifier, content):
    value = parse_json(content)
    require(isinstance(value, dict) and valid_id(value.get("id")), "Sidecar requires a typed record ID")
    if identifier is None:
        identifier = value["id"]
    require(value["id"] == identifier, f"Sidecar ID differs for {identifier}")
    kind = value.get("kind")
    require(isinstance(kind, str) and KIND.fullmatch(kind), f"Invalid kind for {identifier}")
    ids(value.get("depends_on"))
    require("status" not in value, f"Status follows snapshot membership for {identifier}")
    return value


def entry_for(identifier, record):
    require(
        isinstance(record, dict) and set(record) == {"markdown", "metadata"}
        and all(isinstance(value, str) for value in record.values()),
        f"Invalid stored record: {identifier}",
    )
    meta = metadata_for(identifier, record["metadata"])
    hashes = {key + "_sha256": digest(value.encode("utf-8")) for key, value in record.items()}
    return {
        **hashes,
        "revision": digest(canonical(hashes)),
        "kind": meta["kind"],
        "depends_on": meta["depends_on"],
    }


def missing_edges(entries):
    return {
        identifier: missing
        for identifier, entry in sorted(entries.items())
        if (missing := sorted(set(entry["depends_on"]) - entries.keys()))
    }


def check_graph(entries):
    missing = missing_edges(entries)
    require(not missing, "Missing normative dependency: " + ", ".join(
        f"{identifier} -> {', '.join(targets)}" for identifier, targets in missing.items()
    ))


def dependents(entries, roots):
    reverse = {}
    for identifier, entry in entries.items():
        for target in entry["depends_on"]:
            reverse.setdefault(target, set()).add(identifier)
    visited = set(roots)
    pending = list(roots)
    while pending:
        unseen = reverse.get(pending.pop(), set()) - visited
        pending.extend(unseen)
        visited.update(unseen)
    return sorted(visited - set(roots))


def proposal_digest(proposal):
    return digest(canonical({key: value for key, value in proposal.items() if key != "proposal_digest"}))


def verify_proposal(proposal, expected):
    require(isinstance(proposal, dict), "Proposal must be an object")
    require(
        valid_digest(expected) and proposal.get("proposal_digest") == expected
        and proposal_digest(proposal) == expected, "Proposal digest mismatch",
    )
    fields = {
        "schema", "work", "continuity", "base", "ids", "retire", "drafts", "entries",
        "affected", "retired", "proposal_digest",
    }
    schema = proposal.get("schema")
    require(type(schema) is int and schema in (1, 2), "Unsupported proposal schema")
    if schema == 2:
        fields.add("review_sources")
    require(proposal.keys() == fields, "Unsupported proposal schema")
    if schema == 2:
        review_source_paths(proposal["review_sources"])
    require(valid_id(proposal["work"], "work-"), "Expected a work- ID")
    require(valid_id(proposal["continuity"], "continuity-"), "Expected a continuity- ID")
    require(proposal["base"] is None or valid_digest(proposal["base"]), "Invalid base snapshot digest")
    for field in ("ids", "retire", "affected", "retired"):
        ids(proposal[field])
    require(isinstance(proposal["entries"], dict), "Invalid proposal entries")
    require(isinstance(proposal["drafts"], dict), "Invalid proposal drafts")


def review_source_paths(sources):
    require(isinstance(sources, list) and sources, "Bound proposal requires review sources")
    paths = []
    for source in sources:
        require(
            isinstance(source, dict) and source.keys() == {"path", "sha256"}
            and valid_digest(source["sha256"]), "Invalid review source binding",
        )
        relative_parts(source["path"])
        paths.append(source["path"])
    require(len(paths) == len(set(paths)), "Duplicate review source")
    require(paths == sorted(paths), "Review sources must use stable path order")
    return paths


def nonempty_text(value):
    return isinstance(value, str) and bool(value.strip())


def evidence_labels(value):
    return isinstance(value, list) and bool(value) and all(nonempty_text(item) for item in value)


def verify_review_packet(packet, proposal):
    fields = {
        "schema", "proposal_digest", "work", "continuity", "base", "record_scope", "review_sources",
        "reviewer", "coverage", "findings", "packet_digest",
    }
    require(
        isinstance(packet, dict) and packet.keys() == fields
        and type(packet["schema"]) is int and packet["schema"] == 1,
        "Unsupported review packet schema",
    )
    body = {key: value for key, value in packet.items() if key != "packet_digest"}
    require(
        valid_digest(packet["packet_digest"]) and digest(canonical(body)) == packet["packet_digest"],
        "Review packet digest mismatch",
    )
    require(
        all(packet[key] == proposal[key] for key in ("proposal_digest", "work", "continuity", "base", "review_sources")),
        "Review packet does not match the proposal and bound sources",
    )
    require(packet["record_scope"] == {
        "selected": proposal["ids"], "retired": proposal["retire"],
        "unchanged_dependents": proposal["affected"],
    }, "Review packet record scope does not match the proposal")
    reviewer = packet["reviewer"]
    require(
        isinstance(reviewer, dict) and reviewer.keys() == {"id", "role", "evidence"}
        and all(nonempty_text(value) for value in reviewer.values()), "Review packet requires reviewer evidence",
    )
    coverage = packet["coverage"]
    require(isinstance(coverage, list) and coverage, "Review packet requires evidence coverage")
    for item in coverage:
        require(
            isinstance(item, dict) and item.keys() == {"kind", "scope", "evidence"}
            and nonempty_text(item["kind"]) and nonempty_text(item["scope"]) and evidence_labels(item["evidence"]),
            "Invalid review coverage entry",
        )
    findings = packet["findings"]
    require(isinstance(findings, list), "Invalid review findings")
    seen = set()
    for finding in findings:
        require(
            isinstance(finding, dict)
            and (finding.keys() - {"resolution"}) == {"id", "scope", "severity", "status", "evidence"}
            and valid_id(finding["id"]) and finding["scope"] in ("in-scope", "out-of-scope")
            and finding["severity"] in ("blocker", "note")
            and finding["status"] in ("open", "resolved", "dismissed")
            and evidence_labels(finding["evidence"]), "Invalid review finding",
        )
        identifier = finding["id"]
        require(identifier not in seen, f"Duplicate review finding: {identifier}")
        seen.add(identifier)
        if finding["severity"] == "blocker":
            if finding["status"] == "open":
                require(finding["scope"] != "in-scope", f"Open in-scope blocker: {identifier}")
            else:
                require(nonempty_text(finding.get("resolution")), f"Review blocker requires a resolution: {identifier}")
    return packet["packet_digest"]


def verify_decision(content, proposal_id, packet_digest=None):
    decision = parse_json(content)
    require(
        isinstance(decision, dict) and decision.get("proposal_digest") == proposal_id
        and decision.get("decision") == "accepted"
        and isinstance(decision.get("author"), str) and bool(decision["author"].strip()),
        "Decision receipt must identify the author and explicitly accept this proposal digest",
    )
    if packet_digest is not None:
        require(decision.get("review_packet_digest") == packet_digest, "Decision receipt must accept this review packet")


def snapshot_id(proposal, decision_path, decision):
    return digest(canonical({
        "proposal_digest": proposal["proposal_digest"],
        "decision_path": decision_path,
        "decision_sha256": digest(decision.encode("utf-8")),
    }))


class Project:
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        require(self.root.is_dir(), "Project root must be a directory")

    def owned(self, relative):
        path = self.root
        for part in relative_parts(relative):
            path = path / part
            require(not path.is_symlink(), f"Symlinks are unsupported: {relative}")
        return path

    def init(self):
        directories = [
            self.owned(relative) for relative in (".narrative", ".narrative/records", ".narrative/snapshots")
        ]
        for directory in directories:
            require(not directory.exists() or directory.is_dir(), f"Project path is not a directory: {directory.name}")
        for directory in directories:
            directory.mkdir(exist_ok=True)
        return {"drafts": ".narrative/records", "snapshots": ".narrative/snapshots"}

    def drafts(self):
        path = self.owned(".narrative/records")
        require(path.is_dir(), "Draft directory is missing. Initialize the narrative project.")
        return path

    def draft_locations(self):
        directory = self.drafts()
        pending = [directory]
        pairs = {}
        while pending:
            for path in sorted(pending.pop().iterdir()):
                relative = path.relative_to(self.root).as_posix()
                require(not path.is_symlink(), f"Symlinks are unsupported: {relative}")
                if path.is_dir():
                    pending.append(path)
                elif path.suffix in {".md", ".json"}:
                    require(path.is_file(), f"Required regular file is missing: {relative}")
                    prefix = relative[:-len(path.suffix)]
                    pairs.setdefault(prefix, set()).add(path.suffix)
        record_prefix = directory.relative_to(self.root).as_posix() + "/"
        unpaired = sorted(prefix.removeprefix(record_prefix) for prefix, suffixes in pairs.items()
                          if suffixes != {".md", ".json"})
        require(not unpaired, "Missing draft Markdown or sidecar: " + ", ".join(unpaired))
        entries = {}
        for prefix in sorted(pairs):
            content = read_text(self.owned(prefix + ".json"))
            metadata = metadata_for(None, content)
            identifier = metadata["id"]
            require(identifier not in entries, f"Duplicate draft ID: {identifier}")
            entries[identifier] = (prefix, content, metadata)
        return entries

    def draft(self, identifier, locations):
        require(identifier in locations, f"Selected record is missing: {identifier}")
        prefix, metadata, _ = locations[identifier]
        return {"markdown": read_text(self.owned(prefix + ".md")), "metadata": metadata}

    def draft_entries(self):
        return {identifier: metadata for identifier, (_, _, metadata) in self.draft_locations().items()}

    def snapshot_path(self, identifier):
        require(valid_digest(identifier), "Expected a SHA-256 snapshot digest")
        return self.owned(f".narrative/snapshots/{identifier}.json")

    def snapshot(self, identifier):
        value = parse_json(read_text(self.snapshot_path(identifier)))
        require(isinstance(value, dict), "Unsupported snapshot format")
        proposal = value.get("proposal")
        require(isinstance(proposal, dict), "Snapshot proposal must be an object")
        verify_proposal(proposal, proposal.get("proposal_digest"))
        fields = {"proposal", "decision_path", "decision", "records"}
        if proposal["schema"] == 2:
            fields.add("review_packet")
        require(value.keys() == fields, "Unsupported snapshot format")
        packet_digest = verify_review_packet(value["review_packet"], proposal) if proposal["schema"] == 2 else None
        require(isinstance(value["decision"], str), "Invalid archived decision")
        verify_decision(value["decision"], proposal["proposal_digest"], packet_digest)
        relative_parts(value["decision_path"])
        require(
            identifier == snapshot_id(proposal, value["decision_path"], value["decision"]),
            "Snapshot identity mismatch",
        )
        records = value["records"]
        require(isinstance(records, dict), "Invalid snapshot records")
        require(all(valid_id(record_id) for record_id in records), "Invalid snapshot record ID")
        entries = {record_id: entry_for(record_id, record) for record_id, record in records.items()}
        require(entries == proposal["entries"], "Snapshot record hashes differ from the accepted proposal")
        require(not set(proposal["retired"]).intersection(entries), "Retired snapshot record is active")
        check_graph(entries)
        return value

    def context(self, snapshot, selected):
        value = self.snapshot(snapshot)
        records = value["records"]
        if selected is not None:
            entries = value["proposal"]["entries"]
            pending = list(ids(selected))
            closure = set(pending)
            for identifier in pending:
                require(identifier in entries, f"Selected record is missing: {identifier}")
            while pending:
                unseen = set(entries[pending.pop()]["depends_on"]) - closure
                closure.update(unseen)
                pending.extend(unseen)
            records = {identifier: records[identifier] for identifier in sorted(closure)}
        result = {
            "snapshot": snapshot, **value["proposal"],
            "records": records, "decision_path": value["decision_path"],
            "decision": value["decision"],
        }
        if "review_packet" in value:
            result["review_packet"] = value["review_packet"]
        return result

    def inventory(self, snapshot):
        if snapshot is None:
            locations = self.draft_locations()
            records = []
            for identifier, (prefix, _, metadata) in sorted(locations.items()):
                revision = entry_for(identifier, self.draft(identifier, locations))["revision"]
                records.append({"id": identifier, "kind": metadata["kind"], "status": "draft",
                                "revision": revision, "markdown": prefix + ".md",
                                "sidecar": prefix + ".json"})
            return {"scope": "drafts", "records": records}
        value = self.snapshot(snapshot)
        proposal = value["proposal"]
        archive = self.snapshot_path(snapshot).relative_to(self.root).as_posix()
        accepted = [{"id": identifier, "kind": entry["kind"], "status": "accepted",
                     "revision": entry["revision"], "archive": archive}
                    for identifier, entry in proposal["entries"].items()]
        retired = [{"id": identifier, "status": "retired"} for identifier in proposal["retired"]]
        return {"scope": "accepted", "snapshot": snapshot, "work": proposal["work"],
                "continuity": proposal["continuity"], "decision_path": value["decision_path"],
                "records": sorted(accepted + retired, key=lambda record: record["id"])}

    def impact(self, selected, snapshot, *, extended=False, work_pins=(), dramatic=(), suspected=()):
        selected = ids(selected)
        archive = self.snapshot(snapshot) if snapshot is not None else None
        if archive is None:
            locations = self.draft_locations()
            entries = {identifier: meta for identifier, (_, _, meta) in locations.items()}
        else:
            entries = archive["proposal"]["entries"]
        for identifier in selected:
            require(identifier in entries, f"Selected record is missing: {identifier}")
        result = {
            "scope": snapshot if snapshot is not None else "drafts",
            "ids": sorted(selected),
            "affected": dependents(entries, selected),
            "unresolved": missing_edges(entries),
        }
        if not extended:
            return result

        if archive is None:
            metadata = entries
            revisions = {identifier: entry_for(identifier, self.draft(identifier, locations))["revision"]
                         for identifier in locations} if work_pins else {}
            provenance = {identifier: prefix + ".json" for identifier, (prefix, _, _) in locations.items()}
            retired, continuity = set(), None
        else:
            metadata = {identifier: metadata_for(identifier, record["metadata"])
                        for identifier, record in archive["records"].items()}
            provenance = {identifier: f".narrative/snapshots/{snapshot}.json" for identifier in metadata}
            retired = set(archive["proposal"]["retired"])
            continuity = archive["proposal"]["continuity"]
            revisions = {identifier: entry["revision"] for identifier, entry in entries.items()}
        touched = set(selected) | set(result["affected"])
        result.update({
            "normative": {"closure_valid": not result["unresolved"],
                          "selected_changes": result["ids"], "dependent_records": result["affected"]},
            "optional": self.impact_optional(metadata, provenance, retired, touched),
            "dramatic": self.impact_dramatic(dramatic, metadata, retired, touched),
            "suspected": self.impact_suspected(suspected, touched),
            "work_pins": self.impact_work_pins(work_pins, snapshot, continuity, selected, entries, revisions),
        })
        return result

    @staticmethod
    def impact_target_status(identifier, records, retired):
        if identifier in records:
            return "active"
        if identifier in retired:
            return "retired"
        return "unresolved"

    def impact_optional(self, metadata, provenance, retired, touched):
        kinds = {"mentions", "features", "occurs-at", "causes", "precedes", "adapted-from"}
        rows = []
        for source, record in sorted(metadata.items()):
            relationships = record.get("relationships", [])
            require(isinstance(relationships, list), f"Invalid optional relationships: {source}")
            for link in relationships:
                require(isinstance(link, dict) and isinstance(link.get("kind"), str)
                        and link["kind"] in kinds and valid_id(link.get("target")),
                        f"Invalid optional relationship: {source}")
                target = link["target"]
                if source not in touched and target not in touched:
                    continue
                rows.append({
                    **{key: link[key] for key in ("kind", "scope", "locator") if key in link},
                    "source": source,
                    "target": target,
                    "source_locator": provenance[source],
                    "target_status": self.impact_target_status(target, metadata, retired),
                })
        return sorted(rows, key=canonical)

    def impact_dramatic(self, paths, records, retired, touched):
        kinds = {"prepares", "pays-off", "poses-question", "reveals", "reframes", "contrasts", "reprises-motif"}
        rows, seen = [], set()
        for path in sorted(set(paths)):
            link = parse_json(read_text(self.owned(path)))
            require(isinstance(link, dict) and valid_id(link.get("id")) and link["id"] not in seen
                    and isinstance(link.get("relation"), str) and link["relation"] in kinds,
                    f"Invalid or duplicate dramatic intent: {path}")
            seen.add(link["id"])
            for key in ("source", "target"):
                endpoint = link.get(key)
                require(isinstance(endpoint, dict) and valid_id(endpoint.get("scene"))
                        and ("beat" not in endpoint or valid_id(endpoint["beat"])),
                        f"Invalid dramatic endpoint: {path}")
            source, target = (link[key]["scene"] for key in ("source", "target"))
            if source in touched or target in touched:
                rows.append({
                    **{key: link[key] for key in ("id", "source", "target", "relation", "scope", "coverage")
                       if key in link},
                    "source_locator": path,
                    "scope_resolution": "unverified",
                    "source_status": self.impact_target_status(source, records, retired),
                    "target_status": self.impact_target_status(target, records, retired),
                    "beat_resolution": "unverified" if any("beat" in link[key] for key in ("source", "target"))
                    else "not-specified",
                })
        return sorted(rows, key=canonical)

    def impact_suspected(self, paths, touched):
        rows = []
        for path in sorted(set(paths)):
            report = parse_json(read_text(self.owned(path)))
            require(isinstance(report, dict) and isinstance(report.get("links"), list),
                    f"Expected a suspected link list: {path}")
            for link in report["links"]:
                require(isinstance(link, dict) and valid_id(link.get("source")) and valid_id(link.get("target"))
                        and isinstance(link.get("evidence"), str) and bool(link["evidence"].strip())
                        and isinstance(link.get("question"), str) and bool(link["question"].strip()),
                        f"Invalid suspected link: {path}")
                if link["source"] in touched or link["target"] in touched:
                    rows.append({
                        **{key: link[key] for key in ("source", "target", "evidence", "question", "scope")
                           if key in link},
                        "source_locator": path,
                        "status": "unverified",
                    })
        return sorted(rows, key=canonical)

    def impact_work_pins(self, paths, snapshot, continuity, selected, entries, revisions):
        rows, seen = [], set()
        for path in sorted(set(paths)):
            manifest = parse_json(read_text(self.owned(path)))
            require(isinstance(manifest, dict) and type(manifest.get("schema_version")) is int
                    and manifest["schema_version"] == 1 and valid_id(manifest.get("work_id"), "work-")
                    and valid_id(manifest.get("continuity_id"), "continuity-"),
                    f"Invalid work manifest: {path}")
            work, work_continuity = manifest["work_id"], manifest["continuity_id"]
            require(work not in seen, f"Duplicate selected work: {work}")
            seen.add(work)
            pin = manifest.get("canon_pin")
            require(isinstance(pin, dict) and "digest" in pin
                    and pin.get("state") in ("accepted", "empty", "unresolved"),
                    f"Invalid work canon pin: {path}")
            row = {"work": work, "continuity": work_continuity,
                   "source_locator": path, "current_pin": {"state": pin["state"], "digest": pin["digest"]}}
            if pin["state"] != "accepted":
                require(pin["digest"] is None, f"Unresolved work pin must have null digest: {path}")
                row["comparison"] = "no-accepted-pin"
            else:
                current = self.snapshot(pin["digest"])["proposal"]
                require(current["continuity"] == work_continuity, f"Work pin continuity differs: {path}")
                row["historical_pin"] = "preserved"
                if continuity is not None and continuity != work_continuity:
                    row["comparison"] = "different-continuity"
                else:
                    old_entries = current["entries"]
                    dependents_to_review = sorted(set(dependents(entries, selected))
                                                  | set(dependents(old_entries, selected)))
                    old_revisions = {key: entry["revision"] for key, entry in old_entries.items()}
                    relevant = set(selected) | set(dependents_to_review)
                    unavailable = relevant - revisions.keys() if snapshot is None else set()
                    changed = sorted(key for key in relevant - unavailable
                                     if old_revisions.get(key) != revisions.get(key))
                    row["comparison"] = ("already-selected" if snapshot == pin["digest"] else
                                         "selected-snapshot" if snapshot is not None else "draft-scope-unverified")
                    row["if_moved"] = {
                        "changed_records": changed,
                        "unchanged_dependents": [key for key in dependents_to_review
                                                 if key not in changed and key not in unavailable],
                    }
                    if unavailable:
                        row["if_moved"]["unavailable_records"] = sorted(unavailable)
            rows.append(row)
        return sorted(rows, key=lambda row: row["work"])

    def review_source_bindings(self, paths):
        require(len(paths) == len(set(paths)), "Duplicate review source")
        bindings = []
        for relative in sorted(paths):
            source = self.owned(relative)
            require(source.is_file(), f"Required review source is missing or not a regular file: {relative}")
            bindings.append({"path": relative, "sha256": digest(source.read_bytes())})
        return bindings

    def prepare(self, work, continuity, base, selected, retire, review_sources=()):
        require(valid_id(work, "work-"), "Expected a work- ID")
        require(valid_id(continuity, "continuity-"), "Expected a continuity- ID")
        selected = sorted(ids(selected))
        retire = sorted(ids(retire))
        require(selected or retire, "Select at least one draft or retirement")
        require(not set(selected).intersection(retire), "A record cannot be proposed and retired together")
        existing, entries, retired = {}, {}, set()
        if base is not None:
            original = self.snapshot(base)
            require(original["proposal"]["continuity"] == continuity, "Base snapshot belongs to another continuity")
            existing = original["records"]
            entries = original["proposal"]["entries"]
            retired = set(original["proposal"]["retired"])
        for identifier in retire:
            require(identifier in existing, f"Retirement requires an active base entry: {identifier}")
        locations = self.draft_locations() if selected else {}
        drafts = {identifier: self.draft(identifier, locations) for identifier in selected}
        replacements = {identifier: entry_for(identifier, record) for identifier, record in drafts.items()}
        records = {key: value for key, value in existing.items() if key not in retire} | drafts
        candidate = {key: value for key, value in entries.items() if key not in retire} | replacements
        check_graph(candidate)
        changed = [identifier for identifier, entry in replacements.items() if entries.get(identifier) != entry]
        proposal = {
            "schema": 1, "work": work, "continuity": continuity, "base": base,
            "ids": selected, "retire": retire, "drafts": replacements, "entries": candidate,
            "affected": sorted(set(dependents(candidate, changed)) - set(selected)),
            "retired": sorted((retired | set(retire)) - set(selected)),
        }
        if review_sources:
            proposal["schema"] = 2
            proposal["review_sources"] = self.review_source_bindings(review_sources)
        proposal["proposal_digest"] = proposal_digest(proposal)
        return proposal, records

    def accept(self, proposal_path, expected, decision_path, review_packet_path=None):
        proposal_file = Path(proposal_path)
        proposal_text = read_text(proposal_file)
        proposal = parse_json(proposal_text)
        verify_proposal(proposal, expected)
        bound = proposal["schema"] == 2
        packet = packet_text = packet_digest = None
        review_sources = []
        if bound:
            require(review_packet_path is not None, "Bound proposal requires a review packet")
            packet_text = read_text(self.owned(review_packet_path))
            packet = parse_json(packet_text)
            packet_digest = verify_review_packet(packet, proposal)
            review_sources = review_source_paths(proposal["review_sources"])
        else:
            require(review_packet_path is None, "A legacy proposal has no review packet")
        decision = read_text(self.owned(decision_path))
        verify_decision(decision, expected, packet_digest)
        identifier = snapshot_id(proposal, decision_path, decision)
        destination = self.snapshot_path(identifier)
        if destination.exists():
            self.snapshot(identifier)
            return {"snapshot": identifier, "created": False}

        inputs = [proposal[key] for key in ("work", "continuity", "base", "ids", "retire")]

        def checked_records():
            current, records = self.prepare(*inputs, review_sources)
            if bound:
                require(current["review_sources"] == proposal["review_sources"],
                        "Bound review source changed. Prepare and review a new proposal.")
            require(current == proposal, "Proposal sources changed. Prepare and review a new proposal.")
            return records

        archive = {
            "proposal": proposal, "decision_path": decision_path, "decision": decision, "records": checked_records(),
        }
        if bound:
            archive["review_packet"] = packet
        temporary = None
        try:
            with NamedTemporaryFile(dir=destination.parent, prefix=".pending-", delete=False) as stage:
                temporary = Path(stage.name)
                stage.write(canonical(archive) + b"\n")
                stage.flush()
                os.fsync(stage.fileno())
            checked_records()
            if bound:
                require(read_text(proposal_file) == proposal_text, "Proposal changed before publication")
                require(read_text(self.owned(review_packet_path)) == packet_text,
                        "Review packet changed before publication")
            require(read_text(self.owned(decision_path)) == decision, "Decision receipt changed before publication")
            try:
                os.link(temporary, self.snapshot_path(identifier))
            except FileExistsError:
                self.snapshot(identifier)
                return {"snapshot": identifier, "created": False}
            return {"snapshot": identifier, "created": True}
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "context", "inventory", "impact", "propose", "accept"):
        command = commands.add_parser(name)
        command.add_argument("root")
        if name == "context":
            command.add_argument("--snapshot", required=True)
            command.add_argument("--ids", nargs="+")
        elif name in {"impact", "inventory"}:
            scope = command.add_mutually_exclusive_group(required=True)
            scope.add_argument("--drafts", action="store_true")
            scope.add_argument("--snapshot")
            if name == "impact":
                command.add_argument("--ids", required=True, nargs="+")
                command.add_argument("--extended", action="store_true")
                command.add_argument("--work-pin", action="append", default=[])
                command.add_argument("--dramatic", action="append", default=[])
                command.add_argument("--suspected", action="append", default=[])
        elif name == "propose":
            command.add_argument("--work", required=True)
            command.add_argument("--continuity", required=True)
            command.add_argument("--base")
            command.add_argument("--ids", nargs="+", default=[])
            command.add_argument("--retire", nargs="+", default=[])
            command.add_argument("--review-source", action="append", default=[])
        elif name == "accept":
            command.add_argument("--proposal", required=True)
            command.add_argument("--expected-proposal", required=True)
            command.add_argument("--decision", required=True)
            command.add_argument("--review-packet")
    return parser.parse_args()


def main():
    args = arguments()
    try:
        project = Project(args.root)
        if args.command == "init":
            result = project.init()
        elif args.command == "context":
            result = project.context(args.snapshot, args.ids)
        elif args.command == "inventory":
            result = project.inventory(args.snapshot)
        elif args.command == "impact":
            extended = args.extended or bool(args.work_pin or args.dramatic or args.suspected)
            result = project.impact(args.ids, args.snapshot, extended=extended,
                                    work_pins=args.work_pin, dramatic=args.dramatic,
                                    suspected=args.suspected)
            if extended and result["unresolved"]:
                print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
                return 1
        elif args.command == "propose":
            result, _ = project.prepare(args.work, args.continuity, args.base, args.ids, args.retire, args.review_source)
        else:
            result = project.accept(args.proposal, args.expected_proposal, args.decision, args.review_packet)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
        return 0
    except (ValueError, OSError) as error:
        print(f"narrative-state: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
