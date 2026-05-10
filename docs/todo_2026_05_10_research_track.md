# TODO — 2026-05-10 Research Track

## Current major direction

The project has shifted from single-condition buy logic to cumulative feature-asset research.

The current high-level flow is:

```text
condition-search universe
    -> feature asset discovery
    -> winner/loser explanation score
    -> time-aware candidate score
    -> independent SuperTrend regime discovery
    -> regime-aware entry/exit strategy
    -> chart validation
```

## Completed baseline assets

### 1. Experiment registry

Status: DONE

Files:

```text
docs/experiment_registry.md
```

Purpose:

```text
Preserve every experiment, including weak/failed logic, as a future reference asset.
```

---

### 2. Winner Pattern Discovery

Status: DONE

Files:

```text
docs/winner_pattern_discovery_plan.md
sql/create_winner_pattern_discovery.sql
src/analysis/build_winner_pattern_discovery.py
scripts/build_winner_pattern_discovery.ps1
reports/winner_pattern_discovery_report.html
```

Purpose:

```text
Find which features separate actual winners from losers in the same condition-search universe.
```

Important result:

```text
intraday amount, first-hour strength, day range, singlebar 3~5%, and radar-pullback are useful winner-explaining features.
```

---

### 3. Winner Feature Score v1

Status: DONE

Files:

```text
docs/winner_feature_score_v1_plan.md
sql/create_winner_feature_score.sql
src/analysis/build_winner_feature_score.py
scripts/build_winner_feature_score.ps1
src/review/generate_winner_feature_score_dashboard.py
scripts/build_winner_feature_score_dashboard.ps1
reports/winner_feature_score_dashboard.html
```

Purpose:

```text
Convert discovered feature assets into an explainable full-day score.
```

Important caution:

```text
v1 is a discovery/explanation score, not a real-time trading score.
It uses full-day/future-aware values.
```

---

### 4. Time-Aware Winner Feature Score v2

Status: DONE

Files:

```text
docs/winner_feature_score_v2_time_aware_plan.md
sql/create_winner_feature_score_time.sql
src/analysis/build_winner_feature_score_time.py
scripts/build_winner_feature_score_time.ps1
src/review/generate_winner_feature_score_time_dashboard.py
scripts/build_winner_feature_score_time_dashboard.ps1
reports/winner_feature_score_time_dashboard.html
```

Purpose:

```text
Remove future-data leakage by scoring candidates only with candles available up to each decision timestamp.
```

Important result:

```text
09:20 / 09:30 / 10:00 etc. are useful diagnostic timestamps,
but they should not become magic strategy constraints.
```

Current interpretation:

```text
WinnerScoreTime v2 is a candidate selection diagnostic layer.
It is not yet the final entry/exit strategy.
```

---

## Major pivot added now

### SuperTrend Regime Discovery

Status: NEXT

This is now the next priority before building final entry/exit rules.

### Why this pivot is needed

The previous next step was almost:

```text
WinnerScoreTime v2 -> Exit Simulation
```

But that is too narrow because it may overfit to fixed decision times such as 09:30.

The better direction is:

```text
Study SuperTrend uptrend regimes independently across all candidates and all dates.
```

Purpose:

```text
Discover when SuperTrend uptrend segments are real high-profit trend regimes and when they are noisy sideways false regimes.
```

SuperTrend should first be used as a regime label, not as a direct sell rule.

---

## Next bundle to implement

### Bundle name

```text
SuperTrend Regime Discovery Bundle
```

### Required files

```text
docs/supertrend_regime_discovery_plan.md
sql/create_supertrend_regime_discovery.sql
src/analysis/build_supertrend_regime_discovery.py
scripts/build_supertrend_regime_discovery.ps1
src/review/generate_supertrend_regime_discovery_dashboard.py
scripts/build_supertrend_regime_discovery_dashboard.ps1
```

### Required tables

```text
supertrend_regime_segment
supertrend_regime_summary
supertrend_regime_feature_summary
```

### Required report

```text
reports/supertrend_regime_discovery_dashboard.html
```

---

## SuperTrend Regime Discovery requirements

### Analysis universe

Start with:

```text
condition-search captured stocks
all available dates
5-minute candles
```

Later extension:

```text
entire market universe
1-minute / 3-minute timeframe
```

### Parameters to test first

```text
ST(7, 1.5)
ST(7, 2.0)
ST(10, 2.0)
ST(14, 2.0)
```

### Segment unit

One row per:

```text
code + trade_date + supertrend parameter + uptrend segment
```

### Segment fields

```text
code
name
trade_date
timeframe
st_period
st_multiplier
segment_no
st_up_start_time
st_up_end_time
st_up_bars
st_up_start_price
st_up_max_price
st_up_end_price
st_up_min_price
st_up_max_return_pct
st_up_end_return_pct
st_up_max_drawdown_pct
```

### Start-state fields

```text
start_from_day_open_pct
start_from_day_low_pct
start_cum_amount
start_cum_volume
start_range_so_far_pct
start_high_so_far_from_open_pct
max_singlebar_return_before_start
singlebar_3pct_exists_before_start
singlebar_5pct_exists_before_start
```

### Segment internal fields

```text
segment_amount
segment_volume
segment_avg_amount_per_bar
segment_max_singlebar_return_pct
segment_green_bar_count
segment_red_bar_count
```

### Labels

```text
label_st_gain_3pct
label_st_gain_5pct
label_st_gain_10pct
label_st_fail_1pct
label_st_end_negative
```

---

## Questions this bundle must answer

```text
1. How many SuperTrend uptrend segments occur across the full period?
2. What percent of ST uptrend segments reach +3%, +5%, +10%?
3. Which ST parameter gives the best high-profit / low-noise balance?
4. What separates Good ST segments from Bad ST segments?
5. Do good ST segments start with higher cumulative amount?
6. Do good ST segments start from lower, less overheated positions?
7. Are singlebar/radar-pullback features common before good ST segments?
8. Is ST itself useful as a regime label before adding WinnerScore/JMA/news/sector features?
```

---

## Important conceptual rule

Do not frame this as:

```text
SuperTrend down -> sell strategy
```

Frame it as:

```text
SuperTrend uptrend segment -> measurable strong-regime label
```

Later sell strategies can use:

```text
TP inside ST regime
JMA after target profit
trailing stop inside ST regime
VI-aware cooldown
```

But those come after ST regime discovery.

---

## After SuperTrend Regime Discovery

### Next stage 1

```text
Good ST Segment Similarity Score
```

Goal:

```text
Score whether the current ST uptrend segment resembles historically profitable ST segments.
```

### Next stage 2

```text
WinnerScoreTime + Good ST Regime filter
```

Goal:

```text
Use WinnerScoreTime to select strong candidates,
and Good ST Regime features to decide whether the current trend segment is worth trading.
```

### Next stage 3

```text
ST + JMA profit strategy
```

Goal:

```text
If ST is rising, do not exit on weak JMA dips.
After target profit, use JMA down-turn or trailing logic for profit capture.
```

### Next stage 4

```text
Macro/context feature layer
```

Features:

```text
news exposure
leading sector
theme strength
KOSPI/KOSDAQ state
program net buy
foreign/institution behavior
LLM final judgment
```

---

## Immediate next action

Implement:

```text
SuperTrend Regime Discovery Bundle
```

Do this before adding more entry/exit strategy rules.

The goal is to build a reusable database of profitable and unprofitable SuperTrend uptrend regimes.
