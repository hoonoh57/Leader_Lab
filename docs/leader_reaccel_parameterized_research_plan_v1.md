# Leader Reacceleration Parameterized Research Plan v1

Date: 2026-05-14
Repository: hoonoh57/Leader_Lab

## Core direction

The practical main research line should move from first-spike VIX chasing to leader reacceleration.

Concept:

```text
A stock already showed strong operator/leader activity.
It cools down instead of being bought at the first spike.
Then it reaccelerates with renewed price, momentum, and participation evidence.
```

This fits the project's source condition universe because the condition formula already captures many high-potential leader candidates. The research task becomes selecting the cleanest reacceleration entries inside that universe.

## Why this is better than raw VIX entry

Raw VIX +10% entry can be contaminated by pre-09:00 or first-observable-bar extension. A stock may already be too high by the time reliable 5-minute OpenAPI candles are available.

Leader reacceleration avoids this structural weakness by requiring:

```text
prior strength
cooldown
reclaim/reacceleration
renewed participation
```

Instead of entering the first vertical move, it enters after a measurable reset and renewed leader behavior.

## Parameterized strategy family

Strategy family name:

```text
Leader_Reaccel_Parametric_v1
```

Base entry skeleton:

```text
1. trend reclaim condition
2. momentum reclaim condition
3. reacceleration candle condition
4. participation condition
5. prior leader/base-bar context condition
6. optional market/sector condition
```

## Parameter block A: trend reclaim

Initial condition:

```text
close > SMA20
```

Parameter candidates:

```text
SMA period: 10, 20, 30
EMA period: 10, 20
JMA state: JMA_UP / JMA slope > threshold
VWAP reclaim if available
```

Research variables:

```text
trend_type
trend_period
trend_buffer_pct
```

## Parameter block B: momentum cooldown and reclaim

Initial condition:

```text
RSI(14) was below 70, then crosses above 70
```

Parameter candidates:

```text
RSI period: 7, 14, 21
reclaim level: 60, 65, 70
cooldown level: 50, 55, 60, 65, 70
cooldown lookback bars: 3, 6, 12, 24
minimum bars after cooldown: 1, 2, 3
```

Research variables:

```text
rsi_period
rsi_reclaim_level
rsi_cooldown_level
rsi_cooldown_lookback_bars
bars_since_rsi_cooldown
```

## Parameter block C: reacceleration candle

Initial condition:

```text
single 5-minute candle return > 3%
```

Parameter candidates:

```text
single_bar_return_min_pct: 1.5, 2.0, 2.5, 3.0, 4.0
close_position_in_range >= 0.5, 0.6, 0.7
upper_tail_ratio <= 0.3, 0.4, 0.5
body_ratio >= 0.4, 0.5, 0.6
```

Research variables:

```text
bar_return_min_pct
close_position_min
upper_tail_max
body_ratio_min
```

## Parameter block D: participation / operator activity

Initial condition:

```text
bar amount >= 1B KRW OR cumulative amount >= 5B KRW
```

Alternative or additional variables:

```text
bar amount threshold: 0.5B, 1B, 2B, 3B
cumulative amount threshold: 3B, 5B, 10B, 20B
volume ratio to previous N bars
amount velocity rank inside condition-captured universe
tick intensity threshold if available
trade count / tick count if available
large-trade frequency if available
up-tick ratio if available
```

Research variables:

```text
participation_type
bar_amount_min
cum_amount_min
amount_velocity_min
volume_ratio_min
tick_intensity_min
tick_count_min
large_trade_count_min
```

## Parameter block E: prior leader / base-bar context

Initial condition:

```text
recent 5-day high-rise rate > 10%
```

Upgrade candidates:

```text
recent base-bar exists within N days
base-bar high breakout
base-bar close breakout
current cumulative amount / base-bar amount ratio
current cumulative amount / previous day amount ratio
current price above base-bar midpoint
prior leader day followed by cooling period
```

Research variables:

```text
lookback_days
high_rise_min_pct
basebar_min_return_pct
basebar_min_amount
basebar_break_type
basebar_amount_ratio_min
cooldown_after_basebar_min_bars
```

## Parameter block F: source condition compatibility

The source universe is important. The condition formula already captures candidate leaders.

Benchmark modes:

```text
A. source condition universe only
B. source condition + leader reaccel signal
C. source condition + leader reaccel score TopN
D. all-candle scan if performance permits
```

## Score formulation

The first score should not be overcomplicated.

Initial score:

```text
score =
  trend_score
+ rsi_reclaim_score
+ reaccel_candle_score
+ participation_score
+ basebar_context_score
- extension_risk_penalty
```

Each score block must be visible in the report so the result remains WYSIWYT.

## Benchmark outputs

```text
reports/leader_reaccel_parametric_detail_v1.csv
reports/leader_reaccel_parametric_summary_v1.csv
reports/leader_reaccel_parametric_daily_v1.csv
reports/leader_reaccel_parametric_grid_v1.csv
reports/leader_reaccel_parametric_v1.html
```

## Evaluation metrics

```text
entry_count
win_count
win_rate
loss_count
loss_rate
avg_realized_pnl_pct
total_realized_pnl_pct
profit_factor
avg_mfe_pct
avg_mae_pct
avg_holding_minutes
daily_positive_rate
max_daily_loss
TopN daily performance
```

## Research sequence

```text
Step 1. Add RSI cooldown-before-cross to existing RSI70_MA20_AMOUNT strategy.
Step 2. Add participation_type parameter: amount / volume / tick-intensity placeholder.
Step 3. Add base-bar context columns.
Step 4. Build small parameter grid, not a huge optimization grid.
Step 5. Promote stable versions into registry without deleting older successful versions.
```

## Versioning rule

Do not overwrite successful strategies.

Preserve:

```text
VIX_JMA_PARTIAL_TRAIL_v1
RSI70_MA20_AMOUNT_BREAKOUT_v1
Leader_Reaccel_RSI70_MA20_Amount_BaseBar_v1
Leader_Reaccel_Parametric_v1
```

Each improvement must be compared against prior baselines.
