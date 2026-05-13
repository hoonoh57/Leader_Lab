# Leader_Lab TODO / Implementation Roadmap

## 0. 최상위 목표

`Leader_Lab`의 1차 목표는 오직 하나다.

```text
족집게 도사 만들기:
Score Top10 안에 실제 대장주/대박주 7개 이상 포함
```

모든 UI, DB, 수집기, 에이전트, 백테스트, 시뮬레이션, 리포트는 이 목표를 위해 존재한다.

핵심 검증식:

```text
분석 순위 Score Rank
=
눈으로 검증된 종목별 실제 최고수익률 Actual MaxRet Rank
```

현재 기준선:

```text
10개 중 2개 적중 = 현수준 / 최악 기준선
```

강력 통과 기준:

```text
10개 중 7개 이상 적중 = 족집게 도사 후보
```

---

## 1. 현재 연구 스택 위치

현재 연구 흐름은 아래 순서로 고정한다.

```text
Experiment Registry
→ Winner Pattern Discovery
→ Winner Feature Score v1
→ Time-Aware Winner Feature Score v2
→ SuperTrend Regime Discovery
→ Chart Consistency Gate  ← 현재 최우선
→ Good ST Segment Similarity
→ Regime-aware entry/exit strategy
→ Macro/news/sector/LLM overlay
```

현재는 `SuperTrend Regime Discovery` 결과가 생성된 상태이며, 다음 차례는 매수/매도 전략이 아니라 `Chart Consistency Gate`이다.

절대 바로 진입/매도전략으로 넘어가지 않는다.

먼저 아래 5가지를 확인한다.

```text
1. 차트가 09:00 이전 warmup 봉을 포함하는가
2. 09:00 기준선이 보이는가
3. ST Up / ST Down 선이 보이는가
4. DB에 저장된 ST 상승구간 음영이 ST Up 선과 일치하는가
5. 장초반 강한 상승구간이 warmup 부족 때문에 누락되지 않는가
```

관련 문서:

```text
docs/supertrend_chart_consistency_gate.md
```

최근 실행 기준:

```text
targets=2622
params=(7,1.5), (7,2.0), (10,2.0), (14,2.0)
warmup_bars=80
segments=25070
report=reports/supertrend_regime_discovery_dashboard.html
```

---


### Mandatory repository working rules

Before any future code, script, or document modification, read and follow:

```text
docs/workflow_server_editing_v1.md
docs/powershell_script_rule_v1.md
docs/pre_edit_reading_rule_v1.md
docs/todo_update_rule_v1.md
todo_list.md
latest task handoff document in docs/
```

Server-first editing remains mandatory. GitHub/server files are created or modified first. Local work is limited to pull, run the versioned script, and status verification.

PowerShell scripts must be Windows PowerShell 5.1 safe. Use ASCII-only ps1 source by default. If Korean text must be written by ps1, write it through UTF-8 Base64 decoding, not direct Korean string literals.
## 2. 구현 원칙

### 2.1 계획 기반 구현

앞으로 구현은 이 `todo_list.md` 순서대로 진행한다.

새 기능을 추가하기 전 반드시 확인한다.

```text
이 기능이 Hit@10, Label10Rate, PF/MDD 개선에 직접 기여하는가?
```

단, 현재 `Chart Consistency Gate`는 모든 후속 전략 실험의 데이터/화면 신뢰성을 결정하는 선행 관문이므로 최우선 예외로 둔다.

### 2.2 GitHub 작업 방식

GitHub 툴 사용 권한 요청을 줄이기 위해 다음 방식으로 진행한다.

```text
작은 파일 하나씩 즉흥 수정 금지
한 Phase 안의 관련 코드/DDL/스크립트/테스트를 한 번에 생성 또는 수정
로컬에서는 git pull 후 실행
실패 로그를 기반으로 다음 Phase 단위로 수정
```

즉, 앞으로는 다음 단위로 크게 묶어 작업한다.

```text
Phase 단위 구현
= SQL + Python modules + scripts + tests + docs 업데이트를 한 번에 처리
```

### 2.3 Core / Experiment 분리

불변 Core:

