# Session Handoff: Causal Board Guard v1

Date: 2026-05-13
Repository: hoonoh57/Leader_Lab

This document is mandatory reading for the next session.

## 1. Why this handoff exists

The current session exposed a serious process failure.

A mixed-date research board named `LIVE_COMPACT_V3_4` was interpreted as if it were a current/selected-date buy-priority board. This caused a false alarm: `Ssenotek` appeared as rank 1, but its `trade_date` was `2026-01-29`, not the current day. The board was generated on `2026-05-12`, but that timestamp was only `realtime_snapshot_time` / table generation time, not the recommendation date.

This was not a trading logic failure. It was a board-type and data-lineage failure.

Never again treat a board as a recommendation board before verifying:

```text
1. board_type
2. selected trade date
3. source table
4. universe count
5. rank/action basis
6. future/result column usage
7. whether the board is CAUSAL_BOARD, ANSWER_BOARD, or RESEARCH_BOARD
```

## 2. Fixed terminology from now on

Use these terms exactly.

```text
CAUSAL_BOARD
= test sheet. Uses only data available at capture/search time.

ANSWER_BOARD
= answer/validation board. May use ST result labels, st_up_max_return_pct, max_ret_in_period, actual ranks.

RESEARCH_BOARD
= mixed-date or offline research sample. Never call it live or selected-date recommendation.

SELECTED_DATE_BOARD
= board filtered to exactly one search_date/trade_date and one source condition.
```

Forbidden interpretation:

```text
LIVE_COMPACT_V3_4 = today buy-priority board
```

Correct interpretation:

```text
LIVE_COMPACT_V3_4 / v3.4 smoke UI = research/mixed-date compact board unless selected date is explicitly shown.
```

## 3. SuperTrend target definition

The project is no longer simply evaluating `capture time -> end-of-day max return`.

The SuperTrend regime work exists to evaluate:

```text
capture/search-time candidate
→ future SuperTrend up segment
→ profit available inside the best ST up segment
```

Primary ST validation target:

```text
st_up_max_return_pct
label_st_gain_3pct
label_st_gain_5pct
label_st_gain_10pct
st_up_start_time
st_up_end_time
st_up_max_drawdown_pct
```

Secondary comparison fields only:

```text
max_ret_in_period
ret_1m
ret_3m
ret_7h
actual_rank_by_max_ret
```

Do not confuse max_ret_in_period ranking with the SuperTrend segment validation target.

## 4. Confirmed source tables

### Selected-date candidate source

```text
performance_result
row_count observed: 2893
selected date column: search_date
time column: search_time
code column: code
condition column: condition_name
main condition used: 1516
```

This table is the selected-date candidate universe source.

### SuperTrend answer/validation source

```text
supertrend_regime_segment
row_count observed: 25070
selected date column: trade_date
time column: search_time
code column: code
capture_time exists
ST segment fields exist
ST gain labels exist
```

This table is the ST answer/validation source.

## 5. Confirmed audit results

### Data-lineage audit

Script:

```text
scripts/audit_top_candidate_board_data_lineage_v3_7.ps1
```

Finding:

```text
supertrend_top_candidate_board_dedup_view_v3_4 is mixed-date.
It contains trade_date values from 2026-01 through 2026-04.
realtime_snapshot_time=2026-05-12 is table/snapshot generation time, not selected recommendation date.
```

### Selected-date source inspection

Script:

```text
scripts/inspect_selected_date_sources_v3_8a.ps1
```

Finding:

```text
performance_result is the usable selected-date universe.
supertrend_regime_segment is the usable ST validation source.
```

### Selected-date answer board

Script:

```text
scripts/build_selected_date_candidate_board_v3_8.ps1
```

Observed run:

```text
TradeDate=2026-04-30
ConditionName=1516
raw_rows=21
dedup_rows=21
summary_rows=1
universe_count=21
st_matched_count=21
review_candidate_count=17
great_count=6
good_count=4
watch_count=7
bad_count=3
max_st_up_max_return_pct=26.991869918699184
```

