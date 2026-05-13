# VIX Entry JMA/ST Hold Overlay Observation 2026-05-13

Date: 2026-05-13
Repository: hoonoh57/Leader_Lab

## Input benchmark

Universe:

```text
condition-captured +10% breakout entries = 882
entry mode = M0-style early +10% threshold entry
JMA period = 7
JMA phase = 50
JMA power = 2
ST periods = 10, 14
ST multipliers = 2, 3
P1 values = 1.5, 2.0, 2.5, 3.0
P2 values = 4, 5, 6
```

## Best result

Best average realized PnL came from:

```text
exit_policy = P1_JMA_PROFIT
breakout_threshold_pct = 10
jma_period = 7
st_period = 14
st_multiplier = 3
profit_trigger_p1 = 3.0
profit_target_p2 = 4/5/6, irrelevant for P1
entry_count = 882
win_count = 558
win_rate = 63.27%
loss_count = 324
loss_rate = 36.73%
avg_realized_pnl_pct = +2.2937
total_realized_pnl_pct = +2023.03
profit_factor = 2.8782
avg_mfe_pct = 8.1884
avg_mae_pct = -4.5318
avg_holding_minutes = 71.66
```

## Policy ranking by best average PnL

```text
P1_JMA_PROFIT           best_avg = +2.2937, best_pf = 2.9121
P2_JMA_SUPPRESS_ST_UP   best_avg = +2.0275, best_pf = 2.4281
P0_FIXED_TARGET_STDOWN  best_avg = +1.8661, best_pf = 4.4896
P3_SECOND_WAVE_ST_HOLD  best_avg = +1.8601, best_pf = 2.3079
```

## Interpretation

The first validated dynamic exit result is:

```text
+10% fast entry
→ wait until profit reaches about +3%
→ then use JMA down-turn as the profit-taking trigger
→ use SuperTrend down as a fail/final exit guard
```

This outperforms the earlier mechanical fixed +2% target with wide -8% stop baseline.

Earlier best simple fixed stop result:

```text
M0 +10% entry, target +2%, stop -8%
avg expected per entry = +0.764
profit factor = 1.87
avg MAE = -5.77
```

Current best JMA policy:

```text
P1 JMA profit-taking with P1=3%
avg realized PnL = +2.294
profit factor = 2.878
avg MAE = -4.532
```

Therefore, JMA profit-taking substantially improves realized return and reduces average adverse excursion.

## Important caution

P2/P3 underperformed P1 in this run.
This does not mean SuperTrend hold is useless. It means the current implementation of sell suppression is too blunt:

```text
JMA down is suppressed whenever ST is UP,
then the position can wait too long until ST down or P2,
causing giveback.
```

The next version should test:

```text
1. P1 as the promoted baseline.
2. P2 only when the suppressed JMA sell had enough unrealized profit cushion.
3. P3 with trailing-high protection.
4. Partial sell at first JMA down, remainder held by ST.
```

## Promotion decision

Promote to candidate strategy:

```text
VIX_JMA_P1_v1
entry = +10% breakout
profit trigger = +3%
profit exit = first JMA down-turn after profit trigger
fail/final exit = SuperTrend down
JMA = 7/50/2
ST = 14/3 primary, 10/2 and 10/3 as comparison
```

Next benchmark:

```text
VIX_JMA_P1_vs_Partial_ST_Remainder_v1
```

Core question:

```text
Can partial profit at JMA down keep the strong P1 realized edge while allowing the remaining quantity to capture ST-led second waves?
```
