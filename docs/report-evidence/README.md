# 현재 결과보고서의 근거 자료

2026-10-14에 보고서와 GitHub를 동기화했다. 분석 자료의 기준일을 새로 바꾸거나 현장 운영을 확인한 것은 아니다.

| 보고서 항목 | 자료 |
|---|---|
| 접점 643→1,347, 대상 70→54 | [243개 지역 비교표](01_접점과_대상비교.csv), [접점 집계](../../analysis/theory_validation/inputs/outlet_expansion_audit.json) |
| 같은 50곳 거리 9.08% 감소 | [경로 비교 요약](../../analysis/theory_validation/comparison/final_expanded_input/report_evidence.json), [상세 결과](../../analysis/theory_validation/comparison/final_expanded_input/comparison_results.json) |
| 금융업무 확인 상태와 271·334곳 제외 | [설명과 재현](../../analysis/feedback_validation/README.md), [지점별 확인](../../analysis/feedback_validation/nh_coop_row_audit.csv), [민감도 요약](../../analysis/feedback_validation/sensitivity_reader_summary.csv) |
| 공식 조회 기록 | [출처·해시](../../analysis/feedback_validation/source_manifest.json), [조회 당시 원문](../../analysis/feedback_validation/source_snapshots/) |
| 고창군 방문 순서·시간표 | [시간표](04_동선예시.csv), [계산 조건](04_동선예시_조건.json) |
| 공통 도로망·경계 확인 | [입력 자료 기록](../../analysis/theory_validation/inputs/input_manifest.json) |
| 기준 위치·거리 기준 비교 | [공간 검증 결과](../../analysis/theory_validation/spatial/results/summary.json), [거리 기준 민감도](../../analysis/theory_validation/spatial/results/threshold_sensitivity.csv) |
| 대시보드 | [화면 파일](../demo-jeonbuk/), [검증 범위](../DASHBOARD_VALIDATION.md), [현재본 동작 기록](07_현재본_동작확인.json), [2026-10-13 첨부본 기록](06_대시보드_동작확인.json) |

기본안은 50/54곳·1,003.716km다. 하루 상한을 3곳으로 바꾸고 지역 배정도 다시 계산하면
43/54곳·912.448km다. 고창군 73.594km·13:50 복귀는 기본안의 고정 예시다.
업무 표시가 없는 지점을 제외한 민감도 분석은 대상이 달라지므로 9.08% 비교와 합치지 않는다.

과거 제출의 57/69곳은 다른 입력의 결과다. 현재 결과와 구분해 `data/processed/`와
`result/reports/`에 보존했다. 실제 금융업무·영업시간·장소 승인·실차 운행은 미검증이다.
