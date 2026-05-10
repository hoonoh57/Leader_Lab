# Session Handoff: Leader_Lab

작성일: 2026-05-10  
목적: 다음 세션에서 현재 흐름을 끊김 없이 이어가기 위한 상세 인수인계 문서

---

## 1. 현재 프로젝트의 최상위 목적

`Leader_Lab`의 1차 목표는 하나로 고정한다.

```text
족집게 도사 만들기:
Score Top10 안에 실제 대장주/대박주 7개 이상 포함
```

현재 기준선은 대략 다음 수준으로 본다.

```text
Score Top10 중 실제 대장주/대박주 2개 수준 = 현 수준 / 최악 기준선
Score Top10 중 실제 대장주/대박주 7개 이상 = 강력 통과 / 족집게 후보
```

모든 데이터 수집, UI, DB, feature, agent, backtest, simulation, report는 이 목표를 위해 존재한다.

최종 검증 문장:

```text
눈으로 검증된 종목별 실제 최고수익률 순위
=
분석 순위 / Score Rank
```

즉, What You See Is What You Get 구조가 핵심이다.

---

## 2. 현재까지 확정한 핵심 철학

### 2.1 WYSIWYG 검증 원칙

화면은 반드시 다음을 보여야 한다.

```text
Actual MaxRet Rank vs Score Rank
Score Top10 안에 Actual Top10이 몇 개 들어왔는가
Score Top5 중 MaxRet >= 10% 비율은 얼마인가
실패한 종목은 왜 실패했는가
실제 대장주인데 놓친 종목은 무엇이 부족했는가
```

### 2.2 김치국 방지 원칙

다음 전제는 금지한다.

```text
데이터를 많이 모으면 자동으로 족집게가 된다.
UI를 만들면 프로젝트가 완성된다.
당일 대장주 선정만 성공하면 수익화가 된다.
당일청산 전략 하나만으로 충분하다.
```

대신 아래 구조를 사용한다.

```text
데이터 확보
→ 품질 검증
→ baseline 측정
→ feature 단독 검증
→ score version 생성
→ walk-forward 검증
→ 실패 원인 분류
→ 대체 경로 검토
→ 다음 실험
```

### 2.3 실패가 자산이 되는 구조

프로젝트가 실패하는 것은 Hit@10 7개를 즉시 못 맞히는 것이 아니다.

진짜 실패는 다음이다.

```text
왜 실패했는지 기록하지 못함
다음 개선 방향을 도출하지 못함
성공/실패 사례가 누적되지 않음
Core와 Experiment가 뒤엉켜 재사용 불가능해짐
```

따라서 실패 사례와 성공 사례를 DB에 누적해야 한다.

---

## 3. GitHub 저장소 상태

Repository:

```text
https://github.com/hoonoh57/Leader_Lab
```

로컬 경로:

```text
E:\2026\Leader_Lab
```

현재 GitHub에는 다음 주요 문서가 추가되어 있다.

```text
docs/north_star_metric.md
docs/wysiwyg_validation_principle.md
docs/contingency_flow_if_target_not_met.md
docs/sustainable_project_flowchart.md
docs/daily_pipeline_ui_plan.md
docs/custom_screener_architecture.md
docs/local_agent_score_supply_architecture.md
docs/server32_agent_operating_architecture.md
docs/session_handoff_2026_05_10.md
todo_list.md
```

`todo_list.md`는 앞으로의 구현 순서를 결정하는 Phase 기반 구현 로드맵이다.

---

## 4. GitHub 작업 방식

사용자가 GitHub 툴 사용 권한 허락을 매번 눌러야 하므로, 앞으로는 작은 파일 하나씩 생성/수정하지 않는다.

원칙:

```text
Phase 단위 / Bundle 단위로 크게 묶어서 구현한다.
SQL + Python module + script + test + docs를 한 번에 생성/수정한다.
로컬에서는 git pull 후 실행한다.
실패 로그를 다음 Bundle 수정에 반영한다.
```

