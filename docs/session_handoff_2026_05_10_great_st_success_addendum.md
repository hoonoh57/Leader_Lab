# Session Handoff Addendum — GREAT ST Early Signature Success

Date: 2026-05-10

## Must read first in next session

This document records the first clearly successful practical logic track in the Leader_Lab research sequence.

Before continuing SuperTrend-based entry logic, read:

```text
docs/success_great_st_early_signature_2026_05_10.md
docs/great_st_early_signature_discovery_plan.md
docs/session_handoff_2026_05_10_supertrend_regime_pivot.md
docs/todo_2026_05_10_research_track.md
```

---

## Current conclusion

The project has found a usable practical direction:

```text
Major uptrend sections can be labeled with SuperTrend regimes,
and GREAT regimes show strong early differences from BAD regimes within the first 1~3 bars.
```

This is not yet a finished buy strategy.

It is a successful answer-label and early-signature discovery:

```text
ST uptrend regime label
    -> GREAT / GOOD / BAD classification
    -> early 1~3 bar feature comparison
    -> clear GREAT-vs-BAD separation
```

---

## Exact successful run

Command:

```powershell
cd E:\2026\Leader_Lab
.\scripts\build_great_st_early_signature.ps1
```

Result:

```text
=== DONE build_great_st_early_signature ===
rows=25070
```

This converted 25,070 SuperTrend uptrend segment rows into early-signature rows.

---

## Core successful finding

### ST(7,2.0) GREAT vs BAD

GREAT:

```text
row_count = 559
avg_st_up_max_return_pct = 15.38%
avg_early1_high_return_pct = 2.06%
avg_early1_amount = 58.45억
avg_early2_high_return_pct = 4.73%
avg_early2_cum_amount = 113.70억
early2_break_start_high_rate = 69.77%
avg_early3_high_return_pct = 6.57%
avg_early3_cum_amount = 167.07억
early3_break_start_high_rate = 79.43%
```

BAD:

```text
row_count = 3351
avg_st_up_max_return_pct = 1.17%
avg_early1_high_return_pct = 0.64%
avg_early1_amount = 23.08억
avg_early2_high_return_pct = 0.92%
avg_early2_cum_amount = 38.66억
early2_break_start_high_rate = 36.05%
avg_early3_high_return_pct = 1.00%
avg_early3_cum_amount = 49.09억
early3_break_start_high_rate = 42.14%
```

Interpretation:

```text
GREAT ST regimes expand immediately after ST start.
BAD ST regimes do not.
```

---

## Successful logic principle

The correct idea is not:

```text
Buy every SuperTrend upturn.
```

The correct idea is:

```text
Detect whether a new SuperTrend uptrend segment is becoming a GREAT regime
by measuring the first 1~3 bars after ST start.
```

---

## Most important feature direction

### Strong positive early features

```text
early1_amount
early2_cum_amount
early3_cum_amount
early2_high_return_pct
early3_high_return_pct
early2_break_start_high
early3_break_start_high
early2_max_singlebar_return_pct
early3_max_singlebar_return_pct
```

### Important negative/penalty idea

```text
start_cum_amount is not simply good.
```

For ST(7,2.0):

```text
GREAT start_cum_amount = 116.78억
BAD   start_cum_amount = 293.78억
ratio = 0.40
```

Interpretation:

```text
If too much transaction amount already occurred before ST start,
the segment may be exhausted/late and more likely BAD.
```

---

## Rising-Embryo SuperTrend v0

The newly discovered logic concept is:

```text
Rising-Embryo SuperTrend v0

1. ST uptrend segment starts.
2. The segment is not already overheated/exhausted before ST start.
3. Within the first 1~3 bars:
   - transaction amount expands strongly,
   - high price expands strongly,
   - start bar high is broken,
   - early return remains positive.
4. This early signature is much more likely to become GREAT/GOOD than BAD.
```

---

## Candidate thresholds for first score experiment

These are not final trading rules. They are first hypotheses for score testing.

For ST(7,2.0):

```text
early1_amount >= 40억
early2_cum_amount >= 80억
early2_high_return_pct >= 3%
early3_cum_amount >= 100억
early3_high_return_pct >= 4~5%
early3_break_start_high = 1
start_cum_amount not overheated
```

---

## Immediate next stage

Next work item:

```text
GREAT ST Early Score v1
```

Goal:

```text
Convert early signature features into a rankable score.
```

Evaluation:

```text
For each trade_date and ST parameter:
    compute score for each active ST segment using only early available features
    rank Top1 / Top3 / Top5
    measure hit rate against GREAT and GOOD_OR_GREAT labels
```

Score components:

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

---

## Updated research stack

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

---

## Important warning for next session

Do not skip directly to live entry/exit simulation.

The next session should first build:

```text
sql/create_great_st_early_score.sql
src/analysis/build_great_st_early_score.py
scripts/build_great_st_early_score.ps1
```

Then evaluate:

```text
Top1 / Top3 / Top5 GREAT hit rate
Top1 / Top3 / Top5 GOOD_OR_GREAT hit rate
average st_up_max_return_pct by score bucket
false-positive BAD rate by score bucket
```

Only after that should entry timing and exit strategy be designed.
