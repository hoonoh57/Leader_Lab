# SuperTrend Segment Ranking Discovery v1.1 Plan

Date: 2026-05-11

## Purpose

v1 proved that early score has meaningful segment-selection power inside the same stock/date/ST-parameter group.

Key v1 result:

```text
score_rank1_is_return_rank1_rate
ST 7:1.5   71.17%
ST 7:2.0   79.69%
ST 10:2.0  78.91%
ST 14:2.0  77.61%
```

The strongest base parameter is currently:

```text
ST 7:2.0
score_rank1_is_return_rank1_rate = 79.69%
avg_return_rank_of_score_rank1   = 1.23
avg_score_rank1_return_pct       = 5.81%
```

This means:

```text
Inside the same stock/date/ST parameter, early score rank 1 often identifies the best realized-return ST segment.
```

However, v1 also showed that score-rank-1 by itself is not sufficient for live trading:

```text
ST 7:2.0 score rank 1
GREAT rate         = 18.48%
GOOD_OR_GREAT rate = 40.05%
BAD rate           = 41.92%
```

Interpretation:

```text
Segment score can choose the best segment inside a stock-day,
but the stock-day itself must first be a strong leader candidate.
```

Therefore v1.1 focuses on false positive analysis and state-label correction.

---

## Critical correction from v1

The v1 state label `WEAK_FOLLOW_THROUGH_ST` is semantically wrong.

Observed v1 result:

```text
ST 7:2.0 WEAK_FOLLOW_THROUGH_ST
row_count                 = 765
avg_st_up_max_return_pct  = 10.01%
median                    = 8.47%
GREAT rate                = 39.87%
GOOD_OR_GREAT rate        = 83.53%
BAD rate                  = 11.76%
```

This is not weak. It is the strongest detected state.

Correct interpretation:

```text
WEAK_FOLLOW_THROUGH_ST in v1 actually captured early expansion strength.
```

Rename/reclassify into:

```text
EARLY_EXPANSION_ST
FAILED_EARLY_EXPANSION_ST
```

---

## v1.1 objectives

### Objective 1 — rename and split early expansion states

Create a clearer segment state classifier:

```text
EARLY_EXPANSION_ST
    early high expansion is strong
    early return/close retention is not weak
    not exhausted

FAILED_EARLY_EXPANSION_ST
    early high expansion is strong
    but early return/close retention is weak
    or realized result becomes BAD

EXHAUSTED_ST
    start position is overheated
    or start cumulative amount is too large
    or late segment after earlier move

LOW_POWER_ST
    early amount and expansion are weak

NEUTRAL_ST
    otherwise
```

### Objective 2 — compare score-rank-1 GOOD/GREAT vs score-rank-1 BAD

The key comparison table:

```text
score_rank1 + GOOD_OR_GREAT
vs
score_rank1 + BAD
```

Compare:

```text
score_total
st_up_max_return_pct
st_up_bars
segment_no
st_up_start_time
start_from_day_open_pct
start_from_day_low_pct
start_cum_amount
early1_amount
early2_cum_amount
early3_cum_amount
early1_high_return_pct
early2_high_return_pct
early3_high_return_pct
early2_return_pct
early3_return_pct
early3_close_retention_ratio
early2_to_early3_amount_growth
```

### Objective 3 — prepare actionable filter candidates

The output should clearly identify:

```text
1. states to add bonus
2. states to penalize
3. states to reject
4. features that distinguish high-score BAD from high-score GOOD/GREAT
```

---

## Required new derived features

### early3_close_retention_ratio

Purpose:

```text
Detect whether early high expansion was maintained into the 3rd bar close.
```

Formula:

```text
early3_close_retention_ratio = early3_return_pct / early3_high_return_pct
```

If early3_high_return_pct <= 0, set NULL.

Interpretation:

```text
High value  = price expansion held into close
Low/negative value = high spike failed
```

### early2_to_early3_amount_growth

Purpose:

```text
Detect whether money flow continued from early2 to early3.
```

Formula:

```text
early2_to_early3_amount_growth = early3_cum_amount / early2_cum_amount
```

If early2_cum_amount <= 0, set NULL.

Interpretation:

```text
> 1.0 means cumulative amount continued expanding.
```

### st_start_minutes_from_open

Purpose:

```text
Distinguish 09:05 early leadership from late/exhausted ST starts.
```

Formula:

```text
minutes from 09:00 to st_up_start_time
```

---

## Output tables

```text
st_segment_ranking_v1_1
st_segment_ranking_state_summary_v1_1
st_segment_ranking_score_rank1_quality_compare_v1_1
st_segment_ranking_false_positive_examples_v1_1
```

---

## Success criteria

v1.1 is successful if it produces:

```text
1. A clearer high-performance early expansion state.
2. A measurable distinction between score-rank-1 GOOD/GREAT and score-rank-1 BAD.
3. Practical filter candidates for Actionable ST Segment Validation v1.
```

---

## Important interpretation

v1.1 is still not live trading validation.

It is a diagnostic analysis that prepares the live-style rule:

```text
Stock-Day Score filter
+ Segment Score rank/threshold
+ Early Expansion state
+ False Positive rejection
= Actionable ST Segment Validation v1 candidate rule
```

---

## Expected command

```powershell
cd E:\2026\Leader_Lab
git pull
.\scripts\build_supertrend_segment_ranking_discovery_v1_1.ps1
```
