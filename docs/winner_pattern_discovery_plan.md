# Winner Pattern Discovery Plan

## Purpose

Stop designing strategy from one magic intraday phenomenon.

The project's real advantage is:

```text
1. Six months of same-condition-search universe data.
2. Less than 50 candidates per day.
3. Actual large winners are included inside this filtered universe.
4. We can compare winners and losers in the same daily candidate pool.
```

Therefore the next research flow is winner-first:

```text
Actual winners -> common prior features -> loser comparison -> feature candidates -> backtest -> chart review.
```

## Core question

```text
Among all stocks captured by the same condition search,
what did actual +10% / TopN winners commonly have BEFORE they rose?
```

## Groups

### Winner groups

```text
W_TOP3: actual_rank <= 3
W_TOP5: actual_rank <= 5
W_TOP10: actual_rank <= 10
W_RET10: actual_max_after_return_pct >= 10
W_RET15: actual_max_after_return_pct >= 15
```

### Loser / avoid groups

```text
L_LOW3: actual_max_after_return_pct < 3
L_CLOSE_M3: close_return_pct <= -3
L_CLOSE_M5: close_return_pct <= -5
```

## Feature layers

### 1. Daily / swing context

These features answer whether the stock was structurally worth trading:

```text
prev5_high_break
prev10_high_break
prev20_high_break
prev5_volume_high
prev10_volume_high
prev20_volume_high
prev_day_close_up
downtrend_flag
ma5_above_ma20
ma20_slope_up
```

### 2. Intraday position and participation

```text
capture_from_day_open_pct
capture_from_day_low_pct
day_range_pct
first_hour_high_from_open_pct
intraday_amount_proxy
intraday_volume_proxy
```

### 3. Minute/radar behavior

```text
singlebar_2pct_exists
singlebar_3pct_exists
singlebar_5pct_exists
singlebar_max_return_pct
singlebar_max_from_day_open_pct
radar_pullback_candidate_exists
```

## Output

The first version produces:

```text
winner_pattern_feature_result
winner_pattern_feature_summary
reports/winner_pattern_discovery_report.html
```

The report must show:

```text
1. Feature prevalence in winners vs losers.
2. Difference score: winner_rate - loser_rate.
3. Candidate features worth backtesting.
4. Avoidance features that appear more often in losers.
```

## Principle

Previous experiments are preserved as reference assets. Nothing is thrown away.

Failed or weak logic is still useful when it explains:

```text
why direct entries fail,
why a feature is overheat-sensitive,
which chart state should be avoided,
which feature should become a filter instead of a trigger.
```
