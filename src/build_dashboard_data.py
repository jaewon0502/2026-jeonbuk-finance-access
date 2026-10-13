"""Build the compact, offline data bundle for the Jeonbuk dashboard."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
VALIDATION = ROOT / "analysis" / "theory_validation"
OUTPUT = ROOT / "docs" / "demo-jeonbuk" / "data.js"


def read_csv(name: str | Path) -> list[dict[str, str]]:
    with (DATA / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def compact_outlets(path: str | Path = "outlets_validated.csv") -> tuple[list[dict], int]:
    listed = read_csv(path)
    outlets = []
    for row in listed:
        if row.get("finance_open") != "Y":
            continue
        if not row.get("lat") or not row.get("lon"):
            continue
        outlets.append({
            "outlet_id": row["outlet_id"],
            "type": row["type"],
            "name": row["name"],
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "finance_open": row["finance_open"],
            "expansion_group": row.get("expansion_group", "submission_snapshot"),
            "finance_status": row.get("finance_status", ""),
        })
    return outlets, len(listed)


def source_as_of() -> dict[str, str]:
    manifest = json.loads(
        (ROOT / "data" / "source_manifest.json").read_text(encoding="utf-8")
    )
    sources = {row["source_id"]: row for row in manifest["sources"]}
    outlet_ids = (
        "koreapost_offices_20250301",
        "kfb_jeonbuk_branches_202512",
        "cu_jeonbuk_search_20260810",
        "kfcc_jeonbuk_20260811",
    )
    outlet_as_of = [sources[source_id].get("as_of_date") for source_id in outlet_ids]
    outlet_retrieved = [sources[source_id].get("retrieved_on") for source_id in outlet_ids]
    return {
        "admin": sources["sgis_admin_boundaries_20260701"]["as_of_date"],
        "population_65plus": sources["mois_age_sex_20260630"]["as_of_date"],
        "outlets": min(date for date in outlet_as_of if date),
        "outlets_retrieved": max(date for date in outlet_retrieved if date),
        "generated_on": manifest["generated_on"],
    }


def service_zone(sigungu: str) -> str:
    return "전주시" if sigungu.startswith("전주시") else sigungu


def priority(row: dict[str, str]) -> str:
    road_km = float(row["road_km"])
    if row["road_distance_primary"] != "Y":
        return "quality_deferred" if road_km > 3 else "accessible"
    if road_km > 5:
        return "P1"
    if road_km > 3:
        return "P2"
    return "accessible"


def compact_engine(route: dict) -> dict:
    zones = []
    for zone in route["engine_input"]["zones"]:
        engine = zone["engine_input"]
        zones.append({
            "zone_id": zone["zone_id"],
            "engine_input": {
                "vehicle_count": 1,
                "max_stops_per_vehicle": engine["max_stops_per_vehicle"],
                "service_cycle_days": engine["service_cycle_days"],
                "operating_start": engine["operating_start"],
                "operating_end": engine["operating_end"],
                "start_node_id": engine["start_node_id"],
                "end_node_id": engine["end_node_id"],
                "priority_tiers": engine["priority_tiers"],
                "targets": [
                    {
                        "target_id": row["target_id"],
                        "name": row["name"],
                        "lat": row["lat"],
                        "lon": row["lon"],
                        "priority_tier": row["priority_tier"],
                    }
                    for row in engine["targets"]
                ],
                "candidates": [
                    {
                        "candidate_id": row["candidate_id"],
                        "name": row["name"],
                        "lat": row["lat"],
                        "lon": row["lon"],
                        "serves_target_ids": row["serves_target_ids"],
                        "service_minutes": row["service_minutes"],
                        "time_window_start": row["time_window_start"],
                        "time_window_end": row["time_window_end"],
                    }
                    for row in engine["candidates"]
                ],
                "distance_km": engine["distance_km"],
                "travel_minutes": engine["travel_minutes"],
            },
        })
    return {
        "vehicle_count": route["engine_input"]["vehicle_count"],
        "operating_days_per_cycle": route["engine_input"][
            "operating_days_per_cycle"
        ],
        "minimum_route_days_per_active_zone": route["engine_input"][
            "minimum_route_days_per_active_zone"
        ],
        "service_cycle_days": route["engine_input"]["service_cycle_days"],
        "priority_tiers": route["engine_input"]["priority_tiers"],
        "zones": zones,
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validated_evidence(route: dict, scenario_path: Path) -> tuple[dict, dict, dict]:
    spatial_path = VALIDATION / "spatial/results/summary.json"
    comparison_path = VALIDATION / "comparison/final_expanded_input/comparison_results.json"
    evidence_path = VALIDATION / "comparison/final_expanded_input/report_evidence.json"
    spatial = json.loads(spatial_path.read_text(encoding="utf-8"))
    comparisons = json.loads(comparison_path.read_text(encoding="utf-8"))
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    scenario_hash = sha256(scenario_path)
    if evidence["scenario_sha256"] != scenario_hash or comparisons["input_sha256"] != scenario_hash:
        raise RuntimeError("report comparison and dashboard scenario hashes differ")
    files = [
        scenario_path,
        VALIDATION / "spatial/route_inputs/access_road.csv",
        VALIDATION / "inputs/outlets_expanded.csv",
        spatial_path,
        comparison_path,
        evidence_path,
    ]
    checks = {
        files[1]: route["input_hashes"]["access_road_sha256"],
        files[2]: route["input_hashes"]["outlets_validated_sha256"],
        scenario_path.parent / "outlets_validated.csv": route["input_hashes"]["outlets_validated_sha256"],
        VALIDATION / "spatial/results/threshold_sensitivity.csv": spatial["outputs"]["threshold_sensitivity.csv"],
    }
    for path, expected in checks.items():
        if sha256(path) != expected:
            raise RuntimeError(f"validated input hash mismatch: {path.relative_to(ROOT)}")
    if route["validation_provenance"]["graph"]["inputs"] != spatial["graph"]["inputs"]:
        raise RuntimeError("access and route road provenance differ")
    if route["input_hashes"]["access_road_sha256"] != spatial["outputs"]["access_expanded_internal.csv"]:
        raise RuntimeError("route access differs from the validated spatial result")

    primary = [row for row in evidence["primary"] if row["cap"] == 4]
    labels = {"nearest": "가까운 곳부터", "priority_nearest": "우선순위 후 가까운 곳부터", "exact_dp": "우선순위와 경로 최적화"}
    runs = {
        row["method"]: row for row in comparisons["results"]
        if row["max_stops_per_route"] == 4 and row["allocation_method"] == "target_count_reference"
    }
    dp_targets = set(runs["exact_dp"]["covered_target_ids"])
    methods = [{
        "id": row["method"], "label": labels[row["method"]],
        "covered_target_count": row["covered"], "coverage_by_tier": row["coverage"],
        "travel_km": row["distance_km"],
        "same_targets_as_dp": set(runs[row["method"]]["covered_target_ids"]) == dp_targets,
    } for row in primary]
    default = next(row for row in route["sensitivity_presets"] if row["preset_id"] == "default")
    current = spatial["cells"]["expanded_internal"]
    original = spatial["cells"]["baseline_internal"]["routing_category_counts"]
    comparison = {
        row["dp_vs"]: {
            "distance_saved_km": row["distance_saved_km"],
            "distance_saved_percent": row["distance_saved_percent"],
            "same_targets": set(runs[row["dp_vs"]]["covered_target_ids"]) == dp_targets,
        } for row in evidence["dp_contrasts"] if row["cap"] == 4
    }
    report = {
        "snapshot_id": "2026-10-12-expanded", "analysis_date": route["analysis_date"],
        "methods": methods, "comparisons": comparison,
        "validation": {
            "scenario_sha256": scenario_hash,
            "comparison_count": evidence["verification"]["comparison_count"],
            "route_replay_violations": evidence["verification"]["route_replay_violations"],
            "baseline_target_count": original["P1"] + original["P2"],
            "expanded_target_count": route["scope"]["route_eligible_target_count"],
            "origin_stable_count": spatial["expanded_origin_robustness"]["stable"],
            "origin_comparable_count": spatial["origin_geometry"]["spearman_valid_primary_pair_count"],
        },
        "reference_parameters": default["parameters"],
        "reference_allocation": evidence["fixed_reference_allocation"],
        "cap_sensitivity": evidence["primary"],
        "unvisited": next(row for row in primary if row["method"] == "exact_dp")["unvisited"],
    }
    thresholds = [{
        key: value if key == "cell" else float(value) if "threshold_km" in key else int(value)
        for key, value in row.items()
    } for row in read_csv(VALIDATION / "spatial/results/threshold_sensitivity.csv") if row["cell"] == "expanded_internal"]
    summary = {
        "threshold_sensitivity": thresholds,
        "stop_cap_sensitivity": [{
            "max_stops_per_route": row["cap"], "visited_admin_target_count": row["covered"],
            "visit_count_by_tier": row["coverage"], "route_days_used": row["used_days"],
            "travel_km": row["distance_km"], "max_route_elapsed_minutes": row["maximum_route_minutes"],
            "allocation_method": row["allocation"],
        } for row in evidence["primary"] if row["method"] == "exact_dp"],
        "speed_service_sensitivity": [],
        "candidate_proxy_audit": {"candidate_count": route["scope"]["candidate_count"], "every_candidate_serves_exactly_one_target": route["measurement_contract"]["every_candidate_serves_exactly_one_target"]},
        "route_duration_audit": {"operating_horizon_minutes": 480, "all_routes_within_horizon": evidence["verification"]["route_replay_violations"] == 0},
    }
    provenance = {
        "version": report["snapshot_id"], "scenario_sha256": scenario_hash,
        "inputs": [{"path": str(path.relative_to(ROOT)), "sha256": sha256(path)} for path in files],
        "road_date": "2026-10-11", "pbf_sha256": spatial["graph"]["inputs"]["pbf_sha256"],
        "boundary_sha256": spatial["graph"]["inputs"]["boundary_sha256"],
        "typology_status": "historical_not_recomputed",
        "notes": ["금융접점은 공식 목록 기준이며 실제 영업시간과 업무 범위는 확인하지 않았습니다.", "도 경계 밖 접점은 농협과 지역신협 일부만 포함합니다.", "대표점 비교는 기하학적 민감도 검증이며 주민 접근성을 검증한 결과는 아닙니다."],
    }
    if current["routing_category_counts"]["quality_deferred"] != 3:
        raise RuntimeError("unexpected validated quality-deferred count")
    return report, summary, provenance


def build_payload(legacy: bool = False) -> dict:
    dataset = DATA if legacy else VALIDATION / "spatial/route_inputs"
    access = read_csv(dataset / "access_road.csv")
    typology = {row["code"]: row for row in read_csv("access_typology.csv")}
    if len(access) != 243 or set(typology) != {row["code"] for row in access}:
        raise RuntimeError("dashboard admin join must cover exactly 243 codes")

    scenario_path = dataset / "jeonbuk_route_scenario.json"
    route = json.loads(scenario_path.read_text(encoding="utf-8"))
    if legacy:
        scenario_evidence = json.loads((DATA / "scenario_evidence.json").read_text(encoding="utf-8"))
        report, provenance = None, None
    else:
        report, scenario_evidence, provenance = validated_evidence(route, scenario_path)
    venue_metadata = json.loads(
        (DATA / "venues_jeonbuk_metadata.json").read_text(encoding="utf-8")
    )
    admins = []
    for row in access:
        type_row = typology[row["code"]]
        admins.append({
            "code": row["code"],
            "sigungu": row["sigungu"],
            "service_zone": service_zone(row["sigungu"]),
            "dong": row["dong"],
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "pop_total": int(row["pop_total"]),
            "pop_65plus": int(row["pop_65plus"]),
            "ratio_65plus": float(row["ratio_65plus"]),
            "road_km": float(row["road_km"]),
            "line_km": float(row["nearest_km"]),
            "road_distance_primary": row["road_distance_primary"],
            "route_quality": row["route_quality"],
            "nearest_name": row["road_nearest_name"],
            "nearest_type": row["road_nearest_type"],
            "cnt_3km": int(row["cnt_3km"]),
            "priority": priority(row),
            "cluster_label": type_row["cluster_label"] if legacy else "",
            "rule_type": type_row["rule_type"] if legacy else "",
            "typology_status": type_row["typology_status"] if legacy else "historical_not_recomputed",
            "historical_cluster_label": type_row["cluster_label"],
            "historical_rule_type": type_row["rule_type"],
        })
    admins.sort(key=lambda row: (row["service_zone"], row["dong"], row["code"]))
    outlets, listed_outlet_count = compact_outlets(dataset / "outlets_validated.csv")

    payload = {
        "analysis_date": route["analysis_date"],
        "status": route["status"],
        "operational_ready": route["operational_ready"],
        "scope": route["scope"],
        "admins": admins,
        "input_controls": route["input_controls"],
        "sensitivity_presets": route["sensitivity_presets"],
        "measurement_contract": route["measurement_contract"],
        "evidence_summary": {
            "threshold_sensitivity": scenario_evidence["threshold_sensitivity"],
            "stop_cap_sensitivity": scenario_evidence["stop_cap_sensitivity"],
            "speed_service_sensitivity": scenario_evidence["speed_service_sensitivity"],
            "candidate_proxy_audit": scenario_evidence["candidate_proxy_audit"],
            "route_duration_audit": scenario_evidence["route_duration_audit"],
        },
        "route": {
            "engine_input": compact_engine(route),
            "depots_by_zone": route["depots_by_zone"],
            "excluded_targets": route["excluded_targets"],
            "travel_model": {
                key: route["travel_model"][key]
                for key in (
                    "distance",
                    "oneway_respected",
                    "time",
                    "uniform_speed_kmh",
                    "actual_traffic_time",
                    "interzone_repositioning_modeled",
                )
            },
            "input_hashes": route["input_hashes"],
        },
        "outlets": outlets,
        "source_as_of": source_as_of(),
        "source_summary": {
            "admin_count": len(admins),
            "finance_outlet_count": len(outlets),
            "finance_outlet_listed_count": listed_outlet_count,
            "senior_center_source_rows": venue_metadata["source_rows"],
            "senior_center_geocoded_rows": venue_metadata["geocoded_rows"],
            "senior_center_failed_rows": venue_metadata["failed_rows"],
            "road_primary_count": sum(
                row["road_distance_primary"] == "Y" for row in admins
            ),
            "quality_deferred_admin_count": sum(row["road_distance_primary"] != "Y" for row in admins),
        },
    }
    if not legacy:
        for preset in payload["sensitivity_presets"]:
            preset["allocation_method"] = "priority_dp"
            preset["parameters"]["service_cycle_days"] = route["engine_input"]["service_cycle_days"]
        payload["report_evidence"] = report
        payload["validation"] = provenance
        payload["source_as_of"].update({
            "outlets": "원천별 기준일 상이",
            "outlets_note": "우체국 2025-03-01 · 은행 2025-12-31 · 신협·새마을금고 2026-08 수집 · 농협·인접 신협 2026-10-12 수집",
            "outlets_retrieved": "2026-10-12",
            "generated_on": route["analysis_date"], "roads": provenance["road_date"],
        })
        payload["historical_typology"] = {"status": "historical_not_recomputed", "source": "data/processed/access_typology.csv", "label": "1차 제출 자료의 유형 분류 · 보완 접점으로 다시 계산하지 않음"}
        if len(outlets) != 1347 or listed_outlet_count != 1385 or len(admins) != 243:
            raise RuntimeError("dashboard must match the report's expanded input counts")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy", action="store_true", help="1차 제출 자료로 명시적으로 재생성")
    args = parser.parse_args()
    payload = build_payload(legacy=args.legacy)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    OUTPUT.write_text(
        "const JEONBUK_DASHBOARD=" + encoded + ";\n"
        "if(typeof window!==\"undefined\")window.JEONBUK_DASHBOARD=JEONBUK_DASHBOARD;\n"
        "if(typeof module!==\"undefined\")module.exports=JEONBUK_DASHBOARD;\n",
        encoding="utf-8",
    )
    print(
        f"전북 대시보드 데이터: {len(payload['admins'])}개 행정동·"
        f"{payload['source_summary']['finance_outlet_count']}개 분석가용 접점·"
        f"{payload['scope']['route_eligible_target_count']}개 경로대상"
    )
    print(f"→ {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