```text
DB schema
Data loader
Quality checker
Metric evaluator
Report generator
Experiment registry
Agent contract
Chart consistency validator
```

가변 Experiment:

```text
Feature set
Score weights
Filter threshold
Candidate universe
Holding horizon
Entry policy
Exit policy
Model type
Agent score usage
ST parameter
```

Core는 안정화하고, 실험은 설정/버전으로 바꾼다.

---

## 3. 현재 완료/진행 상태

### 완료

- [x] GitHub repo 기본 구조 일부 생성
- [x] `.gitignore`
- [x] `.env.example`
- [x] `requirements.txt`
- [x] MySQL `performance_result` DDL
- [x] MySQL `minute5_candles` DDL
- [x] SQLite 1516 -> MySQL `performance_result` 이관
- [x] `performance_result` 검증
- [x] TopK metric skeleton
- [x] baseline report skeleton
- [x] 구조화 문서 추가
  - `docs/north_star_metric.md`
  - `docs/wysiwyg_validation_principle.md`
  - `docs/contingency_flow_if_target_not_met.md`
  - `docs/sustainable_project_flowchart.md`
  - `docs/daily_pipeline_ui_plan.md`
  - `docs/custom_screener_architecture.md`
  - `docs/local_agent_score_supply_architecture.md`
  - `docs/server32_agent_operating_architecture.md`
  - `docs/supertrend_chart_consistency_gate.md`
- [x] SuperTrend Regime Discovery 결과 생성
  - `segments=25070`
  - `reports/supertrend_regime_discovery_dashboard.html`
- [x] Top Candidate Board v3.2 integration guide verified
  - docs/top_candidate_board_integration_v3_2.md
  - vbnet/TopCandidateBoardIntegrationGuide.vb
  - vbnet/frmTopCandidateBoard.vb
  - verification script: scripts/build_top_candidate_board_integration_v3_2.ps1
  - observed result: integration tokens OK, working tree clean
  - next step: SuperTrend Chart Consistency Gate
### 현재 최우선 진행 중

- [ ] SuperTrend Regime Discovery Dashboard에 선택 ST 파라미터 기준 ST Up / ST Down line 표시
- [ ] 09:00 기준선 표시
- [ ] warmup 영역 또는 Warmup OK/FAIL badge 표시
- [ ] DB segment shade와 ST Up line 정합성 검증
- [ ] Chart Consistency PASS/FAIL 카드 표시

### 기존 진행 중

- [ ] 874개 성과검증 대상 종목의 5분봉 기간 캐시 구축
- [ ] 5분봉 캐시 coverage 검증

---

## 4. 전체 구현 플로우

```mermaid
flowchart TD
    A[Data Foundation] --> B[Quality Gate]
    B --> C{Data usable?}
    C -- No --> C1[Fix ingestion / mapping / coverage]
    C1 --> A

    C -- Yes --> D[Label Definition]
    D --> E[Baseline Evaluation]
    E --> F[Feature Experiment]
    F --> G[Score / Screener Version]
    G --> H[Walk-forward Validation]
    H --> I{Hit@10 >= 7/10?}

    I -- Yes --> J[Strategy Simulation]
    J --> K{Portfolio return valid?}
    K -- Yes --> L[Permanent Candidate]
    K -- No --> K1[Exit / Holding / Position Redesign]
    K1 --> J

    I -- No --> M[Failure Analysis]
    M --> N{Failure type}
    N -- Data --> A
    N -- Label --> D
    N -- Feature --> F
    N -- Universe --> O[Custom Screener Redesign]
    N -- Model --> P[Ranking / Regime / Rule Gate]
    N -- Strategy --> Q[Strategy Diversification]
    N -- Unknown --> R[Case Mining]

    O --> F
    P --> G
    Q --> J
    R --> S[Knowledge Base]
    S --> T[New Hypothesis]
    T --> F
```

---

# Phase ST-0. SuperTrend Chart Consistency Gate

## 목적

SuperTrend Regime Discovery에서 DB에 저장한 ST 상승구간이 실제 차트의 ST Up line과 일치하는지 검증한다.

## 구현 묶음

