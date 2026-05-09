# Local Agent Score Supply Architecture

## 1. 목적

`Leader_Lab`의 1차 목표는 명확하다.

```text
족집게 도사 만들기:
Score Top10 안에 실제 대장주/대박주 7개 이상 포함
```

이 목표를 달성하기 위해 필요한 점수 요소가 부족하면, 로컬에서 24시간 가동 가능한 LLM/Agent들을 별도 프로세스로 운영하여 점수화 요소를 공급한다.

핵심 원칙:

- 메인 LeaderScore 엔진은 안정적으로 유지한다.
- 로컬 Agent들은 독립적으로 데이터를 수집/분석한다.
- Agent 결과는 표준 feature/score 테이블에 저장한다.
- LeaderScore는 이 점수 요소를 조합해 최종 ranking을 만든다.
- Agent가 실패해도 Core pipeline은 멈추지 않는다.

---

## 2. 전체 구조

```mermaid
flowchart TD
    A[Raw Market Data] --> B[Core DB]
    B --> C[Feature Builder]

    D[News Agent] --> J[Agent Score Tables]
    E[Program Trading Agent] --> J
    F[Sector Leadership Agent] --> J
    G[Strategy Simulation Agent] --> J
    H[Pattern Mining Agent] --> J
    I[Failure Case Mining Agent] --> J

    C --> K[LeaderScore Engine]
    J --> K
    K --> L[Score Ranking]
    L --> M[TopK Validation]
    M --> N{Hit@10 >= 7?}
    N -- Yes --> O[Permanent Candidate]
    N -- No --> P[Failure Analysis]
    P --> Q[Agent Task Queue]
    Q --> D
    Q --> E
    Q --> F
    Q --> G
    Q --> H
    Q --> I
```

---

## 3. Agent 설계 원칙

### 3.1 Core와 분리

Agent는 Core DB를 읽고, 자기 전용 결과 테이블에만 쓴다.

금지:

```text
Agent가 performance_result, minute1_candles, daily_candles 원본을 직접 수정
```

허용:

```text
Agent가 원본을 읽고 agent_* 테이블에 score/result 저장
```

### 3.2 표준 출력 형식

모든 Agent는 최종적으로 아래 형태의 score를 제공해야 한다.

```text
trade_date
code
agent_name
score_name
score_value
confidence
reason
source_ref
created_at
```

이 구조가 있어야 LeaderScore에서 일관되게 조합 가능하다.

### 3.3 24시간 비동기 운영

Agent는 다음 방식으로 운영한다.

- Windows Task Scheduler
- local service
- self-hosted runner
- Python daemon
- Ollama/local LLM worker

각 Agent는 독립 실행 가능해야 한다.

---

## 4. 필수 Agent 후보

## 4.1 News Collection / Analysis Agent

목적:

```text
뉴스/공시/테마 노출이 실제 대장주 형성에 기여하는지 점수화
```

입력:

- 뉴스 제목/본문
- 공시
- 테마 키워드
- 종목명/섹터 매핑

출력 score:

- news_heat_score
- theme_relevance_score
- breaking_news_score
- news_freshness_score
- news_sustainability_score

평가:

```text
뉴스 score 상위 종목이 실제 MaxRet Top10에 얼마나 들어가는가?
```

---

## 4.2 Program Trading Pattern Agent

목적:

```text
프로그램 순매수/수급 패턴이 급등 지속성과 관련 있는지 점수화
```

입력:

- 프로그램 순매수
- 외국인/기관 매수 추정
- 거래대금 변화
- 호가/체결 가능 데이터

출력 score:

- program_buy_accum_score
- program_buy_accel_score
- foreign_institution_sync_score
- liquidity_absorption_score

평가:

```text
수급 score가 높은 종목이 실제 대장주/스윙 수익 종목과 일치하는가?
```

---

## 4.3 Sector Leadership Agent

목적:

```text
주도섹터와 섹터 내 대장주/추종주 관계를 점수화
```

입력:

- 섹터 구성종목
- 섹터 평균 수익률
- 섹터 거래대금
- 섹터 내 상대강도
- 뉴스 테마 매핑

출력 score:

- sector_heat_score
- sector_leader_score
- sector_follow_through_score
- theme_rotation_score

평가:

```text
섹터 score 상위 종목이 actual TopK와 일치하는가?
```

---

## 4.4 Strategy Simulation Agent

목적:

```text
당일청산이 실패할 경우 1주/1개월/3개월 전략 수익화 가능성 탐색
```

전략군:

- IntradayLeader
- OpeningMomentum
- PullbackReEntry
- SwingEarlyTrend
- ThemeContinuation
- StructuralBreakout

출력:

- strategy_name
- holding_horizon
- expected_return_score
- risk_score
- pf_score
- mdd_score
- turnover_score

평가:

```text
족집게 적중률이 낮아도 전략 포트폴리오 수익 구조가 있는가?
```

---

## 4.5 Pattern Mining Agent

목적:

```text
Actual Top Winners의 공통 사전 패턴을 자동 탐색
```

입력:

- actual Top10 종목
- daily/minute feature
- success/failure case library

출력:

- candidate_rule
- feature_importance_hint
- pattern_cluster
- next_experiment_suggestion

주의:

이 Agent는 바로 실전 점수를 만들지 않고, 다음 실험 후보를 만든다.

