# Logic Registry: SuperTrend Answer Reverse Analysis

Date: 2026-05-13
Repository: hoonoh57/Leader_Lab

## Purpose

This registry preserves every useful SuperTrend answer-sheet / causal-submission logic version so that a later session does not overwrite, forget, or reinterpret prior successful logic.

The project does not search for one magic 5-minute pattern. The core research loop is:

```text
ST high-return answer sheet
→ reverse-analysis of why the segment worked
→ one or more causal submission hypotheses
→ overlap evaluation
→ versioned performance comparison
```

## Permanent rules

```text
1. Do not delete a working logic version.
2. Do not overwrite a prior score formula without registering a new version.
3. Do not call an ANSWER_BOARD a recommendation board.
4. Do not rank a CAUSAL_BOARD with future/result fields.
5. Compare all new versions against the same answer sheet whenever possible.
6. Focus first on MISSED_GREAT and FALSE_BUY; these explain what is missing or over-trusted.
```

## Board definitions

```text
ANSWER_BOARD
= answer/validation board. It may contain future ST result fields such as st_up_max_return_pct and st_quality.

CAUSAL_BOARD
= test sheet. It must use only data available at decision_time/capture/search time.

EVALUATION_BOARD
= joined view for study. It may display both causal score and answer labels, but causal ranking must already be finalized before answer fields are joined.
```

## Registered logic versions

| Version | Board Type | Purpose | Rank Basis | Leakage Status | Output | Status |
|---|---|---|---|---|---|---|
| v3.8 | ANSWER_BOARD | Selected-date ST answer board using performance_result candidates and ST regime results | answer fields: st_up_max_return_pct, max_ret_in_period, ST labels | VALID AS ANSWER ONLY | selected-date candidate board v3.8 | preserve |
| v7-1 | EVALUATION_BOARD | Overlay existing causal submission score on the current ST answer dashboard and classify HIT/MISS groups | causal score from existing v2.0/v2.1 candidate tables; answer fields display only after join | guarded by forbidden-column check | reports/supertrend_regime_discovery_dashboard_v7_1.html, reports/st_answer_reverse_eval_v7_1.csv | current |

## v7-1 research question

```text
Why did this SuperTrend up segment become GREAT?
Did the existing causal submission score already capture that reason at decision_time?
If not, what structural feature is missing?
```

## v7-1 evaluation groups

```text
HIT_GREAT
= causal submission said BUY/WATCH and answer label is GREAT.

MISSED_GREAT
= answer label is GREAT but causal submission did not say BUY/WATCH or no causal submission matched.

FALSE_BUY
= causal submission said BUY/WATCH but answer label is BAD/NEUTRAL.

TRUE_REJECT
= causal submission did not say BUY/WATCH and answer label is not GREAT.
```

## Future version queue

```text
v7-2: add answer-segment early 1/3/5-bar reverse-analysis fields.
v7-3: add daily structure context.
v7-4: add m30/h1 multi-timeframe context.
v7-5: add sector/market context.
```

Do not start v7-2 until v7-1 is opened and MISSED_GREAT/FALSE_BUY rows are visually reviewed.
