"""Check that the public dashboard stays on the final report's frozen inputs."""

import csv
import hashlib
import json
import unittest
from pathlib import Path

from build_dashboard_data import build_payload


ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "analysis/theory_validation"


def read_bundle(name, variable):
    text = (ROOT / "docs/demo-jeonbuk" / name).read_text(encoding="utf-8")
    return json.loads(text.split(f"const {variable}=", 1)[1].split(";\n", 1)[0])


class DashboardValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = build_payload()
        cls.scenario_path = VALIDATION / "spatial/route_inputs/jeonbuk_route_scenario.json"
        cls.scenario = json.loads(cls.scenario_path.read_text(encoding="utf-8"))

    def test_default_rebuild_uses_expanded_report_inputs(self):
        data = self.payload
        self.assertEqual(data, read_bundle("data.js", "JEONBUK_DASHBOARD"))
        self.assertEqual(len(data["admins"]), 243)
        self.assertEqual(data["source_summary"]["finance_outlet_count"], 1347)
        self.assertEqual(data["source_summary"]["finance_outlet_listed_count"], 1385)
        self.assertEqual(data["source_summary"]["road_primary_count"], 240)
        self.assertEqual(data["source_summary"]["quality_deferred_admin_count"], 3)
        self.assertEqual(data["scope"]["threshold_target_count"], 55)
        self.assertEqual(data["scope"]["route_eligible_target_count"], 54)
        self.assertEqual(sum(row["priority"] == "P1" for row in data["admins"]), 21)
        self.assertEqual(sum(row["priority"] == "P2" for row in data["admins"]), 33)
        self.assertEqual(data["source_as_of"]["outlets"], "원천별 기준일 상이")
        self.assertIn("보완 목록 2026-10-12 수집", data["source_as_of"]["outlets_note"])
        self.assertEqual(data["source_as_of"]["outlets_retrieved"], "2026-10-12")

    def test_admin_values_match_expanded_access_without_rounded_classification(self):
        with (VALIDATION / "spatial/results/access_expanded_internal.csv").open(encoding="utf-8-sig") as handle:
            expected = {row["code"]: row for row in csv.DictReader(handle)}
        for row in self.payload["admins"]:
            source = expected[row["code"]]
            self.assertEqual(row["road_km"], float(source["road_km"]))
            self.assertEqual(row["line_km"], float(source["nearest_km"]))
            self.assertEqual(row["cnt_3km"], int(source["cnt_3km"]))
            self.assertEqual(row["nearest_name"], source["road_nearest_name"])
            self.assertEqual(row["cluster_label"], "")
            self.assertEqual(row["rule_type"], "")
            self.assertEqual(row["typology_status"], "historical_not_recomputed")

    def test_comparison_is_same_targets_only_for_priority_nearest(self):
        evidence = self.payload["report_evidence"]
        methods = {row["id"]: row for row in evidence["methods"]}
        self.assertEqual(methods["exact_dp"]["travel_km"], 1003.716)
        self.assertEqual(methods["priority_nearest"]["travel_km"], 1103.950)
        self.assertEqual(methods["nearest"]["travel_km"], 1078.751)
        for row in methods.values():
            self.assertEqual(row["covered_target_count"], 50)
            self.assertEqual(row["coverage_by_tier"], {"P1": 21, "P2": 29})
        self.assertTrue(methods["priority_nearest"]["same_targets_as_dp"])
        self.assertFalse(methods["nearest"]["same_targets_as_dp"])
        self.assertEqual(evidence["comparisons"]["priority_nearest"]["distance_saved_percent"], 9.08)
        self.assertEqual({row["name"] for row in evidence["unvisited"]}, {"계화면", "진안읍", "백운면", "마령면"})
        self.assertEqual(evidence["validation"]["baseline_target_count"], 70)
        self.assertEqual(evidence["validation"]["origin_comparable_count"], 238)

    def test_route_matrix_and_provenance_match_report(self):
        expected_hash = hashlib.sha256(self.scenario_path.read_bytes()).hexdigest()
        self.assertEqual(self.payload["validation"]["scenario_sha256"], expected_hash)
        self.assertEqual(self.payload["report_evidence"]["validation"]["scenario_sha256"], expected_hash)
        for zone, source in zip(self.payload["route"]["engine_input"]["zones"], self.scenario["engine_input"]["zones"]):
            self.assertEqual(zone["zone_id"], source["zone_id"])
            self.assertEqual(zone["engine_input"]["distance_km"], source["engine_input"]["distance_km"])
            self.assertEqual(zone["engine_input"]["travel_minutes"], source["engine_input"]["travel_minutes"])
        for item in self.payload["validation"]["inputs"]:
            self.assertEqual(hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest(), item["sha256"])
        self.assertEqual(self.payload["evidence_summary"]["speed_service_sensitivity"], [])
        self.assertEqual([row["max_stops_per_route"] for row in self.payload["evidence_summary"]["stop_cap_sensitivity"]], [3, 4, 5])
        self.assertTrue(all(row["allocation_method"] == "priority_dp" for row in self.payload["sensitivity_presets"]))

    def test_map_uses_current_road_and_every_current_directed_leg(self):
        map_data = read_bundle("map-data.js", "JEONBUK_MAP")
        provenance = self.payload["validation"]
        for key in ("scenario_sha256", "pbf_sha256", "boundary_sha256", "road_date", "version"):
            self.assertEqual(map_data["source"][key], provenance[key])
        self.assertLessEqual(map_data["source"]["maximum_matrix_path_delta_km"], 0.002)
        legs = {(row["zone_id"], row["origin_id"], row["destination_id"]): row for row in map_data["route_legs"]}
        expected_keys = set()
        for zone in self.scenario["engine_input"]["zones"]:
            for origin, destinations in zone["engine_input"]["distance_km"].items():
                for destination, distance in destinations.items():
                    if origin == destination:
                        continue
                    key = (zone["zone_id"], origin, destination)
                    expected_keys.add(key)
                    self.assertEqual(legs[key]["matrix_km"], round(distance, 3))
                    self.assertGreaterEqual(len(legs[key]["path"]), 2)
        self.assertEqual(set(legs), expected_keys)


if __name__ == "__main__":
    unittest.main()
