"""Controlled routing and allocation experiments; existing source stays unchanged."""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))
import route_scenario as engine

METHODS = ("nearest", "priority_nearest", "exact_dp")


def priority_greedy_solution(payload: dict) -> dict:
    """Choose feasible new tier coverage first, then nearest, then candidate ID."""
    engine.validate_input(payload)
    candidates = [{**row, "index": i} for i, row in enumerate(payload["candidates"])]
    used = 0
    routes = []
    for _ in range(int(payload["vehicle_count"])):
        state = {
            "mask": 0,
            "last_node_id": payload["start_node_id"],
            "finish_minute": engine.parse_hhmm(payload["operating_start"]),
            "travel_minutes": 0.0,
            "travel_km": 0.0,
            "wait_minutes": 0.0,
            "service_minutes": 0,
            "stops": [],
        }
        for _ in range(int(payload["max_stops_per_vehicle"])):
            before, covered = engine._coverage(payload, used | state["mask"])
            options = []
            for candidate in candidates:
                bit = 1 << candidate["index"]
                if (used | state["mask"]) & bit:
                    continue
                after, new_covered = engine._coverage(payload, used | state["mask"] | bit)
                new_count = len(new_covered - covered)
                if new_count == 0:
                    continue
                next_state = engine._transition(payload, state, candidate)
                if next_state is None:
                    continue
                key = (
                    *[-(a - b) for a, b in zip(after, before)],
                    -new_count,
                    round(payload["travel_minutes"][state["last_node_id"]][candidate["candidate_id"]], 9),
                    candidate["candidate_id"],
                )
                options.append((key, next_state))
            if not options:
                break
            state = min(options, key=lambda item: item[0])[1]
        if state["mask"]:
            used |= state["mask"]
            routes.append(engine._finalize_route(payload, state))
    return {"candidate_mask": used, "routes": routes}


def run_method(payload: dict, method: str) -> tuple[dict, float]:
    engine.validate_input(payload)
    functions = {
        "nearest": engine.greedy_solution,
        "priority_nearest": priority_greedy_solution,
        "exact_dp": engine.exact_solution,
    }
    start = time.perf_counter()
    result = engine.summarize_solution(payload, functions[method](payload), method)
    return result, time.perf_counter() - start


def validate_province(payload: dict) -> None:
    zones = payload["zones"]
    if not zones:
        raise ValueError("no eligible service zones")
    if len({z["zone_id"] for z in zones}) != len(zones):
        raise ValueError("zone IDs must be unique")
    all_targets = []
    tier_ids = [tier["tier_id"] for tier in payload["priority_tiers"]]
    for zone in zones:
        local = zone["engine_input"]
        engine.validate_input(local)
        if tier_ids != [tier["tier_id"] for tier in local["priority_tiers"]]:
            raise ValueError("all zones must use the same ordered priority tiers")
        ids = [t["target_id"] for t in local["targets"]]
        if len(ids) != len(set(ids)):
            raise ValueError("target IDs must be unique within each zone")
        all_targets.extend(ids)
    if len(all_targets) != len(set(all_targets)):
        raise ValueError("target IDs must be disjoint across service zones")
    if int(payload["operating_days_per_cycle"]) > int(payload["service_cycle_days"]):
        raise ValueError("operating days exceed service cycle")


def outcome_tables(payload: dict) -> dict:
    """Use exactly the current province solver's candidate/day bounds and waiver."""
    capacity = payload["vehicle_count"] * payload["operating_days_per_cycle"]
    minimum = payload["minimum_route_days_per_active_zone"]
    if capacity < minimum * len(payload["zones"]):
        raise ValueError("capacity cannot meet minimum zone quotas")
    table = {}
    for zone in sorted(payload["zones"], key=lambda z: z["zone_id"]):
        local = zone["engine_input"]
        rows = {}
        for days in range(max(1, minimum), min(len(local["candidates"]), capacity) + 1):
            zone_input = {**local, "vehicle_count": days}
            outcomes, durations = {}, {}
            for method in METHODS:
                outcomes[method], durations[method] = run_method(zone_input, method)
            rows[days] = {"outcomes": outcomes, "runtime_seconds": durations}
        infeasible = rows and not rows[min(rows)]["outcomes"]["exact_dp"]["routes"]
        if minimum == 0 or infeasible:
            empty = engine._empty_summary(local, "no_route_day_allocated")
            zero = {
                "outcomes": {method: copy.deepcopy(empty) for method in METHODS},
                "runtime_seconds": {method: 0.0 for method in METHODS},
            }
            if infeasible:
                rows = {0: zero}
            else:
                rows[0] = zero
        table[zone["zone_id"]] = rows
    return table


