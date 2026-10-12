"""Audit six neighboring-province CU listings and filter official coordinates.

Public website list pagination and branch-detail JSON only. No map API key.
Institution/group-restricted branches are retained in the audit but not the
regional-common-bond sensitivity input. ATM listing is never queried.
"""
import concurrent.futures
import csv
import datetime as dt
import hashlib
import html
import json
import math
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
PROVINCES = {"sido07": "대전", "sido11": "경북", "sido12": "경남", "sido13": "충북", "sido14": "충남", "sido18": "전남광주"}
LIST_URL = "https://www.cu.co.kr/cu/ad/cuSearch.do"
DETAIL_URL = "https://www.cu.co.kr/cu/ad/assc.do"
BBOX = (126, 35.1, 128.1, 36.35)


def fetch(url, params, relative):
    path = ROOT / "raw" / "cu" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = path.with_suffix(path.suffix + ".request.json")
    if path.exists() and meta.exists():
        return path.read_bytes(), json.loads(meta.read_text())
    request = urllib.request.Request(url, data=urllib.parse.urlencode(params).encode(), headers={"Referer": LIST_URL + "?mi=100076"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=35) as response:
                raw = response.read()
                obs = dict(url=url, method="POST", parameters=params, http_status=response.status,
                           retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                           content_type=response.headers.get("Content-Type"))
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(1)
    obs.update(sha256=hashlib.sha256(raw).hexdigest(), byte_count=len(raw), raw_path=str(path.relative_to(ROOT)))
    path.write_bytes(raw)
    meta.write_text(json.dumps(obs, ensure_ascii=False, indent=2))
    time.sleep(0.10)
    return raw, obs


def collect_province(code):
    entries, observations, expected = [], [], None
    page = 1
    while expected is None or len(entries) < expected:
        params = dict(mi="100076", cuSearchTab="1", ctprvn=code, signgu="", currPage=str(page), searchTxt="", searchTy="")
        raw, obs = fetch(LIST_URL, params, f"lists/{code}_{page:03}.html")
        s = raw.decode("utf-8")
        total = int(re.search(r"Total\s*<strong>([\d,]+)</strong>", s).group(1).replace(",", ""))
        if expected is None:
            expected = total
        assert expected == total, (code, "total changed", expected, total)
        pairs = re.findall(r"fn_selectCuInfo\(['\"](\d+)['\"],['\"](\d+)['\"]\)", s)
        assert pairs or not expected, (code, page, "empty page")
        entries.extend(dict(cuNo=a, cuMbrCd=b, province_query=code, list_page=page, list_raw_path=obs["raw_path"]) for a, b in pairs)
        observations.append(dict(parsed_rows=len(pairs), reported_total=total, **obs))
        page += 1
        if expected == 0:
            break
    assert len(entries) == expected
    assert len({(x["cuNo"], x["cuMbrCd"]) for x in entries}) == expected
    print("province", code, PROVINCES[code], expected, flush=True)
    return entries, dict(code=code, name=PROVINCES[code], reported_total=expected, collected_rows=len(entries), pages=observations)


def detail(entry):
    params = {k: entry[k] for k in ("cuNo", "cuMbrCd")}
    raw, obs = fetch(DETAIL_URL, params, f"details/{entry['cuNo']}_{entry['cuMbrCd']}.json")
    r = json.loads(raw)
    assert str(r.get("cuIngno")) == entry["cuNo"] and str(r.get("mnbrCode")) == entry["cuMbrCd"], (entry, r)
    lon, lat = r.get("x"), r.get("y")
    valid = isinstance(lon, (float, int)) and isinstance(lat, (float, int)) and 124 < lon < 132 and 33 < lat < 39
    in_box = valid and BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]
    common_bond = str(r.get("uniRelTy", ""))
    eligibility = "include_regional_bond_proxy" if common_bond == "1" else "exclude_workplace_restricted" if common_bond == "3" else "exclude_group_access_unconfirmed" if common_bond == "2" else "exclude_bond_unknown"
    addr = " ".join(str(r.get(k) or "").strip() for k in ["mnbrDongAddr", "mnbrDtlAddr"]).strip()
    return dict(outlet_id="CUOFF-"+entry["cuNo"]+"-"+entry["cuMbrCd"], type="신협",
                name=str(r.get("cuNm", ""))+" "+str(r.get("mnbrNm", "")), addr=addr,
                lat=lat, lon=lon, cu_no=entry["cuNo"], branch_code=entry["cuMbrCd"], network_code=r.get("netwCode"),
                common_bond_code=common_bond, common_bond={"1":"지역", "2":"단체", "3":"직장"}.get(common_bond, "unknown"),
                eligibility=eligibility, official_coordinate_valid=valid, in_context_bbox=in_box,
                services_reported=r.get("upmuMatt"), phone=r.get("ownTelNo"),
                finance_status="official_branch_listing_assumed_open", service_confirmation="regional_common_bond_and_branch_listing; individual_hours_unconfirmed",
                baseline_date_status="unknown_at_2026-08_baseline", coordinate_source="official_assc_json_x_lon_y_lat",
                source_url=DETAIL_URL, source_entrypoint=LIST_URL+"?mi=100076", retrieved_at=obs["retrieved_at"],
                raw_path=obs["raw_path"], **entry)


def write_csv(name, rows):
    if not rows:
        return
    with (ROOT / name).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    all_entries, province_audits = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        for entries, audit in ex.map(collect_province, PROVINCES):
            all_entries.extend(entries); province_audits.append(audit)
    keyed = {(x["cuNo"], x["cuMbrCd"]): x for x in all_entries}
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
        for i, row in enumerate(ex.map(detail, keyed.values()), 1):
            rows.append(row)
            if i % 50 == 0:
                print("details", i, "/", len(keyed), flush=True)
    boxed = [r for r in rows if r["in_context_bbox"]]
    eligible = [r for r in boxed if r["eligibility"] == "include_regional_bond_proxy" and not r["addr"].startswith(("전북", "전라북"))]
    write_csv("cu_six_provinces_all_listed.csv", rows)
    write_csv("cu_context_bbox_all_listed.csv", boxed)
    write_csv("cu_outside_jeonbuk_context_eligible.csv", eligible)
    manifest = dict(source_entrypoint=LIST_URL+"?mi=100076", detail_endpoint=DETAIL_URL, provinces=province_audits,
                    unique_branches_queried=len(keyed), collected_details=len(rows),
                    context_bbox_lon_lat=BBOX, bbox_records=len(boxed), eligible_outside_jeonbuk_records=len(eligible),
                    missing_or_invalid_coordinates=[r["outlet_id"] for r in rows if not r["official_coordinate_valid"]],
                    bbox_exclusions=[dict(outlet_id=r["outlet_id"], name=r["name"], common_bond=r["common_bond"], eligibility=r["eligibility"]) for r in boxed if r["eligibility"]!="include_regional_bond_proxy"],
                    temporal_limit="Retrieved 2026-10-12. Presence and operation at August 2026 baseline are unknown.",
                    coverage_limit="All listed branches from six specified province queries, then official-coordinate bbox filter. Not a nationwide or cross-provider census. Invalid-coordinate records are not assumed absent from bbox.",
                    retrieval_started_at=min(r["retrieved_at"] for a in province_audits for r in a["pages"]),
                    retrieval_finished_at=max(r["retrieved_at"] for r in rows))
    (ROOT / "cu_collection_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print("DONE", len(rows), "details", len(boxed), "bbox", len(eligible), "eligible", flush=True)
