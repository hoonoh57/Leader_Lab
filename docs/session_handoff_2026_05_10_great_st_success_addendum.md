# Session Handoff Addendum — GREAT ST Early Signature / Stock-Day Success

Date: 2026-05-10

## Must read first in next session

This document records the first clearly successful practical logic track in the Leader_Lab research sequence.

Before continuing SuperTrend-based entry logic, read:

```text
docs/success_great_st_early_signature_2026_05_10.md
docs/great_st_early_signature_discovery_plan.md
docs/great_st_early_score_v1_plan.md
docs/great_st_early_stock_day_score_v1_plan.md
docs/session_handoff_2026_05_10_supertrend_regime_pivot.md
docs/todo_2026_05_10_research_track.md
```

---

## Current conclusion

The project has found a usable practical direction:

```text
Major uptrend sections can be labeled with SuperTrend regimes,
GREAT regimes show strong early differences from BAD regimes within the first 1~3 bars,
and stock-day aggregation can compress daily candidates to Top1/Top3 leader candidates.
```

This is not yet a finished buy strategy.

It is a successful research chain:

```text
ST uptrend regime label
    -> GREAT / GOOD / BAD classification
    -> early 1~3 bar feature comparison
    -> GREAT ST Early Score v1
    -> stock-day aggregation with multi-parameter confirmation
    -> daily leader candidate Top1/Top3 validation
```

---

## Exact successful runs

### 1. GREAT ST Early Signature

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

### 2. GREAT ST Early Score v1

Command:

```powershell
.\scripts\build_great_st_early_score_v1.ps1
```

Strong segment-level result:

```text
ST(7,2.0) Top1:
GREAT hit group rate         = 65.85%
GOOD_OR_GREAT hit group rate = 95.12%
BAD in Top1 rate             = 3.66%
avg_top_st_up_max_return     = 13.12%
```

### 3. GREAT ST Early Stock-Day Score v1

Command:

```powershell
.\scripts\build_great_st_early_stock_day_score_v1.ps1
```

Strong stock-day result:

```text
Stock-Day Top1:
GREAT hit day rate          = 87.80%
GOOD_OR_GREAT hit day rate  = 96.34%
avg_top_stock_max_return    = 15.91%
```

Interpretation:

```text
Daily Top1 stock candidate selected by the current SuperTrend early score framework often contained a real major ST uptrend regime.
```

---

## Core successful finding

### ST(7,2.0) GREAT vs BAD early signature

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

Then practical stock selection is:

```text
Aggregate ST parameter/segment scores into stock-day candidates,
while preserving multi-parameter confirmation as a strength signal.
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

### Multi-parameter confirmation

Important principle:

```text
Same stock appearing across multiple ST parameters is not duplication noise.
It is a confirmation signal when the overlapping rows have high scores.
```

Use:

```text
score_ge_80_param_count
score_ge_60_param_count
good_or_great_param_count
great_param_count
param_score_top2_avg
param_score_top3_avg
```

Do not use simple raw `param_count` alone as a positive signal.

---

## Rising-Embryo SuperTrend v1

The newly discovered logic concept is:

```text
Rising-Embryo SuperTrend v1

1. ST uptrend segment starts.
2. The segment is not already overheated/exhausted before ST start.
3. Within the first 1~3 bars:
   - transaction amount expands strongly,
   - high price expands strongly,
   - start bar high is broken,
   - early return remains positive.
4. The same stock is confirmed by multiple high-scoring ST parameter rows.
5. This early signature is much more likely to become GREAT/GOOD than BAD.
```

Candidate ingredients:

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

These are not final live trading rules. They are validated score ingredients and candidate thresholds.

---

## How to use this successful logic in future sessions

### Research build chain

Run this chain when rebuilding the successful validation stack:

```powershell
cd E:\2026\Leader_Lab
.\scripts\build_supertrend_regime_discovery.ps1
.\scripts\build_great_st_early_signature.ps1
.\scripts\build_great_st_early_score_v1.ps1
.\scripts\build_great_st_early_stock_day_score_v1.ps1
```

Inspect these tables:

```text
great_st_early_stock_day_topn_summary_v1
great_st_param_confirmation_summary_v1
great_st_early_stock_day_rank_v1
great_st_early_stock_day_score_v1
```

### Date-input leader validation usage

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

## Current problem to fix before entry strategy

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
pure_bad_rate = true failure-risk candidate rate
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

## Immediate next stage

Next work item:

```text
GREAT ST Early Stock-Day Score v1.1
```

Goal:

```text
Separate pure_bad from mixed_good_bad,
correct the risk metric,
and preserve the strong Stock-Day Top1 GREAT/GOOD_OR_GREAT validation.
```

Recommended files to implement next:

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

## Updated research stack

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

---

## Important warning for next session

Do not skip directly to live entry/exit simulation.

Next session should first build v1.1 and verify:

```text
Top1 GREAT hit day rate
Top1 GOOD_OR_GREAT hit day rate
Top1 pure_bad_rate
Top1 mixed_good_bad_rate
Top3 / Top5 same metrics
average stock_max_return_pct
```

Only after v1.1 confirms the risk metric should entry timing and exit strategy be designed.