현재 todo_list.md에 정의된 Bundle:

```text
Bundle A. Data Foundation Bundle
Bundle B. WYSIWYG Evaluation Bundle
Bundle C. Feature + Score v1 Bundle
Bundle D. Walk-forward + Case Knowledge Bundle
Bundle E. Strategy Diversification Bundle
Bundle F. Agent System Bundle
Bundle G. UI Foundation Bundle
Bundle H. Experiment UI Bundle
```

다음 세션에서는 반드시 `todo_list.md`를 기준으로 이어가야 한다.

---

## 5. 현재 DB / 데이터 상태

### 5.1 performance_result 이관 완료

SQLite 1516 결과를 MySQL `stock_info.performance_result`로 이관했다.

실행 결과:

```text
source_rows      = 3018
converted        = 2893
skipped          = 125
saved_or_updated = 2893

day_count        = 88
first_date       = 2026-01-05
last_date        = 2026-05-06
code_count       = 874
label10_count    = 490
avg_max_ret      = 4.7214933
rank null        = 0
```

해석:

```text
성과검증 전체기간 2026-01-05 ~ 2026-05-06
88거래일
고유 종목 874개
max_ret >= 10% 라벨 약 490건
```

### 5.2 skipped 125건

`converted=2893`, `skipped=125`는 주로 종목코드 매핑 실패 때문이다.

이전 미매칭 종목 예:

```text
APS이노베이션
KG파이낸셜
LIG아큐버
SP삼화
TPC로보틱스
국전
나라스페이스테크놀로
다이나믹솔루션
리센스메디컬
보원케미칼
블리츠웨이엔터테인먼
스모트로닉
신화프리텍
씨메스로보틱스
아이엠바이오로직스
알엔티엑스
액스비스
에이프로젠바이오로직
에코심플렉스
에피소드컴퍼니
우성머티리얼스
위너스일렉
이노에이엑스
제이스로보틱스
지구홀딩스
큐리옥스바이오시스템
파라택시스이더리움
파수AI
페니트리움바이오
한패스
```

이 미매칭 종목 중 일부는 성과가 좋았기 때문에 나중에 별도 보완 대상이다.

---

## 6. 5분봉 캐시 현재 진행 상황

현재 사용자는 874개 종목에 대해 5분봉 기간 데이터를 열심히 다운로드 중이다.

server32 주소:

```env
SERVER32_BASE_URL=http://localhost:8082
```

초기에는 `8081`로 되어 있었으나, 실제 정상 동작은 `8082`였다.

현재 사용 중인 핵심 명령:

```powershell
cd E:\2026\Leader_Lab
python -m src.cache.download_minute5_period_from_server32 --env .env --start 2026-01-05 --end 2026-05-06 --tick 5
```

검증 명령:

```powershell
python -m src.cache.verify_minute5_cache --env .env
```

이전 검증 상태:

```text
minute5_candles summary
candle_count : 48348
code_count   : 8
first_time   : 2026-01-05 09:05
last_time    : 2026-05-06 15:30

coverage:
perf_rows    : 2893
enough_rows  : 20
partial_rows : 14
missing_rows : 2859
avg_cached_count : 2.5572
```

해석:

```text
당시에는 8개 종목만 캐싱된 상태였음.
현재는 874개 다운로드가 진행 중이므로 완료 후 verify 결과를 다시 확인해야 함.
```

---

## 7. server32 분봉 요청 로직에 대한 중요한 정리

### 7.1 잘못된 접근

개별 performance row마다 200개씩 요청하는 방식은 최종 구조가 아니다.

또한 10일 전부터 무조건 요청하는 방식도 불필요하다.

### 7.2 현재 이해한 server32 방식

server32 endpoint:

```text
GET http://localhost:8082/api/market/candles/minute?code={code}&tick=5&stopTime=yyyyMMddHHmmss
```

응답 예:

```json
{ Success:true, Data:[{ '체결시간':'20260209152000', '시가':'...', '고가':'...', '저가':'...', '현재가':'...', '거래량':'...' }] }
```

