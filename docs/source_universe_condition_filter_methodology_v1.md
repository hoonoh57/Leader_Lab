# Source Universe / Condition Filter Methodology v1

Date: 2026-05-13
Repository: hoonoh57/Leader_Lab

## Why this document exists

Before testing SuperTrend selector logic, the source universe must be defined.
A weak source universe makes every downstream selector unstable.

The core research task is not:

```text
Find a magic profit rule from all stocks.
```

The correct task is:

```text
Build a source condition universe that already contains likely same-day leaders,
then improve the selection rate of true strong SuperTrend regimes inside that universe.
```

## Phase 0 objective: macro hit-rate improvement

The first objective is to improve the condition-search source itself.

Example:

```text
09:05 condition captures 40 stocks.
Among them, 5 later reach at least +10% max return.
Macro hit rate = 5 / 40 = 12.5%.
```

The upstream task is to raise this macro hit rate before applying any refined SuperTrend selector.

```text
condition_capture_count = number of stocks captured by the condition at the decision time
leader_hit_count = number of captured stocks whose future max return reaches the leader threshold
macro_hit_rate = leader_hit_count / condition_capture_count
```

A condition formula is useful only if it improves this rate while keeping enough candidates for practical trading.

## Critical timing correction: analyze the +10% breakout event window

Do not treat only 09:05 cumulative amount ratios as the main evidence.
The meaningful leader evidence must be measured up to the actual +10% breakout time, whenever it occurs.

For each captured candidate:

```text
T_capture = condition detection time, e.g. 09:05
T10 = first time when intraday high/current price reaches +10% from previous close
T_end = later evaluation horizon, e.g. 7h, day close, or VI-release-specific window
```

The key evidence window is:

```text
[T_capture, T10]
```

This window captures whether the stock accumulated enough participation, amount, and price-strength before the first VI/+10% breakout.

Separate analysis after T10:

```text
T10 -> VI release -> post-breakout movement
```

This post-10% movement is a separate strategy layer. It must not be mixed with the pre-10% leader-selection evidence.

## Fixed hypothesis

Every trading day has a limited number of true leaders.
They usually leave relative evidence before or near the +10% breakout and strong SuperTrend regime:

```text
1. exceptional trading amount accumulated before T10,
2. exceptional tick/participation intensity before T10,
3. high rank among same-day candidates before T10,
4. daily breakout / pullback / re-rise structure before the day starts or before T10,
5. sector/theme leadership or follower structure before and around T10.
```

Therefore, the first validation target is the condition-search source itself, and the second target is pre-T10 leader evidence.

## Source universe definition

Primary source universe candidates should be built from conditions such as:

```text
A. source condition universe
   stocks captured by the condition formula at T_capture, e.g. 09:05

B. +10% breakout universe
   among A, stocks whose intraday price reaches +10% at T10

C. pre-T10 amount-leader universe
   among B or A, rank by amount accumulated from T_capture to T10 and keep Top N

D. SuperTrend-transition universe
   among A/B/C, detect SuperTrend UP transition or near-transition state

E. structural re-rise universe
   daily breakout -> pullback -> re-rise candidates

F. sector/theme leadership universe
   leaders and followers inside same theme/sector strength cluster
```

The condition-search formula itself is not a minor detail. It is the upstream classifier.

## Condition-source scorecard

For each condition formula and each decision time, compute:

```text
condition_name
condition_version
trade_date
T_capture
candidate_count
leader_hit_count_5pct
leader_hit_count_10pct
macro_hit_rate_5pct
macro_hit_rate_10pct
candidate_median_future_max_return
candidate_avg_future_max_return
candidate_bad_count
candidate_bad_rate
amount_topN_overlap
st_up_overlap_count
st_strong_overlap_count
```

For the user's current reference example:

```text
condition_name = 1516 or candidate condition formula
trade_date = selected date
T_capture = 09:05
candidate_count = 40
leader_hit_count_10pct = 5
macro_hit_rate_10pct = 12.5%
```

The next condition formula is considered improved only if it raises macro_hit_rate_10pct or reduces bad_rate without collapsing candidate_count.

