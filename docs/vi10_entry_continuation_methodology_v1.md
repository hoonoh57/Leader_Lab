# VI10 Entry Continuation Methodology v1

Date: 2026-05-13
Repository: hoonoh57/Leader_Lab

## Corrected core premise

The breakout threshold itself is the entry filter.

The initial threshold is +10%, but it must be tested as a variable, not as a fixed constant.

The task is not to predict every +10% candidate before it reaches +10%.
The task is:

```text
From the condition-captured candidate pool,
enter only when a stock reaches a breakout threshold X%,
then distinguish stocks that continue strongly after X%
from stocks that reject, collapse, or stall near X%.
```

## Why X% must be variable

The +10% zone is the first VI / liquidity-attraction zone.
Some operators may use the 10% area to create liquidity and unload.
Therefore, a delayed confirmation entry such as +12% breakout may avoid many 10% reject/stall cases.

The benchmark must compare at least:

```text
X = 10%
X = 11%
X = 12%
X = 13%
```

The final threshold must be chosen by measured post-breakout continuation performance, not by one-day observation.

## Event timeline

```text
T_capture = condition detection time, e.g. 09:05
TX        = first time the stock reaches +X% from previous close
T_entry   = TX, or executable entry immediately around TX
T_after   = post-TX evaluation window
```

For the base case:

```text
X = 10%, TX = T10
X = 12%, TX = T12
```

## Allowed evidence at entry

At TX, the following are available and valid for filtering/ranking:

```text
condition formula metadata at T_capture
price path from T_capture to TX
amount accumulated from T_capture to TX
tick intensity from T_capture to TX
pullback and high-hold behavior before TX
time taken from T_capture to TX
daily structure known before/during TX
sector/theme behavior up to TX
SuperTrend state up to TX
```

These are not future data if the actual entry is at TX.

## Post-TX outcomes

The outcome must be measured strictly after TX.

```text
post_TX_plus2_success
= after TX, price reaches entry_price * 1.02 before the stop/failure condition.

post_TX_max_return_pct
= max return after TX within the evaluation window.

post_TX_mae_pct
= maximum adverse excursion after TX.

post_TX_reject_flag
= price fails to continue and falls below the rejection threshold.
```

## Primary strategy benchmark

```text
Universe: condition-captured stocks at T_capture.
Entry candidate: stock reaches +X% at TX.
Entry rule: enter at/around +X%.
Target: +2% from entry.
Failure: post-TX rejection/stop condition.
```

The first benchmark is not a complex SuperTrend strategy. It is:

```text
Among stocks that reach +X% after being captured by the condition,
what percentage produce +2% after TX?
```

## Key classification

```text
VIX_CONTINUATION_WIN
= reaches +2% after TX before rejection/stop.

VIX_WEAK_REJECT
= touches +X% but fails to reach +2% and rejects/falls.

VIX_STALL
= touches +X% but neither reaches +2% nor breaks stop in the evaluation window.

NO_VIX_ENTRY
= condition-captured stock never reaches +X%.
```

## Evidence table

```text
trade_date
condition_name
T_capture
breakout_threshold_pct
code
name
TX
entry_price
minutes_capture_to_TX
return_capture_to_TX
amount_capture_to_TX
amount_velocity_capture_to_TX
amount_rank_at_TX
tick_intensity_capture_to_TX
tick_rank_at_TX
pullback_depth_before_TX
high_hold_ratio_before_TX
first_reclaim_or_breakout_pattern
daily_breakout_reaccel_state
sector_leader_state
st_state_at_TX
post_TX_max_return_pct
post_TX_mae_pct
post_TX_plus2_success
post_TX_outcome_label
```

## Scorecard

For each condition formula, date, and breakout threshold X:

```text
candidate_count
breakout_threshold_pct
viX_entry_count
viX_entry_rate
viX_plus2_success_count
viX_plus2_success_rate
viX_reject_count
viX_reject_rate
avg_post_TX_max_return_pct
avg_post_TX_mae_pct
```

For threshold comparison:

```text
breakout_threshold_pct
entry_count
plus2_success_count
plus2_success_rate
reject_count
reject_rate
avg_mae
avg_max_return
missed_10pct_winners_due_to_higher_threshold
```

For Top-N filtering at TX:

```text
breakout_threshold_pct
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
The primary entry trigger is +X% breakout.

SuperTrend can be tested as one optional state variable at TX:

```text
st_state_at_TX
st_up_started_before_TX
st_up_bars_at_TX
st_line_distance_at_TX
```

The question is whether SuperTrend state improves post-TX continuation/rejection separation.

## Do not do

```text
Do not treat +10% as sacred. Test X as a variable.
Do not treat 09:05-only amount as enough evidence.
Do not mix post-TX outcome fields into pre-entry ranking.
Do not call a +X% touch successful unless post-TX continuation is measured.
Do not optimize a rule on one screenshot/day.
Do not force SuperTrend to be the main trigger when +X% is the actual entry event.
```

## Immediate next benchmark

```text
VIX Entry Continuation Benchmark v1
```

Output files:

```text
reports/vix_entry_continuation_benchmark_v1.csv
reports/vix_entry_threshold_comparison_v1.csv
reports/vix_entry_continuation_benchmark_v1.html
```

Core questions:

```text
1. Among condition-captured stocks that reach +X%, which T_capture-to-TX evidence separates +2% continuation winners from weak reject/stall cases?
2. Does a +12% entry reduce 10% liquidity-trap rejects enough to justify missing some earlier +10% winners?
3. Which breakout threshold X works best together with amount/tick/SuperTrend/sector evidence?
```
