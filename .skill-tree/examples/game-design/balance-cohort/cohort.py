"""Analyze the synthetic provider-neutral launch adoption fixture."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from math import erfc, isclose, isfinite, sqrt
from pathlib import Path
import platform

ARMS = ("baseline", "candidate")
ANALYZER = "synthetic-exposure-cohort@1"
FIXTURE = Path(__file__).resolve().parent


def content(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def observation_scope(study):
    builds = study.get("builds")
    if (
        not isinstance(builds, dict)
        or set(builds) != set(ARMS)
        or any(not isinstance(build, str) or not build for build in builds.values())
        or not isinstance(study.get("rule"), str)
        or not study["rule"]
    ):
        raise ValueError("both build identities and a rule revision are required")
    segments = study.get("segments")
    if (
        not isinstance(segments, list)
        or not segments
        or any(not isinstance(segment, str) or not segment for segment in segments)
        or len(set(segments)) != len(segments)
    ):
        raise ValueError("segments must contain distinct keys")
    window = study.get("window")
    if not isinstance(window, dict) or window.get("complete") is not True:
        raise ValueError("incomplete observation window")
    start, end = window.get("start_tick"), window.get("end_tick")
    if type(start) is not int or type(end) is not int or start >= end:
        raise ValueError("invalid observation window")
    return start, end


def unique_events(events, excluded):
    indexed = {}
    for event in events:
        if (
            not isinstance(event, dict)
            or event.get("kind") not in ("exposure", "launch-use")
            or not isinstance(event.get("id"), str)
            or not event["id"]
            or type(event.get("tick")) is not int
        ):
            raise ValueError("invalid event kind, ID or tick")
        event_id = event["id"]
        encoded = content(event)
        if event_id in indexed:
            if encoded != indexed[event_id][1]:
                raise ValueError(f"conflicting event ID: {event_id}")
            excluded["duplicate_event"] += 1
        else:
            indexed[event_id] = event, encoded
    return {key: value[0] for key, value in sorted(indexed.items())}


def exposure_rows(study, events, start, end, excluded):
    players = set()
    assigned = Counter()
    exposures = {}
    for event in events.values():
        if event["kind"] != "exposure":
            continue
        arm = event.get("arm")
        if arm not in ARMS or event.get("build") != study["builds"][arm] or event.get("rule") != study["rule"]:
            excluded["foreign_build_or_rule"] += 1
            continue
        if not start <= event["tick"] < end:
            excluded["exposure_outside_window"] += 1
            continue
        player = event.get("player")
        if not isinstance(player, str) or not player:
            raise ValueError("exposures require a player ID")
        if player in players:
            raise ValueError(f"duplicate exposed player: {player}")
        players.add(player)
        assigned[arm] += 1
        if type(event.get("eligible")) is not bool:
            raise ValueError("exposures require explicit eligibility")
        if not event["eligible"]:
            excluded["ineligible_exposure"] += 1
            continue
        segment_tick = event.get("segment_tick")
        if (
            event.get("segment") not in study["segments"]
            or type(segment_tick) is not int
            or segment_tick >= event["tick"]
        ):
            excluded["unknown_pre_exposure_segment"] += 1
            continue
        exposures[event["id"]] = event
    return exposures, assigned


def observed_uses(events, exposures, end, excluded):
    converted = set()
    for event in events.values():
        if event["kind"] != "launch-use":
            continue
        exposure_id = event.get("exposure_id")
        if not isinstance(exposure_id, str) or not exposure_id:
            raise ValueError("outcomes require an exposure ID")
        if exposure_id not in events or events[exposure_id]["kind"] != "exposure":
            excluded["outcome_without_exposure"] += 1
        elif exposure_id not in exposures:
            excluded["outcome_for_excluded_exposure"] += 1
        elif not exposures[exposure_id]["tick"] < event["tick"] < end:
            excluded["outcome_outside_observation"] += 1
        elif exposure_id in converted:
            excluded["repeat_outcome"] += 1
        else:
            converted.add(exposure_id)
    return converted


def rate(events, eligible):
    if not eligible:
        return {"events": events, "eligible": eligible, "rate": None, "wilson_95": None}
    proportion = events / eligible
    z = 1.959963984540054
    denominator = 1 + z * z / eligible
    center = (proportion + z * z / (2 * eligible)) / denominator
    half_width = z * sqrt(proportion * (1 - proportion) / eligible + z * z / (4 * eligible * eligible)) / denominator
    return {
        "events": events,
        "eligible": eligible,
        "rate": proportion,
        "wilson_95": [max(0, center - half_width), min(1, center + half_width)],
    }


def compare(segments, exposures, converted):
    arm_counts = {(arm, segment): [0, 0] for arm in ARMS for segment in segments}
    for exposure_id, exposure in exposures.items():
        counts = arm_counts[exposure["arm"], exposure["segment"]]
        counts[0] += exposure_id in converted
        counts[1] += 1
    baseline_total = sum(arm_counts["baseline", segment][1] for segment in segments)
    weights = {
        segment: arm_counts["baseline", segment][1] / baseline_total if baseline_total else None
        for segment in segments
    }
    arms = {}
    for arm in ARMS:
        split = {segment: rate(*arm_counts[arm, segment]) for segment in segments}
        row = {
            "pooled": rate(sum(cell["events"] for cell in split.values()), sum(cell["eligible"] for cell in split.values())),
            "segments": split,
            "standardized_rate": None,
        }
        empty = [segment for segment in segments if weights[segment] in (None, 0) or split[segment]["rate"] is None]
        if empty:
            row["standardization_hold"] = "empty segment: " + ", ".join(empty)
        else:
            row["standardized_rate"] = sum(weights[segment] * split[segment]["rate"] for segment in segments)
        arms[arm] = row
    return arms, weights


def allocation(study, assigned):
    design = study.get("design")
    if design == "observational":
        return {"status": "not-applicable", "reason": "observational"}
    if design != "randomized":
        raise ValueError("unsupported study design")
    ratios = study.get("assignment_ratios")
    if (
        not isinstance(ratios, dict)
        or set(ratios) != set(ARMS)
        or any(type(ratio) not in (int, float) or not isfinite(ratio) or not 0 < ratio < 1 for ratio in ratios.values())
        or not isclose(sum(ratios.values()), 1, rel_tol=0, abs_tol=1e-12)
    ):
        raise ValueError("randomization requires explicit assignment ratios summing to one")
    observed = {arm: assigned[arm] for arm in ARMS}
    expected = {arm: ratios[arm] * sum(observed.values()) for arm in ARMS}
    packet = {"observed": observed, "expected": expected, "grain": "in-scope exposure before analysis exclusions"}
    if any(count < 5 for count in expected.values()):
        return packet | {"status": "insufficient expected counts"}
    chi_square = sum((observed[arm] - expected[arm]) ** 2 / expected[arm] for arm in ARMS)
    return packet | {"status": "descriptive diagnostic", "chi_square": chi_square, "p_value": erfc(sqrt(chi_square / 2))}


def analyze(study, events):
    """Aggregate at the synthetic player grain under complete observed exposure."""
    start, end = observation_scope(study)
    excluded = Counter()
    indexed = unique_events(events, excluded)
    exposures, assigned = exposure_rows(study, indexed, start, end, excluded)
    converted = observed_uses(indexed, exposures, end, excluded)
    arms, weights = compare(study["segments"], exposures, converted)
    return {
        "study": study["study"],
        "builds": study["builds"],
        "rule": study["rule"],
        "observation_window": study["window"],
        "unit": study["unit"],
        "time_unit": study["time_unit"],
        "eligibility": study["eligibility"],
        "metric": study["metric"],
        "uncertainty": "Descriptive Wilson 95 percent intervals for raw binomial proportions",
        "input_event_count": len(events),
        "canonical_event_sha256": sha256(content(sorted(content(event).decode() for event in events))).hexdigest(),
        "excluded": dict(sorted(excluded.items())),
        "arms": arms,
        "standard_weights": weights,
        "allocation": allocation(study, assigned),
    }


def expected_metrics(actual):
    def counts(cell):
        return {name: cell[name] for name in ("events", "eligible")}

    return {
        arm: {
            "pooled": counts(row["pooled"]),
            "segments": {segment: counts(cell) for segment, cell in row["segments"].items()},
            "standardized_rate": row["standardized_rate"],
        }
        for arm, row in actual["arms"].items()
    }


def report():
    sources = {
        name: (FIXTURE / name).read_bytes() for name in ("cohort.py", "events.jsonl", "study.json", "oracle.json")
    }
    study = json.loads(sources["study.json"])
    events = [json.loads(line) for line in sources["events.jsonl"].splitlines()]
    expected = json.loads(sources["oracle.json"])
    actual = analyze(study, events)
    if expected_metrics(actual) != expected:
        raise ValueError("fixture metrics differ from independent expected counts")
    return {
        "analyzer": ANALYZER,
        "environment": {"lane": "unit", "python": platform.python_version()},
        "source_kind": "synthetic observations",
        "omissions": ["Live event access", "Causal or production inference", "Player identity data"],
        "source_sha256": {name: sha256(data).hexdigest() for name, data in sources.items()},
        "artifact_sha256": sha256(content(actual)).hexdigest(),
        "expected": expected,
        "actual": actual,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_bytes(content(report()))


if __name__ == "__main__":
    main()