## Pre-T10 leader evidence scorecard

For each captured candidate that reaches +10%, compute evidence up to T10:

```text
trade_date
code
name
T_capture
T10
minutes_capture_to_T10
price_return_capture_to_T10
amount_capture_to_T10
amount_rank_among_candidates_at_T10
amount_velocity_capture_to_T10
amount_vs_prev_day_until_T10
amount_vs_recent_Nd_same_elapsed_time
tick_count_capture_to_T10
tick_intensity_capture_to_T10
tick_rank_among_candidates_at_T10
high_hold_ratio_before_T10
pullback_depth_before_T10
st_state_at_T10
st_up_started_before_T10
sector_rank_at_T10
leader_or_follower_at_T10
post_T10_max_return_pct
post_T10_plus2_success
```

Important:

```text
amount_vs_recent_Nd_same_elapsed_time
```

means comparison to the same elapsed intraday window, not a simple 09:05-only ratio.
For a stock that reaches +10% at 10:15, compare its accumulated amount until 10:15 with its historical same-elapsed-time amount distribution.

## Baseline comparisons

Compare at least these condition sources:

```text
B0: all SuperTrend UP segments
B1: existing 1516 captured candidates at T_capture
B2: B1 stocks that later reach +10%
B3: B2 ranked by pre-T10 accumulated amount Top N
B4: B3 + pre-T10 tick-intensity Top N
B5: B4 + daily breakout/pullback/re-rise structure
B6: B5 + sector/theme leader/follower classification
B7: B6 + SuperTrend UP/near-UP state before or at T10
```

The first report must show whether B1 already has useful macro hit rate, and whether pre-T10 amount/tick/daily/sector evidence improves leader selection.

## Why +10% breakout and pre-T10 amount Top N matter

A same-day leader is not defined only by return.
A leader usually dominates attention and liquidity before the first +10% breakout.

The first leader filter should therefore test:

```text
Among condition-captured stocks that later reach +10%,
which stocks ranked in the top N by accumulated amount and tick intensity before T10?
```

This helps separate real leaders from low-liquidity spikes and weak/late followers.

## Condition-search-first validation loop

```text
Step 1. Define source condition candidates at T_capture.
Step 2. For each date and T_capture, generate the captured candidate universe.
Step 3. Measure macro hit rate: +10% leaders / captured candidates.
Step 4. For +10% leaders, compute pre-T10 amount/tick/structure evidence.
Step 5. Test whether pre-T10 evidence ranks true post-T10 continuers above weak +10% touchers.
Step 6. Only inside the best source universe, test SuperTrend strong-regime selectors.
Step 7. Compare every selector against the same source-universe baseline.
```

## Required data

Already available or planned sources:

```text
performance_result / Kiwoom 1516 capture results
supertrend_regime_segment
daily_candles / intraday candles
condition-search candidate tables
intraday trading amount by time
optional tick-intensity tables
optional sector/theme mapping
```

## Do not do

```text
Do not treat 09:05 amount ratios as the main evidence when the stock reaches +10% much later.
Do not mix pre-T10 leader evidence with post-T10 VI-release movement.
Do not test a downstream SuperTrend filter without first recording its source universe.
Do not call a selector successful if the source condition already preselected only winners.
Do not mix full-market ST segments with condition-search candidates without labeling the universe source.
Do not optimize thresholds on one selected date.
Do not proceed to refined SuperTrend filtering until the macro hit rate of the source condition is known.
```

## Immediate next benchmark

```text
Condition Source + Pre-T10 Leader Evidence Benchmark v1
```

Output files:

```text
reports/condition_source_benchmark_v1.csv
reports/pre_t10_leader_evidence_v1.csv
reports/condition_source_benchmark_v1.html
```

Core questions:

```text
1. Which condition-search source most reliably contains the day's +10% leader candidates?
2. Among those +10% candidates, which pre-T10 amount/tick/structure evidence best separates true leaders from weak +10% touchers?
3. Which pre-T10 evidence works best with later SuperTrend section trading?
```

This source-universe and pre-T10 benchmark must come before any new Strong SuperTrend selector benchmark.
