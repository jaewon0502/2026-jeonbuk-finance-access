# 전북 금융 사각지대 진단과 찾아가는 은행 최적 동선 설계 — 코드·분석파일

팀명: **금방**(금융 방방곡곡) · 대표자: 정다은

2026 제4회 전북 청년 AI·빅데이터 경진대회 · **현안 해결 구현 분야** 제출물.

전북 14개 시군 243개 행정동의 금융 접근성을 공개 데이터로 진단하고, 차량 수·운영일·
방문 상한이 제한된 조건에서 찾아가는 금융 서비스의 시군별 순회 거점과 방문 순서를
제안한다.

- 대회 필수 데이터: 한국은행 ECOS `141Y003` 예금은행 지역별 대출금(말잔)

## 현재 보고서와 대시보드 기준

현재 대시보드는 `analysis/theory_validation`의 검증 자료를 읽는다. 기존 제출 자료는
`data/processed`에 그대로 남겨 두었다. 2026-10-14에 보고서의 추가 분석과 화면 보완분을
동기화했다. 접점·도로망 분석 기준일은 2026-10-12이며 지점 업무 표시 확인은 2026-10-13 기록이다.

| 항목 | 현재 화면과 최종 보고서 기준 |
|---|---|
| 금융접점 | 목록 1,385곳 중 분석가용 1,347곳 |
| 도로거리 품질 | 243개 행정동 중 주 지표 240곳과 품질유보 3곳 |
| 경로대상 | 3km 초과 55곳 중 품질유보 1곳을 제외한 54곳 |
| 기본조건 | 54곳 중 50곳 방문 · P1 21곳 · P2 29곳 · 1,003.716km |
| 동일 대상 비교 | 우선순위 최근접 방법과 같은 50곳을 방문하며 이동거리 9.08% 감소 |

종합 화면의 보고서 비교는 고정 결과다. 운영 시나리오는 선택한 시군의 경로와 운영일 배정을
함께 다시 계산한다. 최대 방문 수를 바꾸면 고정 배정 비교와 결과가 달라질 수 있다.
군집분석은 보완 자료로 다시 적합하지 않았으므로 현재 판정에 쓰지 않는다.

| 접점 포함 조건 | 분석 접점 | 대상 | 방문 | 모형 이동거리 |
|---|---:|---:|---:|---:|
| 공식 목록 모두 포함 | 1,347 | 54 | 50 | 1,003.716km |
| 업무 표시 없는 전북 농·축협 271곳 제외 | 1,076 | 68 | 58 | 1,063.647km |
| 추가 전북 농·축협 334곳 모두 제외 | 1,013 | 70 | 58 | 1,057.792km |

업무 표시가 없다는 사실은 금융업무를 하지 않는다는 뜻이 아니다. 대상과 방문 장소가
다르므로 위 세 조건 사이의 거리 차이를 효율 개선율로 해석하지 않는다.
[지점별 확인·민감도 분석과 재현 방법](analysis/feedback_validation/README.md),
[보고서 표·고창군 동선·화면 확인 자료](docs/report-evidence/README.md)를 함께 제공한다.
종합 화면에는 대상 54곳·방문 50곳·미방문 4곳과 고창군 기본 동선 지도·시간표를 표시한다.

```bash
python3 src/build_dashboard_data.py
bash verify_offline.sh
python3 -m http.server 8000 --bind 127.0.0.1 --directory docs/demo-jeonbuk
```

화면 자료 재생성은 저장된 검증 입력의 SHA-256을 확인한다. 지도 전체 재생성 명령은
`python3 src/build_map_visualization.py`이며 제외된 도로망·경계 원본이 필요하다.
브라우저 열람과 일반 검증에는 생성된 지도 파일을 쓴다. `--legacy`는 제출 당시 자료를
명시적으로 재생성할 때만 사용한다. 현재 설계와 검증 범위는
[`docs/DASHBOARD_VALIDATION.md`](docs/DASHBOARD_VALIDATION.md)에 정리했다.

---

## 1. 빠른 실행 (5분)

원본 대용량 데이터나 API 키 없이, 이 압축파일만으로 전체 검증이 돌아간다.

```bash
cd 금방_전북금융사각지대진단과찾아가는은행최적동선설계_코드분석파일
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python3 -m pip install -r requirements.txt
bash verify_offline.sh             # 문법·테스트·산출물 재생성·무결성 검증
```

마지막 줄에 `PASS (offline)` 이 찍히면 정상이다.

대시보드는 서버 없이 파일을 그대로 열면 된다.

```bash
open docs/demo-jeonbuk/index.html          # Windows: start docs\demo-jeonbuk\index.html
```

