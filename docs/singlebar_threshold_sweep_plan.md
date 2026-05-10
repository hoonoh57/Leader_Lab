# Single-Bar Threshold Sweep Plan

## Purpose

The 5-minute single-bar rise threshold must not be hardcoded to 5%.

The current 5% value is an important discovered reference point, but market regime changes can require different thresholds:

```text
Strong market: many stocks may exceed 5%, so the threshold can be raised or combined with stricter filters.
Weak market: very few stocks exceed 5%, so 3%~4% may be more practical.
```

## Validation target

Sweep the single 5-minute candle open-to-close threshold and compare:

```text
3.0%
3.5%
4.0%
4.5%
5.0%
5.5%
6.0%
```

The core candle definition is:

```text
singlebar_close_return_pct = (bar_close - bar_open) / bar_open * 100
```

This must remain separate from day-open based metrics.

## Metrics

For each threshold and filter condition, measure:

```text
sample_count
avg_pass_per_day
active_days
actual_top10_count
hit_rate_to_actual_top10
avg_actual_max_after_return_pct
median_actual_max_after_return_pct
avg_break_after_max_return_pct
avg_break_after_close_return_pct
avg_break_after_max_drawdown_pct
win_rate_after_3pct
win_rate_after_5pct
win_rate_after_10pct
loss_rate_after_close_minus3pct
loss_rate_after_close_minus5pct
```

## Filter variants per threshold

```text
T_ONLY:
    singlebar_close_return_pct >= threshold

T_BREAK:
    T_ONLY + later base-high breakout

T_BREAK_VOL_03:
    T_BREAK + break_volume / base_volume >= 0.3

T_BREAK_VOL_05:
    T_BREAK + break_volume / base_volume >= 0.5

T_BREAK_VOL_07:
    T_BREAK + break_volume / base_volume >= 0.7

T_BREAK_VOL_10:
    T_BREAK + break_volume / base_volume >= 1.0

T_BREAK_RSI:
    T_BREAK + (RSI14 > 60 OR RSI14 rising)
```

## Selection rule

The best threshold is not the threshold with the most matches.

Preferred thresholds should satisfy:

```text
avg_pass_per_day between 0.5 and 3.0
win_rate_after_5pct high
loss_rate_after_close_minus5pct low
actual_top5/top10 inclusion meaningful
```

## Final use

The selected threshold should become a regime-sensitive parameter:

```text
bad market: 3.0~4.0
neutral market: 4.0~5.0
good market: 5.0~6.0+
```

The final trading UI must allow this threshold to be selected rather than hardcoded.
