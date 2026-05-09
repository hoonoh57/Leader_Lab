# Custom Screener Architecture

## 1. 목적

`Leader_Lab`은 키움 1516 성과검증 데이터만 분석하는 프로젝트에서 확장하여, 자체 조건검색 엔진을 구축한다.

핵심 방향:

- 원천 데이터: 일봉 + 1분봉
- 파생 데이터: 3분봉 / 5분봉 / 15분봉 / 30분봉 / 60분봉
- 분석 대상: 전체 종목 또는 필터링된 종목군
- 목적: 키움 조건검색식으로 표현하기 어려운 복합 조건을 자체 필터로 구현

최종 목표:

> 키움 조건검색과 별도로, 자체 데이터베이스와 사용자 지표를 이용해 실시간/장후 후보 종목을 선별하고, 그 선별 결과가 실제 장중 최고수익률 상위 종목과 얼마나 일치하는지 검증한다.

---

## 2. 왜 1분봉 원본 저장이 중요한가

5분봉만 저장하면 다음 한계가 생긴다.

- 3분봉 전략 검증 불가
- 1분 단위 급등/눌림/재돌파 분석 불가
- 09:05 전후 수급 변화를 세밀하게 볼 수 없음
- TickIntensity 유사 지표를 정밀하게 만들기 어려움
- 기준봉의 시작/종료 위치가 5분 단위로 뭉개짐

반대로 1분봉을 저장하면 다음이 가능하다.

- 1분봉에서 3/5/15/30/60분봉 조립
- 종목별 다중 타임프레임 feature 생성
- 조건검색식보다 복잡한 사용자 정의 필터 구성
- 장중 특정 시점 기준 시뮬레이션
- 전략별로 다른 타임프레임을 동시에 테스트

---

## 3. 데이터 저장 전략

### 원본 테이블

- `stock_info.minute1_candles`
- `stock_info.daily_candles`
- `stock_info.stock_base_info`
- `stock_info.performance_result`

### 파생 테이블

상위 분봉 전체를 DB에 중복 저장하지 않는 것을 기본 원칙으로 한다.

- 3분봉 / 5분봉 / 15분봉은 메모리에서 조립
- 반복 사용되는 핵심 feature만 DB에 저장

예외:

- 성능상 매우 자주 사용하는 5분봉 feature는 별도 feature 테이블에 저장 가능
- 원본 5분봉 전체 저장은 1분봉 체계가 안정화되면 선택적으로 축소

---

## 4. 자체 조건검색 엔진 개념

### 기존 키움 조건검색의 한계

키움 조건식은 빠르게 후보를 좁히는 데 유용하지만 다음 복합 조건을 충분히 표현하기 어렵다.

- TickIntensity 또는 체결빈도 기반 수급 강도
- SuperTrend/JMA 조합
- 프로그램 순매수 추세
- 주도섹터 강도
- 뉴스/테마 노출 강도
- 일봉 기준봉 + 분봉 기준봉 + 재돌파의 결합
- 다중 타임프레임 동시 조건
- 최근 n일 후보 반복 출현 + 당일 거래대금 집중

### 자체 Screener의 목표

`CustomScreener`는 키움 조건검색을 대체하거나 보완하는 자체 조건검색 엔진이다.

입력:

- 일봉 feature
- 1분봉 기반 파생 feature
- 3/5/15분봉 재구성 feature
- 수급 feature
- 섹터/테마 feature
- 뉴스 feature
- 프로그램 순매수 feature

출력:

- 후보 종목 리스트
- 필터 통과 사유
- LeaderScore
- ranking
- 실전 후보 등급

---

## 5. 주요 Feature 그룹

### 5.1 Daily Structure Feature

- 5/10/20/60일 신고가 돌파
- 일봉 기준봉
- 기준봉 거래대금
- 기준봉 종가 위치
- 기준봉 이후 눌림폭
- 기준봉 고가 재돌파
- MA5/20/60 구조
- 과열도

### 5.2 Minute Momentum Feature

1분봉 원본에서 생성한다.

- 1분 수익률
- 3분 수익률
- 5분 수익률
- 15분 수익률
- 1분 거래대금
- 5분 누적 거래대금
- 15분 누적 거래대금
- 거래대금 가속도
- 고점 갱신 속도

### 5.3 TickIntensity-like Feature

틱 데이터가 없더라도 1분봉으로 유사 지표를 만든다.

- 분당 거래량 변화율
- 분당 거래대금 변화율
- 분당 고저 변동폭
- 양봉 지속성
- 상승 1분봉 연속성
- 고점 갱신 빈도
- 거래대금 집중도

향후 실제 틱 데이터가 연결되면 이 그룹은 실제 TickIntensity와 통합한다.

### 5.4 Technical Indicator Feature

- SuperTrend
- JMA
- RSI
- ATR
- ADX
- MACD
- Donchian breakout
- Bollinger expansion

### 5.5 Supply / Program Feature

