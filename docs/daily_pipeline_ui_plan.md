# Daily Pipeline UI Plan

## 1. 목적

`Leader_Lab`의 장 종료 후 데이터 갱신 작업을 UI 기반으로 반자동화한다.

매일 20:00 이후 반드시 관리해야 할 데이터는 다음 3종이다.

1. 1516 성과검증 결과
2. 일봉 캔들
3. 5분봉 캔들

이 3개 데이터가 모두 안정적으로 갱신되어야 이후 LeaderScore 분석, 백테스트, 시뮬레이션, 실전 후보 선별 로직을 신뢰할 수 있다.

핵심 원칙:

- 중간 일자가 빠져도 기간 재실행으로 복구 가능해야 한다.
- 이미 있는 데이터는 중복 생성하지 않고 UPDATE 또는 SKIP되어야 한다.
- 없는 데이터는 INSERT되어야 한다.
- UI에서 작업 상태, 누락 일자, DB 반영 결과, 실패 사유가 보여야 한다.
- 향후 분석/백테스트/시뮬레이션 기능은 탭 단위로 확장한다.

---

## 2. UI 전체 구조

권장 앱 이름:

`LeaderLab.UI`

초기 구현은 Python 기반 UI 또는 WinForms 중 하나를 선택할 수 있다.

현재 프로젝트의 자동화/데이터 파이프라인이 Python으로 구현되어 있으므로 1차 UI는 Python 기반이 효율적이다. 단, 장기적으로 VB.NET 실전 매매 시스템과 결합할 경우 WinForms 버전으로 이식 가능하도록 화면/기능 경계를 명확히 둔다.

초기 탭 구조:

```text
LeaderLab Dashboard
├── 1. Daily Update
├── 2. 1516 Collector
├── 3. Candle Cache
├── 4. Data Quality
├── 5. Baseline / LeaderScore
├── 6. Backtest / Simulation
├── 7. Reports
└── 8. Settings / Logs
```

---

## 3. Tab 1: Daily Update

### 목적

매일 20:00 이후 실행할 전체 데이터 갱신 상태를 한 화면에서 관리한다.

### 화면 구성

상단:

- 기준일 선택: `DatePicker`
- 기간 선택: `StartDate`, `EndDate`
- 기본 시간: `09:05`
- 실행 모드:
  - 단일일자
  - 기간복구
  - 전체검증
- 버튼:
  - `오늘 업데이트`
  - `기간 업데이트`
  - `누락일자 검색`
  - `전체 상태 점검`

중앙 상태 그리드:

| Date | 1516 | Daily | Minute5 | Feature | Score | Status | Last Run | Message |
|---|---|---|---|---|---|---|---|---|
| 2026-05-06 | OK | OK | OK | Pending | Pending | Partial | ... | ... |

하단 로그:

- 실행 단계별 로그
- 실패 사유
- 저장/업데이트 건수
- 재시도 대상

### 버튼별 동작

#### 오늘 업데이트

1. 오늘이 장 종료 후인지 확인한다.
2. 1516 데이터 저장 상태를 확인한다.
3. 1516 미완료이면 1516 탭으로 안내한다.
4. 일봉 업데이트를 실행한다.
5. 5분봉 업데이트를 실행한다.
6. feature 생성 대기 상태로 표시한다.

#### 기간 업데이트

1. StartDate~EndDate 범위를 생성한다.
2. 날짜별 1516 존재 여부 확인
3. 날짜별 일봉 존재 여부 확인
4. 날짜별 5분봉 coverage 확인
5. 부족분만 다운로드/업데이트
6. 전체 결과 요약 표시

#### 누락일자 검색

다음 조건을 기준으로 누락 일자를 계산한다.

- `performance_result`에 해당일 1516 row가 없는 날짜
- `daily_candles`에 해당일 일봉이 부족한 종목
- `minute5_candles`의 해당일 09:00~15:30 count가 부족한 종목

---

## 4. Tab 2: 1516 Collector

### 목적

키움 HTS 1516 성과검증 화면을 이용해 특정 일자의 성과검증 데이터를 MySQL `stock_info.performance_result`에 저장한다.

### 사용자 흐름

1. 사용자가 UI에서 `1516 Collector` 탭을 연다.
2. UI가 안내 메시지를 표시한다.

