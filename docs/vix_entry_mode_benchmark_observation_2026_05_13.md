# VIX Entry Mode Benchmark Observation 2026-05-13

Date: 2026-05-13
Repository: hoonoh57/Leader_Lab

## Input benchmark

Entry threshold:

```text
X = +10%
Target = +2%
Stop sweep = -1, -2, -3, -4, -5, -6, -8
```

Entry modes:

```text
M0_MECHANICAL_TX      = enter at +10% touch threshold
M1_TX_CLOSE_CONFIRM   = enter on TX candle close above threshold
M2_NEXT1_LOW_GUARD    = enter after next bar low does not violate -2% guard
M3_NEXT3_HOLD_CONFIRM = enter after next 3 bars show breakout-zone hold
```

## Best result by simple fixed target/stop

```text
M0_MECHANICAL_TX, stop=-8
entry_count = 882
win_count = 725
win_rate = 82.20%
loss_count = 97
loss_rate = 11.00%
expected_pct_per_entry = +0.764
profit_factor_simple = 1.87
avg_post_entry_mfe_pct = 10.05
avg_post_entry_mae_pct = -5.77
```

## Confirmation modes

### M3 next3 hold confirmation

```text
M3, stop=-8
entry_count = 537
win_rate = 76.91%
loss_rate = 10.99%
expected_pct_per_entry = +0.659
profit_factor_simple = 1.75
avg_post_entry_mfe_pct = 5.94
avg_post_entry_mae_pct = -6.31
```

M3 reduces trade count but does not materially reduce the -8 stop dependency. It also enters later, reducing available MFE.

### M2 next1 low guard

```text
M2, stop=-8
entry_count = 590
win_rate = 75.93%
loss_rate = 13.39%
expected_pct_per_entry = +0.447
profit_factor_simple = 1.42
avg_post_entry_mfe_pct = 6.31
avg_post_entry_mae_pct = -6.48
```

M2 is useful as an avoidance observation, but when converted into delayed entry, it reduces expected return compared with M0.

### M1 TX close confirmation

```text
M1, stop=-8
entry_count = 586
win_rate = 61.09%
loss_rate = 30.89%
expected_pct_per_entry = -1.249
profit_factor_simple = 0.49
avg_post_entry_mfe_pct = 7.98
avg_post_entry_mae_pct = -7.86
```

M1 is not a good standalone entry mode. Entering at TX close after confirmation appears too late or selects many already-exhausted closes.

## Interpretation

The entry-mode benchmark shows:

```text
1. The previous avoidance rules are useful as risk-quality diagnostics.
2. Turning those diagnostics into delayed entry modes reduces the available post-entry MFE.
3. M0 remains the best simple fixed target/stop baseline, but only with an unrealistically wide -8 stop.
4. Confirmation modes alone do not solve the problem.
```

Therefore the next stage should not keep adding entry-delay filters. The project should move to dynamic exit:

```text
M0 or near-M0 entry
+ JMA profit-taking after profit trigger
+ SuperTrend UP sell-suppression
+ SuperTrend DOWN final exit
```

## Next benchmark

```text
VIX Entry + JMA Profit Taking + SuperTrend Hold Overlay v1
```

Core question:

```text
Can JMA/ST exit management keep the M0 early-entry advantage while reducing reliance on -8% fixed stop?
```
