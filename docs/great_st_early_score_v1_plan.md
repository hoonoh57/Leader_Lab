# GREAT ST Early Score v1 Plan

## Purpose

`GREAT ST Early Signature Discovery` proved that GREAT SuperTrend uptrend regimes differ from BAD regimes within the first 1~3 bars after ST uptrend start.

This stage converts those early features into a simple explainable score and tests whether high-scoring segments actually rank near GREAT / GOOD_OR_GREAT outcomes.

This is still a research score, not a final live trading rule.

---

## Input table

```text
great_st_early_signature
```

One row means:

```text
one SuperTrend uptrend segment + its first 1~3 bar early features
```

Labels:

```text
GREAT = st_up_max_return_pct >= 10%
GOOD  = st_up_max_return_pct >= 5%
BAD   = st_up_max_return_pct < 1% or end negative
```

---

## Score design

Score v1 is intentionally simple and explainable.

### Components

```text
StartPenalty
    penalizes overheated/exhausted setup before ST start

EarlyPower
    rewards early transaction amount within first 1~3 bars

EarlyExpansion
    rewards early high-price expansion within first 1~3 bars

BreakConfirm
    rewards breaking the ST start bar high within 2~3 bars

SinglebarPower
    rewards strong single 5-minute candle inside first 2~3 bars
```

### Recommended first component weights

```text
StartPenalty     -20 max penalty
EarlyPower        30 max points
EarlyExpansion    30 max points
BreakConfirm      20 max points
SinglebarPower    20 max points
```

Total score:

```text
score_total = StartPenalty + EarlyPower + EarlyExpansion + BreakConfirm + SinglebarPower
```

Expected range:

```text
0 ~ 100 approximate
```

---

## First threshold assumptions for ST(7,2.0)

From the successful early signature result:

```text
early1_amount >= 40억
early2_cum_amount >= 80억
early3_cum_amount >= 100억
early2_high_return_pct >= 3%
early3_high_return_pct >= 4~5%
early3_break_start_high = 1
```

These are not hard trading rules. They are used to calibrate the first score.

---

## Required output tables

```text
great_st_early_score_v1
great_st_early_score_v1_daily_rank
great_st_early_score_v1_summary
```

---

## Evaluation questions

The score must answer:

```text
1. Do Top1 / Top3 / Top5 by score contain GREAT segments?
2. Do Top1 / Top3 / Top5 by score contain GOOD_OR_GREAT segments?
3. Does average st_up_max_return_pct rise by score bucket?
4. Does BAD false-positive rate fall as score bucket increases?
5. Which ST parameter works best for early score ranking?
```

---

## Ranking unit

Daily ranking should be grouped by:

```text
trade_date + st_period + st_multiplier
```

A future refinement can rank only segments after condition capture and before a live decision time. v1 simply ranks all discovered current-day segments to test whether the early signature score is directionally useful.

---

## Expected next command

```powershell
cd E:\2026\Leader_Lab
git pull
.\scripts\build_great_st_early_score_v1.ps1
```

---

## Success condition

The score is useful if:

```text
Top score buckets show higher average st_up_max_return_pct,
Top1/Top3/Top5 GREAT hit rate is materially higher than the base GREAT rate,
and BAD rate drops in high-score buckets.
```

If this passes, the next stage is:

```text
GREAT ST Early Score v1 dashboard
or
Regime-aware entry timing simulation
```
