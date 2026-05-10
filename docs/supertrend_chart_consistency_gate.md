# SuperTrend Chart Consistency Gate

작성일: 2026-05-10  
현재 단계: `SuperTrend Regime Discovery` 이후, `Good ST Segment Similarity` 이전

---

## 1. 목적

`SuperTrend Regime Discovery`에서 생성된 DB 저장 ST 상승구간이 실제 차트의 SuperTrend 상승선과 정확히 일치하는지 검증한다.

이 단계는 매수/매도 전략 설계 단계가 아니다. 전략으로 넘어가기 전에 반드시 차트 정합성을 통과해야 한다.

---

## 2. 현재 연구 스택 위치

```text
Experiment Registry
→ Winner Pattern Discovery
→ Winner Feature Score v1
→ Time-Aware Winner Feature Score v2
→ SuperTrend Regime Discovery
→ Chart Consistency Gate  ← 현재 pending
→ Good ST Segment Similarity
→ Regime-aware entry/exit strategy
→ Macro/news/sector/LLM overlay
```

현재는 `Chart Consistency Gate`를 통과시키는 것이 최우선 작업이다.

---

## 3. 현재 생성 결과 기준

최근 실행 결과 기준:

```text
targets=2622
params=[(7, 1.5), (7, 2.0), (10, 2.0), (14, 2.0)]
warmup_bars=80
segments=25070
report=reports/supertrend_regime_discovery_dashboard.html
```

대시보드는 생성되었지만, 현재 차트는 세그먼트 음영과 마커 중심이라 실제 SuperTrend Up/Down line 검증이 어렵다.

---

## 4. 반드시 검증할 항목

아래 5개 항목이 모두 화면에서 확인되어야 한다.

```text
1. 차트가 09:00 이전 warmup 봉을 포함하는가
2. 09:00 기준선이 보이는가
3. ST Up / ST Down 선이 보이는가
4. DB에 저장된 ST 상승구간 음영이 ST Up 선과 일치하는가
5. 장초반 강한 상승구간이 warmup 부족 때문에 누락되지 않는가
```

---

## 5. 대시보드 필수 표시 요소

차트에는 아래 요소가 반드시 함께 표시되어야 한다.

```text
1. Candlestick
2. Volume
3. 09:00 vertical baseline
4. Warmup area 또는 Warmup OK/FAIL badge
5. ST Up line
6. ST Down line
7. DB segment shade
8. ST Start marker
9. ST End marker
10. ST Max marker
11. Capture time marker
12. Day open horizontal line
```

---

## 6. ST 파라미터 연동 규칙

대시보드의 `ST Parameter` 드롭다운은 아래 모든 영역과 같은 기준으로 연동되어야 한다.

```text
7:1.5
7:2.0
10:2.0
14:2.0
```

사용자가 파라미터를 바꾸면 다음이 모두 같은 기준으로 갱신되어야 한다.

```text
1. 좌측 세그먼트 목록
2. 상단 summary 카드
3. 차트의 ST Up/Down line
4. ST Start/End/Max marker
5. DB segment shade
6. Consistency PASS/FAIL 카드
```

---

## 7. 데이터 생성 원칙

브라우저에서 SuperTrend를 새로 계산하지 않는다.

세그먼트 생성에 사용한 동일한 bar-level SuperTrend 결과를 차트용 JSON에 포함한다.

권장 candle JSON 구조:

```json
{
  "ts": "2026-01-05T09:35:00",
  "open": 2780,
  "high": 2830,
  "low": 2740,
  "close": 2810,
  "volume": 123456,
  "amount": 345678900,
  "st_value": 2748.25,
  "st_dir": 1,
  "st_up": 2748.25,
  "st_down": null,
  "is_warmup": false,
  "is_after_0900": true
}
```

핵심 원칙:

```text
세그먼트 생성에 사용한 ST 값 = 차트에 표시되는 ST 값
```

---

## 8. Plotly trace 요구사항

필수 trace:

```text
candlestickTrace
volumeTrace
stUpTrace
stDownTrace
segmentShade
stStartMarker
stEndMarker
stMaxMarker
```

`stUpTrace`와 `stDownTrace`는 반드시 `connectgaps: false`를 사용한다.

상승구간과 하락구간이 하나의 선으로 이어져 보이면 검증이 불가능하다.

---

## 9. PASS 조건

```text
1. 선택한 ST Parameter와 차트 ST line이 일치한다.
2. ST Up / ST Down 선이 캔들 위에 직접 표시된다.
3. ST Start marker가 ST Down → ST Up 전환 봉과 일치한다.
4. ST End marker가 ST Up → ST Down 전환 봉과 일치한다.
5. DB segment shade 시작/종료가 ST Up 구간과 일치한다.
6. 09:00 기준선이 보인다.
7. warmup 포함 여부가 표시된다.
8. 09:05~09:30 구간의 첫 강한 상승 ST 구간 누락 위험이 LOW로 판정된다.
```

---

## 10. FAIL 조건

```text
1. ST line이 없다.
2. ST line은 있지만 선택 파라미터와 다르다.
3. ST Start/End marker가 ST line 전환점과 다르다.
4. DB segment shade가 ST Up 구간과 1봉 이상 어긋난다.
5. 09:00 기준선이 없다.
6. warmup 포함 여부가 불명확하다.
7. 장초반 강한 상승구간이 warmup 부족 때문에 누락될 위험이 있다.
```

---

## 11. 권장 자동 검증 CSV

추가 대상 스크립트:

```text
src/research/verify_supertrend_chart_consistency.py
```

출력 파일:

```text
reports/supertrend_chart_consistency.csv
```

권장 컬럼:

```text
search_date
code
name
st_period
st_multiplier
segment_id
segment_start_time
segment_end_time
chart_first_time
has_pre_0900_warmup
has_0900_baseline
st_up_line_exists
st_down_line_exists
db_segment_matches_st_up
early_segment_possible
early_segment_missing_risk
pass_fail
fail_reason
```

---

## 12. 이번 단계 완료 기준

```text
reports/supertrend_regime_discovery_dashboard.html 열기
→ ST Parameter 선택
→ 좌측 세그먼트 클릭
→ 캔들 위에 ST Up / ST Down 선 표시
→ 09:00 기준선 표시
→ warmup 표시 또는 Warmup OK/FAIL badge 표시
→ DB segment shade와 ST Up line 일치 여부 확인
→ Chart Consistency PASS/FAIL 카드 표시
```

이 조건을 만족해야 다음 단계인 `Good ST Segment Similarity`로 넘어간다.

---

## 13. 이번 단계에서 하지 않을 것

```text
진입전략 설계
매도전략 설계
손절/익절 조건 설계
Good ST Segment Similarity 점수화
Macro/news/sector/LLM overlay 결합
```

아직 차트와 DB의 ST 구간이 같은지 검증되지 않았기 때문에 전략 설계는 보류한다.
