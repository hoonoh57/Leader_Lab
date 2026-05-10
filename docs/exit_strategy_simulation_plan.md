# Exit Strategy Simulation Plan

## Purpose

The high-precision entry gate has found very selective candidates:

```text
A+ candidate:
    threshold_pct = 6.0
    filter_name = T_BREAK_RSI_GT60

A candidate:
    threshold_pct = 5.5
    filter_name = T_BREAK_RSI_GT60
```

The raw threshold sweep showed these candidates have high actual max-return potential, but many lose strength by close. Therefore the next goal is:

```text
Convert intraday max-return potential into realized profit with tested exit rules.
```

## Entry model

Entry is assumed at the detected breakout price after a single 5-minute base candle:

```text
singlebar_close_return_pct >= threshold_pct
later candle breaks base_high
RSI14 > 60 at breakout candle
entry_price = break_price
entry_time = break_time
```

This intentionally focuses on high-confidence candidates rather than high-frequency trading.

## Strategy families

### 1. Max-profit style

Goal: capture large intraday continuation.

Examples:

```text
TP10_SL3_TR5
TP12_SL4_TR5
TP15_SL5_TR7
TRAIL5_ONLY
TRAIL7_ONLY
```

### 2. Risk-reward style

Goal: maximize profit factor and expected value.

Examples:

```text
TP5_SL2
TP7_SL25
TP10_SL3
TP7_SL25_TR3
TP10_SL3_TR5
```

### 3. Stable target style

Goal: repeat smaller, reliable profits.

Examples:

```text
TP3_SL2
TP4_SL2
TP5_SL2
TP3_SL15_TIME6
TP5_SL2_TIME6
```

## Evaluation metrics

For each entry filter and exit strategy:

```text
sample_count
avg_return_pct
median_return_pct
win_rate
loss_rate
profit_factor
avg_win_pct
avg_loss_pct
max_loss_pct
avg_max_profit_before_exit_pct
avg_max_drawdown_before_exit_pct
avg_holding_bars
exit_reason_counts
```

## Primary selection criteria

### High return logic

```text
highest avg_return_pct
highest median_return_pct
acceptable max_loss_pct
```

### Best risk-reward logic

```text
highest profit_factor
avg_win / abs(avg_loss)
win_rate >= 45~55%
```

### Stable target logic

```text
win_rate high
loss_rate low
max_loss limited
avg_return positive
avg_holding_bars short
```

## Rule

No exit logic is accepted because it looks good on a chart. It must improve realized-return metrics over the high-confidence candidate set.
