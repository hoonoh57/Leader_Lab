# GREAT ST Early Stock-Day Score v1 Plan

## Purpose

`GREAT ST Early Score v1` successfully ranked SuperTrend segment/parameter rows.

However, the same stock and same date can appear multiple times because the same move is detected by several ST parameter sets:

```text
ST(7,1.5)
ST(7,2.0)
ST(10,2.0)
ST(14,2.0)
```

This must not be treated as simple duplicate noise.

Important interpretation:

```text
If the same stock is detected by multiple SuperTrend parameter sets,
it may mean the move is confirmed across multiple trend sensitivities.
```

Therefore this stage is not just duplicate removal.

It is:

```text
Stock-day aggregation + Multi-Parameter Confirmation Analysis
```

---

## Key principle

### Wrong approach

```text
Same date + same stock appears under multiple ST parameters
-> remove duplicates and keep only one row
```

### Correct approach

```text
Same date + same stock appears under multiple ST parameters
-> keep one stock-day row
-> preserve the overlap as a confirmation feature
-> test whether higher overlap correlates with higher max return
```

The duplicate occurrence itself can be a signal.

---

## Input

```text
great_st_early_score_v1
```

One input row means:

```text
one ST segment + one ST parameter score
```

---

## Output

```text
great_st_early_stock_day_score_v1
great_st_early_stock_day_rank_v1
great_st_early_stock_day_summary_v1
great_st_param_confirmation_summary_v1
```

---

## Aggregation unit

One row per:

```text
trade_date + code
```

---

## Aggregation fields

### Basic identity

```text
trade_date
code
name
```

### Best parameter result

```text
best_score_total
best_st_period
best_st_multiplier
best_quality_label
best_st_up_max_return_pct
best_st_up_start_time
```

### Multi-parameter confirmation fields

```text
param_count
score_ge_80_param_count
score_ge_60_param_count
score_ge_40_param_count
great_param_count
good_or_great_param_count
bad_param_count
```

### Score aggregation fields

```text
param_score_max
param_score_avg
param_score_sum
param_score_top2_avg
param_score_top3_avg
```

### Outcome aggregation fields

```text
stock_max_return_pct = max(st_up_max_return_pct across ST params)
stock_best_quality_label
stock_has_great
stock_has_good_or_great
stock_has_bad
```

---

## Multi-Parameter Confirmation Analysis

The following correlation-style summaries are required:

```text
score_ge_80_param_count -> avg stock_max_return_pct / great_rate / bad_rate
score_ge_60_param_count -> avg stock_max_return_pct / great_rate / bad_rate
param_count             -> avg stock_max_return_pct / great_rate / bad_rate
great_param_count       -> avg stock_max_return_pct / great_rate / bad_rate
bad_param_count         -> avg stock_max_return_pct / great_rate / bad_rate
```

Example question:

```text
Do stocks captured by 3~4 high-score ST parameter sets have higher future max return than stocks captured by only one parameter?
```

If yes, then parameter overlap is a strong score feature.

---

## Final stock score v1

First version:

```text
base_score = max(score_total across ST params)
```

Multi-parameter confirmation bonus:

```text
strong_confirm_bonus = min(score_ge_80_param_count - 1, 3) * 4
mid_confirm_bonus    = min(score_ge_60_param_count - score_ge_80_param_count, 3) * 1.5
```

Bad penalty:

```text
bad_penalty = min(bad_param_count, 3) * 2
```

Final:

```text
stock_score_v1 = clamp(
    base_score
    + strong_confirm_bonus
    + mid_confirm_bonus
    - bad_penalty,
    0,
    100
)
```

Interpretation:

```text
A stock with one high-scoring ST parameter can be strong.
A stock with several high-scoring ST parameters is more strongly confirmed.
A stock with many BAD parameter rows receives a penalty.
```

---

## Evaluation

Daily ranking by:

```text
trade_date
```

Metrics:

```text
Top1 GREAT hit rate
Top1 GOOD_OR_GREAT hit rate
Top1 BAD rate
Top3 GREAT hit group rate
Top3 GOOD_OR_GREAT hit group rate
Top3 BAD candidate rate
Top5 metrics
average stock_max_return_pct
```

---

## Why this matters

Segment-level score already showed a strong result:

```text
ST(7,2.0) Top1:
GREAT hit group rate = 65.85%
GOOD_OR_GREAT hit group rate = 95.12%
BAD in Top1 rate = 3.66%
avg_top_st_up_max_return_pct = 13.12%
```

Stock-day aggregation with multi-parameter confirmation tests the more practical question:

```text
If the system recommends one or a few stocks per day,
and several ST parameter sets confirm the same move,
how often are those stocks real GREAT/GOOD candidates?
```

---

## Practical interpretation of ST parameter overlap

```text
ST(7,1.5) high score only
    = early/sensitive signal, possibly noisy

ST(7,2.0) also high score
    = short-term trend confirmation

ST(10,2.0) also high score
    = stronger trend continuity confirmation

ST(14,2.0) also high score
    = broader trend regime confirmation
```

Thus:

```text
Multi-parameter overlap is not duplication to discard.
It is a confirmation-strength signal.
```

---

## Expected command

```powershell
cd E:\2026\Leader_Lab
git pull
.\scripts\build_great_st_early_stock_day_score_v1.ps1
```