- [ ] `generate_supertrend_regime_discovery_dashboard.py` 또는 현재 대시보드 생성부 수정
- [ ] chart candle JSON에 `st_up`, `st_down`, `st_value`, `st_dir`, `is_warmup`, `is_after_0900` 추가
- [ ] ST Parameter 드롭다운과 차트 ST line 완전 연동
- [ ] Plotly `stUpTrace`, `stDownTrace` 추가
- [ ] `connectgaps: false` 적용
- [ ] 09:00 vertical baseline 추가
- [ ] warmup area 또는 Warmup OK/FAIL badge 추가
- [ ] Chart Consistency PASS/FAIL 카드 추가
- [ ] 필요 시 `src/research/verify_supertrend_chart_consistency.py` 추가
- [ ] 필요 시 `reports/supertrend_chart_consistency.csv` 생성

## 완료 기준

- [ ] `reports/supertrend_regime_discovery_dashboard.html`에서 ST Parameter 선택 가능
- [ ] 선택 파라미터 기준 ST Up / ST Down 선이 차트에 직접 표시됨
- [ ] DB segment shade가 ST Up line과 일치하는지 눈으로 확인 가능
- [ ] 09:00 기준선 표시
- [ ] warmup 포함 여부 표시
- [ ] 장초반 강한 상승구간 누락 위험 확인 가능
- [ ] PASS/FAIL 카드 표시

## 통과 후 다음 단계

```text
Good ST Segment Similarity
```

## 아직 하지 않을 것

```text
진입전략
매도전략
손절/익절
Macro/news/sector/LLM overlay
```

---

# Phase 0. Repo / Project Contract Stabilization

## 목적

프로젝트가 커져도 동맥경화에 걸리지 않도록 기본 규약과 실행 단위를 고정한다.

## 구현 묶음

한 번의 GitHub 작업에서 다음을 함께 처리한다.

- [x] `README.md` 최신 구조 반영
- [x] `todo_list.md` 최신화
- [x] `docs/supertrend_chart_consistency_gate.md` 추가
- [ ] `docs/` 인덱스 문서 추가
- [ ] `configs/` 기본 설정 추가
- [ ] `scripts/` 실행 순서 표준화
- [ ] `tests/` smoke test 정리

## 완료 기준

- [ ] 사용자가 `git pull` 후 현재 진행 순서를 바로 이해할 수 있음
- [ ] 실행 스크립트 이름이 일관됨
- [ ] 민감정보는 `.env`에만 있음

---

# Phase 1. Data Foundation

## 목적

족집게 로직 검증에 필요한 원천 데이터를 빠짐없이 확보한다.

## 핵심 데이터

```text
performance_result  : 1516 성과검증 정답 라벨
stock_base_info     : 종목 기본정보 / 제외 플래그 / 섹터
stock_info.daily_candles : 일봉
minute5_candles     : 현재 구축 중인 5분봉 캐시
minute1_candles     : 향후 원본 분봉 기준 테이블
```

## 구현 묶음 1A: 5분봉 캐시 완성/검증

- [ ] `download_minute5_period_from_server32.py` 안정화
- [ ] 전체 기간 2026-01-05 ~ 2026-05-06 coverage 검증
- [ ] `verify_minute5_cache.py`를 일자별/종목별 coverage 중심으로 개선
- [ ] 불필요한 잘못된 범위 데이터 purge 유틸 유지

완료 기준:

- [ ] `performance_result` 대상 code 대부분의 target date 09:00~15:30 coverage 확보
- [ ] `missing_rows` 명확히 표시
- [ ] 실패 code/date가 재시도 가능 목록으로 출력

## 구현 묶음 1B: 1분봉 원본 체계

- [ ] `sql/create_minute1_candles.sql`
- [ ] `src/cache/download_minute1_period_from_server32.py`
- [ ] `src/cache/verify_minute1_cache.py`
- [ ] `scripts/download_minute1_cache.ps1`
- [ ] 1분봉 용량/coverage 리포트

완료 기준:

- [ ] `minute1_candles`에 성과검증 대상 종목 1분봉 저장 가능
- [ ] 1분봉에서 3/5/15분봉 조립 가능한 상태

---

# Phase 2. Data Quality Gate

