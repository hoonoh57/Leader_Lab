# VIX Preopen Gap Risk and Entry Correction v1

Date: 2026-05-14
Repository: hoonoh57/Leader_Lab

## Problem

The current VIX_JMA_PARTIAL_TRAIL_v1 benchmark assumes:

```text
entry = first +10% breakout from previous close
```

However, the live data environment can be different:

```text
Some stocks may already trade or move strongly before the OpenAPI 5-minute candle stream becomes reliable from 09:00.
If the stock is already +15% to +20% by the time 09:00+ 5-minute candles are available,
then a +10% trigger reconstructed from 09:00 candles is not a true early entry.
```

This creates a dangerous mismatch:

```text
Backtest entry = early +10% breakout
Live practical entry = already extended after pre-09:00 rise
```

In such cases, entering on the nominal +10% rule may actually mean entering into late-stage upward exhaustion and higher downside pressure.

## Correction principle

The strategy must distinguish:

```text
A. true first +10% breakout after observable session start
B. already-extended stocks at 09:00 or first available 5-minute bar
C. stocks whose +10% breakout occurred before reliable intraday candles are available
```

Do not treat B/C as normal VIX_JMA_PARTIAL_TRAIL_v1 entries.

## Required first-bar diagnostics

For each candidate/date, compute from first available 5-minute bar:

```text
first_bar_time
first_bar_open_return_from_prev_close_pct
first_bar_high_return_from_prev_close_pct
first_bar_close_return_from_prev_close_pct
first_bar_amount
first_bar_range_pct
preobservable_gap_proxy_pct
```

Where:

```text
preobservable_gap_proxy_pct = first_bar_open / previous_close - 1
```

This is not a full 08:00 tape reconstruction, but it detects whether the stock is already extended before the strategy can observe normal 5-minute evidence.

## Entry validity labels

```text
VALID_OBSERVABLE_VIX_ENTRY
= first available bar open is below the entry threshold zone, and +10% is reached later inside observable bars.

ALREADY_EXTENDED_AT_OPEN
= first available bar open is already above a defined extension threshold, e.g. +13%, +15%, +18%, +20%.

PREOBSERVED_BREAKOUT_RISK
= first available bar high/close suggests +10% occurred before reliable signal formation.

LATE_EXHAUSTION_RISK
= first available bar open/close is already very high and first 1-2 bars show weakness.
```

## Initial filter candidates

### F0. strict observable entry only

```text
Allow entry only if first available bar open return < +10%.
```

### F1. early-extension guard

```text
Avoid if first available bar open return >= +13%.
```

### F2. severe-extension guard

```text
Avoid if first available bar open return >= +15% or +18% or +20%.
```

### F3. open-extension + weakness guard

```text
Avoid if first available bar open return >= +13%
and first/second observable bar closes weak or breaks below first bar open.
```

### F4. open-extension score penalty

Instead of hard exclusion, assign a risk penalty:

```text
extension_risk_score = max(0, first_bar_open_return_pct - 10)
```

Use it for TopN selection / sizing:

```text
position_scale = lower when extension_risk_score is high
```

## Benchmark comparison

The next benchmark must split VIX_JMA_PARTIAL_TRAIL_v1 results into groups:

```text
Group A: first_bar_open_return < +10%
Group B: +10% <= first_bar_open_return < +13%
Group C: +13% <= first_bar_open_return < +15%
Group D: +15% <= first_bar_open_return < +18%
Group E: first_bar_open_return >= +18%
```

For each group, report:

```text
entry_count
avg_realized_pnl_pct
total_realized_pnl_pct
profit_factor
win_rate
loss_rate
avg_mfe_pct
avg_mae_pct
avg_holding_minutes
```

## Critical validation question

```text
Does VIX_JMA_PARTIAL_TRAIL_v1 edge come mostly from observable +10% entries,
or is it contaminated by stocks already extended before 09:00/first available candle?
```

If highly extended-at-open groups show poor expectancy or worse MAE, they must be excluded or sharply downweighted.

## Integration with current best strategy

Current promoted candidate:

```text
VIX_JMA_PARTIAL_TRAIL_v1
entry = +10% breakout
P1 = +3%
JMA = 7/50/2
ST = 14/3
partial sell = 30%
remainder = 70%
remainder exit = 1% trailing from post-partial high or ST down
```

Corrected live-safe version:

```text
VIX_JMA_PARTIAL_TRAIL_v1_1
= VIX_JMA_PARTIAL_TRAIL_v1
+ observable-entry validation
+ first-bar extension guard
```

## Immediate next benchmark

```text
VIX Preopen Gap Risk Split Benchmark v1
```

Output files:

```text
reports/vix_preopen_gap_risk_detail_v1.csv
reports/vix_preopen_gap_risk_summary_v1.csv
reports/vix_preopen_gap_risk_daily_v1.csv
reports/vix_preopen_gap_risk_v1.html
```

Core output:

```text
Compare VIX_JMA_PARTIAL_TRAIL_v1 performance by first available 5-minute bar open-return bucket.
```
