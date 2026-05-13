# VIX Entry + SuperTrend Hold Overlay v1

Date: 2026-05-13
Repository: hoonoh57/Leader_Lab

## Core premise

The breakout threshold X% is the entry trigger.

SuperTrend is not forced to be the entry trigger in this benchmark. Instead, it is tested as a sell-suppression / hold overlay:

```text
Enter near +X% breakout.
If the post-entry SuperTrend section remains strong/up, suppress premature profit-taking.
If SuperTrend weakens or turns down, allow exit by target/stop/trailing policy.
```

This reflects the intended live-trading use case: during a true strong SuperTrend section, avoid selling too early.

## Why this overlay matters

The previous VIX Entry Continuation benchmark used a fixed +2% target and a fixed stop. That is too restrictive for stocks that continue into a strong SuperTrend regime.

A realistic benchmark must compare:

```text
A. fixed target only
B. fixed target + stop sweep
C. SuperTrend hold overlay
D. SuperTrend hold overlay + stop/trailing sweep
```

The key question changes from:

```text
Did the stock give +2% after X%?
```

to:

```text
After X% entry, does SuperTrend identify the section where selling should be delayed?
```

## Event timeline

```text
T_capture = condition detection time, e.g. 09:05
TX        = first time stock reaches +X% from previous close
T_entry   = TX or the executable bar after TX
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

### P1. SuperTrend hold suppresses target sell

```text
entry = +X%
if SuperTrend is UP after entry:
    do not exit at +2%; hold until ST down or trailing stop
else:
    apply fixed target/stop baseline
```

### P2. SuperTrend hold with protective stop

```text
entry = +X%
while ST is UP:
    hold unless protective stop S is hit
exit when ST turns DOWN or trailing stop is hit
```

### P3. Hybrid partial sell

```text
entry = +X%
if +2% reached:
    sell partial quantity
    hold remainder while ST is UP
exit remainder on ST down/trailing stop
```

## Required benchmark metrics

For each X threshold, stop S, ST parameter, and exit policy:

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
ST_hold_exit_count
fixed_target_exit_count
stop_exit_count
```

## Required comparison

```text
P0 fixed +2% target baseline
vs
P1/P2/P3 SuperTrend hold overlay
```

A SuperTrend hold overlay is useful only if:

```text
1. avg_pnl_pct improves versus fixed +2% baseline,
2. total_pnl_pct improves,
3. MAE or loss frequency does not explode,
4. results remain stable across dates,
5. it works on the condition-captured source universe, not only on hand-picked charts.
```

## SuperTrend state features at and after entry

```text
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
Do not use SuperTrend future section labels to decide at entry.
Do not call ST hold useful because one chart held to the top.
Do not compare ST hold against an unrealistic fixed stop only.
Do not optimize X, S, ST period, and target all at once without versioned grids.
```

## Immediate next benchmark

```text
VIX Entry Stop Sweep + ST Hold Overlay v1
```

Output files:

```text
reports/vix_entry_stop_sweep_summary_v1.csv
reports/vix_entry_st_hold_overlay_summary_v1.csv
reports/vix_entry_st_hold_overlay_detail_v1.csv
reports/vix_entry_st_hold_overlay_v1.html
```

Core question:

```text
After +X% entry, does a SuperTrend UP section justify delaying the fixed +2% sell and produce better realized PnL under controlled stop/trailing rules?
```
