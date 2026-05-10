# Experiment Registry

This project must not discard failed or weak logic.

Every evaluated idea becomes a reusable research asset:

```text
experiment -> result table -> summary table -> chart review -> conclusion -> next hypothesis
```

## Principle

A weak strategy is still useful if it tells us:

```text
1. which market state it works in,
2. which market state it fails in,
3. which feature separates winners from losers,
4. which chart pattern should be avoided.
```

Therefore, scripts and tables are preserved unless they are technically broken.

## Current Experiments

### 1. Hypothesis Validation v1

Purpose:

```text
Validate the original single 5-minute strong candle hypothesis.
```

Related assets:

```text
src/analysis/build_hypothesis_validation_v1.py
hypothesis_validation_v1_result
hypothesis_validation_v1_summary
```

Status:

```text
Useful as a leader-detection reference.
Not sufficient as a direct buy trigger.
```

Main lesson:

```text
Strong singlebar events can identify actual daily leaders,
but direct breakout entries are often too late or overheated.
```

---

### 2. Singlebar Threshold Sweep

Purpose:

```text
Test whether 3.0~6.0% singlebar thresholds should replace fixed 5%.
```

Related assets:

```text
src/analysis/build_singlebar_threshold_sweep_raw.py
singlebar_threshold_sweep_summary
```

Status:

```text
Useful for mapping singlebar strength vs overheat risk.
```

Main lesson:

```text
5.5~6.0% with RSI > 60 finds strong leaders,
but it often enters after excessive intraday rise.
```

---

### 3. Exit Strategy Simulation

Purpose:

```text
Test if high-confidence direct breakout entries can be converted into realized profit.
```

Related assets:

```text
src/analysis/build_exit_strategy_simulation_strict.py
src/analysis/build_exit_strategy_simulation_nextopen.py
src/analysis/build_exit_strategy_simulation_breakfill.py
exit_strategy_sim_result
exit_strategy_sim_summary
```

Status:

```text
Useful as a failed direct-entry reference.
```

Main lesson:

```text
The selected stocks were often actual leaders,
but direct entries after strong 5-minute moves had poor risk/reward.
```

---

### 4. Chart Review Bundle

Purpose:

```text
Make every statistical result visually inspectable.
```

Related assets:

```text
src/review/build_chart_review_case.py
src/review/generate_chart_review_dashboard.py
chart_review_case
reports/chart_review_dashboard.html
```

Status:

```text
Active validation layer.
```

Main lesson:

```text
WYSIWYG review is essential. Many numeric winners are visually late-entry or overheat cases.
```

---

### 5. Radar Pullback Entry Evaluation

Purpose:

```text
Use relaxed 2~4% radar candles to detect leaders,
then wait for pullback and re-expansion before entry.
```

Related assets:

```text
src/analysis/build_radar_pullback_entry_eval.py
radar_pullback_entry_result
radar_pullback_entry_summary
src/review/generate_radar_pullback_review_dashboard.py
reports/radar_pullback_review_dashboard.html
```

Status:

```text
Useful but not final.
Still needs whole-universe winner-first context.
```

Main lesson:

```text
Radar-Pullback improves opportunity count and reduces direct breakout chase risk,
but some entries remain too high or late.
```

## Next Research Direction

### Winner Pattern Discovery

Purpose:

```text
Instead of starting from one magic intraday phenomenon,
start from actual winners in the 6-month condition-search universe.
```

Core question:

```text
Among all stocks captured by the same condition search,
what did actual +10% / TopN winners commonly have BEFORE they rose?
```

Feature layers:

```text
1. Swing / daily structure
2. Intraday market participation
3. Minute-level entry timing
4. Avoidance patterns
```

Expected output:

```text
Reusable winner/loser feature map.
This becomes the new basis for strategy design.
```
