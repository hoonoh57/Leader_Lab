# RSI70 MA20 Amount Breakout Strategy Spec v1

Date: 2026-05-14
Repository: hoonoh57/Leader_Lab

## Purpose

Emergency proposal benchmark:

```text
1. 5-minute close > 20MA
   and crossup(RSI(14), 70)
   and single 5-minute candle return > 3%

2. 5-minute trading amount >= 1,000,000,000 KRW
   or intraday cumulative trading amount >= 5,000,000,000 KRW

3. Within the last 5 trading days, high-rise rate > 10%
```

This strategy is tested as an independent entry signal, separate from the previous +10% VIX entry trigger.

## Entry definition

```text
Signal bar = first 5-minute bar satisfying all conditions.
Entry      = next bar open by default.
```

Reason:

```text
The signal depends on 5-minute close and RSI crossup at bar close.
Using same-bar close as entry may overstate execution.
Next-bar open is the default realistic benchmark.
```

Optional modes can later be added:

```text
same_bar_close
next_bar_open
next_bar_vwap_proxy
```

## Indicator definitions

```text
MA20 = SMA(close, 20)
RSI14 = Wilder RSI(close, 14)
RSI crossup 70 = previous RSI <= 70 and current RSI > 70
single_bar_return_pct = (close / previous_close - 1) * 100
bar_amount = ((open + high + low + close) / 4) * volume
cum_amount = intraday cumulative bar_amount
```

## 5-day high-rise condition

At signal bar:

```text
last_5d_low  = minimum low from recent 5 trading days, including current intraday bars available up to signal time
last_5d_high = maximum high from same available window
last_5d_high_rise_pct = (last_5d_high / last_5d_low - 1) * 100
condition = last_5d_high_rise_pct > 10
```

Implementation note:

```text
Use previous daily candles plus current intraday bars up to signal time.
Do not use later same-day bars after signal time.
```

## Default exit policy

The first benchmark uses the currently promoted exit style:

```text
VIX_JMA_PARTIAL_TRAIL_v1 style exit

After entry:
1. if profit reaches P1 = +3% and JMA(7,50,2) turns down:
       sell Q = 30%
2. keep 70% remainder
3. remainder exits by 1% trailing from post-partial high
4. if SuperTrend(14,3) turns down first, exit remaining quantity
5. if no exit by day end, exit at day-end close
```

Reason:

```text
The entry condition is new, but the exit logic should reuse the best currently validated exit baseline.
This keeps evaluation comparable and avoids introducing another arbitrary fixed stop.
```

## Universe

Default benchmark universe:

```text
1516 condition-captured candidate universe from SQLite
```

Optional future mode:

```text
scan all codes in candle table by date
```

The default is candidate-universe based because it is already the project's verified source universe and is computationally smaller.

## Output files

```text
reports/rsi70_ma20_amount_breakout_detail_v1.csv
reports/rsi70_ma20_amount_breakout_summary_v1.csv
reports/rsi70_ma20_amount_breakout_daily_v1.csv
reports/rsi70_ma20_amount_breakout_v1.html
```

## Main evaluation columns

```text
trade_date
code
name
signal_time
entry_time
entry_price
ma20
rsi14_prev
rsi14
single_bar_return_pct
bar_amount
cum_amount
last5d_high_rise_pct
exit_time
exit_reason
realized_pnl_pct
max_favorable_excursion_pct
max_adverse_excursion_pct
holding_minutes
```

## Promotion criteria

This strategy can be promoted only if it beats the current VIX baseline on at least one practical axis:

```text
1. higher avg_realized_pnl_pct
2. higher profit factor
3. lower average MAE
4. better daily stability
5. fewer but higher-quality trades suitable for TopN operation
```