사용자가 설명한 핵심:

```text
과거 특정 일자를 불러오려면 stopTime을 키로 하는 기간별 요청이 맞다.
원하는 일자 하루 전 14:00:00을 넣으면 이 이후 데이터가 나오고,
루프를 돌다가 원하는 종료일 이후 데이터가 나타나면 종료한다.
```

전체기간 구축 시 개념:

```text
대상: performance_result에 등장한 전체 code
기간: 2026-01-05 ~ 2026-05-06
시작 기준: 시작일 전일 14:00 근처
종료 기준: 종료일 15:30
처리: 반환 데이터 reverse/정렬 후 필요한 기간만 upsert
```

일일 증분 업데이트 시 개념:

```text
TargetDate 전일 14:00부터 TargetDate 15:30까지 다운로드
있으면 UPDATE
없으면 INSERT
```

---

## 8. MySQL CLI PATH 문제

PowerShell에서 다음 명령은 실패했다.

```powershell
mysql -u root -p -e "DELETE FROM stock_info.minute5_candles WHERE candle_time > '2026-05-06 15:30:00';"
```

오류:

```text
mysql : 'mysql' 용어가 cmdlet, 함수, 스크립트 파일 또는 실행할 수 있는 프로그램 이름으로 인식되지 않습니다.
```

따라서 앞으로는 `mysql` CLI 직접 호출보다 Python 모듈 방식으로 처리한다.

추가된 purge 유틸:

```powershell
python -m src.cache.purge_minute5_cache --env .env --start 2026-01-05 --end 2026-05-06
```

전체 삭제:

```powershell
python -m src.cache.purge_minute5_cache --env .env --delete-all
```

---

## 9. .env 기준

로컬 `.env`는 GitHub에 올리지 않는다.

필수 값 예:

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=실제비밀번호
MYSQL_DB_STOCK_INFO=stock_info
MYSQL_DB_STOCK_INFORMATION=stock_information

SQLITE_1516_DB=E:\2026\kiwoom1516\kiwoom_1516.sqlite3
SERVER32_BASE_URL=http://localhost:8082
SERVER32_MINUTE_ENDPOINT=/api/market/candles/minute
REPORT_ROOT=reports
MINUTE5_PREFETCH_COUNT=200
```

비밀번호, 민감정보는 `.env`에만 둔다.

---

## 10. 주요 구현 파일 현황

현재 GitHub에 생성/수정된 주요 Python 파일:

```text
src/common/env_loader.py
src/common/db.py
src/migration/migrate_1516_sqlite_to_mysql.py
src/migration/verify_performance_result.py
src/cache/rebuild_minute5_targets.py
src/cache/download_minute5_from_server32.py
src/cache/download_minute5_period_from_server32.py
src/cache/verify_minute5_cache.py
src/cache/purge_minute5_cache.py
src/evaluation/rank_match_metrics.py
src/evaluation/baseline_topk_report.py
```

주요 scripts:

```text
scripts/setup_mysql_schema.ps1
scripts/migrate_1516_to_mysql.ps1
scripts/download_minute5_cache.ps1
scripts/run_leader_lab.ps1
```

CI:

```text
.github/workflows/ci_sample_test.yml
```

---

## 11. 앞으로의 우선 구현 순서

현재 todo_list.md 기준 다음 순서가 권장된다.

```text
현재 5분봉 전체기간 캐시 완료
→ verify_minute5_cache 결과 확인
→ Bundle B: WYSIWYG Evaluation Bundle
→ Bundle C: Feature + Score v1 Bundle
→ Bundle D: Walk-forward + Case Knowledge Bundle
→ 필요 시 Bundle A: 1분봉 Data Foundation 확장
```

단, 5분봉으로 바로 한계가 보이면 1분봉 Bundle A를 앞당긴다.

---

## 12. Bundle B: WYSIWYG Evaluation Bundle 목표

다음 세션에서 가장 우선 구현 후보는 Bundle B다.

목적:

```text
현재 5분봉/성과검증 데이터만으로도 Actual Rank vs Score Rank를 눈으로 비교하는 체계 확립
```

구현 내용:

```text
baseline evaluator 고도화
Actual Rank vs Score Rank 일자별 비교표 생성
Score Rank vs Actual Rank 반대 비교표 생성
Hit@10 / Hit@5 / Top1Capture / Label10Rate / NDCG / Lift 계산
CSV + Markdown report 생성
reports/baseline_summary.md 생성
```

Baseline 후보:

```text
ret_1m
ret_3m
search_volume
log_volume
1516 자체 ranking
oracle max_ret
```

완료 기준:

```text
날짜별로 실제 최고수익률 Top10과 분석 Score Top10을 나란히 확인 가능
현재 10개 중 2개 수준이 수치로 고정됨
```

---

## 13. Bundle C: Feature + Score v1 목표

Bundle B 이후 구현한다.

목적:

```text
feature를 만들고 LeaderScore_v1로 일자별 Score Rank를 생성
```

초기 Feature:

```text
Daily Structure:
- 5/10/20/60일 신고가 돌파
- 기준봉
- 기준봉 거래대금
- 기준봉 이후 눌림폭
- 기준봉 고가 재돌파

