from __future__ import annotations

import copy
import itertools
import unittest

import run_comparison as comparison


def fixture(rows: list[tuple[str, list[str]]], tiers: dict[str, str], *, days=1, stops=1) -> dict:
    ids = ["depot", *[row[0] for row in rows]]
    matrix = {a: {b: 0.0 if a == b else 10.0 for b in ids} for a in ids}
    return {
        "vehicle_count": days,
        "max_stops_per_vehicle": stops,
        "service_cycle_days": 7,
        "operating_start": "09:00",
        "operating_end": "17:00",
        "start_node_id": "depot",
        "end_node_id": "depot",
        "priority_tiers": [{"tier_id": "P1"}, {"tier_id": "P2"}],
        "targets": [{"target_id": key, "priority_tier": value} for key, value in tiers.items()],
        "candidates": [{"candidate_id": name, "serves_target_ids": targets, "time_window_start": "09:00", "time_window_end": "17:00", "service_minutes": 30} for name, targets in rows],
        "travel_minutes": matrix,
        "distance_km": copy.deepcopy(matrix),
    }


def province(zones: dict[str, dict], capacity: int, minimum: int) -> dict:
    return {
        "vehicle_count": 1,
        "operating_days_per_cycle": capacity,
        "minimum_route_days_per_active_zone": minimum,
        "service_cycle_days": max(7, capacity),
        "priority_tiers": [{"tier_id": "P1"}, {"tier_id": "P2"}],
        "zones": [{"zone_id": key, "engine_input": value} for key, value in zones.items()],
    }


class PriorityGreedyTests(unittest.TestCase):
    def test_far_high_priority_beats_near_low_priority(self):
        data = fixture([("near", ["low"]), ("far", ["high"])], {"low": "P2", "high": "P1"})
        data["travel_minutes"]["depot"]["near"] = 1.0
        self.assertEqual(comparison.run_method(data, "nearest")[0]["covered_target_ids"], ["low"])
        self.assertEqual(comparison.run_method(data, "priority_nearest")[0]["covered_target_ids"], ["high"])

    def test_infeasible_high_priority_does_not_block_other_target(self):
        data = fixture([("near", ["low"]), ("far", ["high"])], {"low": "P2", "high": "P1"})
        data["candidates"][1]["time_window_end"] = "09:20"
        result = comparison.run_method(data, "priority_nearest")[0]
        self.assertEqual(result["covered_target_ids"], ["low"])

    def test_duplicate_target_does_not_consume_second_route(self):
        data = fixture([("a", ["high"]), ("b", ["high"]), ("c", ["low"])], {"high": "P1", "low": "P2"}, days=2)
        result = comparison.run_method(data, "priority_nearest")[0]
        self.assertEqual(result["covered_target_ids"], ["high", "low"])
        self.assertEqual([r["stops"][0]["candidate_id"] for r in result["routes"]], ["a", "c"])

    def test_partial_overlap_counts_only_new_targets(self):
        data = fixture([("a", ["h1", "h2"]), ("b", ["h1", "low"]), ("c", ["h3"])], {"h1": "P1", "h2": "P1", "h3": "P1", "low": "P2"}, stops=2)
        result = comparison.run_method(data, "priority_nearest")[0]
        self.assertEqual([s["candidate_id"] for s in result["routes"][0]["stops"]], ["a", "c"])

    def test_tie_break_is_candidate_id_not_input_order(self):
        data = fixture([("b", ["tb"]), ("a", ["ta"])], {"tb": "P1", "ta": "P1"})
        result = comparison.run_method(data, "priority_nearest")[0]
        self.assertEqual(result["covered_target_ids"], ["ta"])
        data["candidates"].reverse()
        self.assertEqual(comparison.run_method(data, "priority_nearest")[0]["covered_target_ids"], ["ta"])

    def test_capacity_is_upper_bound_and_return_is_feasible(self):
        data = fixture([("a", ["ta"]), ("b", ["tb"]), ("c", ["tc"])], {"ta": "P1", "tb": "P2", "tc": "P2"}, days=2, stops=2)
        data["operating_end"] = "10:00"
        result = comparison.run_method(data, "priority_nearest")[0]
        self.assertEqual(result["covered_target_count"], 2)
        self.assertEqual(result["vehicles_used"], 2)
        self.assertTrue(all(len(r["stops"]) == 1 for r in result["routes"]))