def reference_allocation(payload: dict, table: dict) -> dict[str, int]:
    """Minimum quotas then bounded largest-remainder allocation by target count."""
    capacity = payload["vehicle_count"] * payload["operating_days_per_cycle"]
    lower = {zone: min(rows) for zone, rows in table.items()}
    upper = {zone: max(rows) for zone, rows in table.items()}
    weights = {
        z["zone_id"]: len({t["target_id"] for t in z["engine_input"]["targets"]})
        for z in payload["zones"]
    }
    assigned = dict(lower)
    remaining = min(capacity, sum(upper.values())) - sum(assigned.values())
    if remaining < 0:
        raise ValueError("capacity cannot meet minimum zone quotas")
    while remaining:
        eligible = [z for z in sorted(assigned) if assigned[z] < upper[z]]
        total_weight = sum(weights[z] for z in eligible)
        if total_weight <= 0:
            raise ValueError("remaining zones must have target-count weights")
        quotas = {z: remaining * weights[z] / total_weight for z in eligible}
        floors = {z: min(math.floor(quotas[z]), upper[z] - assigned[z]) for z in eligible}
        for zone in eligible:
            assigned[zone] += floors[zone]
            remaining -= floors[zone]
        # Ties are decided by zone ID, never by an observed routing outcome.
        remainders = sorted(eligible, key=lambda z: (-(quotas[z] - math.floor(quotas[z])), z))
        for zone in remainders:
            if not remaining:
                break
            if assigned[zone] < upper[zone]:
                assigned[zone] += 1
                remaining -= 1
    return assigned


def optimize_allocation(payload: dict, table: dict, method: str) -> dict[str, int]:
    """Apply the existing province DP objective to the selected solver's outcomes."""
    capacity = payload["vehicle_count"] * payload["operating_days_per_cycle"]
    states = {0: {
        "coverage_by_tier": {t["tier_id"]: 0 for t in payload["priority_tiers"]},
        "covered_target_count": 0,
        "travel_plus_wait_minutes": 0.0,
        "max_route_elapsed_minutes": 0.0,
        "allocated_route_days": 0,
        "plans": [],
    }}
    for zone_id, rows in sorted(table.items()):
        next_states = {}
        for used, state in states.items():
            for days, row in sorted(rows.items()):
                if used + days > capacity:
                    continue
                option = {"zone_id": zone_id, "allocated_route_days": days, "optimized": row["outcomes"][method]}
                candidate = engine._add_plan(payload, state, option)
                if used + days not in next_states or engine._aggregate_key(payload, candidate) < engine._aggregate_key(payload, next_states[used + days]):
                    next_states[used + days] = candidate
        states = next_states
    if not states:
        raise ValueError("no feasible allocation")
    selected = min(states.values(), key=lambda state: engine._aggregate_key(payload, state))
    return {p["zone_id"]: p["allocated_route_days"] for p in selected["plans"]}