## 목적

데이터가 틀리면 어떤 로직도 의미가 없으므로, 모든 분석 전에 품질 관문을 통과시킨다.

## 구현 묶음

- [ ] `stock_info.leader_pipeline_run` DDL
- [ ] `stock_info.leader_pipeline_day_status` DDL
- [ ] `src/quality/check_performance_result.py`
- [ ] `src/quality/check_daily_candles.py`
- [ ] `src/quality/check_minute_cache.py`
- [ ] `src/quality/build_day_status.py`
- [ ] `scripts/run_quality_gate.ps1`

## 검증 항목

- [ ] 1516 row count 날짜별 검증
- [ ] 종목코드 매핑 실패
- [ ] raw hash 중복/날짜 불일치
- [ ] rank null
- [ ] daily_candles 누락
- [ ] minute1/minute5 장중 coverage 부족
- [ ] 장마감 이후 데이터만 사용했는지 여부

## 완료 기준

- [ ] 날짜별 `OK / Partial / Missing / Failed` 상태가 산출됨
- [ ] UI에서 바로 표시 가능한 day status 테이블 생성

---

# Phase 3. Baseline Evaluation / WYSIWYG View

## 목적

현재 수준을 명확히 숫자로 고정한다.

```text
현수준: 10개 중 2개
목표: 10개 중 7개
```

## 구현 묶음

- [ ] baseline evaluator 고도화
- [ ] Actual Rank vs Score Rank 일자별 비교표 생성
- [ ] Score Rank vs Actual Rank 반대 비교표 생성
- [ ] Hit@10 / Hit@5 / Top1Capture / Label10Rate / NDCG / Lift 계산
- [ ] CSV + Markdown report 생성
- [ ] `reports/baseline_summary.md`

## Baseline 후보

- [ ] ret_1m
- [ ] ret_3m
- [ ] search_volume
- [ ] log_volume
- [ ] 1516 자체 ranking
- [ ] oracle max_ret

## 완료 기준

- [ ] “눈으로 검증된 최고수익률 순위 = 분석 순위” 비교표가 나온다.
- [ ] baseline Hit@10이 명확히 산출된다.

---

# Phase 4. Multi-Timeframe Candle Assembly

## 목적

1분봉 원본으로 다양한 분봉 전략을 테스트할 수 있게 한다.

## 구현 묶음

- [ ] `src/candles/aggregate_from_m1.py`
- [ ] 1분봉 -> 3분봉
- [ ] 1분봉 -> 5분봉
- [ ] 1분봉 -> 15분봉
- [ ] 1분봉 -> 30분봉
- [ ] OHLCV/tramount aggregation
- [ ] aggregation unit tests

## 완료 기준

- [ ] 같은 code/date에서 1/3/5/15분봉이 메모리 조립 가능
- [ ] 조립된 5분봉과 기존 `minute5_candles` 비교 검증 가능

---

# Phase 5. Feature Engine v1

## 목적

Actual Top Winners가 사전에 가졌던 조건을 feature로 만든다.

## 구현 묶음

- [ ] `src/features/daily_feature_builder.py`
- [ ] `src/features/minute_feature_builder.py`
- [ ] `src/features/indicator_feature_builder.py`
- [ ] `src/features/feature_snapshot_writer.py`
- [ ] `stock_info.leader_feature_snapshot` DDL

## Feature 그룹

### Daily Structure

- [ ] 5/10/20/60일 신고가 돌파
- [ ] 일봉 기준봉
- [ ] 기준봉 거래대금
- [ ] 기준봉 종가 위치
- [ ] 기준봉 이후 눌림폭
- [ ] 기준봉 고가 재돌파
- [ ] MA5/20/60 구조

### Minute Momentum

- [ ] 1/3/5/15분 수익률
- [ ] 1/5/15분 거래대금
- [ ] 거래대금 가속도
- [ ] 고점 갱신 빈도
- [ ] 기준봉 돌파/유지력

### Indicator

- [ ] SuperTrend
- [ ] JMA
- [ ] RSI
- [ ] ATR
- [ ] ADX

### Risk

- [ ] 단기과열/위험/관리종목 제외
- [ ] 과열 상승 감점
- [ ] 기준봉 이후 이탈 감점