class AllocationTests(unittest.TestCase):
    def setUp(self):
        self.a = fixture([("a1", ["ta1"]), ("a2", ["ta2"])], {"ta1": "P1", "ta2": "P1"})
        self.b = fixture([("b1", ["tb1"]), ("b2", ["tb2"])], {"tb1": "P2", "tb2": "P2"})

    def test_reference_tie_and_bounds_are_deterministic(self):
        data = province({"B": self.b, "A": self.a}, capacity=3, minimum=1)
        table = comparison.outcome_tables(data)
        self.assertEqual(comparison.reference_allocation(data, table), {"A": 2, "B": 1})
        data["operating_days_per_cycle"] = 5
        self.assertEqual(comparison.reference_allocation(data, table), {"A": 2, "B": 2})

    def test_reference_saturates_small_zone_then_redistributes(self):
        small = fixture([("small", ["s"])], {"s": "P1"})
        data = province({"A": small, "B": self.b}, capacity=3, minimum=0)
        table = comparison.outcome_tables(data)
        self.assertEqual(comparison.reference_allocation(data, table), {"A": 1, "B": 2})

    def test_dp_matches_exhaustive_allocation_oracle(self):
        data = province({"A": self.a, "B": self.b}, capacity=2, minimum=0)
        table = comparison.outcome_tables(data)
        for method in comparison.METHODS:
            selected = comparison.optimize_allocation(data, table, method)
            candidates = []
            for a_days, b_days in itertools.product(table["A"], table["B"]):
                if a_days + b_days > 2:
                    continue
                allocation = {"A": a_days, "B": b_days}
                result = comparison.summarize_experiment(data, table, allocation, method, "test", 1)
                key = (-result["coverage_by_tier"]["P1"], -result["coverage_by_tier"]["P2"], -result["covered_target_count"], result["travel_plus_wait_minutes"], result["totals"]["max_route_elapsed_minutes"], a_days + b_days, tuple(allocation.items()))
                candidates.append((key, allocation))
            self.assertEqual(selected, min(candidates)[1])
            self.assertEqual(selected, {"A": 2, "B": 0})

    def test_common_allocation_reproduces_existing_province(self):
        data = province({"A": self.a, "B": self.b}, capacity=3, minimum=1)
        old = comparison.engine.solve_province(data)
        table = comparison.outcome_tables(data)
        allocation = comparison.optimize_allocation(data, table, "exact_dp")
        self.assertEqual(allocation, {r["zone_id"]: r["allocated_route_days"] for r in old["zone_allocations"]})
        for method, old_key in (("nearest", "baseline"), ("exact_dp", "optimized")):
            result = comparison.summarize_experiment(data, table, allocation, method, "test", 1)
            self.assertEqual(result["coverage_by_tier"], old[old_key]["coverage_by_tier"])
            self.assertEqual(result["totals"], old[old_key]["totals"])

    def test_infeasible_zone_receives_same_zero_day_waiver(self):
        self.a["operating_end"] = "09:15"
        data = province({"A": self.a, "B": self.b}, capacity=2, minimum=1)
        table = comparison.outcome_tables(data)
        self.assertEqual(list(table["A"]), [0])
        self.assertEqual(comparison.reference_allocation(data, table), {"A": 0, "B": 2})

    def test_independent_replay_detects_tampered_distance(self):
        data = province({"A": self.a}, capacity=1, minimum=1)
        table = comparison.outcome_tables(data)
        result = comparison.summarize_experiment(data, table, {"A": 1}, "priority_nearest", "test", 1)
        result["routes"][0]["travel_km"] += 1
        self.assertIn("route 0: travel_km mismatch", comparison.check_routes(data, result, {"A": 1}))

    def test_cross_zone_duplicate_targets_are_rejected(self):
        data = province({"A": self.a, "B": copy.deepcopy(self.a)}, capacity=2, minimum=1)
        with self.assertRaisesRegex(ValueError, "disjoint"):
            comparison.validate_province(data)


if __name__ == "__main__":
    unittest.main()
