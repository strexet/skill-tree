"""Query exact revision dependencies in the disposable Mechanics atlas."""
from collections import defaultdict, deque
from hashlib import sha256
from pathlib import Path
import json
import platform
import re

EDGE_KINDS = {
    "uses-rule": ("placement", "rule"),
    "extends-placement": ("placement", "placement"),
    "validates-placement": ("check", "placement"),
}
PIN = re.compile(r"([a-z0-9-]+)/[a-z0-9-]+@[1-9][0-9]*")
FIXTURE_PATH = Path(".skill-tree/examples/game-design/mechanics-impact")
SOURCES = (
    Path(".skill-tree/common/references/game-design-atlas.md"),
    Path(".skill-tree/common/references/game-design-records.md"),
    Path(".skill-tree/tests/test-mechanics-catalog-impact.py"),
    *(FIXTURE_PATH / name for name in ("README.md", "atlas.json", "expected.json", "query.py")),
)


def pin_status(scope, records, pin):
    match = PIN.fullmatch(pin)
    if match is None:
        return "invalid-pin"
    if match[1] != scope:
        return "foreign-scope"
    return "verified" if pin in records else "missing-revision"


def reaches(edges, start, target):
    queue = [start]
    seen = set()
    while queue:
        node = queue.pop()
        if node == target:
            return True
        if node not in seen:
            seen.add(node)
            queue.extend(edges.get(node, ()))
    return False


def dependency_edges(atlas, records):
    verified = []
    unresolved = []
    hierarchy = defaultdict(set)
    triples = sorted({(item["from"], item["type"], item["to"]) for item in atlas["edges"]})
    for origin, relation, target in triples:
        edge = {"from": origin, "type": relation, "to": target}
        status = [pin_status(atlas["scope"], records, pin) for pin in (origin, target)]
        if relation not in EDGE_KINDS:
            reason = "unknown-relation"
        elif status != ["verified", "verified"]:
            reason = next(problem for problem in status if problem != "verified")
        elif (records[origin]["kind"], records[target]["kind"]) != EDGE_KINDS[relation]:
            reason = "wrong-record-type"
        else:
            verified.append(edge)
            if relation == "extends-placement":
                hierarchy[origin].add(target)
            continue
        unresolved.append({**edge, "reason": reason})

    usable = []
    for edge in verified:
        if edge["type"] == "extends-placement" and reaches(hierarchy, edge["to"], edge["from"]):
            unresolved.append({**edge, "reason": "hierarchy-cycle"})
        else:
            usable.append(edge)
    return usable, sorted(unresolved, key=lambda edge: (edge["from"], edge["type"], edge["to"]))


def query(atlas, changed):
    if atlas["schema"] != 1:
        raise ValueError("Unknown fixture atlas schema")
    records = {record["pin"]: record for record in atlas["records"]}
    if len(records) != len(atlas["records"]):
        raise ValueError("Duplicate exact record revision")
    usable, unresolved = dependency_edges(atlas, records)
    result = {"source": changed, "query_status": pin_status(atlas["scope"], records, changed),
              "affected": [], "unresolved": unresolved}
    if result["query_status"] != "verified":
        return result
    if records[changed]["kind"] != "rule":
        result["query_status"] = "wrong-record-type"
        return result

    reverse = defaultdict(list)
    for edge in usable:
        reverse[edge["to"]].append(edge)
    traces = {changed: []}
    ready = deque([changed])
    while ready:
        pin = ready.popleft()
        for edge in reverse[pin]:
            consumer = edge["from"]
            if consumer not in traces:
                traces[consumer] = [*traces[pin], edge]
                ready.append(consumer)

    dependencies = defaultdict(list)
    for edge in usable:
        if edge["from"] in traces and edge["to"] in traces:
            dependencies[edge["from"]].append(edge)
    result["source_evidence"] = records[changed]["evidence"]
    result["affected"] = [
        {**records[pin], "trace": traces[pin], "direct_dependencies": dependencies[pin]}
        for pin in sorted(set(traces) - {changed})
    ]
    return result


def source_digests(root):
    return {path.as_posix(): sha256((root / path).read_bytes()).hexdigest() for path in SOURCES}


def digest_result(observed):
    return sha256(json.dumps(observed, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def make_report(root):
    directory = root / FIXTURE_PATH
    atlas = json.loads((directory / "atlas.json").read_text())
    expected = json.loads((directory / "expected.json").read_text())
    observed = query(atlas, expected["source"])
    return {
        "schema": 1,
        "task_id": "T-8a649e9a-6493-40ed-8d37-0c735aa2983c",
        "scope": "One deterministic disposable atlas",
        "environment": {"python": platform.python_version(), "execution": "local-standard-library"},
        "source_sha256": source_digests(root),
        "result_sha256": digest_result(observed),
        "expected": expected,
        "observed": observed,
        "omissions": [
            "Evidence locators illustrate fixture record pins.",
            "Catalog-wide lookup, real project inspection and similarity ranking are outside the fixture.",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(make_report(Path(__file__).resolve().parents[4]), indent=2, sort_keys=True))