Minute Momentum:
- 1/3/5/15분 수익률
- 거래대금 가속도
- 고점 갱신 빈도
- 기준봉 돌파/유지력

Indicator:
- SuperTrend
- JMA
- RSI
- ATR

Risk:
- 위험종목 제외
- 과열 감점
- 기준봉 이탈 감점
```

초기 Score 구조:

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

---

## 14. Bundle D: Walk-forward + Case Knowledge 목표

목적:

```text
과거 전체기간에만 맞춘 과최적화 방지
성공/실패 사례 누적
```

기본 split:

```text
Train      : 2026-01-05 ~ 2026-03-13
Validation : 2026-03-16 ~ 2026-04-10
Test       : 2026-04-13 ~ 2026-05-06
```

Case Type:

```text
TRUE_POSITIVE
FALSE_POSITIVE
FALSE_NEGATIVE
TRUE_NEGATIVE
```

핵심 산출물:

```text
실제 대장주인데 Score 낮은 종목 목록
Score 높았지만 실제 수익률 낮은 종목 목록
성공 종목의 공통 feature 요약
실패 원인 분류
```

---

## 15. 1분봉 저장 전략

사용자가 제기한 중요한 방향:

```text
5분봉보다 1분봉 전체종목 저장이 가능하면,
1분봉을 원본으로 저장하고 3/5/15분봉을 조립하는 편이 훨씬 강력하다.
```

용량 추정:

```text
874종목 6개월 5분봉: 대략 2~5GB
874종목 6개월 1분봉: 대략 10~25GB
874종목 3년 1분봉: 대략 60~150GB
874종목 5년 1분봉: 대략 100~250GB
```

현재 여유 공간:

```text
465GB 중 약 360GB 사용 가능
```

따라서 성과검증 대상 874종목 기준 1분봉 저장은 충분히 가능성이 있다.

추천 구조:

```text
원본 DB: stock_info.minute1_candles
파생 분봉: 메모리 조립
분석 결과: feature table 저장
백테스트 결과: result table 저장
```

---

## 16. Custom Screener 방향

1분봉 전체종목 다운로드가 가능하면 `Leader_Lab`은 1516 분석기를 넘어 자체 조건검색 엔진이 된다.

목표:

```text
키움 조건검색식으로 표현하기 어려운 복합 필터 구현
```

예:

```text
최근 20일 신고가 돌파 후 눌림
+ 당일 1분 거래대금 가속도 상위 10%
+ 5분 재구성 기준봉 거래대금 5억 이상
+ SuperTrend 상승 전환
+ JMA slope 양전환
+ 주도섹터 강도 상위권
+ 뉴스 테마 노출
```

주요 Feature:

```text
TickIntensity-like feature
SuperTrend
JMA
RSI/ATR/ADX
프로그램 순매수
주도섹터
뉴스/테마
거래대금 가속도
기준봉 재돌파
```

---

## 17. 전략 다변화 방향

당일 족집게 하나만으로 수익이 안 나면 포기하지 않고 전략군을 확장한다.

전략군:

```text
IntradayLeader       : 대장주 당일 단타
OpeningMomentum      : 장초반 기준봉 돌파
PullbackReEntry      : 기준봉 후 눌림 재돌파
SwingEarlyTrend      : 상승 초입 1주 holding
ThemeContinuation    : 주도섹터 1개월 holding
StructuralBreakout   : 일봉 구조 돌파 3개월 holding
```

평가 지표:

```text
평균수익률
중앙수익률
승률
Profit Factor
MDD
평균 보유일
자본회전율
Tail risk
시장 국면별 성능
```

핵심:

```text
당일청산은 실패하지만 1주/1개월/3개월 중 어느 horizon에서 수익 구조가 있으면 전략 포트폴리오 후보로 유지한다.
```

---

## 18. Local Agent 구조

사용자는 로컬 LLM/Agent를 24시간 가동하여 점수 요소를 공급하는 구조를 원한다.

Agent 후보:

```text
News Agent
Program Trading Pattern Agent
Sector Leadership Agent
Strategy Simulation Agent
Pattern Mining Agent
Failure Case Mining Agent
```

Agent 원칙:

```text
Agent는 원본 DB 직접 수정 금지
Agent는 agent_score_result에만 표준 score 저장
Agent score는 단독 검증 전 LeaderScore 편입 금지
Agent 실패는 Core pipeline 실패가 아님
개선 없는 Agent는 DISABLE / ARCHIVE
```

표준 출력:

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

최종 심판:

```text
Agent score를 추가했을 때 Hit@10, Label10Rate, PF/MDD가 개선되는가?
```

---

## 19. server32 중심 구조

Kiwoom/Cybos는 단일 연결만 허용하므로, `server32`를 유일한 provider 세션 브로커로 둔다.

구조:

```text
Kiwoom / Cybos
   ↓
