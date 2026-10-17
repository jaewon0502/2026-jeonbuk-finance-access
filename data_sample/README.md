# 데이터 샘플 안내

샘플은 컬럼과 값을 살펴보는 미리보기이며, 실제 계산에는 저장소에 포함된 전체 입력을 쓴다.
상위 20행은 임의 표본이나 통계적 대표 표본이 아니다.

| 위치 | 원본과 용도 |
|---|---|
| [current/access_road.sample.csv](current/access_road.sample.csv) | 현재 `analysis/theory_validation/spatial/route_inputs/access_road.csv` 243행 중 앞 20행 |
| [current/outlets_validated.sample.csv](current/outlets_validated.sample.csv) | 현재 `analysis/theory_validation/spatial/route_inputs/outlets_validated.csv` 1,385행 중 앞 20행 |
| 이 폴더의 기존 `*.sample.csv` | 8월 기준 `data/processed/` CSV의 앞 20행 이하. 현재 결과와 구분 |
| [source_manifest.json](source_manifest.json) | 8월 원천별 URL·기준일·라이선스·해시 기록 |
| [데이터_설명서.md](데이터_설명서.md) | 현재·과거 입력 경로, 컬럼·단위, 해석과 재현 범위 |

현재 원천 기록은 `analysis/theory_validation/inputs/input_manifest.json`,
`analysis/theory_validation/outlets/`의 매니페스트,
`analysis/feedback_validation/source_manifest.json`에 나누어 보관한다.

`bash verify_offline.sh`는 전체 저장 입력·행렬로 실행한다. 샘플 CSV로 입력을 바꾸면
원래 수치나 무결성 검사를 재현할 수 없다. 대용량 도로망·경계 등 원본은 포함하지 않는다.