def check_routes(payload: dict, summary: dict, allocation: dict) -> list[str]:
    """Independently replay matrix legs, windows, stops, capacity and unique coverage."""
    issues = []
    zones = {z["zone_id"]: z["engine_input"] for z in payload["zones"]}
    used_per_zone = {z: 0 for z in zones}
    seen_candidates = set()
    covered = set()
    travel_total = wait_total = distance_total = 0.0
    route_elapsed = []
    for index, route in enumerate(summary["routes"]):
        zone = route["service_zone"]
        local = zones[zone]
        candidates = {c["candidate_id"]: c for c in local["candidates"]}
        start = engine.parse_hhmm(local["operating_start"])
        current, previous = float(start), local["start_node_id"]
        travel = wait = distance = 0.0
        used_per_zone[zone] += 1
        if len(route["stops"]) > local["max_stops_per_vehicle"]:
            issues.append(f"route {index}: stop limit")
        for stop in route["stops"]:
            candidate_id = stop["candidate_id"]
            if (zone, candidate_id) in seen_candidates:
                issues.append(f"route {index}: repeated candidate {candidate_id}")
            seen_candidates.add((zone, candidate_id))
            c = candidates[candidate_id]
            leg = local["travel_minutes"][previous][candidate_id]
            arrival = current + leg
            begin = max(arrival, engine.parse_hhmm(c["time_window_start"]))
            finish = begin + c["service_minutes"]
            if finish > engine.parse_hhmm(c["time_window_end"]) + 1e-8:
                issues.append(f"route {index}: time window {candidate_id}")
            travel += leg
            distance += local["distance_km"][previous][candidate_id]
            wait += begin - arrival
            current, previous = finish, candidate_id
            covered.update(c["serves_target_ids"])
        last_leg = local["travel_minutes"][previous][local["end_node_id"]]
        travel += last_leg
        distance += local["distance_km"][previous][local["end_node_id"]]
        elapsed = current + last_leg - start
        if current + last_leg > engine.parse_hhmm(local["operating_end"]) + 1e-8:
            issues.append(f"route {index}: operating end")
        for name, actual in (("travel_minutes", travel), ("wait_minutes", wait), ("travel_km", distance), ("elapsed_minutes", elapsed)):
            if abs(route[name] - actual) > 0.000501:
                issues.append(f"route {index}: {name} mismatch")
        travel_total += round(travel, 3)
        wait_total += round(wait, 3)
        distance_total += round(distance, 3)
        route_elapsed.append(round(elapsed, 3))
    for zone, used in used_per_zone.items():
        if used > allocation[zone]:
            issues.append(f"{zone}: allocated capacity exceeded")
    capacity = payload["vehicle_count"] * payload["operating_days_per_cycle"]
    if sum(allocation.values()) > capacity or len(summary["routes"]) > capacity:
        issues.append("province capacity exceeded")
    expected_ids = {t["target_id"] for z in payload["zones"] for t in z["engine_input"]["targets"]}
    if covered != set(summary["covered_target_ids"]):
        issues.append("covered target IDs mismatch")
    if expected_ids - covered != {t["target_id"] for t in summary["unvisited_targets"]}:
        issues.append("unvisited target IDs mismatch")
    target_tier = {t["target_id"]: t["priority_tier"] for z in payload["zones"] for t in z["engine_input"]["targets"]}
    for tier in payload["priority_tiers"]:
        key = tier["tier_id"]
        if sum(target_tier[t] == key for t in covered) != summary["coverage_by_tier"][key]:
            issues.append(f"{key}: coverage mismatch")
    for name, actual in (("travel_minutes", travel_total), ("wait_minutes", wait_total), ("travel_km", distance_total), ("max_route_elapsed_minutes", max(route_elapsed, default=0))):
        if abs(summary["totals"][name] - actual) > 0.000501:
            issues.append(f"province {name} mismatch")
    return issues


