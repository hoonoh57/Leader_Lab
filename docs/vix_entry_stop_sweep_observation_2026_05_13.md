# VIX Entry Stop Sweep Observation 2026-05-13

Date: 2026-05-13
Repository: hoonoh57/Leader_Lab

## Input benchmark

Universe:

```text
condition-captured candidates = 966 rows
breakout thresholds X = 10, 11, 12, 13
profit target P = +2%
stop-loss sweep S = -0.5, -1, -1.5, -2, -2.5, -3, -4, -5, -6, -8
```

## Key result

The best simple fixed target/stop combination in the current benchmark is:

```text
X = 10%
S = -8%
entry_count = 882
plus2_success_count = 725
plus2_success_rate = 82.20%
reject_count = 97
reject_rate = 11.00%
expected_pct_per_entry = +0.76
profit_factor_simple = 1.87
avg_post_TX_max_return_pct = 10.05
avg_post_TX_mae_pct = -5.77
```

## Interpretation

Tight stops are not compatible with the current +X% breakout entry model.

Examples:

```text
X=10, S=-0.5  => success 7.48%, reject 92.40%, expected -0.31
X=10, S=-2.0  => success 22.34%, reject 77.21%, expected -1.10
X=10, S=-6.0  => success 70.86%, reject 24.60%, expected -0.06
X=10, S=-8.0  => success 82.20%, reject 11.00%, expected +0.76
```

This confirms that the earlier 70%+ reject rate was mostly created by the arbitrary -2% stop.

## Strategic implication

A fixed stop is a poor primary exit mechanism for this strategy.
The next benchmark must test dynamic exit logic:

```text
Entry trigger: +X% breakout
Profit sensitivity: JMA down-turn after profit zone
Sell suppression: if SuperTrend remains UP, do not sell on first JMA down-turn
Final exit: SuperTrend DOWN or controlled trailing/MAE rule
```

## Working hypothesis after this result

```text
The strategy has a continuation edge only when enough adverse fluctuation is tolerated.
Therefore, fixed tight stop is not the right expression of the edge.
SuperTrend should be tested as a dynamic stop / hold-regime filter.
JMA should be tested as a sensitive profit-taking trigger.
```

## Next benchmark

```text
VIX Entry + JMA Profit Taking + SuperTrend Hold Overlay v1
```

Required comparison:

```text
P0: fixed +2% target and fixed stop
P1: JMA profit-taking after profit trigger P
P2: JMA down sell suppressed when SuperTrend is UP
P3: next JMA up/down cycle while SuperTrend remains UP
P4: partial profit + ST/JMA remainder hold
```
