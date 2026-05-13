# VIX JMA Partial Profit + ST Remainder Spec v1

Date: 2026-05-13
Repository: hoonoh57/Leader_Lab

## Purpose

Previous benchmark promoted:

```text
VIX_JMA_P1_v1
entry = +10% breakout
profit trigger = +3%
profit exit = first JMA down-turn after profit trigger
fail/final exit = SuperTrend down
JMA = 7/50/2
ST = 14/3 primary
```

This produced materially better performance than fixed +2% target / -8% stop.

The next question is:

```text
Can we preserve the stable P1 JMA profit-taking edge,
while letting a remaining quantity participate in stronger SuperTrend continuation?
```

## Policy candidates

### PP0. Full JMA profit baseline

```text
entry at +X%
if profit >= P1 and JMA turns DOWN:
    sell 100%
if ST turns DOWN before JMA profit exit:
    sell 100%
```

This is the promoted VIX_JMA_P1_v1 baseline.

### PP1. Partial JMA profit + ST remainder

```text
entry at +X%
if profit >= P1 and JMA turns DOWN:
    sell Q% immediately
    keep (100-Q)% while ST remains UP
remainder exit:
    ST DOWN
    or next JMA DOWN after a second target P2
    or day end
```

### PP2. Partial JMA profit + second-wave target

```text
entry at +X%
if profit >= P1 and JMA turns DOWN:
    sell Q%
    keep remainder
if remainder reaches P2:
    sell remainder
else if ST turns DOWN:
    sell remainder
```

### PP3. Partial JMA profit + trailing remainder

```text
entry at +X%
if profit >= P1 and JMA turns DOWN:
    sell Q%
    keep remainder while ST UP
    track high after partial sell
if remainder falls by trailing T% from post-partial high:
    sell remainder
else if ST turns DOWN:
    sell remainder
```

## Variables

```text
X = breakout threshold, initially 10
P1 = first profit trigger, initially 3
Q = partial sell ratio: 0.3, 0.5, 0.7
P2 = second target: 4, 5, 6, 8
T = trailing giveback: 1, 1.5, 2, 3
JMA = 7/50/2 primary
ST = 14/3 primary, compare 10/2, 10/3, 14/2
```

## Evaluation metrics

For each policy and parameter set:

```text
entry_count
avg_realized_pnl_pct
total_realized_pnl_pct
profit_factor
win_rate
loss_rate
avg_mfe_pct
avg_mae_pct
avg_holding_minutes
partial_exit_count
remainder_st_down_exit_count
remainder_p2_exit_count
remainder_trailing_exit_count
```

## Promotion criteria

A partial-remainder policy can be promoted only if it beats PP0 on at least one of:

```text
1. avg_realized_pnl_pct
2. total_realized_pnl_pct
3. profit_factor with comparable total PnL
4. reduced giveback / lower avg MAE
```

and does not materially degrade daily stability.

## Immediate benchmark

```text
VIX_JMA_Partial_ST_Remainder_v1
```

Output files:

```text
reports/vix_jma_partial_st_remainder_detail_v1.csv
reports/vix_jma_partial_st_remainder_summary_v1.csv
reports/vix_jma_partial_st_remainder_daily_v1.csv
reports/vix_jma_partial_st_remainder_v1.html
```