---

## 4.6 Failure Case Mining Agent

목적:

```text
False Positive / False Negative를 분석해 다음 개선 방향 도출
```

입력:

- failure_case
- success_case
- chart context
- feature snapshot

출력:

- failure_reason
- missing_feature_hint
- threshold_adjustment_hint
- label_issue_hint
- universe_issue_hint

---

## 5. DB 테이블 계획

### 5.1 agent_score_result

```sql
CREATE TABLE stock_info.agent_score_result (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    trade_date DATE NOT NULL,
    code CHAR(6) NOT NULL,
    agent_name VARCHAR(50) NOT NULL,
    score_name VARCHAR(80) NOT NULL,
    score_value DECIMAL(12,6) NOT NULL DEFAULT 0,
    confidence DECIMAL(8,4) NOT NULL DEFAULT 0,
    reason VARCHAR(500) NULL,
    source_ref VARCHAR(500) NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_agent_score (trade_date, code, agent_name, score_name),
    KEY idx_agent_score_date (trade_date, agent_name),
    KEY idx_agent_score_code (code, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

### 5.2 agent_task_queue

```sql
CREATE TABLE stock_info.agent_task_queue (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    task_type VARCHAR(50) NOT NULL,
    target_date DATE NULL,
    code CHAR(6) NULL,
    payload_json JSON NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    priority INT NOT NULL DEFAULT 100,
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    message TEXT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_agent_task_status (status, priority, created_at),
    KEY idx_agent_task_date (target_date, task_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

### 5.3 agent_run_log

```sql
CREATE TABLE stock_info.agent_run_log (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    agent_name VARCHAR(50) NOT NULL,
    run_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    started_at DATETIME NOT NULL,
    finished_at DATETIME NULL,
    processed_count INT NOT NULL DEFAULT 0,
    success_count INT NOT NULL DEFAULT 0,
    fail_count INT NOT NULL DEFAULT 0,
    message TEXT NULL,
    PRIMARY KEY (id),
    KEY idx_agent_run (agent_name, started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

---

## 6. LeaderScore 통합 방식

Core LeaderScore는 Agent score를 직접 신뢰하지 않는다.

먼저 각 Agent score의 단독 검증을 수행한다.

```text
agent_score_name vs actual MaxRet TopK
agent_score_name vs label_10
agent_score_name vs swing_label
```

검증을 통과한 score만 `LeaderScore` 후보 feature로 편입한다.

통합 방식:

```text
LeaderScore = CoreFeatureScore + AgentFeatureScore - RiskPenalty
```

AgentFeatureScore 예:

```text
0.15 * sector_heat_score
0.10 * news_heat_score
0.10 * program_buy_accel_score
0.10 * strategy_expected_return_score
```

단, 각 weight는 walk-forward 검증을 통과해야 한다.

---

## 7. Local LLM 역할

로컬 LLM은 실시간 매매 판단자가 아니라 분석 보조자다.

적합한 작업:

- 뉴스 분류
- 테마 키워드 추출
- 실패 사례 요약
- 실험 결과 리포트 요약
- 다음 feature 후보 제안
- case mining 보조

부적합한 작업:

- 검증 없이 매수/매도 신호 직접 생성
- 실시간 체결 판단 단독 수행
- 원본 DB 직접 수정

---

## 8. 운영 방식

### 8.1 Daily Batch

매일 20:00 이후:

```text
1. performance_result 갱신
2. daily/minute 데이터 갱신
3. Core feature 갱신
4. Agent task 생성
5. Agent들이 24시간 분산 처리
6. 다음 날 UI에서 score 요소 반영 여부 확인
```

### 8.2 Continuous Background

장중/장후 상시:

```text
News Agent: 뉴스/공시 수집
Sector Agent: 섹터 강도 업데이트
Program Agent: 수급 패턴 업데이트
Simulation Agent: 전략군 반복 백테스트
Failure Agent: 실패 사례 분석
```

---

## 9. 실패 방지 장치

Agent 구조가 프로젝트를 복잡하게 만들 수 있으므로 다음을 강제한다.

1. Agent는 표준 score 테이블에만 기록한다.
2. Agent가 실패해도 Core pipeline은 멈추지 않는다.
3. Agent score는 단독 검증 전 LeaderScore에 편입하지 않는다.
4. 모든 Agent output은 reason과 confidence를 가져야 한다.
5. 오래된 Agent score는 유효기간을 가진다.
6. Agent별 성능도 TopK metric으로 검증한다.
7. 점수 개선이 없는 Agent는 ARCHIVE 또는 DISABLE한다.

---

## 10. 최종 목표와의 관계

Agent 시스템은 목적이 아니라 수단이다.

```text
목표: Score Top10 안에 실제 대장주/대박주 7개 이상
수단: Core feature + Agent-supplied feature 다변화
```

Agent가 많아지는 것이 성공이 아니다.

성공은 오직 다음으로 판단한다.

```text
Agent score를 추가했을 때 Hit@10, Label10Rate, PF/MDD가 개선되는가?
```

---

## 11. 핵심 문장

로컬 Agent들은 24시간 돌아가는 점수 원료 공장이다.

하지만 최종 심판은 항상 동일하다.

```text
그 점수 원료가 실제 대장주/대박주 적중률을 높였는가?
```
