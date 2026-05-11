# SuperTrend Segment Ranking Discovery v1 Plan

Date: 2026-05-10

## Purpose

The previous research stages proved that:

```text
1. GREAT SuperTrend regimes exist.
2. GREAT regimes differ from BAD regimes within the first 1~3 bars.
3. Stock-Day Top1 leader selection is strong.
```

However, stock-day ranking alone is not enough for real trading validation.

The critical unresolved issue is:

```text
The same stock on the same date can have multiple SuperTrend uptrend segments.
If the analysis selects the best segment only after seeing the future, the result is not actionable.
```

Therefore this stage must analyze SuperTrend segments themselves.

Goal:

```text
For each trade_date + code, rank all ST uptrend segments by realized return and by early score.
Then verify whether early-score rank can identify the actual best-return segment without future data.
```

---

## Correct interpretation

### What Stock-Day Score proved

```text
The framework can identify which stock-day likely contains a major ST uptrend regime.
```

### What Stock-Day Score did NOT prove

```text
It did not prove that the system can choose the correct ST segment inside that stock-day.
```

Therefore:

```text
Stock-Day Score = leader candidate discovery
Segment Ranking = actionable regime selection discovery
```

Both are required.

---

## Input table

```text
great_st_early_score_v1
```

One row means:

```text
one ST uptrend segment under one ST parameter set
```

The input already contains:

```text
st_up_max_return_pct
st_up_end_return_pct
st_up_bars
score_total
score components
early 1~3 bar features
start state features
quality labels
```

---

## Ranking unit

```text
trade_date + code + st_period + st_multiplier
```

Within each group, rank segments by:

```text
1. realized return rank
   rank_return_in_stock_param
   = descending st_up_max_return_pct

2. early score rank
   rank_score_in_stock_param
   = descending score_total
```

Also aggregate across ST parameters later, but v1 must first keep parameter-level segment ranking clean.

---

## Main validation questions

### Question 1

```text
Inside the same stock/date/ST parameter,
is the early-score rank 1 segment also the realized-return rank 1 segment?
```

### Question 2

```text
Does early-score rank 1 have higher average return, GREAT rate, and GOOD_OR_GREAT rate than rank 2+?
```

### Question 3

```text
Which segment states should receive bonus or penalty?
```

---

## Required output tables

```text
st_segment_ranking_v1
st_segment_ranking_rank_summary_v1
st_segment_ranking_state_summary_v1
st_segment_ranking_alignment_summary_v1
```

---

## Core output fields

For each ST segment:

```text
score_id
signature_id
segment_id
trade_date
code
name
st_period
st_multiplier
segment_no
st_up_start_time
st_up_end_time
st_up_bars
quality_label
st_up_max_return_pct
st_up_end_return_pct
score_total
rank_return_in_stock_param
rank_score_in_stock_param
is_return_rank1
is_score_rank1
score_rank_matches_return_rank1
return_rank_of_score_rank1
segment_state_label
```

---

## Segment state labels

The first state classifier is intentionally simple and explainable.

### RISING_EMBRYO_ST

```text
score_total >= 80
AND early3_high_return_pct >= 4
AND early3_cum_amount is strong
AND early3_break_start_high = 1
AND early3_return_pct > 0
```

### WEAK_FOLLOW_THROUGH_ST

```text
early3_high_return_pct is high
BUT early3_return_pct <= 0 or weak
```

### EXHAUSTED_ST

```text
start_cum_amount too high
OR start_from_day_open_pct too high
OR start_from_day_low_pct too high
```

### LOW_POWER_ST

```text
early3_cum_amount weak
AND score_total low
```

### NEUTRAL_ST

```text
none of the above
```

These are not final trading labels. They are diagnostic labels to discover which states are profitable or dangerous.

---

## Required summaries

### Rank summary

Group by:

```text
st_period + st_multiplier + rank_score_in_stock_param
```

Metrics:

```text
row_count
avg_st_up_max_return_pct
median_st_up_max_return_pct
great_rate
good_or_great_rate
bad_rate
avg_score_total
return_rank1_rate
```

### State summary

Group by:

```text
st_period + st_multiplier + segment_state_label
```

Metrics:

```text
row_count
avg_st_up_max_return_pct
great_rate
good_or_great_rate
bad_rate
avg_score_total
```

### Alignment summary

Group by:

```text
st_period + st_multiplier
```

Metrics:

```text
stock_param_group_count
score_rank1_is_return_rank1_rate
score_rank1_is_good_or_great_rate
score_rank1_is_great_rate
avg_return_rank_of_score_rank1
```

---

## Success condition

This stage is successful if:

```text
1. rank_score_in_stock_param = 1 has materially higher return than rank 2+.
2. score-rank-1 frequently overlaps with return-rank-1.
3. RISING_EMBRYO_ST has high GREAT/GOOD_OR_GREAT rate.
4. EXHAUSTED_ST / WEAK_FOLLOW_THROUGH_ST / LOW_POWER_ST show lower returns or higher BAD rate.
```

If these conditions pass, then the next stage is:

```text
Actionable ST Segment Validation v1
```

---

## Important warning

This stage still uses realized returns for ranking comparison.

It must not be treated as live trading validation.

Its purpose is:

```text
Find which early-observable ST segment states correspond to high future returns.
```

The next stage must enforce:

```text
No future best-segment selection.
Only first qualified segment or live sequential selection.
```

---

## Expected command

```powershell
cd E:\2026\Leader_Lab
git pull
.\scripts\build_supertrend_segment_ranking_discovery_v1.ps1
```
