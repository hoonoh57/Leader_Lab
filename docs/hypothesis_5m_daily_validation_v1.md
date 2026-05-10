# Hypothesis Validation v1: 5m Single-Bar Base and Daily Structure

This document locks the validation targets so execution does not drift from the original plan.

## Purpose

Validate whether the recurring chart patterns observed in Kiwoom 1516 performance-result stocks explain actual intraday leader returns.

The target is not a generic volume ranking. The target is:

```text
Condition-captured stocks
→ 5-minute single-bar strength / daily structure
→ breakout confirmation
→ actual max-return rank and post-breakout return
```

## 5-minute hypotheses

### H5M-1. Single 5m base bar + breakout + volume breakout

Definition:

```text
A 5-minute candle is a base bar if:
    singlebar_close_return_pct = (bar_close - bar_open) / bar_open * 100 >= 5

Valid breakout if a later candle:
    high > base_high or close > base_high

Volume breakout if the breakout candle:
    volume > base_volume
```

Metrics:

```text
has_singlebar_close5
break_base_high
break_volume_gt_base
break_after_max_return_pct
break_after_close_return_pct
actual_rank
in_actual_top10
```

### H5M-2. Single 5m base bar + RSI condition

Definition:

```text
singlebar_close_return_pct >= 5
AND later breakout of base_high
AND (RSI(14) > 60 OR RSI(14) > RSI(14)[1]) at breakout candle
```

Metrics:

```text
break_rsi14
break_rsi14_prev
rsi_gt_60
rsi_rising
```

### H5M-3. Single 5m base bar + price crosses MA10

Definition:

```text
singlebar_close_return_pct >= 5
AND later breakout of base_high
AND breakout_close > MA10
AND previous_close <= previous_MA10
```

Metrics:

```text
break_ma10
break_close_gt_ma10
break_close_cross_ma10
```

## Daily hypotheses

These are calculated only when `daily_candles` is available.

### D-1. Within recent 5 trading days: previous-day +10% move, high breakout, and 5m single-bar +3%

Definition:

```text
Within previous 5 daily candles before search_date:
    daily_close_return_pct >= 10

On search_date:
    intraday high breaks that strong daily candle high
    AND at least one 5m candle has singlebar_close_return_pct >= 3
```

### D-2. Within recent 10 trading days: high +20%, previous close rising, 5-day high, 5-day volume high

Definition:

```text
Within previous 10 daily candles before search_date:
    daily_high_return_pct >= 20
    previous close is rising
    day is 5-day high
    day is 5-day volume high
```

## Evaluation output

For every hypothesis:

```text
sample_count
actual_top10_count
hit_rate_to_actual_top10
avg_actual_max_return_pct
avg_break_after_max_return_pct
avg_break_after_close_return_pct
avg_break_after_drawdown_pct
win_rate_after_3pct
win_rate_after_5pct
win_rate_after_10pct
```

## Rule

Do not replace these hypotheses with generic liquidity baselines. Liquidity baselines are only secondary comparison features after these chart hypotheses are measured.
