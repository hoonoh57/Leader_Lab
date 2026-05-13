# RSI70 MA20 Amount Breakout Observation 2026-05-14

Date: 2026-05-14
Repository: hoonoh57/Leader_Lab

## Input benchmark

Strategy:

```text
RSI70_MA20_AMOUNT_BREAKOUT_v1
```

Entry signal:

```text
5-minute close > SMA20
RSI(14) crosses above 70
single 5-minute candle return > 3%
bar amount >= 1B KRW or intraday cumulative amount >= 5B KRW
last 5-day high-rise rate > 10%
entry = next bar open
```

Exit:

```text
VIX_JMA_PARTIAL_TRAIL_v1
P1 = +3%
JMA = 7/50/2
ST = 14/3
partial sell = 30%
remainder trailing = 1%
```

## Result

```text
entry_count = 559
win_count = 368
win_rate = 65.8318%
loss_count = 189
loss_rate = 33.8104%
avg_realized_pnl_pct = +2.3390
total_realized_pnl_pct = +1307.5157
profit_factor = 2.8120
avg_mfe_pct = +7.4423
avg_mae_pct = -3.3415
avg_holding_minutes = 60.35
```

## Comparison with current best VIX baseline

Current best promoted baseline:

```text
VIX_JMA_PARTIAL_TRAIL_v1
entry_count = 882
avg_realized_pnl_pct = +2.7833
total_realized_pnl_pct = +2454.84
profit_factor = 3.5431
avg_mfe_pct = +8.2639
avg_mae_pct = -4.6232
avg_holding_minutes = 86.77
```

Comparison:

```text
RSI strategy has lower average return and lower profit factor than VIX baseline.
RSI strategy has lower average MAE, meaning it is a cleaner and lower-risk subset.
RSI strategy trades fewer cases: 559 vs 882.
```

## Interpretation

RSI70_MA20_AMOUNT_BREAKOUT_v1 should not replace VIX_JMA_PARTIAL_TRAIL_v1 as the main strategy.

However, it is useful as a quality filter / defensive entry subset because:

```text
1. avg MAE improves from about -4.62 to -3.34.
2. holding time is shorter.
3. win rate is almost the same level.
4. it captures a smaller, cleaner subset of the VIX source universe.
```

The weakness is:

```text
1. avg realized PnL is lower than the VIX baseline.
2. total realized PnL is much lower due to fewer trades and smaller MFE.
3. next-bar-open entry after RSI confirmation may be too late for part of the move.
```

## Promotion decision

Do not promote as a replacement main strategy.

Promote as:

```text
RSI70_MA20_AMOUNT_FILTER_v1
```

Role:

```text
Risk-reduction filter / high-quality subset classifier
```

## Next benchmark

```text
VIX_JMA_PARTIAL_TRAIL_v1 + RSI70_MA20_AMOUNT_FILTER_v1 comparison
```

Required test modes:

```text
A. VIX baseline all entries
B. RSI-only independent entry
C. VIX entries that also satisfy RSI filter before or near entry
D. VIX entries ranked by RSI/MA20/amount signal strength
E. TopN per day using RSI score as one factor
```

Core next question:

```text
Can the RSI70/MA20/amount signal reduce MAE and improve daily stability when used as a filter or score inside the VIX entry system?
```
