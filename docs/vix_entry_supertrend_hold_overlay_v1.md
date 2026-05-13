# VIX Entry + JMA Profit Taking + SuperTrend Hold Overlay v1

Date: 2026-05-13
Repository: hoonoh57/Leader_Lab

## Core premise

The breakout threshold X% is the entry trigger.

SuperTrend is not forced to be the entry trigger in this benchmark. Instead, it is tested as a sell-suppression / hold overlay.

JMA is tested as the sensitive profit-taking trigger after a minimum profit zone is reached.

```text
Enter near +X% breakout.
After profit reaches target zone, watch sensitive JMA reversal.
If JMA turns down and SuperTrend is not UP, take profit.
If JMA turns down but SuperTrend is still UP, suppress premature sell and wait for the next JMA up/down cycle or a higher target.
If SuperTrend turns DOWN before the next target is achieved, exit.
```

This reflects the intended live-trading use case: JMA captures short-term exhaustion, while SuperTrend prevents selling too early during a true strong section.

## Why this overlay matters

The previous VIX Entry Continuation benchmark used a fixed +2% target and a fixed stop. That is too restrictive for stocks that continue into a strong SuperTrend regime.

A realistic benchmark must compare:

```text
A. fixed target only
B. fixed target + stop sweep
C. JMA profit-taking
D. JMA profit-taking + SuperTrend sell-suppression
E. SuperTrend down as final exit / dynamic stop substitute
```

The key question changes from:

```text
Did the stock give +2% after X%?
```

to:

```text
After X% entry, does JMA handle sensitive profit-taking while SuperTrend identifies the section where selling should be delayed?
```

## Event timeline

```text
T_capture = condition detection time, e.g. 09:05
TX        = first time stock reaches +X% from previous close
T_entry   = TX or the executable bar after TX
T_JMA_DN  = first JMA down-turn after profit zone
T_JMA_UP2 = next JMA up-turn while SuperTrend remains UP
T_ST_UP   = SuperTrend up-section start time around or after TX
T_ST_DOWN = SuperTrend down-transition after entry
T_exit    = exit time by selected policy
```

## Exit policy candidates

### P0. Fixed target / fixed stop baseline

```text
entry = +X%
target = +2%
stop = variable S
```

### P1. JMA profit-taking baseline

```text
entry = +X%
profit_trigger = variable P, e.g. +1.5%, +2%, +2.5%, +3%
if profit >= P and JMA turns DOWN:
    exit
if SuperTrend turns DOWN before profit trigger:
    exit
```

Purpose:

```text
Use sensitive JMA to avoid giving back a post-breakout gain.
```

### P2. JMA sell signal suppressed by SuperTrend UP

```text
entry = +X%
profit_trigger = variable P
if profit >= P and JMA turns DOWN:
    if SuperTrend is DOWN or neutral:
        exit
    if SuperTrend is still UP:
        suppress sell and continue holding
exit when SuperTrend turns DOWN
```

Purpose:

```text
Do not sell a true strong SuperTrend section just because short-term JMA temporarily bends down.
```

### P3. JMA cycle re-entry target while SuperTrend UP

```text
entry = +X%
profit_trigger_1 = P1, e.g. +2%
profit_trigger_2 = P2, e.g. +4% or trailing target

if profit >= P1 and JMA turns DOWN but SuperTrend is UP:
    hold
    wait for next JMA UP turn
    after next JMA UP, target P2 or trailing high
if SuperTrend turns DOWN before P2:
    exit on ST down
```

Purpose:

```text
In true leaders, use SuperTrend as the regime guard and JMA as the internal wave detector.
```

### P4. Hybrid partial sell + ST/JMA remainder hold

```text
entry = +X%
if profit >= P1 and JMA turns DOWN:
    sell partial quantity
    hold remainder while SuperTrend is UP
exit remainder on ST down, trailing stop, or next JMA down after higher target
```

Purpose:

```text
Realize some profit while preserving exposure to upper-limit/leader continuation.
```

## Stop handling

Fixed stop S is not the final answer. It is a benchmark variable.

SuperTrend down-transition is tested as a dynamic stop / exit substitute:

```text
fixed_stop_exit
vs
supertrend_down_exit
vs
hybrid: max tolerated MAE S while ST remains UP, then exit on ST down
```

The benchmark must report whether replacing fixed stop with ST-down improves total PnL without allowing intolerable drawdown.

## Required benchmark metrics

For each X threshold, profit trigger P, stop S, JMA parameter, ST parameter, and exit policy:

```text
entry_count
win_count
loss_count
stall_count
avg_pnl_pct
median_pnl_pct
total_pnl_pct
profit_factor
avg_holding_minutes
max_adverse_excursion_pct
max_favorable_excursion_pct
JMA_profit_exit_count
JMA_suppressed_sell_count
JMA_second_wave_success_count
ST_hold_exit_count
ST_down_exit_count
fixed_target_exit_count
fixed_stop_exit_count
```

## Required comparison

```text
P0 fixed +2% target baseline
vs
P1 JMA profit-taking
vs
P2/P3/P4 JMA + SuperTrend sell-suppression overlay
```

A JMA + SuperTrend overlay is useful only if:

```text
1. avg_pnl_pct improves versus fixed +2% baseline,
2. total_pnl_pct improves,
3. MAE or loss frequency does not explode,
4. JMA-suppressed sells actually lead to later higher exits often enough,
5. ST-down exits avoid severe giveback better than arbitrary fixed stops,
6. results remain stable across dates,
7. it works on the condition-captured source universe, not only on hand-picked charts.
```

## Indicator state features at and after entry

```text
jma_state_at_TX
jma_slope_at_TX
jma_down_after_profit_time
jma_next_up_time_after_suppressed_sell
jma_second_down_time

st_state_at_TX
st_up_started_before_TX
st_up_bars_at_TX
st_line_distance_at_TX
st_down_after_entry_time
st_up_duration_after_entry
st_up_max_return_after_entry
```

## Do not do

```text
Do not use future SuperTrend section labels to decide at entry.
Do not assume every JMA down-turn is a sell if SuperTrend is still UP.
Do not assume SuperTrend UP always justifies holding if MAE becomes extreme.
Do not call ST/JMA hold useful because one chart held to the top.
Do not compare ST/JMA hold against an unrealistic fixed stop only.
Do not optimize X, P, S, JMA period, ST period, and target all at once without versioned grids.
```

## Immediate next benchmark

```text
VIX Entry Stop Sweep + JMA Profit Taking + ST Hold Overlay v1
```

Output files:

```text
reports/vix_entry_stop_sweep_summary_v1.csv
reports/vix_entry_jma_st_hold_overlay_summary_v1.csv
reports/vix_entry_jma_st_hold_overlay_detail_v1.csv
reports/vix_entry_jma_st_hold_overlay_v1.html
```

Core question:

```text
After +X% entry, does sensitive JMA identify profit-taking waves, and does SuperTrend UP correctly suppress premature JMA sells so that strong sections are held longer and weak sections are exited earlier?
```
