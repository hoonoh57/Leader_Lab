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

## Fixed hypothesis

Every trading day has a limited number of true leaders.
They usually leave relative evidence before or near the strong SuperTrend regime:

```text
1. exceptional intraday trading amount,
2. exceptional tick/participation intensity,
3. high rank among same-day candidates,
4. daily breakout / pullback / re-rise structure,
5. sector/theme leadership or follower structure.
```

Therefore, the first validation target is the condition-search source itself.

## Source universe definition

Primary source universe candidates should be built from conditions such as:

```text
A. high-price-expansion universe
   stocks whose intraday high reached at least +10% from previous close

B. amount-leader universe
   among A, rank by intraday trading amount and keep Top N

C. SuperTrend-transition universe
   among A/B, detect SuperTrend UP transition or near-transition state

D. structural re-rise universe
   daily breakout -> pullback -> re-rise candidates

E. sector/theme leadership universe
   leaders and followers inside same theme/sector strength cluster
```

The condition-search formula itself is not a minor detail. It is the upstream classifier.

## Condition-source scorecard

For each condition formula and each decision time, compute:

```text
condition_name
condition_version
trade_date
decision_time
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
decision_time = 09:05
candidate_count = 40
leader_hit_count_10pct = 5
macro_hit_rate_10pct = 12.5%
```

The next condition formula is considered improved only if it raises macro_hit_rate_10pct or reduces bad_rate without collapsing candidate_count.

## Baseline comparisons

Compare at least these condition sources:

```text
B0: all SuperTrend UP segments
B1: existing 1516 captured candidates
B2: +10% high reached stocks
B3: +10% high reached + amount Top N
B4: +10% high reached + amount Top N + ST UP transition
B5: daily breakout/pullback/re-rise + amount Top N + ST UP transition
B6: B5 + sector/theme leader/follower classification
```

The first report must show whether B1 already has useful macro hit rate, and whether B2/B3-style source filters improve it.

## Why +10% high and amount Top N matter

A same-day leader is not defined only by return.
A leader usually dominates attention and liquidity.

The first leader filter should therefore test:

```text
Among stocks that reached at least +10% intraday high,
which stocks ranked in the top N by trading amount?
```

This helps separate leader candidates from low-liquidity spikes and weak/late followers.

## Condition-search-first validation loop

```text
Step 1. Define source condition candidates.
Step 2. For each date and decision time, generate candidate universe from each source condition.
Step 3. Measure macro hit rate: leader hits / captured candidates.
Step 4. Measure whether the universe contains the day's amount/tick leaders.
Step 5. Only inside the best source universe, test SuperTrend strong-regime selectors.
Step 6. Compare every selector against the same source-universe baseline.
```

## Required data

Already available or planned sources:

```text
performance_result / Kiwoom 1516 capture results
supertrend_regime_segment
daily_candles / intraday candles
condition-search candidate tables
trading amount by time
optional tick-intensity tables
optional sector/theme mapping
```

## Do not do

```text
Do not test a downstream SuperTrend filter without first recording its source universe.
Do not call a selector successful if the source condition already preselected only winners.
Do not mix full-market ST segments with condition-search candidates without labeling the universe source.
Do not optimize thresholds on one selected date.
Do not proceed to refined SuperTrend filtering until the macro hit rate of the source condition is known.
```

## Immediate next benchmark

```text
Condition Source Benchmark v1
```

Output files:

```text
reports/condition_source_benchmark_v1.csv
reports/condition_source_benchmark_v1.html
```

Core question:

```text
Which condition-search source most reliably contains the day's true leader candidates
before applying any refined SuperTrend selector?
```

This source-universe benchmark must come before any new Strong SuperTrend selector benchmark.
