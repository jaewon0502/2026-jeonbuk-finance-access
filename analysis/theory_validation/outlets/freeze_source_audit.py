"""Freeze finite source scope and file checksums after NH/CU collection."""
import collections
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parent


def rows(name):
    return list(csv.DictReader((P / name).open(encoding="utf-8-sig")))


def load(name):
    return json.loads((P / name).read_text())


nh = rows("nh_branches_context_bbox.csv")
jb = rows("nh_coops_jeonbuk_reconciled.csv")
nh_province = rows("nh_coops_jeonbuk.csv")
cu = rows("cu_six_provinces_all_listed.csv")
cu_box = rows("cu_context_bbox_all_listed.csv")
cu_input = rows("cu_outside_jeonbuk_context_eligible.csv")
cu_manifest = load("cu_collection_manifest.json")
nh_manifests = [load("nh_coops_jeonbuk_manifest.json"), load("nh_branches_context_bbox_manifest.json")]
assert len(jb) == 334 and len(nh_province) == 332 and len(nh) == 1018
assert len(cu) == 683 and len(cu_box) == 214 and len(cu_input) == 190
assert len({r["outlet_id"] for r in nh}) == len(nh)
assert len({r["outlet_id"] for r in cu}) == len(cu)
assert all(r["common_bond_code"] == "1" for r in cu_input)
assert all(r["service_type_1"] == "1" for r in nh)
extra = [r for r in jb if r["outlet_id"] not in {x["outlet_id"] for x in nh_province}]
bank_crosswalk = rows("nh_bank_baseline_crosswalk.csv")
audit = dict(
    frozen_at=dt.datetime.now(dt.timezone.utc).isoformat(),
    requested_scope="Official NH regional agricultural/livestock cooperative staffed-branch listings in Jeonbuk, plus NH and CU neighboring-province context candidates.",
    retrieval_date_local="2026-10-12",
    temporal_interpretation="October retrieval is an expanded current-listing sensitivity scenario. August 2026 existence and operating status are unknown; original source baseline is not silently replaced.",
    context_bbox_lon_lat=[126, 35.1, 128.1, 36.35],
    nh=dict(
        official_homepage="https://www.nonghyup.com/main/psniMain.do",
        official_map="https://nonghyup.ttmap.co.kr/main.jsp",
        endpoint="https://nonghyup.ttmap.co.kr/list_branch_2017.jsp",
        province_query_rows=332, province_query_pages=42,
        context_query_rows=1018, context_query_pages=128,
        context_type_counts=dict(collections.Counter(r["type"] for r in nh)),
        jeonbuk_address_coop_rows=334, jeonbuk_address_bank_rows=52,
        outside_jeonbuk_address_rows=632,
        province_query_omission_vs_bbox=[{k:r[k] for k in ["outlet_id", "name", "branch_code", "addr", "lat", "lon", "raw_path"]} for r in extra],
        discrepancy_interpretation="Two Jeonbuk-address records appear in coordinate-bounds query but not province query. Source filter cause is unknown. Use reconciled spatial candidates without calling either query a confirmed real-world census.",
        service_interpretation="svc1=1 branch tab; svc2=2 agricultural/livestock cooperative vs svc2=1 NH Bank. No ATM/store tab queried. Individual financial-service availability/hours unverified. Economic/store-like names retained consistently when official branch category is identical and flagged for review.",
        coordinate_interpretation="Official map setMarker arguments mapX longitude/mapY latitude. No geocoding API used. Source coordinates are not independent ground truth.",
        duplicate_bank_handling="Current Jeonbuk NH Bank 52 records should not be appended to the frozen 52 NH Bank baseline records. Crosswalk is candidate identity evidence, not a coordinate replacement instruction.",
        bank_coordinate_disagreements_over_1km=[r for r in bank_crosswalk if float(r["coordinate_difference_km"]) > 1],
        retrieval_started_at=min(page["retrieved_at"] for m in nh_manifests for page in m["pages"]),
        retrieval_finished_at=max(page["retrieved_at"] for m in nh_manifests for page in m["pages"]),
        request_manifest_files=["nh_coops_jeonbuk_manifest.json", "nh_branches_context_bbox_manifest.json"],
    ),
    cu=dict(
        official_finder="https://www.cu.co.kr/cu/ad/cuSearch.do?mi=100076",
        official_detail_endpoint="https://www.cu.co.kr/cu/ad/assc.do",
        province_counts=[{k:r[k] for k in ["code", "name", "reported_total", "collected_rows"]} for r in cu_manifest["provinces"]],
        six_province_unique_details=683, context_bbox_rows=214, regional_common_bond_input_rows=190,
        context_exclusion_counts=dict(collections.Counter(r["common_bond"] for r in cu_manifest["bbox_exclusions"])),
        restriction_rule="Include only official uniRelTy=1 지역; exclude uniRelTy=3 직장 and hold uniRelTy=2 단체 because general access is unconfirmed. Official finder explicitly cautions workplace and some group coops restrict users.",
        invalid_coordinate_rows=[{k:r[k] for k in ["outlet_id", "name", "addr", "lat", "lon", "raw_path"]} for r in cu if r["official_coordinate_valid"] == "False"],
        coordinate_missingness_rule="Two (0,0) source coordinates excluded from coordinate filtering; not assumed absent from target region. Their listed addresses and raw JSON are preserved.",
        retrieval_started_at=cu_manifest["retrieval_started_at"],
        retrieval_finished_at=cu_manifest["retrieval_finished_at"],
        request_manifest_file="cu_collection_manifest.json",
    ),
    remaining_coverage_gaps=[
        "Cross-border non-NH banks, KFCC, and financial-service post offices were not collected in this supplement. Do not claim exhaustive all-provider border coverage.",
        "KFCC official list endpoint timed out on bounded probe; no repeated unbounded retrieval was attempted.",
        "Current official listing does not independently verify staffed opening hours, service equivalence, accessibility, or August 2026 presence.",
        "NH province selector omitted two current Jeonbuk-address branches present in coordinate query; unresolved source-side inconsistency.",
        "Two CU source coordinates are (0,0), retained as unresolved source records.",
    ],
    integration_boundary="Root performs exact administrative polygon assignment, origin-radius border filtering, deduplication, network snapping, and scenario analysis. These source-context counts are not final added-outlet or changed-priority counts.",
)
file_audit = []
for f in sorted(P.glob("*.csv")):
    rr = rows(f.name)
    file_audit.append(dict(file=f.name, data_rows=len(rr), sha256=hashlib.sha256(f.read_bytes()).hexdigest()))
audit["normalized_files"] = file_audit
(P / "source_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2))
print(json.dumps({"nh_jeonbuk_coops":len(jb), "nh_context":len(nh), "cu_context":len(cu_box), "cu_eligible":len(cu_input), "frozen_at":audit["frozen_at"]}, ensure_ascii=False))
