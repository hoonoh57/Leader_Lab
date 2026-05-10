# Success Record — GREAT ST Early Signature Discovery

Date: 2026-05-10

## Status

```text
SUCCESS — first practical logic track for detecting major uptrend SuperTrend regimes.
```

This document records the first strong positive discovery in the current Leader_Lab research track.

The result must be referenced in future sessions before implementing any new SuperTrend-based entry logic.

---

## Executive summary

The project successfully created a practical research path for detecting major rising segments using SuperTrend.

The key discovery is:

```text
GREAT SuperTrend uptrend segments are not only identifiable after the full day.
They already show strong differences from BAD segments within the first 1~3 bars after ST uptrend start.
```

This means the project now has a realistic path toward:

```text
ST uptrend start
    -> early 1~3 bar signature
    -> GREAT / GOOD / BAD probability score
    -> practical major-uptrend candidate selection
```

---

## What was built

### 1. SuperTrend Regime Discovery

Purpose:

```text
Use SuperTrend as a regime label, not as a direct sell rule.
```

Core label:

```text
One row = one ST uptrend segment.
```

Quality labels:

```text
GREAT = ST uptrend segment reaches +10% or more
GOOD  = ST uptrend segment reaches +5% or more
BAD   = ST uptrend segment fails below +1% or ends negative
```

### 2. GREAT ST Early Signature Discovery

Purpose:

```text
Take the GREAT/GOOD/BAD answer labels and examine only information available at ST start or within the first 1~3 bars.
```

Implemented files:

```text
docs/great_st_early_signature_discovery_plan.md
sql/create_great_st_early_signature.sql
src/analysis/build_great_st_early_signature.py
scripts/build_great_st_early_signature.ps1
```

Tables:

```text
great_st_early_signature
great_st_early_signature_summary
great_st_early_signature_feature_diff
```

Command:

```powershell
cd E:\2026\Leader_Lab
.\scripts\build_great_st_early_signature.ps1
```

---

## Execution result

Latest run:

```text
=== DONE build_great_st_early_signature ===
rows=25070
```

This means 25,070 ST uptrend segment rows were converted into early signature rows.

---

## Representative result — ST(7, 2.0)

### GREAT group

```text
row_count = 559
avg_st_up_max_return_pct = 15.38%
avg_start_from_day_open_pct = 2.35%
avg_early1_high_return_pct = 2.06%
avg_early1_amount = 58.45억
avg_early2_high_return_pct = 4.73%
avg_early2_cum_amount = 113.70억
early2_break_start_high_rate = 69.77%
avg_early3_high_return_pct = 6.57%
avg_early3_cum_amount = 167.07억
early3_break_start_high_rate = 79.43%
```

### BAD group

```text
row_count = 3351
avg_st_up_max_return_pct = 1.17%
avg_start_from_day_open_pct = 1.57%
avg_early1_high_return_pct = 0.64%
avg_early1_amount = 23.08억
avg_early2_high_return_pct = 0.92%
avg_early2_cum_amount = 38.66억
early2_break_start_high_rate = 36.05%
avg_early3_high_return_pct = 1.00%
avg_early3_cum_amount = 49.09억
early3_break_start_high_rate = 42.14%
```

### Interpretation

Compared with BAD ST segments, GREAT ST segments show:

```text
1. early1_amount is about 2.5x larger.
2. early2_cum_amount is about 2.9x larger.
3. early3_cum_amount is about 3.4x larger.
4. early2_high_return_pct is about 5.1x larger.
5. early3_high_return_pct is about 6.6x larger.
6. early3_break_start_high_rate is about 79% vs BAD about 42%.
```

This strongly supports the idea that a major uptrend ST segment can be detected early by watching the first 1~3 bars after ST uptrend start.

---

## Most important discovery

### 1. start_cum_amount is not a positive filter by itself

For ST(7,2.0), GREAT has lower start cumulative amount than BAD:

```text
GREAT start_cum_amount = 116.78억
BAD   start_cum_amount = 293.78억
ratio = 0.40
```

