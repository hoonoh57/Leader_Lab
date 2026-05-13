# VIX JMA Partial Profit + ST Remainder Observation 2026-05-13

Date: 2026-05-13
Repository: hoonoh57/Leader_Lab

## Input benchmark

```text
entry = +10% breakout
JMA = 7 / phase 50 / power 2
SuperTrend = 14 / 3
P1 = +3%
P2 = 4, 5, 6, 8
Q = 0.3, 0.5, 0.7
Trailing = 1, 1.5, 2, 3
entry_count = 882
```

## Previous baseline

```text
PP0_FULL_JMA_PROFIT
avg_realized_pnl_pct = +2.2937
total_realized_pnl_pct = +2023.03
profit_factor = 2.8782
win_rate = 63.27%
loss_rate = 36.73%
avg_mfe_pct = 8.1884
avg_mae_pct = -4.5318
avg_holding_minutes = 71.66
```

## Best new result

```text
policy = PP3_PARTIAL_TRAIL_REMAINDER
X = 10
P1 = 3
Q = 0.3
trail_pct = 1.0
entry_count = 882
win_count = 580
win_rate = 65.76%
loss_count = 302
loss_rate = 34.24%
avg_realized_pnl_pct = +2.7833
total_realized_pnl_pct = +2454.84
profit_factor = 3.5431
avg_mfe_pct = 8.2639
avg_mae_pct = -4.6232
avg_holding_minutes = 86.77
partial_exit_count = 739
remainder_st_down_exit_count = 49
remainder_trailing_exit_count = 710
```

## Improvement over PP0

```text
avg_realized_pnl_pct: +2.2937 -> +2.7833
total_realized_pnl_pct: +2023.03 -> +2454.84
profit_factor: 2.8782 -> 3.5431
win_rate: 63.27% -> 65.76%
loss_rate: 36.73% -> 34.24%
avg_holding_minutes: 71.66 -> 86.77
avg_mae_pct: -4.5318 -> -4.6232
```

## Policy ranking by best avg_realized_pnl_pct

```text
PP3_PARTIAL_TRAIL_REMAINDER: +2.7833
PP2_PARTIAL_P2_REMAINDER:    +2.3845
PP1_PARTIAL_ST_REMAINDER:    +2.3440
PP0_FULL_JMA_PROFIT:         +2.2937
```

## Interpretation

Partial profit plus trailing remainder is superior to full JMA profit-taking in this run.

Best candidate structure:

```text
1. Enter at +10% breakout.
2. When profit reaches +3% and JMA turns down, sell 30%.
3. Keep 70% remainder.
4. Trail the remainder from post-partial high with 1% giveback.
5. If SuperTrend turns down first, exit the remainder.
```

PP1 pure ST remainder hold is only slightly better than PP0 but has much longer holding time and worse MAE.

```text
PP1 best avg = +2.3440
avg_holding_minutes = 308.59
avg_mae_pct = -5.4734
```

Therefore, the remainder needs a trailing rule rather than ST-only holding.

## Promotion decision

Promote:

```text
VIX_JMA_PARTIAL_TRAIL_v1
```

Candidate definition:

```text
entry = +10% breakout
first profit trigger = +3%
JMA = 7/50/2
ST = 14/3
partial sell = 30% at first JMA down after P1
remainder = 70%
remainder exit = 1% trailing from post-partial high or ST down
```

Next benchmark:

```text
VIX_JMA_PARTIAL_TRAIL_v1 daily stability and TopN sizing benchmark
```
