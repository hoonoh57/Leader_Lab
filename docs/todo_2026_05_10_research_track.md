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

## Major pivot: SuperTrend Regime Discovery

### Status

```text
IN PROGRESS — warm-up correction and chart verification are the immediate priority.
```

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

## Implemented SuperTrend Regime Discovery assets

### Files already created

```text
docs/supertrend_regime_discovery_plan.md
sql/create_supertrend_regime_discovery.sql
src/analysis/build_supertrend_regime_discovery.py
scripts/build_supertrend_regime_discovery.ps1
src/review/generate_supertrend_regime_discovery_dashboard.py
scripts/build_supertrend_regime_discovery_dashboard.ps1
```

### Tables already created

```text
supertrend_regime_segment
supertrend_regime_summary
supertrend_regime_feature_summary
```

### Report

```text
reports/supertrend_regime_discovery_dashboard.html
```

---

## Current critical issue

### Problem

The analyzer was corrected to use prior intraday warm-up candles, but chart verification still showed the same early-session issue.

Observed issue:

```text
1. Strong early morning rise can be visually excluded from ST shaded segment.
2. ST segment shading may appear after the real early surge.
3. This makes Good/Bad ST review unreliable.
```

Root cause:

```text
SuperTrend/ATR must not be calculated from only current-day 09:00 candles.
For early-session indicator accuracy, prior-day or previous intraday 5-minute candles are required.
```

Analyzer correction already started:

```text
src/analysis/build_supertrend_regime_discovery.py
    --warmup-bars 80
    loads previous 5-minute candles before current-day 09:00
    calculates ATR/SuperTrend on warmup + current day
    stores only current-day ST uptrend segments
```

However, dashboard verification must also use the exact same principle:

```text
src/review/generate_supertrend_regime_discovery_dashboard.py
    must load warmup candles + current-day candles
    must draw warmup area before 09:00
    must draw day-open vertical line at 09:00
    must recalculate and render ST Up / ST Down lines using warmup + current-day candles
```

---

## Immediate next action for next session

### Step 0 — pull latest code

```powershell
cd E:\2026\Leader_Lab
git pull
```

### Step 1 — verify latest GitHub state

Check these files exist and include warm-up logic:

```text
src/analysis/build_supertrend_regime_discovery.py
src/review/generate_supertrend_regime_discovery_dashboard.py
scripts/build_supertrend_regime_discovery.ps1
scripts/build_supertrend_regime_discovery_dashboard.ps1
```

The dashboard generator must include:

```text
load_warmup_candles_for_segments(..., warmup_bars)
--warmup-bars argument
ST Up / ST Down line rendering
09:00 day-open vertical line
warmup region shading
```

### Step 2 — rerun analyzer

```powershell
.\scripts\build_supertrend_regime_discovery.ps1
```

Expected console markers:

```text
warmup_bars=80
=== DONE build_supertrend_regime_discovery ===
=== supertrend_regime_summary ===
```

### Step 3 — rerun dashboard

```powershell
.\scripts\build_supertrend_regime_discovery_dashboard.ps1
```

Expected console markers:

```text
=== DONE generate_supertrend_regime_discovery_dashboard ===
warmup_bars=80
Report: E:\2026\Leader_Lab\reports\supertrend_regime_discovery_dashboard.html
```

### Step 4 — visually validate

Open:

```text
reports/supertrend_regime_discovery_dashboard.html
```

Confirm:

```text
1. The chart includes previous-day/prior warmup candles before current day 09:00.
2. 09:00 is marked with a vertical dotted line.
3. ST Up and ST Down lines are visible.
4. The stored ST segment shading aligns with the visible ST Up line.
5. Early strong morning rise is no longer lost due to warm-up distortion.
6. If a segment begins after a huge early surge, confirm whether the DB segment itself starts late or only the visual layer was wrong.
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

## Latest observed 1st-pass warmup result

After warmup correction in the analyzer, the uploaded execution log showed changed segment counts and summaries.

Representative ST(7, 2.0) result:

```text
segment_count = 5772
gain3_rate = 36.33%
gain5_rate = 22.54%
gain10_rate = 9.68%
fail1_rate = 35.57%
end_negative_rate = 51.87%
GOOD_GAIN5 count = 1301
GREAT_GAIN10 count = 559
```

Feature separation remained strong:

```text
ST(7,2.0) segment_amount:
    Good avg = 537.7억
    Bad avg  = 102.1억
    Diff     = 435.6억

ST(7,2.0) st_up_bars:
    Good avg = 29.74 bars
    Bad avg  = 13.09 bars
```

Interpretation:

```text
Good ST regimes are still strongly associated with high internal segment amount and longer regime duration.
Start cumulative amount is not a simple positive filter; Bad regimes can have larger start_cum_amount, likely because they are late/overheated or noisy after prior activity.
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

But those come after ST regime discovery and chart validation.

---

## After SuperTrend Regime Discovery is visually validated

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

## Current priority

Do not move to entry/exit simulation yet.

Current priority is:

```text
Fix and verify SuperTrend warm-up chart consistency.
```

Only after the chart shows the same regime as the DB segment should the project proceed to Good ST Segment Similarity Score.
