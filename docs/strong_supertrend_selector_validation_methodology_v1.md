# Strong SuperTrend Selector Validation Methodology v1

Date: 2026-05-13
Repository: hoonoh57/Leader_Lab

## Purpose

The project is not searching for a vague high-profit trading rule.
The narrowed research problem is:

```text
Given all SuperTrend UP transition segments,
which observable pre/early evidence separates true strong SuperTrend regimes
from weak/false SuperTrend regimes?
```

SuperTrend remains a trading-event candidate generator. It is not discarded.
The validation target is the selection ratio improvement:

```text
Baseline: all SuperTrend UP segments
Filtered: SuperTrend UP segments passing a candidate evidence rule
Goal: increase GREAT/GOOD ratio and reduce BAD ratio without collapsing sample size.
```

## Non-negotiable rules

```text
1. Do not call a filter useful because one chart looks good.
2. Do not use post-entry or future fields in selector features.
3. Do not define HIT by visual overlap alone.
4. Do not patch arbitrary thresholds after seeing one failure.
5. Every selector version must be compared against the same baseline.
6. Every feature must be classified as PRE_T0, AT_T0, POST_T0_EARLY, or ANSWER_ONLY.
```

## Unit of analysis

One row = one SuperTrend UP transition segment.

Primary key:

```text
trade_date, code, st_period, st_multiplier, segment_no, st_up_start_time
```

T0:

```text
T0 = st_up_start_time
```

## Answer labels

Answer labels are derived from future segment outcome and are used only for evaluation.

```text
GREAT = st_up_max_return_pct >= 10
GOOD  = 5 <= st_up_max_return_pct < 10
BAD   = st_up_max_return_pct < 3 or end_return negative / fail label
MID   = all remaining cases
```

The exact thresholds can later be versioned, but they must be fixed before a benchmark run.

## Feature timing classes

```text
PRE_T0
= available before the ST UP transition candle starts.
Examples: prior daily structure, prior m30/h1 structure, cumulative amount before T0.

AT_T0
= available at the close of the ST transition candle.
Examples: T0 candle return, T0 amount, T0 range/body.

POST_T0_EARLY
= available within a fixed early confirmation window after T0, e.g. T0+1 to T0+3 bars.
Examples: post3 high-break count, post3 MFE/MAE.

ANSWER_ONLY
= future label or full-segment outcome.
Examples: st_up_max_return_pct, st_up_end_time, full segment amount.
```

Selector benchmarks must report which timing class they use.
PRE_T0 and AT_T0 are primary. POST_T0_EARLY is allowed only as a confirmation benchmark, not as a pre-signal benchmark.

## Evidence families to benchmark

### F1. Intraday leadership evidence

```text
first_bar_return_pct
first_bar_amount
cum_amount_at_0905 / 0910 / 0915 / 0920
cum_amount_vs_prev_day_same_time
cum_amount_percentile_Nd_same_time
amount_rank_in_candidate_universe
tick_intensity_rank_in_candidate_universe
```

Goal: identify the same-day leader before or near ST transition.

### F2. Participation / tick-intensity evidence

```text
tick_count_per_minute
up_tick_ratio
tick_amount_density
large_trade_frequency
candidate_universe_tick_rank
```

Goal: determine whether participation pressure is exceptional relative to other candidates.

### F3. Daily structural evidence

```text
prior_20d_high_distance_pct
prior_60d_high_distance_pct
breakout_after_pullback_state
base_candle_age
pullback_depth_after_breakout
daily_amount_rank_20d
prev_close_position_in_20d_range
```

Goal: distinguish prepared breakout/re-acceleration from random intraday noise.

### F4. Higher timeframe structure

```text
m30_range_break_state
m30_higher_low_state
h1_range_break_state
h1_higher_low_state
prev_day_high_reclaim_state
```

Goal: detect whether 5-minute strength is supported by larger structure.

### F5. Regime / anti-whipsaw evidence

These are benchmark candidates, not final answers.

```text
ADX level/slope
DI+ vs DI-
ATR/TR expansion
Choppiness / range-state proxy
moving-average slope / alignment
```