def summarize_experiment(payload: dict, table: dict, allocation: dict, method: str, allocation_method: str, cap: int) -> dict:
    plans = [
        {"zone_id": zone, "allocated_route_days": days, "selected": table[zone][days]["outcomes"][method]}
        for zone, days in sorted(allocation.items())
    ]
    summary = engine._province_summary(payload, plans, "selected", method)
    violations = check_routes(payload, summary, allocation)
    if violations:
        raise ValueError("; ".join(violations))
    summary.update({
        "max_stops_per_route": cap,
        "allocation_method": allocation_method,
        "zone_allocation": allocation,
        "allocated_route_days": sum(allocation.values()),
        "travel_plus_wait_minutes": round(summary["totals"]["travel_minutes"] + summary["totals"]["wait_minutes"], 3),
        "constraint_violations": violations,
        "runtime_seconds_selected_zone_solves": round(sum(table[z][n]["runtime_seconds"][method] for z, n in allocation.items()), 6),
        "runtime_seconds_all_zone_outcomes": round(sum(row["runtime_seconds"][method] for rows in table.values() for row in rows.values()), 6),
    })
    return summary


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(input_path: Path, output_dir: Path, label: str, caps: list[int]) -> dict:
    source = json.loads(input_path.read_text())
    payload = source.get("engine_input", source)
    validate_province(payload)
    results = []
    frozen_reference = None
    for cap in caps:
        configured = copy.deepcopy(payload)
        for zone in configured["zones"]:
            local = zone["engine_input"]
            local["max_stops_per_vehicle"] = min(cap, len(local["candidates"]))
        table = outcome_tables(configured)
        allocation = reference_allocation(configured, table)
        if frozen_reference is None:
            frozen_reference = allocation
        elif allocation != frozen_reference:
            raise ValueError("reference allocation changed across caps; freeze feasibility policy before comparison")
        for method in METHODS:
            results.append(summarize_experiment(configured, table, allocation, method, "target_count_reference", cap))
        for method in ("priority_nearest", "exact_dp"):
            optimized = optimize_allocation(configured, table, method)
            results.append(summarize_experiment(configured, table, optimized, method, "lexicographic_dp", cap))
        # Reproduce the repository's conditional baseline comparison explicitly.
        dp_allocation = optimize_allocation(configured, table, "exact_dp")
        results.append(summarize_experiment(configured, table, dp_allocation, "nearest", "exact_dp_common_allocation", cap))
        results.append(summarize_experiment(configured, table, dp_allocation, "priority_nearest", "exact_dp_common_allocation", cap))
    artifact = {
        "label": label,
        "input_path": str(input_path.resolve()),
        "input_sha256": sha256(input_path),
        "engine_sha256": sha256(REPO / "src/route_scenario.py"),
        "runner_sha256": sha256(Path(__file__)),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "input_scope": source.get("scope"),
        "protocol": {
            "priority_order": [t["tier_id"] for t in payload["priority_tiers"]],
            "target_count": sum(len(z["engine_input"]["targets"]) for z in payload["zones"]),
            "zone_count": len(payload["zones"]),
            "max_stops": caps,
            "reference_allocation": frozen_reference,
            "primary_comparison": "Three routing methods with one frozen target-count allocation at each cap.",
            "allocation_comparison": "Within each routing method, reference versus DP allocation of that method's own outcomes.",
            "nearest_baseline_note": "Existing nearest-feasible method does not prioritize target tiers.",
            "allocation_capacity_note": "Identical upper bounds; actual route-days need not be equal.",
            "runtime_note": "Single local wall-clock measurements; selected zone solves and all outcome preparation are separate. No statistical runtime claim.",
            "distance_note": "Distance is descriptive. Compare tier coverage lexicographically before travel plus wait and maximum route duration.",
            "scope_note": "Coverage counts unique administrative targets, not residents. Operational assumptions are inherited from input.",
        },
        "results": results,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "comparison_results.json").write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n")
    rows = []
    for result in results:
        rows.append({
            "label": label,
            "max_stops": result["max_stops_per_route"],
            "allocation": result["allocation_method"],
            "method": result["method"],
            **result["coverage_by_tier"],
            "covered": result["covered_target_count"],
            "unvisited": len(result["unvisited_targets"]),
            **result["totals"],
            "travel_plus_wait_minutes": result["travel_plus_wait_minutes"],
            "allocated_days": result["allocated_route_days"],
            "used_days": result["route_days_used"],
            "violations": len(result["constraint_violations"]),
            "runtime_seconds_selected_zone_solves": result["runtime_seconds_selected_zone_solves"],
            "runtime_seconds_all_zone_outcomes": result["runtime_seconds_all_zone_outcomes"],
            "unvisited_ids": "|".join(row["target_id"] for row in result["unvisited_targets"]),
        })
    with (output_dir / "comparison_summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return artifact


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--caps", type=int, nargs="+", default=[3, 4, 5])
    args = parser.parse_args()
    if not args.caps or min(args.caps) < 1:
        parser.error("caps must be positive")
    data = run(args.input, args.output, args.label, args.caps)
    print(json.dumps({"label": data["label"], "input_sha256": data["input_sha256"], "experiments": len(data["results"]), "output": str(args.output)}, ensure_ascii=False))