Interpretation:

```text
Already-exhausted or overheated stocks before ST start are often BAD.
A good setup is not simply “large cumulative amount before ST start.”
```

### 2. early3_cum_amount is a strong positive early feature

For ST(7,2.0):

```text
GREAT early3_cum_amount = 167.07억
BAD   early3_cum_amount = 49.09억
ratio = 3.40
```

Interpretation:

```text
A strong amount surge after ST start is more important than large amount before ST start.
```

### 3. early3_high_return_pct is a direct expansion signal

For ST(7,2.0):

```text
GREAT early3_high_return_pct = 6.57%
BAD   early3_high_return_pct = 1.00%
ratio = 6.59
```

Interpretation:

```text
The first 3 bars after ST start already show whether the segment is expanding strongly or failing.
```

### 4. break_start_high confirms early expansion

For ST(7,2.0):

```text
GREAT early3_break_start_high_rate = 79.43%
BAD   early3_break_start_high_rate = 42.14%
```

Interpretation:

```text
GREAT segments frequently break the ST start bar high within 3 bars.
```

---

## Practical hypothesis v0

The first practical version of the rising-embryo SuperTrend hypothesis is:

```text
Rising-Embryo ST v0

1. ST uptrend segment starts.
2. The stock is not already exhausted before ST start.
3. Within 1~3 bars after ST start:
   - transaction amount increases sharply,
   - high price expands strongly,
   - start bar high is broken,
   - early return remains positive.
4. Such segments are much more likely to become GREAT or GOOD ST regimes.
```

Possible first thresholds for ST(7,2.0), subject to validation:

```text
early1_amount >= 40억
early2_cum_amount >= 80억
early2_high_return_pct >= 3%
early3_cum_amount >= 100억
early3_high_return_pct >= 4~5%
early3_break_start_high = 1
start_cum_amount not overheated
```

These are not final trading rules. They are candidate thresholds for the next scoring experiment.

---

## Why this is a successful logic discovery

Earlier failed/weak tracks tried to buy fixed 5-minute single-bar surges or basebar breakouts directly. Those entries were often late, overheated, or too sparse.

This discovery is stronger because it changes the unit of analysis:

```text
from: one candle event
  to: one SuperTrend uptrend regime
```

Then it asks:

```text
Can the first 1~3 bars of a new ST uptrend segment reveal whether it is likely to become a GREAT segment?
```

The first answer is positive.

This is the first practical path found so far for detecting major uptrend sections with SuperTrend.

---

## Required next stage

Next stage must be:

```text
GREAT ST Early Score v1
```

Goal:

```text
Convert early signature features into a score.
```

Proposed score components:

```text
StartPenalty
    - start_cum_amount overheated
    - start_from_day_open_pct overheated
    - start_from_day_low_pct overheated

EarlyPower
    + early1_amount
    + early2_cum_amount
    + early3_cum_amount

EarlyExpansion
    + early2_high_return_pct
    + early3_high_return_pct
    + early3_return_pct

BreakConfirm
    + early2_break_start_high
    + early3_break_start_high

SinglebarPower
    + early2_max_singlebar_return_pct
    + early3_max_singlebar_return_pct
```

Evaluation target:

```text
For each day and ST parameter:
    rank segments by GREAT_ST_EarlyScore_v1
    evaluate Top1 / Top3 / Top5 hit rate against GREAT and GOOD_OR_GREAT labels
```

---

## Must-reference rule

Before any future session implements ST-based entry/exit strategy, it must first read this document and use this result as the baseline.

Current research stack after this success:

```text
Experiment Registry
Winner Pattern Discovery
Winner Feature Score v1
Time-Aware Winner Feature Score v2
SuperTrend Regime Discovery
GREAT ST Early Signature Discovery  <-- SUCCESS
GREAT ST Early Score v1             <-- NEXT
Regime-aware entry/exit strategy
Macro/news/sector/LLM overlay
```