`verify_offline.sh`가 하는 일은 다섯 단계다.

| 단계 | 내용 |
|---|---|
| 1 | `src/*.py` 전체 컴파일 |
| 2 | 경로 엔진 단위 테스트 (`tests/`) |
| 3 | 유형·순회·민감도·대시보드 산출물 재생성 + 브라우저 엔진 테스트 |
| 4 | 좌표·경계·조인 무결성 + 금융업무 민감도 9개 결과 재계산 + 공식 조회 근거 대조 |
| 5 | 가공 데이터 행 수와 JSON 파싱 확인 |

## 2. 실행 환경

| 항목 | 요구 |
|---|---|
| 운영체제 | macOS / Linux / Windows(WSL 권장) |
| Python | 3.11 이상 (개발·검증: 3.14.6) |
| Node.js | 20 이상 — 브라우저 시나리오 엔진 테스트용 (개발·검증: 26.4.0) |
| 브라우저 | Chrome·Safari·Edge 최신 (대시보드 열람) |
| 네트워크 | **불필요** — 위 검증은 전부 오프라인 |

자세한 내용은 [`docs/실행환경설명서.md`](docs/실행환경설명서.md) (PDF 판본: `docs/실행환경설명서.pdf`)를 따른다.

## 3. 필요 라이브러리

`requirements.txt` 세 개가 전부다. 나머지는 Python 표준 라이브러리만 쓴다.

```
osmium==4.3.1     OSM PBF 파싱 (원본 도로망 재구축 시에만 필요)
numpy==2.4.6      수치 연산
scipy==1.17.1     Ward 계층 군집
```

Node.js는 별도 패키지 설치 없이 내장 `node:test`만 쓴다.

## 4. 폴더 구성

```
금방_전북금융사각지대진단과찾아가는은행최적동선설계_코드분석파일/
├── README.md                  이 문서 — 실행 설명서
├── requirements.txt           필요 라이브러리
├── verify_offline.sh          제출 검증 (키·원본 없이 실행)
├── verify.sh                  API 키 포함 최소 검증
├── verify_source_lineage.sh   원본 보유 환경 전용 계보 검증
├── src/                       수집·정제·분석·경로·시각화 코드 (21개 모듈)
├── config/                    운영 가정·입력 범위 설정
├── tests/                     경로 엔진·유형화·대시보드 엔진 테스트
├── data/
│   ├── processed/             코드가 참조하는 실제 가공 데이터 (전량 포함)
│   └── source_manifest.json   원천별 URL·기준일·수집일·라이선스·SHA-256
├── data_sample/               가공 데이터 상위 20행 미리보기 + 데이터 설명서
├── result/
│   ├── reports/               분석 결과 리포트 4종 (Markdown)
│   └── outputs/               최종 산출 CSV·JSON 사본
└── docs/
    ├── 실행환경설명서.md
    ├── 제출_체크리스트.md
    ├── AI_USAGE.md            AI·바이브 코딩 활용 범위
    ├── THIRD_PARTY_NOTICES.md 오픈소스 출처·라이선스
    ├── DATASETS.md            데이터 목록·출처·재현 조건
    └── demo-jeonbuk/          대시보드·지도·방법론 화면
```

Jupyter 노트북은 두지 않았다. 수집부터 시각화까지 전 과정을 재실행 가능한
스크립트로 구성했고, `verify_offline.sh` 한 줄이 그 파이프라인을 그대로 돌린다.

## 5. 데이터 경로와 파일명

### 코드가 읽는 경로

모든 스크립트는 저장소 루트 기준 상대경로만 쓴다. 절대경로·사용자 홈 경로는 없다.

| 경로 | 내용 | 포함 여부 |
|---|---|---|
| `data/processed/` | 가공·검증 완료 데이터 28개 | **포함** — 그대로 실행 가능 |
| `data/raw/` | 원본 공개 데이터 | **미포함** — 용량(약 370MB)·재배포 조건 |
| `data/source_manifest.json` | 원천 URL·기준일·수집일·라이선스·SHA-256 | 포함 |
| `docs/demo-jeonbuk/data.js`, `map-data.js` | 대시보드 입력 번들 (재생성됨) | 포함 |

`data/raw/`가 없어도 `verify_offline.sh`는 전부 통과한다. 원본이 필요한 단계
(OSM 도로망 재구축, 원천 SHA-256 대조)는 `verify_source_lineage.sh`로 분리했다.

### 주요 파일

