# Leader Reaccel Early RSI Reclaim Correction 2026-05-14

Date: 2026-05-14
Repository: hoonoh57/Leader_Lab

## Issue found from chart review

Example:

```text
2026-01-05 / 014190 / 원익큐브
```

The generated detail sample selected:

```text
signal_time = 2026-01-05 11:55:00
entry_time  = 2026-01-05 12:00:00
rsi_prev    = 65.82
rsi_now     = 73.77
```

But visual chart review shows a much better entry zone around:

```text
around 11:40
RSI crossing above roughly 60
close already above 20MA
before the late 12:00 pullback zone
```

The same late-entry issue appears in 성문전자.

## Root cause

The first implementation was not wrong syntactically, but the default parameter was too late for the intended reacceleration entry.

The previous default was effectively:

```text
RSI reclaim level = 70
RSI cooldown level = 70
bar return threshold = 2 / 2.5 / 3
```

Therefore the script waited until RSI crossed 70, which can occur after the initial reacceleration has already moved too far.

## Correct interpretation

For Leader Reaccel, the key signal should be earlier:

```text
close > MA20
RSI cooled down first
RSI then reclaims 60 or 65
participation confirms
```

RSI 70 should be treated as a later high-momentum confirmation, not the primary early entry trigger.

## Corrected parameter family

Add early reclaim grid:

```text
RSI reclaim level: 60, 65, 70
RSI cooldown level: 50, 55, 60
cooldown lookback bars: 12, 24, 36
bar return min pct: 1.5, 2.0, 2.5, 3.0
```

Expected usage:

```text
Early entry candidate = RSI60 or RSI65 reclaim
Late confirmation = RSI70 reclaim
```

## Important strategy distinction

```text
RSI70_MA20_AMOUNT_BREAKOUT_v1
= high momentum confirmation, can be late.

Leader_Reaccel_EarlyReclaim_v1
= practical entry model, should catch RSI 60/65 reclaim after cooldown.
```

## Implementation decision

Create a dedicated runner:

```text
scripts/build_leader_reaccel_early_reclaim_v1.ps1
```

It uses the same engine:

```text
src/review/build_leader_reaccel_parametric_v1.py
```

but runs a better early-reclaim grid.

## Validation target

Check whether 원익큐브/성문전자 move from late signals such as 12:00/12:25 toward earlier signals near the first RSI60/65 reclaim zone.

Core comparison:

```text
Late RSI70 grid vs Early RSI60/65 grid
```

Metrics:

```text
entry_count
avg_realized_pnl_pct
profit_factor
avg_mae_pct
avg_mfe_pct
signal_time distribution
TopN daily result
```
