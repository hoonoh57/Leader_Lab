# Winner Feature Score v1 Plan

## Purpose

Convert discovered winner/loser features into a reusable scoring layer.

This is not a direct buy strategy yet. It is a candidate ranking layer inside the same condition-search universe.

```text
condition-search candidates
    -> winner feature score
    -> daily rank
    -> chart review
    -> entry timing validation
```

## Source evidence

Winner Pattern Discovery v1 showed that actual winners differ from losers mainly by:

```text
1. intraday_amount_proxy
2. day_range_pct
3. first_hour_high_from_open_pct
4. singlebar_3pct_exists / 4pct / 5pct
5. radar_pullback_exists
6. best_radar_pullback_max_return_pct
```

It also showed that strong singlebar events and radar-pullback are useful features, not standalone buy triggers.

## Score components

### LeaderStrengthScore

```text
intraday_amount_score
first_hour_strength_score
day_range_score
singlebar_strength_score
```

### PullbackStructureScore

```text
radar_pullback_exists_score
best_radar_pullback_max_return_score
```

### CloseStrengthScore

```text
close_from_open_score
best_radar_pullback_close_return_score
```

### OverheatPenalty

```text
singlebar_6pct_penalty
max_5m_singlebar_from_open_penalty
max_5m_singlebar_from_low_penalty
```

## Total score

```text
winner_feature_score =
    LeaderStrengthScore
  + PullbackStructureScore
  + CloseStrengthScore
  - OverheatPenalty
```

## V1 scoring is deliberately simple

No machine learning is used in v1. The goal is to create an explainable baseline.

Later versions may use logistic regression, tree models, or LLM-assisted reasoning, but v1 must stay inspectable.

## Review goals

For each date:

```text
1. Are top-score candidates actual top-rank winners?
2. Do high-score losers expose missing risk features?
3. Does overheat penalty remove obvious chase entries?
4. Does radar-pullback improve score quality as a feature?
```

## Output

```text
winner_feature_score_result
winner_feature_score_summary
reports/winner_feature_score_dashboard.html
```

## Rule

Previous experiments remain reference assets. This scoring layer reuses them rather than replacing them.