```text
1. 키움 HTS에서 [1516] 성과검증(조건식) 화면을 여세요.
2. 조건식과 성과검증 기준을 원하는 상태로 세팅하세요.
3. 검색 시간을 09:05로 맞추세요.
4. 아래 날짜를 선택하고 [성과검증 저장]을 누르세요.
```

3. 사용자가 날짜를 선택한다.
4. `성과검증 저장` 버튼을 누른다.
5. UI 자동화 로직이 다음을 수행한다.

### 내부 처리

1. 1516 창 탐색
2. 날짜 입력
3. 실제 날짜 입력 완료 검증
4. 검색 버튼 클릭
5. 결과 로딩 대기
6. 결과 리스트 우클릭 복사
7. 클립보드 파싱
8. raw hash 계산
9. 중복 raw 여부 확인
10. MySQL `performance_result` UPSERT
11. rank/label 재계산
12. 결과 표시

### 필수 방어 로직

- 날짜 입력 실패 시 저장 금지
- 화면 날짜와 요청 날짜 불일치 시 저장 금지
- 클립보드 비어 있음 저장 금지
- raw hash가 기존과 동일하면 skip 또는 update 확인
- 파일명 날짜와 실제 검색 날짜 불일치 저장 금지
- 동일 날짜 반복 수집 시 중복 INSERT 금지

### 상태 출력

| Item | Value |
|---|---|
| Request Date | 2026-05-06 |
| Screen Date | 2026-05-06 |
| Search Time | 09:05 |
| Clipboard Length | 2152 |
| Parsed Rows | 29 |
| Inserted | 0 |
| Updated | 29 |
| Skipped | 0 |
| Raw Hash | ... |
| Status | OK |

---

## 5. Tab 3: Candle Cache

### 목적

일봉과 5분봉 캐시를 관리한다.

### 하위 섹션

1. Daily Candle Update
2. Minute5 Full Period Cache
3. Minute5 Daily Incremental Update
4. Cache Coverage Verify

### 5.1 Daily Candle Update

입력:

- StartDate
- EndDate
- 대상:
  - performance_result 등장 종목만
  - 전체 stock_base_info 종목

처리:

- MySQL `stock_info.daily_candles`에 이미 있으면 UPDATE
- 없으면 INSERT
- 장 종료 후 데이터만 반영

### 5.2 Minute5 Full Period Cache

초기 구축용.

입력:

- StartDate: 2026-01-05
- EndDate: 2026-05-06
- Tick: 5
- Target: performance_result distinct code

처리:

- code별로 server32 period downloader 실행
- `minute5_candles`에 UPSERT
- 전체 기간 coverage 리포트 생성

### 5.3 Minute5 Daily Incremental Update

매일 갱신용.

입력:

- TargetDate
- IncludePrevFromTime: 14:00:00

처리:

- TargetDate 전일 14:00부터 TargetDate 15:30까지 다운로드
- `minute5_candles`에 UPSERT
- 해당일 performance_result 등장 종목에 대해 coverage 확인

### 5.4 Cache Coverage Verify

표시 항목:

| Metric | Value |
|---|---:|
| performance rows | 2893 |
| minute5 codes | ... |
| enough rows | ... |
| partial rows | ... |
| missing rows | ... |
| first candle | ... |
| last candle | ... |

worst coverage sample도 grid로 표시한다.

---

## 6. Tab 4: Data Quality

### 목적

데이터 품질 문제를 조기에 발견한다.

검증 항목:

1. `performance_result` 날짜별 row 수
2. 미매칭 종목 수
3. `actual_rank_by_max_ret` NULL 여부
4. `label_10` 비율
5. 일봉 누락 종목
6. 5분봉 누락 종목
7. 5분봉 장중 count 이상치
8. 중복 raw hash
9. 동일 날짜 다른 raw 결과 존재 여부

표시:

- Summary cards
- Date grid
- Missing code grid
- Exception log

---

## 7. Tab 5: Baseline / LeaderScore

### 목적

기본 변수와 LeaderScore 버전의 순위 적중률을 비교한다.

초기 baseline:

- ret_1m
- ret_3m
- search_volume
- oracle max_ret

지표:

