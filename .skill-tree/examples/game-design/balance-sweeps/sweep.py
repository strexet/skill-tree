"""Run the bounded deterministic energy fixture."""

import argparse
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import platform

MODEL = "energy-before-recharge@1"
RUNNER = "balance-parameter-sweep@1"
RESERVES = {"spend-when-affordable@1": 0, "keep-one-energy@1": 1}
COLUMNS = ["cost", "recharge", "policy", "actions", "end_energy", "zero_after_actions"]
TRACE_COLUMNS = ["tick", "start_energy", "opportunity", "acted", "after_action", "after_recharge"]
FIXTURE = Path(__file__).resolve().parent


def integer(value, name, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [{minimum}, {maximum}]")
    return value


def levels(values, name, minimum, maximum, *, allow_empty=False):
    if not isinstance(values, list) or (not values and not allow_empty):
        raise ValueError(f"{name} must be a list of levels")
    for value in values:
        integer(value, name, minimum, maximum)
    if len(set(values)) != len(values):
        raise ValueError(f"{name} must contain distinct levels")
    return values


def trace(initial_energy, capacity, ticks, opportunities, cost, recharge, policy):
    energy = initial_energy
    result = []
    for tick in range(1, ticks + 1):
        start = energy
        opportunity = tick in opportunities
        acted = opportunity and start - cost >= RESERVES[policy]
        after_action = start - cost if acted else start
        energy = min(capacity, after_action + recharge)
        result.append([tick, start, opportunity, acted, after_action, energy])
    return result


def summarize(cost, recharge, policy, steps):
    actions = sum(step[3] for step in steps)
    zeros = sum(step[3] and step[4] == 0 for step in steps)
    return [cost, recharge, policy, actions, steps[-1][-1], zeros]


def run(model):
    """Enumerate a small grid and one held-out opportunity schedule."""
    if model.get("model") != MODEL or not isinstance(model.get("study"), str) or not model["study"]:
        raise ValueError("model and study revisions are required")
    capacity = integer(model.get("capacity"), "capacity", 1, 64)
    initial = integer(model.get("initial_energy"), "initial_energy", 0, capacity)
    ticks = integer(model.get("ticks"), "ticks", 1, 64)
    costs = levels(model.get("costs"), "costs", 1, capacity)
    recharges = levels(model.get("recharges"), "recharges", 0, capacity)
    policies = model.get("policies")
    if (
        not isinstance(policies, list)
        or not policies
        or any(not isinstance(policy, str) or policy not in RESERVES for policy in policies)
        or len(set(policies)) != len(policies)
    ):
        raise ValueError("policies must contain distinct supported revisions")

    holdout = model.get("holdout")
    if holdout is not None:
        if not isinstance(holdout, dict):
            raise ValueError("holdout must be an object")
        hold_cost = integer(holdout.get("cost"), "holdout cost", 1, capacity)
        hold_recharge = integer(holdout.get("recharge"), "holdout recharge", 0, capacity)
        opportunities = frozenset(levels(holdout.get("opportunities"), "opportunities", 1, ticks, allow_empty=True))
    combinations = len(costs) * len(recharges) * len(policies)
    if combinations > 64:
        raise ValueError("grid budget exceeded")
    runs = combinations + (len(policies) if holdout is not None else 0)
    if runs * ticks > 1024:
        raise ValueError("step budget exceeded")

    grid = []
    every_tick = range(1, ticks + 1)
    for cost, recharge, policy in product(costs, recharges, policies):
        steps = trace(initial, capacity, ticks, every_tick, cost, recharge, policy)
        grid.append(summarize(cost, recharge, policy, steps))
    held_out = []
    held_out_traces = []
    if holdout is not None:
        for policy in policies:
            steps = trace(initial, capacity, ticks, opportunities, hold_cost, hold_recharge, policy)
            held_out.append(summarize(hold_cost, hold_recharge, policy, steps))
            held_out_traces.append(steps)
    return {
        "columns": COLUMNS,
        "grid": grid,
        "held_out": held_out,
        "trace_columns": TRACE_COLUMNS,
        "held_out_traces": held_out_traces,
    }


def content(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def report():
    model_bytes = (FIXTURE / "model.json").read_bytes()
    oracle_bytes = (FIXTURE / "oracle.json").read_bytes()
    model = json.loads(model_bytes)
    actual = run(model)
    expected = json.loads(oracle_bytes)
    if actual != expected:
        raise ValueError("fixture results differ from the independent oracle")
    return {
        "runner": RUNNER,
        "study": model["study"],
        "model": MODEL,
        "policy_reserve_energy": RESERVES,
        "environment": {"lane": "unit", "python": platform.python_version()},
        "phase_order": ["action opportunity", "post-action sample", "capped recharge"],
        "units": {"clock": "tick", "stock": "energy points", "actions": "successful actions"},
        "adverse_metric": "zero energy immediately after a successful action",
        "omissions": ["Product configuration", "Gameplay or human response evidence"],
        "source_sha256": {
            "model.json": sha256(model_bytes).hexdigest(),
            "oracle.json": sha256(oracle_bytes).hexdigest(),
            "sweep.py": sha256(Path(__file__).read_bytes()).hexdigest(),
        },
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
