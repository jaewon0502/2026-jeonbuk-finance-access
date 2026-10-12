"""Freeze additive outlet scenarios without replacing the submission snapshot."""
from pathlib import Path
import csv
import hashlib
import json
from collections import Counter

from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform, unary_union
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "analysis/theory_validation"
INPUT = WORK / "inputs"


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    base = read(ROOT / "data/processed/outlets_validated.csv")
    features = json.loads((INPUT / "hjd2026.geojson").read_text())["features"]
    geometries = [shape(f["geometry"]) for f in features]
    tree = STRtree(geometries)
    jb = unary_union([g for g, f in zip(geometries, features) if f["properties"]["sido"] == "52"])
    project = Transformer.from_crs(4326, 5179, always_xy=True).transform
    jb_m = transform(project, jb)
    extras = ["expansion_group", "source_branch_code", "source_url", "retrieved_at", "baseline_date_status", "boundary_distance_m"]
    fields = list(base[0]) + extras
    output = [{**r, **{k: "" for k in extras}, "expansion_group": "submission_snapshot"} for r in base]
    raw = read(WORK / "outlets/nh_branches_context_bbox.csv")
    audit = []
    for row in raw:
        point = Point(float(row["lon"]), float(row["lat"]))
        matches = [int(i) for i in tree.query(point) if geometries[i].covers(point)]
        props = features[min(matches)]["properties"] if matches else {}
        inside = jb.covers(point)
        distance = transform(project, point).distance(jb_m)
        coop = row["type"] == "농·축협"
        if inside and not coop:
            reason = "existing_jeonbuk_nh_bank_category_retained_from_submission"
        elif not inside and distance > 20000:
            reason = "outside_predeclared_20km_boundary_buffer"
        else:
            reason = "include_jeonbuk_coop" if inside else "include_border_nh"
        audit.append({"outlet_id": row["outlet_id"], "name": row["name"], "type": row["type"], "addr": row["addr"], "inside_jeonbuk": inside, "coord_admin_code": props.get("adm_cd2", ""), "boundary_distance_m": round(distance, 3), "decision": reason})
        if not reason.startswith("include"):
            continue
        item = {k: "" for k in fields}
        item.update({
            "outlet_id": row["outlet_id"], "type": row["type"], "name": row["name"], "addr": row["addr"],
            "sigungu": props.get("sggnm", ""), "lat": row["lat"], "lon": row["lon"],
            "finance_open": "Y", "finance_status": "listed_assumed_open",
            "status_basis": "농협 공식 영업점 조회 등재. 영업시간과 현재 운영 여부는 별도 확인하지 않음",
            "geo_how": "official_directory_coordinates", "geo_quality": "official_coordinate_polygon_checked",
            "coord_admin_code": props.get("adm_cd2", ""), "coord_sigungu": props.get("sggnm", ""),
            "coord_dong": props.get("adm_nm", "").split()[-1] if props else "",
            "geo_inside_jeonbuk": "Y" if inside else "N", "geo_review": "polygon_validated",
            "source": "농협 공식 영업점 안내", "source_snapshot": row["retrieved_at"][:10],
            "source_branch_code": row["branch_code"], "source_url": row["source_detail_url"],
            "retrieved_at": row["retrieved_at"], "baseline_date_status": row["baseline_date_status"],
            "expansion_group": "jeonbuk_coop" if inside else "border_nh_20km",
            "boundary_distance_m": round(distance, 3),
        })
        output.append(item)
    assert len({r["outlet_id"] for r in output}) == len(output)
    write(INPUT / "outlets_expanded_nh.csv", output, fields)
    write(INPUT / "nh_geographic_audit.csv", audit, list(audit[0]))
    write(INPUT / "outlets_jeonbuk_coops_only.csv", [r for r in output if r["expansion_group"] != "border_nh_20km"], fields)
    cu_raw = read(WORK / "outlets/cu_outside_jeonbuk_context_eligible.csv")
    cu_audit = []
    for row in cu_raw:
        point = Point(float(row["lon"]), float(row["lat"]))
        inside = jb.covers(point)
        distance = transform(project, point).distance(jb_m)
        matches = [int(i) for i in tree.query(point) if geometries[i].covers(point)]
        props = features[min(matches)]["properties"] if matches else {}
        reason = "existing_jeonbuk_cu_category_retained" if inside else "outside_predeclared_20km_boundary_buffer" if distance > 20000 else "include_border_cu"
        cu_audit.append({"outlet_id": row["outlet_id"], "name": row["name"], "addr": row["addr"], "inside_jeonbuk": inside, "boundary_distance_m": round(distance, 3), "decision": reason})
        if reason != "include_border_cu":
            continue
        item = {k: "" for k in fields}
        item.update({
            "outlet_id": row["outlet_id"], "type": "신협", "name": row["name"], "addr": row["addr"],
            "sigungu": props.get("sggnm", ""), "lat": row["lat"], "lon": row["lon"],
            "finance_open": "Y", "finance_status": "listed_assumed_open",
            "status_basis": "신협 공식 영업점 조회의 지역 공동유대. 영업시간과 현재 운영 여부는 별도 확인하지 않음",
            "geo_how": "official_directory_coordinates", "geo_quality": "official_coordinate_polygon_checked",
            "coord_admin_code": props.get("adm_cd2", ""), "coord_sigungu": props.get("sggnm", ""),
            "coord_dong": props.get("adm_nm", "").split()[-1] if props else "", "geo_inside_jeonbuk": "N", "geo_review": "polygon_validated",
            "source": "신협중앙회 신협찾기", "source_snapshot": row["retrieved_at"][:10],
            "source_branch_code": row["cu_no"] + "-" + row["branch_code"], "source_url": row["source_entrypoint"],
            "retrieved_at": row["retrieved_at"], "baseline_date_status": row["baseline_date_status"],
            "expansion_group": "border_cu_20km", "boundary_distance_m": round(distance, 3),
        })
        output.append(item)
    assert len({r["outlet_id"] for r in output}) == len(output)
    write(INPUT / "outlets_expanded.csv", output, fields)
    write(INPUT / "cu_geographic_audit.csv", cu_audit, list(cu_audit[0]))
    result = {
        "boundary_buffer_m": 20000, "boundary_buffer_crs": "EPSG:5179",
        "old_snapshot_total": len(base), "old_snapshot_eligible": sum(r["finance_open"] == "Y" for r in base),
        "input_nh_bbox_count": len(raw), "geographic_decisions": dict(Counter(r["decision"] for r in audit)),
        "input_cu_bbox_eligible_count": len(cu_raw), "cu_geographic_decisions": dict(Counter(r["decision"] for r in cu_audit)),
        "scenario_groups": dict(Counter(r["expansion_group"] for r in output)),
        "scenario_total": len(output), "scenario_eligible": sum(r["finance_open"] == "Y" for r in output),
        "limitations": ["Current official listings are an assumed-open proxy, not an operating audit.", "October additions do not establish their presence at the August baseline.", "NH and regional CU records in the collection rectangle and within a 20 km province buffer are expanded; other border providers are not a complete census.", "Original submitted outlets and coordinates are frozen to isolate additive scope.", "CU records with invalid source coordinates are not assumed absent from the collection rectangle."],
        "source_hashes": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT / "data/processed/outlets_validated.csv", INPUT / "hjd2026.geojson", WORK / "outlets/nh_branches_context_bbox.csv", WORK / "outlets/cu_outside_jeonbuk_context_eligible.csv"]},
    }
    (INPUT / "outlet_expansion_audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