## 완료 기준

- [ ] performance_id 단위 feature snapshot 생성
- [ ] look-ahead 방지 검증

---

# Phase 6. LeaderScore / Custom Screener v1

## 목적

feature를 조합해 일자별 Score Rank를 만든다.

## 구현 묶음

- [ ] `configs/score_v1.yaml`
- [ ] `src/scoring/leader_score_engine.py`
- [ ] `src/scoring/rule_gate_engine.py`
- [ ] `src/scoring/score_version_registry.py`
- [ ] `stock_info.leader_score_result` DDL
- [ ] `scripts/run_score_v1.ps1`

## 초기 구조

```text
Gate:
- 위험종목 제외
- 최소 거래대금
- 최소 분봉 momentum

Score:
DailyStructureScore
+ MinuteMomentumScore
+ IndicatorScore
+ VolumeAccelerationScore
+ RiskPenalty
```

## 완료 기준

- [ ] 날짜별 Score Top10 생성
- [ ] Actual MaxRet Top10과 비교 가능
- [ ] Hit@10 / Label10Rate 산출

---

# Phase 7. Walk-forward / Overfitting Guard

## 목적

과거 전체기간에만 맞는 김치국 로직을 제거한다.

## 구현 묶음

- [ ] `src/evaluation/walkforward_validator.py`
- [ ] `src/evaluation/overfit_guard.py`
- [ ] `configs/experiment.yaml`
- [ ] train/validation/test split
- [ ] threshold stability test
- [ ] 날짜/종목 편중도 검사

## 기본 구간

```text
Train      : 2026-01-05 ~ 2026-03-13
Validation : 2026-03-16 ~ 2026-04-10
Test       : 2026-04-13 ~ 2026-05-06
```

## 완료 기준

- [ ] Test 성능이 Train 대비 70% 이상 유지
- [ ] 특정 날짜/종목 의존성 리포트 생성
- [ ] Permanent 후보/폐기 여부 자동 판정

---

# Phase 8. Failure / Success Case Knowledge Base

## 목적

틀린 이유와 맞힌 이유를 누적해 다음 로직이 강해지게 한다.

## 구현 묶음

- [ ] `stock_info.failure_case` DDL
- [ ] `stock_info.success_case` DDL
- [ ] `src/cases/build_failure_cases.py`
- [ ] `src/cases/build_success_cases.py`
- [ ] `src/cases/case_mining_report.py`

## Case Type

```text
TRUE_POSITIVE
FALSE_POSITIVE
FALSE_NEGATIVE
TRUE_NEGATIVE
```

## 완료 기준

- [ ] Score 높은데 실패한 종목 목록 생성
- [ ] 실제 대장주인데 Score 낮은 종목 목록 생성
- [ ] 실패/성공 공통 feature 요약

---

# Phase 9. Strategy Diversification Lab

## 목적

당일 족집게가 수익 미달일 경우 전략 다변화로 수익화 가능성을 검증한다.

## 구현 묶음

- [ ] `src/strategy/intraday_leader.py`
- [ ] `src/strategy/opening_momentum.py`
- [ ] `src/strategy/pullback_reentry.py`
- [ ] `src/strategy/swing_early_trend.py`
- [ ] `src/strategy/theme_continuation.py`
- [ ] `src/strategy/structural_breakout.py`
- [ ] `src/backtest/strategy_backtester.py`
- [ ] `stock_info.strategy_backtest_result` DDL

## 전략군

- [ ] 당일청산
- [ ] 익일청산
- [ ] 1주 holding
- [ ] 1개월 holding
- [ ] 3개월 holding
- [ ] 목표수익/손절/트레일링/분할청산

## 평가 지표

- [ ] 평균수익률
- [ ] 중앙수익률
- [ ] 승률
- [ ] Profit Factor
- [ ] MDD
- [ ] 평균 보유일
- [ ] 자본회전율
- [ ] Tail risk

## 완료 기준

- [ ] 당일전략 실패 시 스윙/중기 전략 대체 가능성 판단
- [ ] 전략 포트폴리오 후보 산출

---

