"""Factorial outlet/origin validation without changing submitted data.

The four cells share one directed road graph. Distances remain unrounded for
classification. The centroid is an area centroid in EPSG:5179 over all polygon
components and holes. Neither origin estimates individual residents' access.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import pickle
import platform
import statistics
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

import build_roadnet as road
from pyproj import Transformer
from shapely import transform
from shapely.geometry import Point, shape
from scipy.stats import spearmanr

TO_METERS = Transformer.from_crs(4326, 5179, always_xy=True).transform
TO_WGS84 = Transformer.from_crs(5179, 4326, always_xy=True).transform


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"empty output: {path}")
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def projected_centroid(geometry: dict) -> tuple[float, float, bool, float]:
    original = shape(geometry)
    if original.geom_type not in {"Polygon", "MultiPolygon"} or not original.is_valid:
        raise ValueError("boundary must be a valid Polygon or MultiPolygon")
    projected = transform(original, TO_METERS, interleaved=False)
    if projected.is_empty or projected.area <= 0:
        raise ValueError("boundary has no positive area")
    center = transform(projected.centroid, TO_WGS84, interleaved=False)
    return center.x, center.y, original.covers(center), projected.area / 1_000_000


def category(distance, lower: float = 3.0, upper: float = 5.0) -> str:
    if distance in ("", None) or not math.isfinite(float(distance)):
        return "unrouted"
    if float(distance) > upper:
        return "P1"
    if float(distance) > lower:
        return "P2"
    return "within_threshold"


def route_category(row: dict, lower: float = 3.0, upper: float = 5.0) -> str:
    if row["origin_inside_boundary"] != "Y":
        return "outside_origin"
    if row["road_distance_primary"] != "Y":
        return "quality_deferred"
    return category(row["road_km"], lower, upper)


def quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    index = (len(values) - 1) * q
    left = math.floor(index)
    right = math.ceil(index)
    return values[left] + (values[right] - values[left]) * (index - left)


def distribution(values: list[float]) -> dict:
    return {
        "n": len(values),
        "min": min(values) if values else None,
        "p10": quantile(values, 0.1),
        "median": statistics.median(values) if values else None,
        "p90": quantile(values, 0.9),
        "max": max(values) if values else None,
        "mean": statistics.mean(values) if values else None,
    }


def graph_provenance(pbf: Path, boundaries: Path) -> dict:
    return {
        "pbf_sha256": sha256(pbf),
        "boundary_sha256": sha256(boundaries),
        "build_roadnet_sha256": sha256(ROOT / "src/build_roadnet.py"),
        "geo_utils_sha256": sha256(ROOT / "src/geo_utils.py"),
        "python_version": platform.python_version(),
        "osmium_version": importlib.metadata.version("osmium"),
        "bbox_margin_degrees": 0.25,
        "max_snap_km": road.MAX_SNAP_KM,
        "grid_degrees": road.GRID_DEGREES,
    }


def load_graph(pbf: Path, boundaries: Path, cache_dir: Path) -> tuple[dict, dict]:
    provenance = graph_provenance(pbf, boundaries)
    key = hashlib.sha256(json.dumps(provenance, sort_keys=True).encode()).hexdigest()
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = cache_dir / f"{key}.json"
    graph_path = cache_dir / f"{key}.pickle"
    if graph_path.exists() and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest["inputs"] != provenance or manifest["graph_sha256"] != sha256(graph_path):
            raise RuntimeError("graph cache provenance mismatch")
        # Only this runner's hash-verified local cache is loaded.
        with graph_path.open("rb") as handle:
            graph = pickle.load(handle)
        print(f"Reused graph cache: {graph_path.name}", flush=True)
    else:
        road.PBF = pbf
        road.GEOJSON = boundaries
        bbox, lats, lons, active, offsets, neighbors, weights, edge_count, active_count = road.build_graph()
        graph = {
            "bbox": bbox, "lats": lats, "lons": lons, "active": active,
            "offsets": offsets, "neighbors": neighbors, "weights": weights,
            "edge_count": edge_count, "active_count": active_count,
        }
        with graph_path.open("wb") as handle:
            pickle.dump(graph, handle, protocol=pickle.HIGHEST_PROTOCOL)
        manifest = {"inputs": provenance, "graph_sha256": sha256(graph_path)}
        write_json(manifest_path, manifest)
    graph["grid"] = road.build_grid(graph["lats"], graph["lons"], graph["active"])
    return graph, {**manifest, "cache_file": str(graph_path.resolve())}


def origin_rows(access: list[dict], boundaries: Path) -> dict[str, list[dict]]:
    features = json.loads(boundaries.read_text(encoding="utf-8"))["features"]
    lookup = {}
    for feature in features:
        code = str(feature["properties"].get("adm_cd2", ""))
        if code:
            if code in lookup:
                raise ValueError(f"duplicate boundary code: {code}")
            lookup[code] = feature["geometry"]
    internal, centroids = [], []
    for row in access:
        geometry = lookup[row["code"]]
        lon, lat, inside, area = projected_centroid(geometry)
        original_inside = shape(geometry).covers(Point(float(row["lon"]), float(row["lat"])))
        shared = {"projected_area_km2": area, "centroid_inside_boundary": "Y" if inside else "N"}
        internal.append({
            **row, **shared, "origin_variant": "submitted_internal",
            "origin_inside_boundary": "Y" if original_inside else "N",
            "origin_displacement_km": 0.0,
        })
        centroids.append({
            **row, **shared, "lon": lon, "lat": lat,
            "point_method": "full_geometry_area_centroid_epsg5179",
            "origin_variant": "full_centroid", "origin_inside_boundary": "Y" if inside else "N",
            "origin_displacement_km": road.haversine(float(row["lat"]), float(row["lon"]), lat, lon),
        })
    return {"internal": internal, "centroid": centroids}


def load_outlets(path: Path) -> list[dict]:
    rows = read_csv(path)
    seen = set()
    for row in rows:
        if row["outlet_id"] in seen:
            raise ValueError(f"duplicate outlet_id: {row['outlet_id']}")
        seen.add(row["outlet_id"])
        row["lat"], row["lon"] = float(row["lat"]), float(row["lon"])
        if not (-90 <= row["lat"] <= 90 and -180 <= row["lon"] <= 180):
            raise ValueError(f"invalid coordinates: {row['outlet_id']}")
    return rows


def validate_additive_pool(baseline: list[dict], expanded: list[dict]) -> None:
    lookup = {row["outlet_id"]: row for row in expanded}
    for row in baseline:
        other = lookup.get(row["outlet_id"])
        if other is None or any(row[key] != other[key] for key in ("lat", "lon", "finance_open")):
            raise ValueError(f"expanded pool is not additive: {row['outlet_id']}")


def shortest_paths(graph: dict, outlets: list[dict]) -> tuple[tuple, dict]:
    eligible = sorted((row for row in outlets if row["finance_open"] == "Y"), key=lambda row: row["outlet_id"])
    if not eligible:
        raise ValueError("outlet pool has no eligible finance counter")
    attachments, failures = [], []
    for index, outlet in enumerate(eligible):
        nearby = road.nearby_nodes(graph["grid"], graph["lats"], graph["lons"], outlet["lat"], outlet["lon"])
        if nearby:
            node, connector = min(nearby, key=lambda item: (item[1], item[0]))
            attachments.append((node, connector, index))
        else:
            failures.append(outlet["outlet_id"])
    distances, sources, seed_legs, pops = road.multi_source_to_targets(
        graph["offsets"], graph["neighbors"], graph["weights"], attachments
    )
    return (eligible, distances, sources, seed_legs), {
        "outlet_rows": len(outlets), "eligible_outlets": len(eligible),
        "snapped_outlets": len(attachments), "outlet_snap_failures": failures,
        "dijkstra_heap_pops": pops,
    }


def straight_line_fields(row: dict, outlets: list[dict]) -> dict:
    distances = [(road.haversine(float(row["lat"]), float(row["lon"]), p["lat"], p["lon"]), p) for p in outlets]
    eligible = [(distance, p) for distance, p in distances if p["finance_open"] == "Y"]
    distance, closest = min(eligible, key=lambda item: (item[0], item[1]["outlet_id"]))
    any_distance, any_closest = min(distances, key=lambda item: (item[0], item[1]["outlet_id"]))
    extra = {
        "nearest_km": distance, "nearest_outlet_id": closest["outlet_id"],
        "nearest_name": closest["name"], "nearest_type": closest["type"],
        "nearest_open_km": distance, "nearest_open_name": closest["name"],
        "nearest_any_km": any_distance, "nearest_any_outlet_id": any_closest["outlet_id"],
        "nearest_any_name": any_closest["name"], "nearest_any_type": any_closest["type"],
        "distance_model": f"{row['origin_variant']}_straight_line",
        "distance_scope": "finance_open_proxy_Y", "population_exposure_valid": "N",
    }
    for kind in sorted({p["type"] for p in outlets}):
        values = [d for d, p in eligible if p["type"] == kind]
        extra[f"near_{kind}_km"] = min(values) if values else ""
    for radius in (1, 3, 5):
        extra[f"cnt_{radius}km"] = sum(d <= radius for d, _ in eligible)
        extra[f"cnt_any_{radius}km"] = sum(d <= radius for d, _ in distances)
    return extra


def evaluate_origins(graph: dict, rows: list[dict], outlets: list[dict], paths: tuple, pool_name: str) -> list[dict]:
    eligible, distances, sources, seed_legs = paths
    output = []
    for row in rows:
        nearby = road.nearby_nodes(graph["grid"], graph["lats"], graph["lons"], float(row["lat"]), float(row["lon"]))
        nearest = min(nearby, key=lambda item: (item[1], item[0])) if nearby else None
        extra = {
            "road_km": "", "network_km": "", "admin_snap_km": "", "outlet_snap_km": "",
            "road_outlet_id": "", "road_nearest_name": "", "road_nearest_type": "",
            "route_straight_km": "", "detour": "", "route_status": "admin_snap_failed",
            "routing_method": "directed_all_outlet_reverse_multisource_dijkstra",
            "oneway_respected": "Y", "max_snap_km": road.MAX_SNAP_KM,
            "admin_snap_strategy": "", "route_quality": "", "road_distance_primary": "N",
            "outlet_pool": pool_name, "admin_osm_node_index": "",
            "fixed_nearest_node_reachable": "N",
        }
        chosen = None
        if nearest:
            if sources[nearest[0]] >= 0:
                chosen = nearest
                extra.update({"admin_snap_strategy": "exact_nearest_node", "route_quality": "standard_proxy", "road_distance_primary": "Y", "fixed_nearest_node_reachable": "Y"})
            else:
                expanded = road.nearby_nodes(graph["grid"], graph["lats"], graph["lons"], float(row["lat"]), float(row["lon"]), slack_km=road.MAX_SNAP_KM)
                reachable = [item for item in expanded if sources[item[0]] >= 0]
                chosen = min(reachable, key=lambda item: (item[1], item[0])) if reachable else None
                extra.update({"admin_snap_strategy": "nearest_directed_reachable_node_fallback", "route_quality": "low_large_connector_fallback", "route_status": "no_directed_path_to_eligible_outlet"})
        if chosen:
            node, connector = chosen
            outlet = eligible[sources[node]]
            road_km = connector + distances[node]
            direct = road.haversine(float(row["lat"]), float(row["lon"]), outlet["lat"], outlet["lon"])
            extra.update({
                "road_km": road_km, "network_km": max(0.0, distances[node] - seed_legs[node]),
                "admin_snap_km": connector, "outlet_snap_km": float(seed_legs[node]),
                "road_outlet_id": outlet["outlet_id"], "road_nearest_name": outlet["name"],
                "road_nearest_type": outlet["type"], "route_straight_km": direct,
                "detour": road_km / direct if direct > 0 else "",
                "route_status": "ok" if extra["road_distance_primary"] == "Y" else "fallback_nearest_reachable",
                "admin_osm_node_index": node,
            })
        combined = {**row, **straight_line_fields(row, outlets), **extra}
        combined["distance_category"] = category(combined["road_km"])
        combined["routing_category"] = route_category(combined)
        output.append(combined)
    return output


def pair_comparison(before: list[dict], after: list[dict], enforce_additive: bool = False) -> tuple[list[dict], dict]:
    lookup = {row["code"]: row for row in after}
    output, fixed_primary_deltas = [], []
    for old in before:
        new = lookup[old["code"]]
        both_routed = old["road_km"] != "" and new["road_km"] != ""
        delta = float(new["road_km"]) - float(old["road_km"]) if both_routed else ""
        both_primary = old["road_distance_primary"] == new["road_distance_primary"] == "Y"
        same_node = str(old["admin_osm_node_index"]) == str(new["admin_osm_node_index"])
        if enforce_additive and both_primary:
            if not same_node or delta > 1e-8:
                raise AssertionError(f"additive-pool monotonicity violation: {old['code']}")
            fixed_primary_deltas.append(delta)
        output.append({
            "code": old["code"], "sigungu": old["sigungu"], "dong": old["dong"],
            "before_road_km": old["road_km"], "after_road_km": new["road_km"], "delta_km": delta,
            "before_category": category(old["road_km"]), "after_category": category(new["road_km"]),
            "before_routing_category": route_category(old), "after_routing_category": route_category(new),
            "before_outlet_id": old["road_outlet_id"], "after_outlet_id": new["road_outlet_id"],
            "nearest_outlet_changed": "Y" if old["road_outlet_id"] != new["road_outlet_id"] else "N",
            "before_quality": old["route_status"], "after_quality": new["route_status"],
            "before_inside_boundary": old["origin_inside_boundary"], "after_inside_boundary": new["origin_inside_boundary"],
            "both_primary": "Y" if both_primary else "N", "same_admin_osm_node": "Y" if same_node else "N",
        })
    valid = [row for row in output if row["both_primary"] == "Y" and row["before_inside_boundary"] == row["after_inside_boundary"] == "Y"]
    return output, {
        "rows": len(output),
        "all_routed_delta_km": distribution([row["delta_km"] for row in output if row["delta_km"] != ""]),
        "valid_primary_pair_count": len(valid),
        "valid_primary_delta_km": distribution([row["delta_km"] for row in valid]),
        "valid_primary_absolute_delta_km": distribution([abs(row["delta_km"]) for row in valid]),
        "category_transitions_all": dict(Counter(f"{row['before_category']} -> {row['after_category']}" for row in output)),
        "category_transitions_valid_primary": dict(Counter(f"{row['before_category']} -> {row['after_category']}" for row in valid)),
        "routing_category_transitions": dict(Counter(f"{row['before_routing_category']} -> {row['after_routing_category']}" for row in output)),
        "nearest_outlet_changes_all": sum(row["nearest_outlet_changed"] == "Y" for row in output),
        "nearest_outlet_changes_valid_primary": sum(row["nearest_outlet_changed"] == "Y" for row in valid),
        "additive_fixed_primary_monotonicity_checked": len(fixed_primary_deltas) if enforce_additive else None,
    }


def cell_summary(rows: list[dict]) -> dict:
    return {
        "admin_count": len(rows), "distance_category_counts": dict(Counter(category(row["road_km"]) for row in rows)),
        "routing_category_counts": dict(Counter(route_category(row) for row in rows)),
        "route_status_counts": dict(Counter(row["route_status"] for row in rows)),
        "outside_origin_codes": [row["code"] for row in rows if row["origin_inside_boundary"] != "Y"],
        "distance_km_all_routed": distribution([float(row["road_km"]) for row in rows if row["road_km"] != ""]),
        "distance_km_valid_primary": distribution([float(row["road_km"]) for row in rows if row["road_distance_primary"] == "Y" and row["origin_inside_boundary"] == "Y"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pbf", type=Path, required=True)
    parser.add_argument("--boundaries", type=Path, required=True)
    parser.add_argument("--access", type=Path, required=True)
    parser.add_argument("--outlets-baseline", type=Path, required=True)
    parser.add_argument("--outlets-expanded", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path(__file__).parent / "cache")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    access = read_csv(args.access)
    if len(access) != 243 or len({row["code"] for row in access}) != 243:
        raise ValueError("expected exactly 243 unique submitted administrative areas")
    origins = origin_rows(access, args.boundaries)
    baseline = load_outlets(args.outlets_baseline)
    expanded = load_outlets(args.outlets_expanded)
    validate_additive_pool(baseline, expanded)
    input_paths = {name: getattr(args, name) for name in ("pbf", "boundaries", "access", "outlets_baseline", "outlets_expanded")}
    inputs = {name: {"path": str(path.resolve()), "sha256": sha256(path)} for name, path in input_paths.items()}
    graph, graph_manifest = load_graph(args.pbf, args.boundaries, args.cache_dir)
    cells, pool_stats = {}, {}
    for pool_name, outlets in (("baseline", baseline), ("expanded", expanded)):
        print(f"Evaluate pool: {pool_name}", flush=True)
        paths, pool_stats[pool_name] = shortest_paths(graph, outlets)
        for origin_name, rows in origins.items():
            key = f"{pool_name}_{origin_name}"
            cells[key] = evaluate_origins(graph, rows, outlets, paths, pool_name)
            write_csv(args.output_dir / f"access_{key}.csv", cells[key])
        del paths
    comparisons = {}
    for name, before, after, additive in (
        ("outlet_effect_internal", "baseline_internal", "expanded_internal", True),
        ("outlet_effect_centroid", "baseline_centroid", "expanded_centroid", True),
        ("origin_effect_baseline", "baseline_internal", "baseline_centroid", False),
        ("origin_effect_expanded", "expanded_internal", "expanded_centroid", False),
    ):
        rows, comparisons[name] = pair_comparison(cells[before], cells[after], additive)
        write_csv(args.output_dir / f"{name}.csv", rows)
    sensitivity = []
    for name, rows in cells.items():
        for lower in (2.5, 3.0, 3.5):
            for upper in (4.0, 5.0, 6.0):
                counts = Counter(route_category(row, lower, upper) for row in rows)
                sensitivity.append({"cell": name, "lower_threshold_km": lower, "upper_threshold_km": upper, **{key: counts[key] for key in ("P1", "P2", "within_threshold", "quality_deferred", "outside_origin")}})
    write_csv(args.output_dir / "threshold_sensitivity.csv", sensitivity)
    stable = []
    by_cell = {name: {row["code"]: row for row in rows} for name, rows in cells.items()}
    for row in cells["expanded_internal"]:
        alt = by_cell["expanded_centroid"][row["code"]]
        valid = row["road_distance_primary"] == alt["road_distance_primary"] == row["origin_inside_boundary"] == alt["origin_inside_boundary"] == "Y"
        status = "not_comparable_quality_or_outside" if not valid else "stable" if row["distance_category"] == alt["distance_category"] else "origin_sensitive"
        stable.append({"code": row["code"], "sigungu": row["sigungu"], "dong": row["dong"], "internal_category": row["distance_category"], "centroid_category": alt["distance_category"], "internal_km": row["road_km"], "centroid_km": alt["road_km"], "status": status, "centroid_inside": alt["origin_inside_boundary"], "centroid_displacement_km": alt["origin_displacement_km"]})
    write_csv(args.output_dir / "origin_robustness_expanded.csv", stable)
    comparable = [row for row in stable if row["status"] != "not_comparable_quality_or_outside"]
    rho = spearmanr([float(row["internal_km"]) for row in comparable], [float(row["centroid_km"]) for row in comparable]).statistic if len(comparable) > 1 else None
    displacements = [float(row["origin_displacement_km"]) for row in origins["centroid"]]
    legacy_changes = []
    original = {row["code"]: row for row in access}
    for row in cells["baseline_internal"]:
        old = original[row["code"]]
        legacy_changes.append({"code": row["code"], "sigungu": row["sigungu"], "dong": row["dong"], "submitted_rounded_km": old["road_km"], "rerun_unrounded_km": row["road_km"], "submitted_category": category(old["road_km"]), "rerun_category": category(row["road_km"]), "rerun_rounded_category": category(round(float(row["road_km"]), 3)) if row["road_km"] != "" else "unrouted", "submitted_quality": old["route_status"], "rerun_quality": row["route_status"]})
    write_csv(args.output_dir / "submitted_vs_common_road_baseline.csv", legacy_changes)
    summary = {
        "generated_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
        "inputs": inputs, "runner_sha256": sha256(Path(__file__)), "graph": graph_manifest,
        "packages": {name: importlib.metadata.version(name) for name in ("shapely", "pyproj", "osmium")},
        "design": {
            "factorial_cells": "2 outlet pools x 2 origins over all 243 submitted administrative areas",
            "centroid": "all components and holes; area centroid in EPSG:5179; transformed to EPSG:4326",
            "internal": "exact submitted CSV coordinates preserved",
            "outside_centroid": "retained as diagnostic; excluded from valid-origin and routing comparisons",
            "thresholds": "full precision: P1 > 5 km; P2 > 3 km and <= 5 km",
            "fallback": "nearest reachable node by connector distance then node index; non-primary; differs from legacy index-order fallback",
            "resident_coverage_available": False,
            "monotonicity": "checked only with both primary on the same fixed nearest node",
            "outlet_seed_order": "outlet_id ascending; same-node equal connector retains first seed",
        },
        "pool_stats": pool_stats, "cells": {name: cell_summary(rows) for name, rows in cells.items()},
        "comparisons": comparisons, "expanded_origin_robustness": dict(Counter(row["status"] for row in stable)),
        "origin_geometry": {
            "submitted_method_counts": dict(Counter(row["point_method"] for row in access)),
            "displacement_km_all_243": distribution(displacements),
            "displacement_over_10m_count": sum(value > 0.01 for value in displacements),
            "displacement_over_100m_count": sum(value > 0.1 for value in displacements),
            "spearman_valid_primary_pair_count": len(comparable),
            "road_distance_spearman_valid_primary": float(rho) if rho is not None and math.isfinite(rho) else None,
            "interpretation": "geometric sensitivity only; most submitted origins already use the largest-component centroid; no resident-location validation",
        },
        "legacy_baseline_category_changes": [row for row in legacy_changes if row["submitted_category"] != row["rerun_category"]],
        "precision_only_category_changes_common_road": [row for row in legacy_changes if row["rerun_category"] != row["rerun_rounded_category"]],
        "outputs": {path.name: sha256(path) for path in sorted(args.output_dir.glob("*.csv"))},
    }
    write_json(args.output_dir / "summary.json", summary)
    print(json.dumps({"cells": summary["cells"], "origin_robustness": summary["expanded_origin_robustness"]}, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
