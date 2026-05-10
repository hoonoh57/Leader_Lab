# Session Handoff Addendum — SuperTrend Regime Pivot

## 1. Why this addendum exists

A major direction change occurred after implementing Time-Aware Winner Feature Score v2.

The previous continuation path was almost:

```text
WinnerScoreTime v2
    -> entry/exit simulation
    -> TP / SL / time exit / SuperTrend exit
```

This has been corrected.

The new direction is:

```text
First analyze SuperTrend uptrend regimes independently.
Then use those regime labels as reusable feature assets.
Only after that combine them with WinnerScore, RadarPullback, JMA, TP/trailing, news, sector, and macro features.
```

This addendum must be read together with:

```text
docs/session_handoff_2026_05_10_winner_feature_track.md
docs/todo_2026_05_10_research_track.md
```

---

## 2. What was corrected

### Incorrect interpretation

SuperTrend was initially discussed too narrowly as:

```text
If SuperTrend turns down, sell.
```

That is not the intended next research step.

### Correct interpretation

SuperTrend should first be used as:

```text
A regime label that defines where a real uptrend segment starts and ends.
```

The important measurement is not sell performance yet.

The important measurement is:

```text
During a SuperTrend uptrend segment,
what was the maximum achievable return?
```

This becomes a new outcome label:

```text
st_up_max_return_pct
```

---

## 3. Why this matters

Existing labels such as:

```text
actual_max_after_return_pct
future_max_return_pct
future_close_return_pct
```

are useful, but they mix many different market states:

```text
initial surge
pullback
re-expansion
afternoon fade
late rebound
close collapse
```

SuperTrend regime labeling separates the actual trend portion:

```text
ST uptrend start
    -> trend continuation
    -> ST down transition
```

This gives a cleaner question:

```text
Did this stock produce a tradable strong trend regime?
```

rather than:

```text
Did it have any high price before the end of day?
```

---

## 4. Important conceptual rule

Do not hard-code a magic timestamp such as 09:30 for this SuperTrend regime discovery.

Time-aware WinnerScore v2 used decision timestamps such as:

```text
09:20
09:30
10:00
10:30
11:00
13:00
```

Those are useful diagnostic views, but the SuperTrend regime study must be event/state-driven.

Correct base flow:

```text
condition-search capture time
    -> find SuperTrend uptrend regimes after capture
    -> label each ST uptrend segment
    -> compare good ST segments vs bad ST segments
```

The strategy should not require:

```text
The stock must be selected at 09:30.
```

Instead, the logic should allow:

```text
The stock is captured at 09:05.
If a valid SuperTrend uptrend regime starts at 09:10, 09:25, 10:05, or later,
that regime can be evaluated.
```

---

## 5. Immediate next bundle

The next implementation should be:

```text
SuperTrend Regime Discovery Bundle
```

Required files:

```text
docs/supertrend_regime_discovery_plan.md
sql/create_supertrend_regime_discovery.sql
src/analysis/build_supertrend_regime_discovery.py
scripts/build_supertrend_regime_discovery.ps1
src/review/generate_supertrend_regime_discovery_dashboard.py
scripts/build_supertrend_regime_discovery_dashboard.ps1
```

Required tables:

```text
supertrend_regime_segment
supertrend_regime_summary
supertrend_regime_feature_summary
```

Required report:

```text
reports/supertrend_regime_discovery_dashboard.html
```

---

## 6. First universe for SuperTrend Regime Discovery

Start with the current practical universe:

```text
condition-search captured stocks
all available dates
5-minute candles
```

Do not immediately expand to the full market. The current condition-search universe is already valuable because:

```text
1. It is the real operating universe.
2. It contains fewer than about 50 candidates per day.
3. It includes many actual large movers.
4. It is already connected to analysis_5m_result and minute5_candles.
```

Later expansion can include:

```text
entire market universe
1-minute candles
3-minute candles
sector universes
```

---

## 7. SuperTrend parameters to test first

Use a controlled parameter set:

```text
ST(7, 1.5)
ST(7, 2.0)
ST(10, 2.0)
ST(14, 2.0)
```

Reason:

```text
ST(7, 1.5)  = sensitive / early but noisy
ST(7, 2.0)  = short-term trend candidate
ST(10, 2.0) = balanced 5-minute trend candidate
ST(14, 2.0) = user's familiar baseline
```

---

## 8. Segment definition

One row should represent:

