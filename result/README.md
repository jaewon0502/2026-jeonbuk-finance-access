# result — 분석 결과

현재 보고서·대시보드는 분석 접점 1,347곳, 경로 대상 54곳, 기본 방문 50곳을 사용한다.
현재 결과는 아래 원본 위치에서 확인한다. 이 폴더의 `reports/`와 `outputs/`는 8월 결과다.

## 현재 결과 원본

| 결과 | 파일 |
|---|---|
| 경로 방법·조건별 비교 21행 | [comparison_summary.csv](../analysis/theory_validation/comparison/final_expanded_input/comparison_summary.csv) |
| 선택 대상·방문 순서·제약 검사 | [comparison_results.json](../analysis/theory_validation/comparison/final_expanded_input/comparison_results.json) |
| 보고서 수치와 비교 조건 | [report_evidence.json](../analysis/theory_validation/comparison/final_expanded_input/report_evidence.json) |
| 금융업무 표시 민감도 | [sensitivity_reader_summary.csv](../analysis/feedback_validation/sensitivity_reader_summary.csv) |
| 공식 조회 근거와 해석 | [보완 분석 README](../analysis/feedback_validation/README.md) |
| 고창군 동선·시간표와 보고서 표 | [report-evidence/README.md](../docs/report-evidence/README.md) |

기본안은 차량 3대·5일·하루 최대 4곳·장소당 45분 조건에서 50/54곳을 방문하고,
모형 이동거리는 1,003.716km다. 9.08% 감소는 **같은 50곳**을 방문하는 우선순위 최근접
방법의 1,103.950km와 비교한 값이다. 실제 운행 실적이나 주민 수혜 증가율이 아니다.

재계산은 [실행환경 설명서 3절](../docs/실행환경설명서.md)을 따른다.
현재 결과를 이 폴더에 중복 복사하지 않고 원본으로 연결해 버전 혼동을 줄였다.

## reports/ — 과거 결과 문서

| 파일 | 내용 |
|---|---|
| `quality_report.md` | 데이터 품질·검증 항목과 남은 한계 |
| `coverage_by_sigungu.md` | 시군별 접근성 커버리지 |
| `typology_evaluation.md` | 군집 후보 `k=2..5` 채택·기각 근거 |
| `scenario_evidence.md` | 임계값·방문상한·속도·서비스시간 민감도 감사 |

## outputs/ — 과거 산출물 사본

| 파일 | 내용 |
|---|---|
| `access_jeonbuk.csv` | 행정동 243개 직선거리 접근성 |
| `access_road.csv` | 행정동 243개 OSM 도로거리 접근성 |
| `access_typology.csv` | 행정동 243개 취약유형 라벨 |
| `coverage_by_sigungu.csv` | 시군별 집계 |
| `outlets_validated.csv` | 검증 완료 금융 접점 681건 |
| `ecos_jeonbuk_loans_202508_202605.csv` | ECOS 전북 원화대출금 공개 샘플 10개월 |
| `jeonbuk_route_scenario.json` | 차량 3대·5일 순회 배정 결과 |
| `scenario_evidence.json` | 민감도 감사 원자료 |
| `typology_evaluation.json` | 군집 채택 게이트 지표 |

이 파일들은 `data/processed/`에서 재생성되는 산출물의 사본이다.
`bash verify_offline.sh`를 돌리면 `data/processed/` 쪽이 다시 계산되며,
이 폴더의 사본을 자동 갱신하지는 않는다. 현재 결과는 위 원본 파일을 사용한다.

## 시각화 결과

대시보드와 지도는 `docs/demo-jeonbuk/index.html`을 브라우저로 열면 된다.
계산 수식·군집·경로 이론 설명은 `docs/demo-jeonbuk/methodology.html`에 있다.