| 파일 | 행 수 | 내용 |
|---|---:|---|
| `data/processed/points_raw.csv` | 681 | 은행·우체국·신협·새마을금고 접점 원본 |
| `data/processed/outlets_validated.csv` | 681 | 좌표·경계 검증 완료 접점 |
| `data/processed/access_jeonbuk.csv` | 243 | 행정동별 직선거리 접근성 |
| `data/processed/access_road.csv` | 243 | 행정동별 OSM 도로거리 접근성 |
| `data/processed/access_typology.csv` | 243 | 취약유형 라벨 |
| `data/processed/venues_jeonbuk.csv` | 6,856 | 전북 14개 시군 공식 경로당 좌표화 |
| `data/processed/ecos_jeonbuk_loans_202508_202605.csv` | 10 | ECOS 전북 원화대출금 공개 샘플 |
| `data/processed/jeonbuk_route_scenario.json` | — | 차량 3대·5일 순회 배정 결과 |
| `data/processed/scenario_evidence.json` | — | 임계값·속도·서비스시간 민감도 감사 |

전체 원천 목록·수집 방식·라이선스는 [`docs/DATASETS.md`](docs/DATASETS.md),
기계판독 원장은 `data/source_manifest.json`을 따른다.

## 6. 현재 결과와 과거 제출 자료

현재 결과는 `analysis/theory_validation/`의 접점·대표점·경로 비교와
`analysis/feedback_validation/`의 금융업무 표시 민감도 분석이다. 현재 대시보드 기본안은
**50/54곳 방문, 1,003.716km**이며 동일한 50곳을 방문하는 비교안 대비 **9.08% 감소**다.

### 과거 제출 자료 보관

`result/reports/`의 네 문서는 2026년 8월 제출 당시 입력의 분석 기록이다.
아래 수치는 과거 입력의 결과이며 현재 보고서·대시보드 수치로 사용하지 않는다.

| 문서 | 내용 |
|---|---|
| `quality_report.md` | 데이터 품질·검증 항목과 남은 한계 |
| `coverage_by_sigungu.md` | 시군별 접근성 커버리지 |
| `typology_evaluation.md` | 군집 후보 `k=2..5` 채택·기각 근거 |
| `scenario_evidence.md` | 순회 시나리오 민감도 감사 |

과거 제출 당시 수치는 다음과 같다.

- 전북 243개 행정동 중 도로거리 3km 초과 **71개**, 이 중 품질 게이트 통과 **69개**를 경로 대상으로 사용
- 차량 3대·5일 기본안에서 **57/69곳** 방문. 최소안 1대 20곳, 확대안 5대 69곳
- 취약유형은 `k=2` 채택 (실루엣 0.686, 재표집 ARI 중앙 1.000, `log1p` 대안 ARI 0.779)

`57/69`는 **방문 대상 행정동 대표점 수**이지 주민 커버리지나 접근성 개선 인구가 아니다.
거리 결과는 행정동 대표점 하나에서 계산한 접근성 프록시이며, 주민 개인의 실제
이동거리로 해석하면 안 된다. 차고지·장소 사용승인·시간창이 확정되지 않아
대시보드는 `operational_ready=false`를 그대로 표시한다.

## 7. AI 활용 범위

[`docs/AI_USAGE.md`](docs/AI_USAGE.md)에 전문을 두었다. 요약하면,

- **탐색형 분석모델**: SciPy Ward 계층 군집으로 농촌 읍·면 155개의 취약유형을 탐색.
  실루엣·재표집 ARI·최소 군집 크기·전처리 민감도 게이트를 모두 통과한 후보만 공개한다.
- **생성형 AI 개발 보조**: Claude·Codex를 코드 초안, 검증 스크립트, 문서 정리,
  방법론 조사 보조에 사용했다. 줄 단위 생성 이력을 남기지 않았으므로 **저장소의 코드와
  문서 전체를 AI 보조 범위로 보수적으로 간주**한다.
- **쓰지 않은 범위**: 생성형 AI를 산출물 기능에 넣지 않았고, 순회 경로 계산은 동적계획법
  기반 운영최적화이지 AI 모델이 아니다. 개인 위험도 산출·금융상품 추천은 하지 않는다.

## 8. 오픈소스·외부 데이터 출처

[`docs/THIRD_PARTY_NOTICES.md`](docs/THIRD_PARTY_NOTICES.md)에 라이선스 전문 위치를 정리했다.
주요 항목은 OpenStreetMap(ODbL), SGIS 기반 행정동 경계 재배포본(CC BY 4.0),
Pretendard 글꼴(SIL OFL 1.1), NumPy·SciPy·PyOsmium(BSD/LGPL)이다.

## 9. 제출 기준 대응

`docs/제출_체크리스트.md`에 「코드·분석파일 제출 기준」의 확인 항목별 근거 파일을 정리했다.
