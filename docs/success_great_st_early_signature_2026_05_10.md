# Success Record — GREAT ST Early Signature / Score / Stock-Day Validation

Date: 2026-05-10

## Status

```text
SUCCESS — first practical logic track for detecting major uptrend SuperTrend regimes and compressing them to daily Top1/Top3 stock candidates.
```

This document records the first strong positive discovery in the current Leader_Lab research track.

The result must be referenced in future sessions before implementing any new SuperTrend-based entry logic.

---

## Executive summary

The project successfully created a practical research path for detecting major rising segments using SuperTrend.

The core discovery is:

```text
GREAT SuperTrend uptrend segments are not only identifiable after the full day.
They already show strong differences from BAD segments within the first 1~3 bars after ST uptrend start.
```

Then the project successfully converted those early features into a score and stock-day ranking:

```text
ST uptrend start
    -> early 1~3 bar signature
    -> GREAT ST Early Score v1
    -> stock-day aggregation with multi-parameter confirmation
    -> daily Top1 / Top3 / Top5 leader candidates
```

The current strongest stock-day validation result is:

```text
Stock-Day Top1:
GREAT hit day rate          = 87.80%
GOOD_OR_GREAT hit day rate  = 96.34%
avg_top_stock_max_return    = 15.91%
```

This means the system entered a practical validation stage where a user can eventually input any date and retrieve the strongest leader candidate(s), then verify the expected profit section on a chart.

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

Important technical requirement:

```text
SuperTrend/ATR must be calculated with prior intraday warm-up candles.
Do not calculate early-session SuperTrend from current-day 09:00 only.
```

---

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

Latest known result:

```text
=== DONE build_great_st_early_signature ===
rows=25070
```

---

### 3. GREAT ST Early Score v1

Purpose:

```text
Convert early signature features into a rankable score.
```

Implemented files:

```text
docs/great_st_early_score_v1_plan.md
sql/create_great_st_early_score_v1.sql
src/analysis/build_great_st_early_score_v1.py
scripts/build_great_st_early_score_v1.ps1
```

Score components:

```text
StartPenalty
EarlyPower
EarlyExpansion
BreakConfirm
SinglebarPower
```

Strong segment-level validation example:

```text
ST(7,2.0) Top1:
GREAT hit group rate         = 65.85%
GOOD_OR_GREAT hit group rate = 95.12%
BAD in Top1 rate             = 3.66%
avg_top_st_up_max_return     = 13.12%
```

Interpretation:

```text
For segment/ST-parameter-level ranking, ST(7,2.0) Top1 already had very high GOOD_OR_GREAT hit rate and very low BAD rate.
```

---

### 4. GREAT ST Early Stock-Day Score v1 + Multi-Parameter Confirmation

Purpose:

```text
Aggregate duplicate ST parameter rows into one stock-day row,
but preserve the overlap as a confirmation signal instead of discarding it.
```

Implemented files:

```text
docs/great_st_early_stock_day_score_v1_plan.md
sql/create_great_st_early_stock_day_score_v1.sql
src/analysis/build_great_st_early_stock_day_score_v1.py
scripts/build_great_st_early_stock_day_score_v1.ps1
```

Tables:

```text
great_st_early_stock_day_score_v1
great_st_early_stock_day_rank_v1
great_st_early_stock_day_summary_v1
great_st_early_stock_day_topn_summary_v1
great_st_param_confirmation_summary_v1
```

Command:

```powershell
cd E:\2026\Leader_Lab
.\scripts\build_great_st_early_stock_day_score_v1.ps1
```

Latest known key result:

```text
Stock-Day Top1:
GREAT hit day rate          = 87.80%
GOOD_OR_GREAT hit day rate  = 96.34%
avg_top_stock_max_return    = 15.91%
```

Interpretation:

```text
After aggregating by trade_date + code, the daily Top1 stock candidate had an extremely high chance of containing a major ST uptrend regime.
```

---

## Representative result — ST(7, 2.0) Early Signature

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

## Most important discoveries

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

### 5. Multi-parameter confirmation is a signal, not duplication noise

Correct interpretation:

```text
If the same stock is detected by multiple SuperTrend parameter sets,
it may mean the move is confirmed across multiple trend sensitivities.
```

Wrong interpretation:

```text
Same stock appears multiple times, so remove duplicates and ignore overlap.
```

Correct use:

```text
Aggregate to one stock-day row,
but keep score_ge_80_param_count, score_ge_60_param_count, good_or_great_param_count, and related overlap metrics as confirmation features.
```

Observed direction:

```text
High-score ST parameter overlap generally increased GREAT probability and average max return.
```

---

## Practical hypothesis v1

The first practical version of the rising-embryo SuperTrend hypothesis is:

```text
Rising-Embryo ST v1

1. ST uptrend segment starts.
2. The stock is not already exhausted before ST start.
3. Within 1~3 bars after ST start:
   - transaction amount increases sharply,
   - high price expands strongly,
   - start bar high is broken,
   - early return remains positive.
4. The same stock is confirmed by multiple ST parameter sets.
5. Such stock-day candidates are much more likely to become GREAT or GOOD ST regimes.
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
score_ge_80_param_count as confirmation bonus
```