Goal: test whether public anti-whipsaw ideas actually improve GREAT/BAD separation in our data.

### F6. Sector/theme leadership evidence

```text
sector_amount_rank
sector_return_rank
same_sector_rising_count
leader_or_follower_lag_minutes
relative_strength_vs_sector
relative_strength_vs_index
```

Goal: identify true sector leaders versus late followers or isolated spikes.

## Statistical evaluation layers

### Layer A. Univariate association

For each feature and binary target, compute:

```text
point_biserial_corr(feature, GREAT_vs_not)
Spearman_corr(feature, st_up_max_return_pct)
mutual_information(feature, GREAT_vs_not)
ROC_AUC(feature_score, GREAT_vs_not)
```

Reason:
- Point-biserial correlation measures binary target vs continuous feature relation.
- Spearman handles monotonic but nonlinear relation.
- Mutual information can detect nonlinear dependency.
- ROC AUC measures ranking power independent of a single threshold.

### Layer B. Filter lift table

For every candidate filter threshold:

```text
coverage = passed_count / total_count
great_rate = GREAT_passed / passed_count
good_plus_rate = (GREAT+GOOD)_passed / passed_count
bad_rate = BAD_passed / passed_count
lift_great = great_rate / baseline_great_rate
bad_reduction = 1 - bad_rate / baseline_bad_rate
```

A filter is not useful unless it improves great_rate or good_plus_rate while reducing bad_rate at acceptable coverage.

### Layer C. Stability by time split

Do not random shuffle. Use chronological splits.

```text
Train: early period
Validation: middle period
Test: later period
```

For each feature/filter, report the same metrics by split.
A filter that works only in one split is marked unstable.

### Layer D. Combination benchmark

Only after univariate and filter-lift results exist:

```text
small rule set = 2 to 4 evidence families
simple interpretable scoring = weighted pass count or logistic model
```

No complex ML before stable evidence families are confirmed.

## Minimum output tables

### Table 1. answer_baseline_summary

```text
st_param
total_segments
great_count
good_count
bad_count
great_rate
good_plus_rate
bad_rate
median_max_return
```

### Table 2. feature_association_summary

```text
feature_name
timing_class
evidence_family
n_valid
point_biserial_great
spearman_max_return
mutual_info_great
roc_auc_great
train_auc
valid_auc
test_auc
status
```

### Table 3. filter_lift_summary

```text
filter_name
threshold
timing_class
coverage
great_rate
good_plus_rate
bad_rate
lift_great
bad_reduction
train_lift
valid_lift
test_lift
status
```

### Table 4. selector_version_registry

```text
selector_version
evidence_families
feature_list
thresholds
train_metrics
valid_metrics
test_metrics
status
next_action
```

## Pass/fail standard for a selector candidate

A selector candidate can be promoted only if:

```text
1. Uses no ANSWER_ONLY fields.
2. Has positive lift_great versus baseline.
3. Reduces bad_rate versus baseline.
4. Keeps enough coverage for practical review.
5. Holds directionally in validation/test periods.
6. Is interpretable as a structural reason, not only a numerical artifact.
```

## Execution sequence

```text
Step 1. Build SuperTrend segment baseline table.
Step 2. Build evidence table with timing_class metadata.
Step 3. Compute univariate association summary.
Step 4. Compute filter lift table.
Step 5. Review strongest and weakest evidence families.
Step 6. Register selector candidates only after stable evidence is found.
Step 7. Compare selector versions against the same baseline.
```

## Current next implementation target

```text
scripts/build_strong_supertrend_selector_benchmark_v1.ps1
src/review/build_strong_supertrend_selector_benchmark_v1.py
reports/strong_supertrend_selector_feature_association_v1.csv
reports/strong_supertrend_selector_filter_lift_v1.csv
reports/strong_supertrend_selector_benchmark_v1.html
```

This methodology replaces ad-hoc overlap HIT patching. v7-1 overlap outputs are diagnostic only and must not be used as success evidence.
