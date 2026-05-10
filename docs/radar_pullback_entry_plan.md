# Radar Pullback Entry Evaluation Plan

## Purpose

The previous high-threshold singlebar logic worked as a leader detector, but direct breakout entries were often too late and too overheated.

This bundle changes the role of the 5-minute singlebar condition:

```text
Old:
    Strong singlebar + breakout -> buy

New:
    Moderate singlebar -> leader radar
    Pullback/compression -> wait
    Re-expansion -> entry
```

The chart review dashboard remains mandatory. Every statistical result must be visually inspectable.

## Main idea

Use a relaxed 5-minute singlebar threshold to detect leader-like stocks early:

```text
radar_singlebar_close_return_pct = (close - open) / open * 100
threshold sweep: 2.0, 2.5, 3.0, 3.5, 4.0
```

Then evaluate whether a pullback and re-expansion gives a better entry than buying the strong bar or the immediate base-high breakout.

## Strategy stages

### 1. Leader Radar

A candidate is detected when:

```text
single 5m candle open->close return >= radar_threshold_pct
```

This is not a buy signal. It means the stock enters a review/watch state.

### 2. Pullback / Compression

After the radar bar:

```text
pullback_depth_pct >= selected depth threshold
pullback occurs within selected number of 5m bars
volume during pullback shrinks versus radar bar volume
```

Initial sweep:

```text
pullback_depth_pct: 2.0, 3.0, 5.0, 7.0
max_pullback_bars: 6, 9, 12
volume_shrink_ratio: 0.7, 0.5, 0.3
```

### 3. Re-expansion Entry

After pullback:

```text
price breaks the pullback reaction high or radar high reference
volume / amount expands again
RSI rises or RSI > 60
```

Initial v1 entry uses:

```text
entry when a later candle closes above the highest high between radar bar and pullback low.
```

## Required metrics

For each parameter set:

```text
sample_count
active_days
avg_trade_per_day
avg_entry_from_day_open_pct
avg_entry_from_day_low_pct
avg_return_after_entry_pct
median_return_after_entry_pct
avg_close_return_from_entry_pct
avg_max_drawdown_after_entry_pct
win_rate_after_3pct
win_rate_after_5pct
win_rate_after_10pct
loss_rate_close_minus3pct
loss_rate_close_minus5pct
actual_top10_count
actual_top10_rate
```

## Visual validation

A generated dashboard must show:

```text
5-minute candles
volume
day open and +5/+10/+15/+20% reference lines
radar bar marker
pullback low marker
entry/re-expansion marker
intraday high marker
entry_from_day_open_pct
entry_from_day_low_pct
post-entry max/close/drawdown
```

## Expected outcome

The target is not to reduce candidates to 0.7 per day.

Target pipeline:

```text
Leader Radar candidates: 5~20 per day
Pullback-ready candidates: 2~5 per day
Actual entries: 1~3 per day
```

This preserves opportunity while avoiding high-position chase buying.