- Top1Capture
- Top5Hit
- Top10Hit
- NDCG@5
- NDCG@10
- Lift@5
- Lift@10
- ScoreTop5 Label10Rate

표시 예:

| Version | Top1Capture | Top5Hit | Top10Hit | Label10Rate | NDCG@5 | Lift@5 | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| baseline_ret_1m | ... | ... | ... | ... | ... | ... | baseline |
| baseline_volume | ... | ... | ... | ... | ... | ... | baseline |
| LeaderScore_v1 | ... | ... | ... | ... | ... | ... | candidate |

---

## 8. Tab 6: Backtest / Simulation

### 목적

향후 점수 상위 N종목 매수 시뮬레이션, 고정 매도정책, 목표수익률/손절/트레일링 검증 기능을 탭으로 추가한다.

초기 기능:

- 날짜 선택
- Score version 선택
- TopN 선택
- 차트 구간 선택
- 매수 시점 선택: 09:05 / 기준봉 돌파 / 재돌파
- 매도 정책 선택: 고정 목표 / max_ret oracle / SuperTrend / JMA / 시간청산

---

## 9. Tab 7: Reports

### 목적

실행 결과와 분석 리포트를 UI에서 바로 확인한다.

파일 목록:

- rank_match_summary.md
- baseline_*_summary.md
- score_version_leaderboard.csv
- walkforward_report.md
- failure_analysis.md
- PermanentLeaderScore_v1.yaml

기능:

- report 열기
- CSV grid 보기
- YAML 보기
- 결과 폴더 열기

---

## 10. Tab 8: Settings / Logs

### 설정 항목

- MySQL 연결 정보는 `.env` 사용
- SQLite 1516 경로
- server32 base URL
- report root
- log root
- 기본 search time: 09:05
- 기본 tick: 5
- daily update time: 20:00

### 로그

- pipeline run log
- step별 성공/실패
- traceback
- warning
- raw copy log

---

## 11. Pipeline 상태 테이블 계획

UI가 매일 상태를 추적하려면 별도 상태 테이블이 필요하다.

### `stock_info.leader_pipeline_run`

컬럼:

- id
- run_type
- start_date
- end_date
- target_date
- status
- started_at
- finished_at
- message

### `stock_info.leader_pipeline_day_status`

컬럼:

- trade_date
- has_1516
- has_daily
- has_minute5
- has_features
- has_score
- performance_count
- minute5_code_count
- minute5_missing_count
- daily_missing_count
- last_checked_at
- status
- message

---

## 12. Daily Update 실행 순서

단일일자 기준:

```text
1. 사용자가 1516 화면을 준비한다.
2. UI에서 TargetDate 선택 후 [성과검증 저장]
3. performance_result UPSERT
4. daily_candles 업데이트
5. minute5_candles 업데이트
   - TargetDate 전일 14:00 ~ TargetDate 15:30
6. data quality check
7. feature build 대기 또는 실행
8. LeaderScore 평가 대기 또는 실행
```

기간복구 기준:

```text
1. StartDate~EndDate 선택
2. 날짜별 상태 점검
3. 1516 없는 날짜는 사용자에게 수집 필요 표시
4. daily/minute5 부족분은 자동 보충
5. 이미 있는 데이터는 update/skip
6. 최종 coverage 리포트 생성
```

---

## 13. 구현 우선순위

### UI Phase 1

- Daily Update 탭
- Settings 탭
- Logs 탭
- Data Quality 탭

### UI Phase 2

- 1516 Collector 탭
- Candle Cache 탭

### UI Phase 3

- Baseline / LeaderScore 탭
- Reports 탭

### UI Phase 4

- Backtest / Simulation 탭

---

## 14. 구현 원칙

- UI는 Python 모듈을 직접 호출하거나 subprocess로 실행한다.
- 모든 실행은 `.env` 기준으로 동작한다.
- DB 쓰기는 전부 UPSERT 기반이다.
- 일자 누락은 재실행으로 복구한다.
- 중복 저장은 허용하지 않는다.
- 화면 자동화 실패 시 DB 저장하지 않는다.
- 장 종료 후 20:00 이후 실행을 기본으로 한다.
- 추후 self-hosted runner나 Windows 작업 스케줄러에서 자동 실행 가능하도록 CLI와 UI를 분리한다.