# Phase 10. Local Agent Score Supply System

## 목적

로컬 LLM/Agent를 24시간 가동해 부족한 점수 요소를 공급한다.

## 구현 묶음

- [ ] `stock_info.agent_task_queue` DDL
- [ ] `stock_info.agent_score_result` DDL
- [ ] `stock_info.agent_run_log` DDL
- [ ] `src/agents/base_agent.py`
- [ ] `src/agents/task_runner.py`
- [ ] `src/agents/score_writer.py`
- [ ] `scripts/run_agent_worker.ps1`

## Agent 후보

- [ ] News Agent
- [ ] Program Trading Pattern Agent
- [ ] Sector Leadership Agent
- [ ] Strategy Simulation Agent
- [ ] Pattern Mining Agent
- [ ] Failure Case Mining Agent

## 원칙

```text
Agent는 원본 DB 직접 수정 금지
Agent score는 단독 검증 전 LeaderScore 편입 금지
Agent 실패는 Core pipeline 실패가 아님
개선 없는 Agent는 DISABLE / ARCHIVE
```

## 완료 기준

- [ ] agent_score_result에 표준 점수 저장
- [ ] Agent score 단독 Hit@10 영향 평가
- [ ] 개선 score만 LeaderScore 후보로 편입

---

# Phase 11. server32 Session Broker / Agent Hub Integration

## 목적

Kiwoom/Cybos 단일 세션 제약을 server32 하나로 집중하고, 메인 프로젝트와 Agent가 같은 데이터 허브를 공유한다.

## 구현 묶음

- [ ] server32 endpoint contract 문서화
- [ ] REST client wrapper 안정화
- [ ] 요청 우선순위 설계
- [ ] cache hit/miss logging
- [ ] agent/main 요청 분리
- [ ] server32 상태 점검 UI hook

## 우선순위

```text
Priority 1: Main realtime / 실전 후보
Priority 2: Daily update
Priority 3: 1516 post-process
Priority 4: Agent light task
Priority 5: Heavy research / full-period download
```

## 완료 기준

- [ ] 메인 프로그램 실행 중에도 Agent가 DB/server32 기반으로 분석 가능
- [ ] Agent heavy task가 메인 realtime 요청을 방해하지 않음

---

# Phase 12. Daily Pipeline UI

## 목적

매일 20:00 이후 1516/일봉/분봉/feature/score 갱신을 UI에서 관리한다.

## 구현 묶음

- [ ] UI shell
- [ ] Daily Update tab
- [ ] 1516 Collector tab
- [ ] Candle Cache tab
- [ ] Data Quality tab
- [ ] Logs tab
- [ ] Settings tab

## 기능

- [ ] 단일일자 업데이트
- [ ] 기간 업데이트
- [ ] 누락일자 검색
- [ ] 1516 화면 준비 안내
- [ ] 성과검증 저장 버튼
- [ ] daily/minute cache update 버튼
- [ ] coverage grid
- [ ] error log viewer

## 완료 기준

- [ ] 중간 누락일자가 있어도 기간 재실행으로 복구 가능
- [ ] 중복 insert 없이 UPSERT
- [ ] 모든 작업 상태가 UI에서 보임

---

# Phase 13. Experiment Board / Case Review UI

## 목적

UI가 단순 실행 버튼이 아니라 검증/의사결정 도구가 되게 한다.

## 구현 묶음

- [ ] Experiment Board tab
- [ ] Actual Rank vs Score Rank grid
- [ ] Version comparison grid
- [ ] Failure Case tab
- [ ] Success Case tab
- [ ] Report Archive tab

## 완료 기준

- [ ] 날짜별 Score Top10과 Actual Top10 교집합 확인
- [ ] 실패종목/성공종목을 눈으로 리뷰
- [ ] 다음 action 결정 가능

---

# Phase 14. Permanent Version Promotion

## 목적

검증된 로직만 실전 후보로 승격한다.

## 구현 묶음

- [ ] `configs/PermanentLeaderScore_v1.yaml`
- [ ] `reports/final_score_v1_report.md`
- [ ] `src/evaluation/promotion_gate.py`
- [ ] `stock_info.experiment_decision` DDL

