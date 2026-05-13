# Condition Source Observation: 2026-05-13

Date: 2026-05-13
Repository: hoonoh57/Leader_Lab

## User observation

The current condition formula already captures high-price leaders even on weak market days.

Observed 1516 performance snapshots:

```text
2026-05-13 09:05: 30 candidates, 6 stocks reached +10% max return.
2026-05-12 09:05: 26 candidates, around 8 stocks reached +10% / upper-limit-class movement.
2026-05-11 09:05: 28 candidates, around 6 stocks reached +10%.
2026-05-08 09:05: 15 candidates, 5 stocks reached +10%.
2026-05-07 09:05: 16 candidates, 1 stock reached +10%; this may be a no-trade day.
2026-05-06 09:05: 30 candidates, 6 stocks reached +10%.
```

## Immediate implication

The source condition formula is not weak. It already has meaningful macro leader-capture ability.

The research problem must therefore be narrowed to:

```text
From the condition-captured candidate pool, select at most 6 tradable leaders per day.
```

This is not a full-market prediction problem.

## Key metrics to add

```text
condition_candidate_count
hit_10_count
macro_hit_rate_10pct = hit_10_count / condition_candidate_count
candidate_count_bucket
market_regime_bucket
top6_selection_hit_count
top6_selection_hit_rate
top6_capture_recall = top6_hit_count / hit_10_count
no_trade_day_flag
```

## Daily quality buckets

```text
STRONG_SOURCE_DAY
= hit_10_count >= 5 and macro_hit_rate_10pct >= 20%

NORMAL_SOURCE_DAY
= hit_10_count >= 3 and macro_hit_rate_10pct >= 10%

WEAK_SOURCE_DAY
= hit_10_count <= 1 or macro_hit_rate_10pct < 8%
```

2026-05-07 appears to be a WEAK_SOURCE_DAY candidate and should be studied as a no-trade / reduced-trade day.

## Revised workflow

```text
1. Measure condition-source macro hit rate by day.
2. Classify days into STRONG/NORMAL/WEAK source days.
3. Build Top6 selector only inside the daily condition candidate pool.
4. Evaluate whether Top6 captures most of the +10% leaders.
5. Only after Top6 leader selection, apply VI breakout / SuperTrend section trading logic.
```

## Why this matters

If a day has 26 to 30 candidates and 6 to 8 +10% leaders, the source condition is already valuable.
The downstream task is not to find every winner, but to rank the captured candidates so that the best 6 tradable stocks include the majority of the real leaders.

If a day has 16 candidates and only 1 +10% leader, the correct action may be no-trade or reduced allocation, not overfitting a selector.
