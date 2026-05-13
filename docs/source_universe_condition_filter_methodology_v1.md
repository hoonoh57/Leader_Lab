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

## Baseline comparisons

For each candidate condition-search source, compute:

```text
condition_name
trade_date
candidate_count
leader_capture_count
st_up_count
strong_st_count
bad_st_count
strong_st_rate
bad_st_rate
avg_forward_mfe
median_forward_mfe
amount_topN_overlap
```

Compare at least these baselines:

```text
B0: all SuperTrend UP segments
B1: existing 1516 captured candidates
B2: +10% high reached stocks
B3: +10% high reached + amount Top N
B4: +10% high reached + amount Top N + ST UP transition
B5: daily breakout/pullback/re-rise + amount Top N + ST UP transition
B6: B5 + sector/theme leader/follower classification
```

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
Step 2. For each date, generate candidate universe from each source condition.
Step 3. Measure whether the universe contains the day's real leaders.
Step 4. Only inside the best source universe, test SuperTrend strong-regime selectors.
Step 5. Compare every selector against the same source-universe baseline.
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
