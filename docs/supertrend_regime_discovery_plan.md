# SuperTrend Regime Discovery Plan

## Purpose

Before mixing SuperTrend with WinnerScore, RadarPullback, JMA, TP, trailing, news, sector, or macro features, SuperTrend itself must be analyzed independently.

The goal is not:

```text
SuperTrend down -> sell strategy
```

The goal is:

```text
SuperTrend uptrend segment -> measurable strong-regime label
```

This bundle extracts every SuperTrend uptrend segment from the current condition-search universe and labels whether that segment was actually profitable.

## Why this is needed

SuperTrend can flip up/down frequently in sideways regimes. If we use it directly as a buy or sell rule, it can generate many noisy signals.

Therefore we first answer:

```text
Which SuperTrend uptrend segments led to +3%, +5%, +10% moves?
Which SuperTrend uptrend segments were false/noisy regimes?
What separated them at the start of the segment?
```

## Analysis universe

V1 universe:

```text
analysis_5m_result valid candidates
minute5_candles
all available dates
```

This is the real practical universe already used by the project:

```text
same condition-search captured stocks
fewer than about 50 candidates per day
contains actual large movers
```

## SuperTrend parameters

Initial controlled sweep:

```text
ST(7, 1.5)
ST(7, 2.0)
ST(10, 2.0)
ST(14, 2.0)
```

## Segment definition

One segment row means:

```text
code + trade_date + timeframe + ST parameter + segment_no
```

A segment starts when:

```text
SuperTrend direction changes to up
```

A segment ends when:

```text
SuperTrend direction changes to down
or the trading day ends
```

If the condition-search capture time occurs while ST is already up, the segment is still included and marked as:

```text
already_up_at_capture = 1
```

## Required segment outcome labels

```text
st_up_max_return_pct
st_up_end_return_pct
st_up_max_drawdown_pct
st_up_bars
```

Important labels:

```text
label_st_gain_3pct
label_st_gain_5pct
label_st_gain_10pct
label_st_fail_1pct
label_st_end_negative
```

## Required start-state features

At ST uptrend start:

```text
start_from_day_open_pct
start_from_day_low_pct
start_cum_amount
start_cum_volume
start_range_so_far_pct
start_high_so_far_from_open_pct
max_singlebar_return_before_start
singlebar_3pct_exists_before_start
singlebar_5pct_exists_before_start
```

These are used to compare Good ST and Bad ST segments.

## Required internal segment features

Inside the ST uptrend segment:

```text
segment_amount
segment_volume
segment_avg_amount_per_bar
segment_max_singlebar_return_pct
segment_green_bar_count
segment_red_bar_count
```

## Summary questions

The summary must answer:

```text
1. How many ST uptrend segments occur?
2. What percent reach +3%, +5%, +10%?
3. Which ST parameter gives the best high-profit / low-noise balance?
4. How many segments are noisy false regimes?
5. What is the average start overheat position of Good vs Bad ST segments?
6. Does higher starting amount improve ST segment quality?
```

## Good / Bad definitions

```text
Good ST Segment:
    st_up_max_return_pct >= 5

Great ST Segment:
    st_up_max_return_pct >= 10

Bad ST Segment:
    st_up_max_return_pct < 1
    OR st_up_end_return_pct < 0
```

## Dashboard requirements

The dashboard must show:

```text
5m candle chart
SuperTrend up/down line
ST uptrend segment shading
ST up start marker
ST up end marker
ST max price marker
st_up_max_return_pct
st_up_end_return_pct
st_up_bars
start-state features
segment features
```

Filters:

```text
ST parameter
trade date
code/name
Good >= 5%
Great >= 10%
Bad
already_up_at_capture
```

## How this connects later

After this bundle:

```text
1. Build Good ST Segment Similarity Score.
2. Combine WinnerScoreTime with Good ST regime quality.
3. Add JMA/TP/trailing strategies inside ST regimes.
4. Add news/sector/index/program-flow/LLM overlays.
```

## Rule

Do not proceed to final entry/exit optimization until ST regime quality is understood independently.