## Promotion 조건

```text
Hit@10 >= 7/10 또는 사전 정의된 강력 통과 기준
Test 성능이 Train 대비 70% 이상
특정 날짜/종목 편중 없음
PF/MDD 실전 가능
실시간 계산 가능
설명 가능
```

## 완료 기준

- [ ] PROMOTE / RETRY / PIVOT / ARCHIVE_FAIL 자동 판정

---

## 5. 권한 요청 최소화를 위한 작업 단위

앞으로 GitHub 코드생성은 다음 단위로 묶는다.

### Bundle ST. SuperTrend Chart Consistency Bundle

포함:

```text
dashboard chartData ST line fields
ST Up/Down Plotly traces
09:00 baseline
warmup badge/area
segment shade vs ST Up consistency card
optional consistency CSV
README/todo/docs update
```

### Bundle A. Data Foundation Bundle

포함:

```text
minute1 schema
download_minute1_period_from_server32
verify_minute1_cache
quality gate 기본
scripts
unit tests
```

### Bundle B. WYSIWYG Evaluation Bundle

포함:

```text
baseline evaluator 고도화
Actual vs Score rank report
NDCG/Lift/Hit@K 확정
reports 생성
sample tests
```

### Bundle C. Feature + Score v1 Bundle

포함:

```text
daily/minute/indicator feature builders
feature snapshot table
score_v1.yaml
leader_score_engine
rule_gate_engine
score report
```

### Bundle D. Walk-forward + Case Knowledge Bundle

포함:

```text
walkforward validator
overfit guard
failure_case/success_case schema
case builders
case mining report
```

### Bundle E. Strategy Diversification Bundle

포함:

```text
strategy interfaces
intraday/nextday/swing strategies
backtester
strategy result schema
PF/MDD report
```

### Bundle F. Agent System Bundle

포함:

```text
agent tables
base_agent
task queue runner
score writer
first Sector/Failure/Simulation agents
agent score evaluator
```

### Bundle G. UI Foundation Bundle

포함:

```text
UI shell
Daily Update
Settings
Logs
Data Quality
Candle Cache basic controls
```

### Bundle H. Experiment UI Bundle

포함:

```text
Experiment Board
Actual vs Score Rank Grid
Case Review
Strategy Lab
Agent Monitor
Report Archive
```

---

## 6. 다음 실행 순서

현재 최우선 실행 순서는 다음이다.

```text
1. git pull
2. docs/supertrend_chart_consistency_gate.md 확인
3. Bundle ST 구현 또는 패치 적용
4. build_supertrend_regime_discovery.ps1 실행
5. build_supertrend_regime_discovery_dashboard.ps1 실행
6. reports/supertrend_regime_discovery_dashboard.html 열기
7. ST Up/Down line, 09:00 baseline, warmup, DB shade 일치 확인
8. Chart Consistency PASS 후 Good ST Segment Similarity로 이동
```

로컬 실행:

```powershell
cd E:\2026\Leader_Lab
git pull
.\scripts\build_supertrend_regime_discovery.ps1
.\scripts\build_supertrend_regime_discovery_dashboard.ps1
start .\reports\supertrend_regime_discovery_dashboard.html
```

그 다음 순서:

```text
Chart Consistency PASS
→ Good ST Segment Similarity
→ Regime-aware entry/exit strategy
```

기존 5분봉 캐시 기반 WYSIWYG 평가 흐름은 Chart Consistency Gate 이후 또는 병렬 보조 작업으로 유지한다.

---

## 7. 최종 원칙

```text
데이터는 누적된다.
실험은 버전으로 남는다.
실패는 분류된다.
성공은 패턴화된다.
Core는 안정화된다.
Experiment는 자유롭게 교체된다.
Agent는 점수 원료를 공급한다.
UI는 실행보다 검증과 의사결정을 돕는다.
Permanent 버전만 실전에 승격한다.
```

`Leader_Lab`은 맞히는 로직 하나를 만드는 프로젝트가 아니다.

```text
맞힌 이유와 틀린 이유가 누적되어,
다음 로직이 이전 로직보다 강해지는 족집게 연구/검증 플랫폼이다.
```
