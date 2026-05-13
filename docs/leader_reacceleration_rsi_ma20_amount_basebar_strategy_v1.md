# Leader Reacceleration RSI/MA20/Amount/Base-Bar Strategy v1

Date: 2026-05-14
Repository: hoonoh57/Leader_Lab

## Background

The VIX_JMA_PARTIAL_TRAIL_v1 strategy showed strong backtest performance, but it has a live-trading structural weakness:

```text
If a stock already rose sharply before 09:00 or before reliable OpenAPI 5-minute candles are available,
then the backtest +10% entry may not be reproducible in live trading.
The live entry can become a late chase after a +15%~+20% preobservable rise.
```

Therefore, VIX-style +10% mechanical entry can be dangerous in live trading unless a preopen/first-bar extension guard is added.

## Safer alternative concept

Instead of buying the first +10% breakout, trade a reacceleration after an already-strong stock cools down and then reclaims strength.

Core idea:

```text
A prior leader rises strongly.
It cools down enough for RSI to fall below 70.
Then it reaccelerates with RSI(14) crossup 70, close above MA20, strong single-bar return, and strong amount.
```

This avoids buying the first VIX spike and focuses on a structurally cleaner second-entry / reacceleration pattern.

## Strategy identity

```text
Leader_Reaccel_RSI70_MA20_Amount_BaseBar_v1
```

## Entry conditions

5-minute signal bar must satisfy:

```text
1. close > SMA20(close)
2. RSI(14) crosses up 70
3. single 5-minute candle return > 3%
4. bar amount >= 1B KRW OR intraday cumulative amount >= 5B KRW
5. recent leader/base-bar condition exists
```

## Reacceleration condition

To ensure this is not the first uncontrolled spike, add the following:

```text
RSI(14) must have been below 70 before the signal within the same day or recent observable window.
```

This means:

```text
first spike / overextended continuation only = avoid
cooldown below RSI70 followed by RSI70 reclaim = candidate
```

## Daily base-bar / leader context

The strategy should not use a vague “5-day high rise > 10%” only. It should explicitly test base-bar style leader context:

```text
recent_5d_high_rise_pct > 10
OR daily base-bar exists within recent N days
OR current day is reclaiming a prior high-volume leader bar zone
```

Initial implementation can use:

```text
recent 5 trading day high-rise > 10%
```

Then upgrade to:

```text
recent 기준봉 발생
기준봉 고가/종가 돌파
기준봉 거래량 대비 current cumulative amount ratio
```

## Why this avoids VIX structural weakness

VIX entry:

```text
May enter a stock that is already too extended when first observable 5-minute bars appear.
```

Reacceleration entry:

```text
Requires a cooldown and reclaim cycle.
Avoids blindly chasing the first +10%/+20% vertical move.
Waits for renewed participation after temporary cooling.
```

## Benchmark comparison required

Compare:

```text
A. VIX_JMA_PARTIAL_TRAIL_v1
B. RSI70_MA20_AMOUNT_BREAKOUT_v1
C. Leader_Reaccel_RSI70_MA20_Amount_BaseBar_v1
D. VIX entries filtered by the Leader_Reaccel signal
```

Metrics:

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
daily stability
first_available_bar_open_return bucket
```

## Promotion criteria

The reacceleration strategy can be promoted if:

```text
1. avg MAE is materially lower than VIX baseline,
2. profit factor is competitive,
3. entries are reproducible after 09:00 observable data,
4. daily stability improves,
5. it does not rely on preobservable +10% entry assumptions.
```

## Immediate implementation direction

Upgrade RSI70_MA20_AMOUNT_BREAKOUT_v1 into:

```text
Leader_Reaccel_RSI70_MA20_Amount_BaseBar_v1
```

Required additions:

```text
1. RSI cooldown-before-cross flag
2. first_available_bar extension bucket
3. daily/base-bar context columns
4. comparison against VIX baseline by date
```
