# VIX Entry JMA + SuperTrend Exit Policy Spec v1

Date: 2026-05-13
Repository: hoonoh57/Leader_Lab

## Purpose

This document fixes the intended sell logic for the VIX breakout strategy.

Entry is triggered by +X% breakout.
Exit is not a fixed +2% sell. Exit is controlled by sensitive JMA reversal and SuperTrend regime state.

## Referenced JMA behavior

The user's VB.NET JMA class calculates:

```text
jma()
up()
down()
slope()
```

The JMA state is interpreted as:

```text
JMA_UP   = up(i) is valid, down(i) is NaN
JMA_DOWN = down(i) is valid, up(i) is NaN
JMA_FLAT = both are NaN or unchanged fallback state
```

The slope is:

```text
slope(i) = round((jma(i) / jma(i-1) - 1) * 100, 1)
```

For benchmark stability, JMA state must be recomputed per code/date/parameter set without cross-symbol cache contamination.

## Entry event

```text
T_capture = condition detection time, e.g. 09:05
X         = breakout threshold variable, e.g. 10, 11, 12, 13
TX        = first time price reaches +X% from previous close
entry     = around TX or the next executable bar after TX
```

## Exit policy JMA_ST_P1

Baseline JMA profit-taking:

```text
if unrealized_profit_pct >= P and JMA turns DOWN:
    exit
elif SuperTrend turns DOWN before P:
    exit
```

Variables:

```text
P = profit trigger, e.g. 1.5, 2.0, 2.5, 3.0
JMA parameter = period, phase, power
ST parameter = period, multiplier
```

## Exit policy JMA_ST_P2

JMA sell signal suppressed by SuperTrend UP:

```text
if unrealized_profit_pct >= P and JMA turns DOWN:
    if SuperTrend is UP:
        suppress sell
        continue holding
    else:
        exit

if SuperTrend turns DOWN:
    exit
```

Meaning:

```text
JMA is the sensitive profit signal.
SuperTrend is the regime guard.
A JMA down-turn during ST UP is treated as a pullback, not an immediate sell.
```

## Exit policy JMA_ST_P3

Second-wave target after suppressed JMA sell:

```text
if profit >= P1 and JMA turns DOWN and ST is UP:
    suppress sell
    wait for next JMA UP
    after next JMA UP, seek P2 or trailing high

if SuperTrend turns DOWN before P2:
    exit on ST down
```

Variables:

```text
P1 = first profit trigger, e.g. +2%
P2 = second-wave target, e.g. +4%, +5%, or trailing-high rule
```

## Exit policy JMA_ST_P4

Partial profit + ST remainder hold:

```text
if profit >= P1 and JMA turns DOWN:
    sell partial quantity Q1
    hold remaining quantity while ST is UP
    exit remaining quantity on ST down or next JMA down after P2
```

Variables:

```text
Q1 = partial sell ratio, e.g. 30%, 50%, 70%
P1 = first profit trigger
P2 = second target for remainder
```

## Required benchmark columns

```text
trade_date
code
name
X
TX
entry_price
JMA_period
JMA_phase
JMA_power
ST_period
ST_multiplier
profit_trigger_P1
profit_target_P2
exit_policy
jma_state_at_TX
st_state_at_TX
first_profit_trigger_time
first_jma_down_after_profit_time
st_state_at_first_jma_down
jma_sell_suppressed_flag
next_jma_up_after_suppression_time
st_down_after_entry_time
exit_time
exit_price
exit_reason
realized_pnl_pct
max_favorable_excursion_pct
max_adverse_excursion_pct
holding_minutes
```

## Success criteria

The JMA + ST exit policy is useful only if it improves against fixed +2% target baseline:

```text
avg_realized_pnl_pct improves
total_realized_pnl_pct improves
profit_factor improves
loss frequency does not explode
average MAE remains tolerable
suppressed JMA sells frequently lead to higher later exits
ST down exits prevent severe giveback
```

## Important implementation notes

```text
1. Do not reuse cached JMA state across different stocks/dates.
2. The benchmark should recompute JMA from a clean warmup window per code/date/parameter set.
3. Use prior bars for warmup so early-session JMA state is not distorted.
4. Do not use future ST segment labels to decide at entry.
5. If using 5-minute candles, mark same-candle target/stop conflicts as ambiguous or run a next-bar execution mode.
```
