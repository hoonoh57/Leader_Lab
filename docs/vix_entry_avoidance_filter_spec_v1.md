# VIX Entry Avoidance Filter Spec v1

Date: 2026-05-13
Repository: hoonoh57/Leader_Lab

## Purpose

The stop sweep result showed that tight fixed stops create excessive rejection, while a very wide stop such as -8% improves simple expectancy.

This does not mean -8% is the desired live stop.
It means the current mechanical +10% entry still includes many stocks that collapse after entry.

The next task is to identify and filter post-breakout collapse patterns before using JMA/ST exit logic.

## Core problem

```text
Condition source captures candidates.
+X% breakout triggers entry.
But some +X% breakouts are liquidity traps or exhausted spikes.
```

Therefore, the strategy needs an avoidance filter:

```text
Enter +X% only when the breakout has continuation-quality evidence.
Avoid +X% entries that show collapse-prone evidence.
```

## Classification target

For every +X% breakout entry candidate:

```text
CONTINUATION
= reaches target/profit wave after TX without severe adverse move.

COLLAPSE_AFTER_TX
= falls deeply after TX, requiring wide stop such as -6%~-8% to survive.

REJECT_NEAR_TX
= fails near +X% and quickly loses the breakout zone.

STALL
= neither meaningful continuation nor immediate collapse.
```

## Avoidance evidence families

### A. Breakout candle quality

```text
TX candle close position within range
TX candle body ratio
TX candle upper-tail ratio
TX candle lower-tail ratio
TX candle closes above X% line or only wicks above it
```

Potential filter:

```text
Avoid if TX is wick-only breakout and close falls below X% zone.
```

### B. Immediate post-TX validation

```text
next_bar_low_vs_entry
next_bar_close_vs_entry
next_2bar_low_vs_entry
next_2bar_close_hold_count
post_TX_breakout_zone_hold_ratio
```

Potential filter:

```text
Avoid if first/second bar after TX closes below entry zone and SuperTrend is not strongly UP.
```

### C. Pre-TX path quality

```text
minutes_capture_to_TX
amount_capture_to_TX
amount_velocity_capture_to_TX
pullback_depth_before_TX
high_hold_ratio_before_TX
number_of_high_reclaims_before_TX
```

Potential filter:

```text
Avoid if TX occurs after weak, slow, low-amount drift or after excessive pullback/recovery failure.
```

### D. Liquidity / participation quality

```text
amount_rank_at_TX among captured candidates
amount_velocity_rank_at_TX
large_trade_frequency before TX
tick_intensity before TX
up_tick_ratio before TX
```

Potential filter:

```text
Avoid if +X% breakout happens without enough participation rank.
```

### E. Overextension / exhaustion risk

```text
open_to_TX_return
low_to_TX_return
capture_to_TX_return
number_of_consecutive_green_bars
single_bar_spike_pct
```

Potential filter:

```text
Avoid if +X% is reached by a single excessive spike with poor close hold.
```

### F. SuperTrend / JMA state at TX

```text
st_state_at_TX
st_line_distance_at_TX
st_up_bars_at_TX
jma_state_at_TX
jma_slope_at_TX
jma_recent_down_before_TX
```

Potential filter:

```text
Avoid if JMA is already down or SuperTrend is down/unstable at TX.
```

## Avoidance benchmark metrics

For each avoidance rule candidate:

```text
rule_name
rule_version
X
selected_entry_count
avoided_entry_count
continuation_kept_count
collapse_avoided_count
continuation_missed_count
false_avoid_rate
collapse_avoid_rate
selected_expected_pct_per_entry
baseline_expected_pct_per_entry
selected_mae_avg
baseline_mae_avg
```

A filter is useful only if:

```text
1. It removes a meaningful share of COLLAPSE_AFTER_TX / REJECT_NEAR_TX cases.
2. It does not remove too many CONTINUATION cases.
3. It reduces required stop width.
4. It improves expected return under realistic stop/JMA/ST exits.
```

## Required outputs

```text
reports/vix_entry_avoidance_feature_summary_v1.csv
reports/vix_entry_avoidance_rule_lift_v1.csv
reports/vix_entry_avoidance_benchmark_v1.html
```

## Implementation order

```text
Step 1. Add TX candle quality features.
Step 2. Add next 1~2 bar post-TX validation features.
Step 3. Label collapse/reject/continuation using post-TX MAE and target outcome.
Step 4. Build univariate rule-lift table.
Step 5. Promote only stable avoidance rules into the JMA/ST hold benchmark.
```

## Relationship with JMA/ST exit

Avoidance filter is upstream of JMA/ST exit.

```text
Condition source
→ +X% breakout event
→ avoidance filter
→ entry
→ JMA profit-taking / SuperTrend hold overlay
```

This prevents the system from relying on a wide -8% tolerance to survive bad entries.
