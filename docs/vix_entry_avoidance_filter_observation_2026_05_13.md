# VIX Entry Avoidance Filter Observation 2026-05-13

Date: 2026-05-13
Repository: hoonoh57/Leader_Lab

## Input benchmark

Universe:

```text
base_entry_count = 882
base_good_count = 473
base_bad_count = 405
base_good_rate = 53.63%
base_bad_rate = 45.92%
base_avg_mae = -5.77
base_avg_mfe = 10.05
```

The benchmark tested simple avoidance rules around the +10% TX breakout event.

## Strongest simple rule

```text
rule_name = NEXT3_HOLD_RATIO_GE_0_67
selected_entry_count = 425
avoided_entry_count = 457
selected_good_count = 290
selected_bad_count = 134
selected_good_rate = 68.24%
selected_bad_rate = 31.53%
collapse_avoid_rate = 66.91%
false_avoid_rate = 38.69%
selected_avg_mae = -4.68
selected_avg_mfe = 13.06
```

Interpretation:

```text
If, during the first 3 bars after TX, the stock keeps closing above the entry zone at least 2/3 of the time,
continuation quality improves materially.
```

This rule cuts many collapse/reject cases and improves both MAE and MFE, but it misses many good trades because confirmation occurs after TX.

## Strongest practical early validation rule

```text
rule_name = NEXT1_LOW_GE_MINUS_2
selected_entry_count = 590
selected_good_count = 380
selected_bad_count = 206
selected_good_rate = 64.41%
selected_bad_rate = 34.92%
collapse_avoid_rate = 49.14%
false_avoid_rate = 19.66%
selected_avg_mae = -4.80
selected_avg_mfe = 10.72
```

Interpretation:

```text
If the first bar after TX does not violate entry by more than -2%,
the entry is much safer while sacrificing fewer good trades.
```

This is more practical than NEXT3_HOLD_RATIO because it requires less waiting and has a lower false-avoid rate.

## Useful breakout-quality rules

```text
TX_CLOSE_ABOVE_ENTRY
selected_good_rate = 60.75%
selected_bad_rate = 38.91%
collapse_avoid_rate = 43.70%
false_avoid_rate = 24.74%
selected_avg_mae = -5.24
selected_avg_mfe = 11.11

NO_WICK_ONLY_BREAKOUT
selected_good_rate = 60.64%
selected_bad_rate = 39.02%
collapse_avoid_rate = 42.96%
false_avoid_rate = 24.10%
selected_avg_mae = -5.23
selected_avg_mfe = 11.04
```

Interpretation:

```text
A +10% breakout that closes above the entry zone is better than a wick-only touch.
However, the rule is weaker than next-bar validation.
```

## Weak or costly rule

```text
TX_UPPER_TAIL_LE_0_35
selected_good_rate = 54.93%
selected_bad_rate = 44.84%
collapse_avoid_rate = 52.84%
false_avoid_rate = 50.53%
```

Interpretation:

```text
Upper-tail filter alone removes too many good trades.
It should not be promoted as a standalone avoidance rule.
```

## Immediate conclusions

```text
1. Post-TX hold validation is more powerful than TX candle shape alone.
2. The best simple continuation evidence is not simply “10% touched”; it is whether the breakout zone is defended after TX.
3. NEXT3_HOLD_RATIO_GE_0_67 is the strongest quality filter but may be too delayed.
4. NEXT1_LOW_GE_MINUS_2 is the most practical first-stage avoidance filter.
5. TX_CLOSE_ABOVE_ENTRY / NO_WICK_ONLY_BREAKOUT can be used as lightweight entry-quality filters.
```

## Next benchmark

The next benchmark should compare three entry modes:

```text
M0: mechanical TX entry
M1: TX close-confirm entry
M2: next-bar validation entry
M3: next3 hold-confirm entry
```

Each mode should then be tested with:

```text
fixed +2 target / stop sweep
JMA profit-taking
JMA profit-taking suppressed by SuperTrend UP
SuperTrend DOWN final exit
```

The goal is to reduce reliance on -8% fixed tolerance by only entering breakouts that defend the breakout zone.