Critical interpretation:

```text
v3.8 is ANSWER_BOARD / validation board.
It uses st_up_max_return_pct, max_ret_in_period, and ST labels.
It is not a causal test sheet.
```

### Leakage audit

Script:

```text
scripts/audit_v3_score_leakage_v3_8b.ps1
```

Finding:

```text
build_selected_date_candidate_board_v3_8.ps1 uses answer/future fields in ranking/action.
That is valid only because v3.8 is an ANSWER_BOARD.
Do not use v3.8 ranking as causal score.
```

### Existing v3 causal logic audit

Script:

```text
scripts/audit_existing_v3_test_logic_v3_8c.ps1
```

Preliminary finding:

```text
supertrend_realtime_entry_candidate_v2_0 has no future/answer columns.
supertrend_realtime_entry_top_candidate_v2_1 has no future/answer columns.
These contain causal score candidates:
- execution_score_v1_9
- score_total
- filter_score_v1_6
- entry_action_v2_0
- entry_score_v2_0
- top_rank_score_v2_1
```

Caution:

```text
v2.2 and later board/screen tables include expected_return_pct and mae_risk_pct.
These may be display/result fields. Do not assume contamination until builder/rank basis is checked.
```

## 6. Mandatory next-session rule

The next session must not build a new scoring formula first.

First task:

```text
Inspect existing v2.0/v2.1 causal score generation logic.
Find the exact script or SQL that created:
- supertrend_realtime_entry_candidate_v2_0
- supertrend_realtime_entry_top_candidate_v2_1
- execution_score_v1_9
- score_total
- filter_score_v1_6
- entry_score_v2_0
- top_rank_score_v2_1
```

Only after confirming the score formula is causal, apply it to selected-date `performance_result` candidates.

## 7. Correct next implementation target

Do not create another generic board.

Create or plan:

```text
SELECTED_DATE_CAUSAL_BOARD_V3_9
```

Purpose:

```text
selected date performance_result universe
+ existing v2.0/v2.1 causal score logic
+ v3.8 ST answer board for comparison only
```

Required display columns:

```text
selected_trade_date
condition_name
universe_count
code
name
search_time
causal_rank_v3_9
causal_score_v3_9
causal_action_v3_9
answer_rank_v3_8
st_quality_v3_8
st_up_max_return_pct
st_up_start_time
st_up_end_time
rank_gap
leakage_status
```

Rank basis:

```text
Allowed for causal rank:
- execution_score_v1_9
- score_total
- filter_score_v1_6
- entry_score_v2_0
- top_rank_score_v2_1
- start_cum_amount
- start_from_day_open_pct
- start_from_day_low_pct
- capture/search-time tick/hoga fields if truly available at that time

Forbidden for causal rank:
- st_up_max_return_pct
- st_up_end_time
- st_up_max_price
- label_st_gain_*
- max_ret_in_period
- actual_rank_by_max_ret
- ret_1m / ret_3m / ret_7h
- expected_return_pct
- mae_risk_pct
```

## 8. Process guard

Before every future implementation response, state the board type being touched:

```text
Board Type: CAUSAL_BOARD / ANSWER_BOARD / RESEARCH_BOARD / SELECTED_DATE_BOARD
Selected Date: explicit date or NONE
Universe Source: explicit table
Rank Basis: causal fields or answer fields
Leakage Status: PASS / FAIL / NOT YET AUDITED
```

If this information is unknown, do not implement. Audit first.

## 9. Local command sequence for next session

Recommended first local verification in the next session:

```powershell
cd E:\2026\Leader_Lab

git pull origin main

.\scripts\audit_existing_v3_test_logic_v3_8c.ps1

git status
```

Then inspect or create a focused script to locate the actual builder for v2.0/v2.1 causal score generation.
