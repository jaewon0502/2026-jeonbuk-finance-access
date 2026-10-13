"""Replay outlet sensitivity with the published 15 route-day allocation frozen.

Research-only calculation; input collection and route-matrix builders are unchanged.
"""
import argparse
import copy
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("comparison", ROOT / "analysis/theory_validation/comparison/run_comparison.py")
comparison = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(comparison)


def without_runtime(value):
    if isinstance(value, dict):
        return {key: without_runtime(item) for key, item in value.items() if not key.startswith("runtime_")}
    if isinstance(value, list):
        return [without_runtime(item) for item in value]
    return value


def run(check=False):
    previous = json.loads((ROOT / "analysis/theory_validation/comparison/final_expanded_input/report_evidence.json").read_text())
    allocation = previous["fixed_reference_allocation"]
    scenarios = {
        "all_added_included": ROOT / "analysis/theory_validation/spatial/route_inputs/jeonbuk_route_scenario.json",
        "exclude_no_service_tag_271": HERE / "exclude_no_service_tag_routes/jeonbuk_route_scenario.json",
        "exclude_all_jeonbuk_coops_334": HERE / "exclude_jeonbuk_coops_routes/jeonbuk_route_scenario.json",
    }
    summaries, detail = [], {}
    for name, path in scenarios.items():
        source = json.loads(path.read_text())
        payload = copy.deepcopy(source["engine_input"])
        comparison.validate_province(payload)
        for zone in payload["zones"]:
            zone["engine_input"]["max_stops_per_vehicle"] = min(4, len(zone["engine_input"]["candidates"]))
        table = comparison.outcome_tables(payload)
        results = [comparison.summarize_experiment(payload, table, allocation, method, "frozen_published_allocation", 4) for method in comparison.METHODS]
        detail[name] = {"input_path": str(path.relative_to(ROOT)), "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "results": results}
        target_count = sum(len(z["engine_input"]["targets"]) for z in payload["zones"])
        for result in results:
            summaries.append({"scenario": name, "method": result["method"], "target_count": target_count,
                "covered": result["covered_target_count"], "P1": result["coverage_by_tier"]["P1"], "P2": result["coverage_by_tier"]["P2"],
                "unvisited": len(result["unvisited_targets"]), "distance_km": result["totals"]["travel_km"],
                "travel_plus_wait_minutes": result["travel_plus_wait_minutes"], "allocated_route_days": sum(allocation.values()),
                "used_route_days": result["route_days_used"], "violations": len(result["constraint_violations"])})
    output = {"accessed_at": "2026-10-13", "fixed_allocation": allocation,
        "comparison_contract": "Same graph, representative points, thresholds, venue inventory, selection/depot rules, daily cap=4, service=45min, speed=40km/h, opening=09:00-17:00 and frozen published zone allocation. Targets and matrices are rebuilt for each outlet pool. Coverage sets can differ, so between-pool distance changes are not efficiency gains.",
        "source_engine_sha256": comparison.sha256(ROOT / "src/route_scenario.py"),
        "source_comparison_sha256": comparison.sha256(ROOT / "analysis/theory_validation/comparison/run_comparison.py"),
        "summaries": summaries, "details": detail}
    if check:
        saved = json.loads((HERE / "sensitivity_route_results.json").read_text())
        if without_runtime(output) != without_runtime(saved):
            raise SystemExit("FAIL: recomputed sensitivity differs from published evidence")
        if any(row["violations"] for row in summaries):
            raise SystemExit("FAIL: route replay constraint violation")
        with (HERE / "sensitivity_route_summary.csv").open(encoding="utf-8-sig", newline="") as handle:
            saved_rows = list(csv.DictReader(handle))
        if saved_rows != [{key: str(value) for key, value in row.items()} for row in summaries]:
            raise SystemExit("FAIL: sensitivity CSV differs from replay")
        print("PASS: 9 sensitivity method/scenario results reproduced; 0 constraint violations")
        return
    (HERE / "sensitivity_route_results.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    with (HERE / "sensitivity_route_summary.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summaries[0])); writer.writeheader(); writer.writerows(summaries)
    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Replay and compare without modifying saved evidence")
    run(check=parser.parse_args().check)
