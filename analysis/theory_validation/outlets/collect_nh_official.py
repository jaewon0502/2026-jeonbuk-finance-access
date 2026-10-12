"""Collect the same public, paginated NH branch lookup used by its official map.

No map SDK, geocoding service, credential, or non-public endpoint is used.
Raw HTML and exact query metadata are retained beside normalized records.
"""
import argparse
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
URL = "https://nonghyup.ttmap.co.kr/list_branch_2017.jsp"
BASE = "https://nonghyup.ttmap.co.kr/main.jsp"


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def extract(s, query_id, page, retrieved_at, raw_path):
    total = int(re.search(r"총\s*<span>([\d,]+)</span>", s).group(1).replace(",", ""))
    records = []
    for block in re.findall(r"<script>(.*?)</script>", s, re.S):
        m = re.search(r"setMarker\((\d+),\s*(\d+),\s*(\d+),\s*\d+,\s*([\d.]+),\s*([\d.]+),\s*html,\s*divHeight,\s*false,\s*'(.*?)'\);", block, re.S)
        if not m:
            continue
        seq, svc1, svc2, lon, lat, name = m.groups()
        address = re.search(r'<td id="td_addr_' + seq + r'">(.*?)</td>', block, re.S)
        branch = re.search(r"<th>지점코드</th>.*?<td>(.*?)</td>", block, re.S)
        services = re.search(r'id="td_bussiness_' + seq + r'">(.*?)</td>', block, re.S)
        phone = re.search(r"<th>전화</th>.*?<td>(.*?)</td>", block, re.S)
        category = "농·축협" if svc2 == "2" else "농협은행" if svc2 == "1" else "other"
        records.append(dict(
            outlet_id="NHMAP-" + seq, source_seq_no=seq,
            branch_code=clean(branch.group(1)) if branch else "",
            type=category, name=clean(name.replace("\\'", "'")),
            addr=clean(address.group(1)) if address else "",
            lat=lat, lon=lon,
            service_type_1=svc1, service_type_2=svc2,
            source_tab="영업점", source_category=category,
            services_reported=clean(services.group(1)) if services else "",
            phone=clean(phone.group(1)) if phone else "",
            finance_status="official_branch_listing_assumed_open",
            service_confirmation="branch_tab_and_institution_category; individual_service_hours_unconfirmed",
            baseline_date_status="unknown_at_2026-08_baseline",
            coordinate_source="official_map_setMarker_lon_lat",
            source_url=URL, source_detail_url="https://nonghyup.ttmap.co.kr/print_2017.jsp?seq_no="+seq,
            query_id=query_id, source_page=page, retrieved_at=retrieved_at,
            raw_path=str(raw_path.relative_to(ROOT)),
        ))
    return total, records


def collect(query_id, params):
    folder = ROOT / "raw" / query_id
    folder.mkdir(parents=True, exist_ok=True)
    observations, allrows = [], []
    page, expected = 1, None
    while expected is None or len(allrows) < expected:
        query = dict(params, pg=str(page))
        path = folder / f"page_{page:03}.html"
        meta = folder / f"page_{page:03}.json"
        if path.exists() and meta.exists():
            raw = path.read_bytes()
            obs = json.loads(meta.read_text())
        else:
            request = urllib.request.Request(URL, data=urllib.parse.urlencode(query).encode(), headers={"Referer": BASE})
            with urllib.request.urlopen(request, timeout=40) as response:
                raw = response.read()
                obs = dict(url=URL, method="POST", params=query, http_status=response.status,
                           retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                           content_type=response.headers.get("Content-Type"))
            obs.update(raw_path=str(path.relative_to(ROOT)), byte_count=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            path.write_bytes(raw)
            meta.write_text(json.dumps(obs, ensure_ascii=False, indent=2))
            time.sleep(0.15)
        total, rows = extract(raw.decode("utf-8"), query_id, page, obs["retrieved_at"], path)
        if expected is None:
            expected = total
        assert total == expected, ("count changed during collection", page, expected, total)
        assert rows or not expected, ("empty page before expected total", page)
        if rows:
            assert all(r["service_type_1"] == "1" for r in rows), "non-branch category"
        allrows.extend(rows)
        observations.append(dict(page=page, total_reported=total, parsed_count=len(rows), **obs))
        print(query_id, page, len(allrows), "/", expected, flush=True)
        page += 1
        assert page <= 1000
        if expected == 0:
            break
    assert len(allrows) == expected, ("retrieved vs reported", len(allrows), expected)
    assert len({r["source_seq_no"] for r in allrows}) == expected, "duplicate seq across pages"
    out = ROOT / (query_id + ".csv")
    if allrows:
        with out.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(allrows[0]))
            writer.writeheader()
            writer.writerows(allrows)
    (ROOT / (query_id + "_manifest.json")).write_text(json.dumps(dict(
        query_id=query_id, official_entrypoint="https://www.nonghyup.com/main/psniMain.do",
        official_map=BASE, endpoint=URL, parameters=params,
        reported_total=expected, collected_rows=len(allrows), unique_seq_ids=len({r["source_seq_no"] for r in allrows}),
        complete_for_this_query=True,
        scope_limit="Complete paginated official-map query, not independently confirmed real-world census. Current listing does not establish presence at August 2026 baseline.",
        pages=observations,
    ), ensure_ascii=False, indent=2))
    return allrows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["jeonbuk", "bounds"])
    args = ap.parse_args()
    params = dict(tab="1", search_type="2", search_classify="3", sido="전북특별자치도", sigungu="", search_word="", list_tab="")
    if args.mode == "jeonbuk":
        collect("nh_coops_jeonbuk", params)
    else:
        params.update(search_type="1", search_classify="1", sido="", lb_x="126000000", lb_y="35100000", rt_x="128100000", rt_y="36350000")
        collect("nh_branches_context_bbox", params)
