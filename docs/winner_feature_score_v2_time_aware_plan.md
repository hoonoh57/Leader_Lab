# Time-Aware Winner Feature Score v2 Plan

## Purpose

Winner Feature Score v1 proved that the discovered features explain actual winners very well.

But v1 is not a live trading score because it uses full-day/future information.

V2 converts the same idea into a time-aware score:

```text
At a specific decision timestamp,
use only the data available up to that timestamp,
rank condition-search candidates,
then evaluate future outcome after that timestamp.
```

## Why v2 is necessary

V1 used some future-sensitive fields:

```text
full-day day_range_pct
full-day close_from_open_pct
full-day intraday_amount_proxy
full-day max_5m_singlebar_return_pct
future radar-pullback results
```

These are valid for feature discovery but not valid for real-time decision-making.

V2 removes this leakage.

## Decision timestamps

V2 starts with:

```text
09:20
09:30
10:00
10:30
11:00
13:00
```

Each timestamp is evaluated separately.

## Allowed features at timestamp T

```text
cum_amount_until_t
cum_volume_until_t
current_close_from_open_pct
high_so_far_from_open_pct
high_so_far_from_low_pct
range_so_far_pct
singlebar_2pct_exists_until_t
singlebar_3pct_exists_until_t
singlebar_4pct_exists_until_t
singlebar_5pct_exists_until_t
singlebar_6pct_exists_until_t
radar_pullback_exists_until_t
radar_pullback_best_max_return_until_t
current_overheat_from_open_pct
current_overheat_from_low_pct
```

## Forbidden features at timestamp T

```text
full-day close
future high after T
future low after T
future total amount
future singlebar events
future radar-pullback events
future best pullback outcome
```

## Score components

### LeaderStrengthScoreTime

```text
cum_amount_score
high_so_far_score
range_so_far_score
singlebar_strength_score_until_t
```

### PullbackStructureScoreTime

```text
radar_pullback_exists_until_t
radar_pullback_best_max_return_until_t
```

### CurrentStrengthScoreTime

```text
current_close_from_open_score
```

### OverheatPenaltyTime

```text
singlebar_6pct_exists_until_t
current_high_from_open_pct
current_high_from_low_pct
```

## Outcome after timestamp

For each candidate and timestamp:

```text
decision_price = close of the last 5m candle at or before timestamp
future_max_return_pct = max future high after timestamp / decision_price
future_close_return_pct = day close / decision_price
future_max_drawdown_pct = min future low after timestamp / decision_price
```

## Main validation questions

```text
1. At 09:30, does Score Top1/Top3 contain actual Top10 winners?
2. At 10:00, does precision improve while remaining early enough?
3. Does the score avoid future losers better than raw condition-search candidates?
4. Which timestamp has the best tradeoff between early entry and prediction accuracy?
5. Which high-score failures should become new penalty features?
```

## Output

```text
winner_feature_score_time_result
winner_feature_score_time_summary
reports/winner_feature_score_time_dashboard.html
```

## Rule

V2 is still a ranking/selection layer, not a final buy/sell strategy.

After v2 proves useful, entry timing and exit simulation are added separately.