These are not final trading rules. They are validated score ingredients and candidate thresholds.

---

## How to use this successful logic

### For research continuation

Use this chain as the baseline:

```powershell
cd E:\2026\Leader_Lab
.\scripts\build_supertrend_regime_discovery.ps1
.\scripts\build_great_st_early_signature.ps1
.\scripts\build_great_st_early_score_v1.ps1
.\scripts\build_great_st_early_stock_day_score_v1.ps1
```

Then inspect:

```text
great_st_early_stock_day_topn_summary_v1
great_st_param_confirmation_summary_v1
great_st_early_stock_day_rank_v1
```

### For a date-input leader validation screen

Given a user-selected date:

```text
1. Query great_st_early_stock_day_rank_v1 for that date.
2. Show Top1 / Top3 / Top5 stocks by stock_score_v1.
3. Display score ingredients:
   - stock_score_v1
   - score_ge_80_param_count
   - score_ge_60_param_count
   - best_st_period / best_st_multiplier
   - best_st_up_start_time
   - best_early3_cum_amount
   - best_early3_high_return_pct
4. Open chart for selected stock.
5. Overlay:
   - prior warm-up candles
   - ST Up / ST Down
   - ST start
   - early 1~3 bar validation window
   - ST max return point
   - ST end
```

This creates the practical loop:

```text
Input date
    -> daily leader candidate Top1/Top3
    -> chart validation
    -> visible expected profit section
```

---

## Required next-stage correction

### Problem found in Stock-Day v1

`bad_candidate_rate` was inflated because current `stock_has_bad` means:

```text
The stock-day has at least one BAD ST segment under any parameter/segment.
```

But a GREAT stock can also contain some BAD ST segments during the day.

Example pattern:

```text
stock_best_quality_label = GREAT
stock_max_return_pct is very high
bad_param_count > 0
```

This is not a failed stock. It is a strong stock with noisy/failed sub-segments.

### Required v1.1 split

Add:

```text
stock_is_pure_bad
    = stock_has_good_or_great = 0 AND bad_param_count > 0

stock_is_mixed_good_bad
    = stock_has_good_or_great = 1 AND bad_param_count > 0
```

Replace misleading output:

```text
bad_candidate_rate
```

with:

```text
pure_bad_rate
mixed_good_bad_rate
```

Interpretation:

```text
pure_bad_rate = true failure risk candidate rate
mixed_good_bad_rate = strong stock that also had noisy BAD sub-segments
```

### Score v1.1 adjustment

Current bad penalty should be softened or changed:

```text
Do not penalize a stock harshly merely because it has BAD sub-segments if it also has GOOD/GREAT confirmation.
Penalize pure_bad more strongly.
```

Suggested v1.1 scoring:

```text
if good_or_great_param_count > 0:
    bad_penalty = min(bad_param_count, 3) * 0.5
else:
    bad_penalty = min(bad_param_count, 3) * 3.0
```

---

## Why this is a successful logic discovery

Earlier failed/weak tracks tried to buy fixed 5-minute single-bar surges or basebar breakouts directly. Those entries were often late, overheated, or too sparse.

This discovery is stronger because it changes the unit of analysis:

```text
from: one candle event
  to: one SuperTrend uptrend regime
  to: one stock-day leader candidate
```

Then it asks:

```text
Can the first 1~3 bars of a new ST uptrend segment reveal whether it is likely to become a GREAT segment?
Can multiple ST parameter confirmations improve stock-day leader ranking?
```

The first answer is strongly positive.

This is the first practical path found so far for detecting major uptrend sections with SuperTrend.

---

## Immediate next stage

Next stage must be:

```text
GREAT ST Early Stock-Day Score v1.1
```

Goal:

```text
Separate pure_bad from mixed_good_bad,
correct the risk metric,
and preserve the strong Stock-Day Top1 GREAT/GOOD_OR_GREAT validation.
```

Required files to implement next:

```text
sql/create_great_st_early_stock_day_score_v1_1.sql
src/analysis/build_great_st_early_stock_day_score_v1_1.py
scripts/build_great_st_early_stock_day_score_v1_1.ps1
```

After v1.1 passes, the next UI/report step is:

```text
Date-input Leader Validation Dashboard
```

It should allow:

```text
User enters a date
    -> system shows Top1/Top3 leader candidates
    -> user clicks stock
    -> chart displays ST regime, early 1~3 bar signature, max-return point, and likely profit section
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
GREAT ST Early Signature Discovery
GREAT ST Early Score v1
GREAT ST Early Stock-Day Score v1 + Multi-Parameter Confirmation  <-- SUCCESS
GREAT ST Early Stock-Day Score v1.1 pure/mixed BAD correction       <-- NEXT
Date-input Leader Validation Dashboard                              <-- NEXT UI
Regime-aware entry/exit strategy
Macro/news/sector/LLM overlay
```