server32
   - 단일 로그인 세션
   - REST API
   - 요청 우선순위 큐
   - 인메모리 캐시
   - DB Writer
   - Rate / Priority Control
   ↓
MySQL stock_info
   ↓
Leader_Lab Main + Local Agents
```

핵심 장점:

```text
Kiwoom/Cybos에는 server32 하나만 로그인
메인 프로젝트와 여러 Agent는 server32/DB만 사용
메인 프로그램에 영향 없이 뉴스/섹터/수급/전략 Agent 병렬 운영 가능
```

요청 우선순위:

```text
Priority 1: Main realtime / 실전 후보
Priority 2: Daily update
Priority 3: 1516 post-process
Priority 4: Agent light task
Priority 5: Heavy research / full-period download
```

---

## 20. Daily Pipeline UI 방향

매일 20:00 이후 필요한 데이터:

```text
1. 1516 성과검증 데이터
2. 일봉 캔들
3. 분봉 캔들
```

UI 흐름:

```text
사용자가 키움 1516 화면을 열고 09:05 세팅
→ UI에서 날짜 선택
→ 성과검증저장 버튼
→ 클립보드 복사/파싱
→ performance_result UPSERT
→ daily_candles update/upsert
→ minute candles update/upsert
→ quality gate
```

중간에 일자가 빠져도 기간 재실행으로 복구 가능해야 한다.

```text
있으면 UPDATE
없으면 INSERT
중복 INSERT 금지
```

UI 탭 구조:

```text
Daily Update
1516 Collector
Candle Cache
Data Quality
Baseline / LeaderScore
Backtest / Simulation
Reports
Settings / Logs
Agent Monitor
Experiment Board
Case Review
```

---

## 21. 다음 세션에서 가장 먼저 할 일

다음 세션 시작 시 아래 순서로 진행한다.

### Step 1. 현재 상태 확인

사용자에게 5분봉 전체 다운로드가 끝났는지 확인한다.

완료됐다면 실행:

```powershell
cd E:\2026\Leader_Lab
python -m src.cache.verify_minute5_cache --env .env
```

결과에서 확인:

```text
candle_count
code_count
first_time
last_time
perf_rows
enough_rows
partial_rows
missing_rows
worst coverage sample
```

### Step 2. GitHub 최신화

```powershell
cd E:\2026\Leader_Lab
git pull
```

### Step 3. todo_list.md 기준 다음 Bundle 선택

권장:

```text
5분봉 coverage 충분 → Bundle B: WYSIWYG Evaluation Bundle
5분봉 coverage 부족 → Bundle A 일부: Data Foundation 보강
```

### Step 4. 권한 요청 최소화 방식으로 구현

다음 세션에서 코드를 생성할 경우, 한두 파일씩 만들지 말고 Bundle 단위로 생성한다.

예: Bundle B 구현 시 한 번에 생성/수정할 것:

```text
src/evaluation/wysiwyg_rank_report.py
src/evaluation/baseline_feature_scores.py
src/evaluation/report_writer.py
scripts/run_wysiwyg_baseline.ps1
tests/test_rank_metrics.py
reports/.gitkeep 또는 docs/report_examples.md
README/todo 업데이트
```

---

## 22. 다음 세션의 첫 응답 권장 문장

다음 세션에서 사용자가 “이어서 진행”이라고 하면, 먼저 다음처럼 응답하면 된다.

```text
현재 상태는 performance_result 이관 완료, 5분봉 전체기간 캐시 진행/완료 대기 상태입니다.
먼저 verify_minute5_cache 결과를 확인한 뒤, coverage가 충분하면 todo_list.md 기준 Bundle B(WYSIWYG Evaluation Bundle)를 한 번에 구현하겠습니다.
```

그 다음 사용자에게 필요한 명령:

```powershell
cd E:\2026\Leader_Lab
git pull
python -m src.cache.verify_minute5_cache --env .env
```

사용자가 결과를 붙여주면 바로 Bundle B 구현을 진행한다.

---

## 23. 주의할 점

1. 절대 UI부터 만들지 말 것.
2. 먼저 WYSIWYG 검증표가 나와야 한다.
3. 모든 기능은 Hit@10, Label10Rate, PF/MDD와 연결되어야 한다.
4. 과최적화 방지를 위해 walk-forward는 반드시 넣어야 한다.
5. 실패한 실험도 DB/리포트로 남겨야 한다.
6. Agent는 목적이 아니라 점수 원료 공급 수단이다.
7. server32는 provider 단일세션 허브로 유지한다.
8. 민감정보는 `.env`에만 둔다.
9. GitHub 작업은 Bundle 단위로 크게 묶는다.
10. 사용자가 요청한 VB.NET 실전 시스템과 향후 연동 가능성을 유지하되, 현재 `Leader_Lab`은 Python/MySQL 기반 검증 플랫폼으로 진행한다.

---

## 24. 현재 세션의 최종 결론

지금은 데이터 구축 단계다.

하지만 단순 데이터 구축 프로젝트가 아니다.

최종 구조는 다음이다.

```text
성과검증 라벨
+ 일봉/1분봉/5분봉 데이터
+ WYSIWYG 평가
+ Feature/Score 버전 실험
+ 실패/성공 사례 지식베이스
+ 전략 다변화
+ Local Agent 점수 공급망
+ server32 단일세션 데이터 허브
=
지속 가능한 족집게 연구/검증 플랫폼
```

다음 세션은 반드시 다음 분기에서 시작한다.

```text
5분봉 캐시 완료 여부 확인
→ verify 결과 확인
→ Bundle B 또는 Data 보강 Bundle 선택
→ GitHub 권한 요청을 줄이기 위해 Bundle 단위로 구현
```
