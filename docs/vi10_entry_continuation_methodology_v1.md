# VI10 Entry Continuation Methodology v1

Date: 2026-05-13
Repository: hoonoh57/Leader_Lab

## Corrected core premise

The +10% breakout itself is the entry filter.

The task is not to predict every +10% candidate before it reaches +10%.
The task is:

```text
From the condition-captured candidate pool,
enter only when a stock reaches +10%,
then distinguish stocks that continue strongly after +10%
from stocks that reject, collapse, or stall near +10%.
```

## Event timeline

```text
T_capture = condition detection time, e.g. 09:05
T10       = first time the stock reaches +10% from previous close
T_entry   = T10, or executable entry immediately around T10
T_after   = post-T10 evaluation window
```

## Allowed evidence at entry

At T10, the following are available and valid for filtering/ranking:

```text
condition formula metadata at T_capture
price path from T_capture to T10
amount accumulated from T_capture to T10
tick intensity from T_capture to T10
pullback and high-hold behavior before T10
time taken from T_capture to T10
daily structure known before/during T10
sector/theme behavior up to T10
SuperTrend state up to T10
```

These are not future data if the actual entry is at T10.

## Post-T10 outcomes

The outcome must be measured strictly after T10.

```text
post_T10_plus2_success
= after T10, price reaches entry_price * 1.02 before the stop/failure condition.

post_T10_max_return_pct
= max return after T10 within the evaluation window.

post_T10_mae_pct
= maximum adverse excursion after T10.

post_T10_reject_flag
= price fails to continue and falls below the rejection threshold.
```

## Primary strategy benchmark

```text
Universe: condition-captured stocks at T_capture.
Entry candidate: stock reaches +10% at T10.
Entry rule: enter at/around +10%.
Target: +2% from entry.
Failure: post-T10 rejection/stop condition.
```

The first benchmark is not a complex SuperTrend strategy. It is:

```text
Among stocks that reach +10% after being captured by the condition,
what percentage produce +2% after T10?
```

## Key classification

```text
VI10_CONTINUATION_WIN
= reaches +2% after T10 before rejection/stop.

VI10_WEAK_REJECT
= touches +10% but fails to reach +2% and rejects/falls.

VI10_STALL
= touches +10% but neither reaches +2% nor breaks stop in the evaluation window.

NO_VI10_ENTRY
= condition-captured stock never reaches +10%.
```

## Evidence table

```text
trade_date
condition_name
T_capture
code
name
T10
entry_price
minutes_capture_to_T10
return_capture_to_T10
amount_capture_to_T10
amount_velocity_capture_to_T10
amount_rank_at_T10
tick_intensity_capture_to_T10
tick_rank_at_T10
pullback_depth_before_T10
high_hold_ratio_before_T10
first_reclaim_or_breakout_pattern
daily_breakout_reaccel_state
sector_leader_state
st_state_at_T10
post_T10_max_return_pct
post_T10_mae_pct
post_T10_plus2_success
post_T10_outcome_label
```

## Scorecard

For each condition formula and date:

```text
candidate_count
vi10_entry_count
vi10_entry_rate
vi10_plus2_success_count
vi10_plus2_success_rate
vi10_reject_count
vi10_reject_rate
avg_post_T10_max_return_pct
avg_post_T10_mae_pct
```

For Top-N filtering at T10:

```text
rank_method
N
selected_count
plus2_success_count
plus2_success_rate
reject_count
reject_rate
missed_plus2_count
```

## Relationship with SuperTrend

SuperTrend is not the primary entry trigger here.
The primary entry trigger is +10%.

SuperTrend can be tested as one optional state variable at T10:

```text
st_state_at_T10
st_up_started_before_T10
st_up_bars_at_T10
st_line_distance_at_T10
```

The question is whether SuperTrend state improves post-T10 continuation/rejection separation.

## Do not do

```text
Do not treat 09:05-only amount as enough evidence.
Do not mix post-T10 outcome fields into pre-entry ranking.
Do not call a +10% touch successful unless post-T10 continuation is measured.
Do not optimize a rule on one screenshot/day.
Do not force SuperTrend to be the main trigger when +10% is the actual entry event.
```

## Immediate next benchmark

```text
VI10 Entry Continuation Benchmark v1
```

Output files:

```text
reports/vi10_entry_continuation_benchmark_v1.csv
reports/vi10_entry_continuation_benchmark_v1.html
```

Core question:

```text
Among condition-captured stocks that reach +10%,
which T_capture-to-T10 evidence separates +2% continuation winners
from weak +10% reject/stall cases?
```
