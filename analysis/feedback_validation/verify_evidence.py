"""Check frozen public-source evidence and sensitivity input/summary consistency."""
import csv
import hashlib
import html
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main():
    sources = json.loads((HERE / "source_manifest.json").read_text())
    for source in sources:
        path = HERE / source["file"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"], path
    audit = rows(HERE / "nh_coop_row_audit.csv")
    assert len(audit) == len({row["outlet_id"] for row in audit}) == 334
    for row in audit:
        raw = (HERE / row["source_snapshot_file"]).read_text()
        branch_id = row["outlet_id"].removeprefix("NHMAP-")
        match = re.search(r'id="td_bussiness_' + re.escape(branch_id) + r'">(.*?)</td>', raw, re.S)
        assert match is not None, row["outlet_id"]
        service = html.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip() or "not_recorded"
        assert service == row["specific_financial_service_listed"], row["outlet_id"]
        assert row["individual_current_operation_verified"] == "N"
    counts = Counter(row["specific_financial_service_listed"] for row in audit)
    assert counts == {"not_recorded": 271, "외환": 61, "대여금고": 2}, counts
    original = {row["outlet_id"]: row for row in rows(ROOT / "analysis/theory_validation/inputs/outlets_expanded.csv")}
    summaries = {row["scenario"]: row for row in json.loads((HERE / "sensitivity_spatial_summary.json").read_text())}
    for stem, scenario, excluded in [
        ("exclude_no_service_tag", "exclude_no_service_tag_271", {row["outlet_id"] for row in audit if row["specific_financial_service_listed"] == "not_recorded"}),
        ("exclude_jeonbuk_coops", "exclude_all_jeonbuk_coops_334", {row["outlet_id"] for row in audit}),
    ]:
        pool = {row["outlet_id"]: row for row in rows(HERE / f"{stem}_outlets.csv")}
        assert set(original) - set(pool) == excluded
        assert all(row == original[key] for key, row in pool.items()), stem
        summary = summaries[scenario]
        assert sum(row["finance_open"] == "Y" for row in pool.values()) == summary["eligible_outlets"]
        access = rows(HERE / f"{stem}_spatial/access_internal.csv")
        eligible = {row["code"] for row in access if row["routing_category"] in ("P1", "P2")}
        assert len(eligible) == summary["candidate_targets"]
        route = json.loads((HERE / f"{stem}_routes/jeonbuk_route_scenario.json").read_text())
        targets = {row["target_id"] for zone in route["engine_input"]["zones"] for row in zone["engine_input"]["targets"]}
        assert targets == eligible, stem
    print(f"PASS: {len(sources)} public-source hashes, 334 service fields, and both exclusion input/target sets")


if __name__ == "__main__":
    main()