- 프로그램 순매수
- 외국인/기관 추정 수급
- 거래대금 순위
- 회전율
- 장중 수급 지속성

### 5.6 Sector / Theme Feature

- 주도섹터 강도
- 섹터 내 대장주/추종주 관계
- 섹터 동반 상승률
- 섹터 거래대금 집중도
- 최근 뉴스 테마 연결

### 5.7 News Feature

- 뉴스 노출 빈도
- 테마 키워드 강도
- 장전/장중 뉴스 발생 여부
- 뉴스 발생 후 분봉 반응
- 뉴스 테마의 지속성

---

## 6. Screener 실행 모드

### 6.1 장후 연구 모드

목적:

- 과거 데이터로 조건 조합 검증
- 성과검증 TopK와 비교
- 과최적화 방지

입력:

- 기간
- feature set
- score config
- target universe

출력:

- TopK hit report
- Score leaderboard
- failure analysis

### 6.2 장중 후보 선별 모드

목적:

- 실시간 후보 선별
- 매매 우선순위 산정

입력:

- 실시간 1분봉 업데이트
- 현재까지 일중 feature
- 전일/최근 일봉 feature

출력:

- 실시간 LeaderScore ranking
- TopN candidate grid
- 필터 통과 사유

### 6.3 조건식 대체 모드

목적:

- 키움 조건검색식이 할 수 없는 자체 조건검색 수행

예:

```text
최근 20일 신고가 돌파 후 3일 이내
+ 당일 5분 재구성 기준봉 거래대금 5억 이상
+ SuperTrend 상승 전환
+ JMA slope 양전환
+ 1분 거래대금 가속도 상위 10%
+ 섹터 강도 상위 20%
+ 뉴스 테마 노출 있음
```

---

## 7. UI 확장 방향

기존 `Daily Pipeline UI`에 다음 탭을 추가한다.

```text
Custom Screener
├── Universe
├── Feature Filters
├── Indicator Filters
├── Sector / News Filters
├── Score Weights
├── Run / Compare
└── Result Grid
```

### 7.1 Universe

- 전체 종목
- performance_result 등장 종목
- KOSPI/KOSDAQ
- 제외 플래그 제거
- 거래대금 상위 N
- 섹터 선택

### 7.2 Feature Filters

- 기준봉 조건
- 거래대금 조건
- 수익률 조건
- 눌림 조건
- 재돌파 조건

### 7.3 Indicator Filters

- SuperTrend
- JMA
- RSI
- ATR
- ADX

### 7.4 Sector / News Filters

- 주도섹터 점수
- 뉴스 점수
- 프로그램 순매수 점수

### 7.5 Result Grid

| Rank | Code | Name | Score | Daily | M1 | M5 | ST | JMA | Sector | News | Reason |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|

---

## 8. DB 추가 계획

### 8.1 minute1_candles

원본 1분봉 저장 테이블.

### 8.2 screener_feature_snapshot

특정 날짜/시간 기준 feature 스냅샷.

### 8.3 screener_result

조건검색 결과 및 점수 저장.

### 8.4 screener_eval_result

조건검색 결과와 실제 최고수익률 TopK 비교 결과.

---

## 9. 검증 원칙

Custom Screener가 좋은지는 다음으로 평가한다.

- 조건 통과 종목 수가 너무 많거나 너무 적지 않은가
- Score Top5/Top10이 실제 max_ret Top5/Top10과 얼마나 일치하는가
- label_10 비율이 baseline보다 높은가
- Train/Validation/Test에서 유지되는가
- 특정 종목/특정 날짜에 과도하게 의존하지 않는가
- 실시간 계산 가능한가

---

## 10. 단계별 구현 계획

### Phase A. 1분봉 원본 저장

- `minute1_candles` DDL
- server32 tick=1 기간 downloader
- 전체/증분 다운로드
- coverage 검증

### Phase B. 분봉 조립 엔진

- 1분봉 -> 3분봉
- 1분봉 -> 5분봉
- 1분봉 -> 15분봉
- OHLCV/tramount aggregation

### Phase C. Feature Engine

- daily feature
- minute feature
- indicator feature
- sector/news/program feature hook

### Phase D. Screener Engine

- rule filter
- score filter
- reason code
- result ranking

### Phase E. Screener Evaluation

- TopK hit
- label_10 concentration
- lift
- NDCG
- failure analysis

### Phase F. UI Integration

- Custom Screener tab
- Filter builder
- Run button
- Result grid
- Report viewer

---

## 11. 핵심 결론

1분봉 전체 저장이 가능해지면 `Leader_Lab`은 단순 1516 분석기가 아니라 자체 조건검색 엔진으로 확장된다.

이 엔진은 키움 조건검색보다 훨씬 복잡한 조합 조건을 사용할 수 있다.

최종 구조:

```text
minute1_candles + daily_candles + sector/news/program data
→ multi-timeframe feature
→ custom screener
→ LeaderScore ranking
→ TopK validation
→ 실전 후보 선별
```
