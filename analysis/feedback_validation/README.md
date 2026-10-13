# Report feedback evidence — 2026-10-13

The main report remains the conditional expanded-outlet scenario. It is not a census of verified currently operating full-service branches.

## Reader-ready files

- `feedback_evidence.json`: reconciled claims, source dates, contradictions, assumptions, sensitivity and limits.
- `sensitivity_reader_summary.csv`: three comparable operating scenarios for the report table.
- `nh_coop_row_audit.csv`: all 334 newly added Jeonbuk coops, service-field evidence, uncertainty and public branch-detail links.
- `source_manifest.json` and `source_snapshots/`: checked public sources with hashes; 78 original official query pages underpin all 334 service-field values.
- `sensitivity_admin_changes.csv`: changes in administrative-area distance and category.
- `sensitivity_route_results.json`: full route replay results under the same published 15-day allocation.
- `verification.json`: original-result parity and all nine route replay checks.

## Findings for the writer

| Scenario | Eligible outlets | Target areas | Model-covered areas | Model distance |
|---|---:|---:|---:|---:|
| All official-listed additions retained | 1,347 | 54 | 50 | 1,003.716 km |
| Exclude 271 Jeonbuk coops with blank service field | 1,076 | 68 | 58 | 1,063.647 km |
| Exclude all 334 added Jeonbuk coops | 1,013 | 70 | 58 | 1,057.792 km |

The 63 other coops explicitly list a specific financial service: foreign exchange at 61 and safe-deposit boxes at 2. This supports a reported specific financial service, not all banking functions, current opening hours, or availability at the August baseline. Blank service fields do not establish that an outlet is nonfinancial. The 271-row case is an uncertainty test; the 334-row case is a broader conservative bound. Targets differ between scenarios, so the cross-scenario distance totals must not be advertised as efficiency gains.

The national NH map lists **전주농협 모악공판장지점** at 천잠로 22. The current local NH office page lists **모악지점** at 천잠로 28 and **공판장** at 천잠로 22. The reason and timing of the difference are not established. Do not silently replace the historical coordinate or mark it operationally verified.

Removing both the 모악 row and **논산계룡농협 하나로마트** leaves the 54-target set unchanged, but 삼천3동's distance changes from 4.0615 to 4.2083 km. It remains in the 3–5 km group. That two-row diagnostic does not justify calling all numerical results unchanged.

Suggested report wording:

> 추가한 전북 농·축협 334곳은 공식 영업점 목록과 대조했습니다. 이 중 63곳은 구체적인 취급업무가 표시되어 있습니다. 외환 61곳과 대여금고 2곳이며, 나머지 271곳은 업무 표시가 비어 있습니다. 업무 표시가 없는 곳을 금융업무를 하지 않는 곳으로 단정하지 않고, 이 271곳을 제외한 경우도 같은 운영조건으로 다시 계산했습니다. 방문 대상 지역은 54곳에서 68곳으로 늘었고, 제안 경로가 포함하는 지역은 50곳에서 58곳으로 바뀌었습니다. 따라서 실제 운영 전에는 해당 지점의 금융업무와 영업 여부를 확인하고 방문 대상을 확정해야 합니다.

> 이동거리 9.08% 감소는 같은 50개 지역을 방문하는 두 경로를 비교한 결과입니다. 차량 3대가 5일 동안 운영하고 하루 최대 4곳에서 45분씩 서비스하는 조건을 적용했습니다. 금융기관이 먼 지역을 먼저 고른 뒤 가까운 곳부터 방문하는 비교 경로는 1,103.950 km, 제안 경로는 1,003.716 km입니다. 실제 운행 실적은 아닙니다.

## Reproduction and verification

### Offline checks for the published snapshot

```sh
python3 analysis/feedback_validation/compare_sensitivity.py --check
python3 analysis/feedback_validation/verify_evidence.py
```

These read-only checks recompute all nine routing results from the retained matrices, verify
source hashes and all 334 archived service fields, and reconcile exclusions with the spatial
and routing target sets. They run inside `bash verify_offline.sh`. Runtime measurements are
excluded from deterministic comparison. The commands below rebuild distances and matrices
and additionally require the original boundary and common OSM PBF.


No production source or frozen original data was changed. Exclusion CSVs retain all other rows and fields. Existing `run_pool_attribution.py` recomputes distances using the hash-checked common graph. Existing `build_route_experiment.py` rebuilds candidate/depot selections and matrices. `compare_sensitivity.py` calls the unchanged comparison functions with the published allocation frozen (완주군 2 days, every other zone 1 day).

```sh
.venv/bin/python analysis/theory_validation/spatial/run_pool_attribution.py --reference-dir analysis/theory_validation/spatial/results --outlets analysis/feedback_validation/exclude_no_service_tag_outlets.csv --output-dir analysis/feedback_validation/exclude_no_service_tag_spatial
.venv/bin/python analysis/theory_validation/spatial/build_route_experiment.py --pbf analysis/theory_validation/inputs/south-korea-261011.osm.pbf --boundaries analysis/theory_validation/inputs/hjd2026.geojson --access analysis/feedback_validation/exclude_no_service_tag_spatial/access_internal.csv --outlets analysis/feedback_validation/exclude_no_service_tag_outlets.csv --output-dir analysis/feedback_validation/exclude_no_service_tag_routes --analysis-date 2026-10-13
.venv/bin/python analysis/feedback_validation/compare_sensitivity.py
```

The all-334 and two-flag spatial runs use the corresponding exclusion CSVs and directories. Original published main results match exactly on coverage, totals, allocation and unvisited targets. Nine replayed method/scenario combinations have zero constraint violations. All 334 parsed service fields match the retained official HTML. These are model/source checks, not field validation.

The same depot selection rule is retained, but actual depot locations change in five zones for the 271-row case and four zones for the 334-row case. This is intentional recomputation after targets change. No old August road result is used as a pure NH sensitivity result.

## Public entry points

- [NH official map](https://nonghyup.ttmap.co.kr/main.jsp)
- [모악공판장지점 national-map detail](https://nonghyup.ttmap.co.kr/print_2017.jsp?seq_no=61024)
- [Jeonju NH office list](https://jjnh.nonghyup.com/jjnh/100150/subview.do)
- [논산계룡농협 하나로마트 detail](https://nonghyup.ttmap.co.kr/print_2017.jsp?seq_no=60731)

The print pages omit service-field metadata. For the 63/271 split, use the attached original query snapshots and row audit, rather than claiming the print page itself shows those services.