```text
code + trade_date + timeframe + ST parameter + uptrend segment number
```

A segment starts when:

```text
SuperTrend state changes to up
```

A segment ends when:

```text
SuperTrend state changes to down
```

If the stock is already in an uptrend after condition capture, this segment is still valid but should have a flag:

```text
already_up_at_capture = 1
```

---

## 9. Required segment columns

### Identity

```text
code
name
trade_date
timeframe
st_period
st_multiplier
segment_no
```

### Segment times

```text
capture_time
st_up_start_time
st_up_end_time
st_up_bars
```

### Segment prices

```text
st_up_start_price
st_up_max_price
st_up_end_price
st_up_min_price
```

### Segment outcomes

```text
st_up_max_return_pct
st_up_end_return_pct
st_up_max_drawdown_pct
```

### Segment quality labels

```text
label_st_gain_3pct
label_st_gain_5pct
label_st_gain_10pct
label_st_fail_1pct
label_st_end_negative
```

---

## 10. Required start-state features

At ST uptrend segment start:

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

These answer:

```text
Was this ST uptrend starting from a healthy early position,
or was it already too overheated?
```

---

## 11. Required internal segment features

During the ST uptrend segment:

```text
segment_amount
segment_volume
segment_avg_amount_per_bar
segment_max_singlebar_return_pct
segment_green_bar_count
segment_red_bar_count
```

These answer:

```text
Was the trend segment supported by real participation,
or was it a weak/noisy ST flip?
```

---

## 12. Good ST vs Bad ST comparison

After extracting segments, classify:

```text
Good ST Segment:
    st_up_max_return_pct >= 5

Great ST Segment:
    st_up_max_return_pct >= 10

Bad ST Segment:
    st_up_max_return_pct < 1
    OR st_up_end_return_pct < 0
```

Then compare:

```text
Good vs Bad start_cum_amount
Good vs Bad start_from_day_open_pct
Good vs Bad start_from_day_low_pct
Good vs Bad start_range_so_far_pct
Good vs Bad max_singlebar_return_before_start
Good vs Bad segment_amount
Good vs Bad segment_bars
```

The goal is to discover what makes a SuperTrend uptrend segment tradable.

---

## 13. Dashboard requirements

The dashboard must show:

```text
5-minute candlestick chart
SuperTrend line
ST uptrend segment shading
ST up start marker
ST up end marker
ST segment max price marker
st_up_max_return_pct
st_up_end_return_pct
st_up_bars
start-state feature panel
segment feature panel
```

Filters:

```text
ST parameter
trade_date
code/name
Good ST >= 5%
Great ST >= 10%
Bad ST
already_up_at_capture
high overheat at start
```

---

## 14. How this connects later

After SuperTrend Regime Discovery is complete, build:

### 1. Good ST Segment Similarity Score

```text
Does the current ST uptrend segment resemble historically profitable ST segments?
```

### 2. WinnerScoreTime + ST regime filter

```text
WinnerScoreTime selects strong candidates.
ST regime quality determines whether the current trend segment is worth trading.
```

### 3. ST + JMA strategy

```text
If ST is rising, do not exit merely because JMA dips.
After target profit, JMA down-turn can be used for profit capture.
```

### 4. TP / trailing inside ST regime

```text
Within ST uptrend regime, test TP3, TP5, trailing, VI-aware cooldown.
```

### 5. Macro/context overlay

```text
news
sector leadership
theme strength
KOSPI/KOSDAQ state
program net buy
foreign/institution flow
LLM final judgment
```

---

## 15. Updated next-session instruction

If the next session starts from here, do not immediately implement more exit simulation.

Start with:

```text
SuperTrend Regime Discovery Bundle
```

Then run:

```powershell
cd E:\2026\Leader_Lab
git pull
```

After implementation, expected commands should be:

```powershell
.\scripts\build_supertrend_regime_discovery.ps1
.\scripts\build_supertrend_regime_discovery_dashboard.ps1
```

---

## 16. Final current conclusion

The current research stack is now:

```text
Experiment Registry
Winner Pattern Discovery
Winner Feature Score v1
Time-Aware Winner Feature Score v2
SuperTrend Regime Discovery  <-- NEXT
Good ST Segment Similarity
Regime-aware entry/exit strategy
Macro/news/sector/LLM overlay
```

This addendum records the pivot so the next session does not fall back into a narrow magic-time or magic-candle approach.
