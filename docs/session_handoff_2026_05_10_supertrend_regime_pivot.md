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

## 2. Current state at handoff

### Implemented assets

The SuperTrend Regime Discovery bundle has been partially implemented.

Files now exist or are being actively corrected:

```text
docs/supertrend_regime_discovery_plan.md
sql/create_supertrend_regime_discovery.sql
src/analysis/build_supertrend_regime_discovery.py
scripts/build_supertrend_regime_discovery.ps1
src/review/generate_supertrend_regime_discovery_dashboard.py
scripts/build_supertrend_regime_discovery_dashboard.ps1
```

Tables:

```text
supertrend_regime_segment
supertrend_regime_summary
supertrend_regime_feature_summary
```

Report path:

```text
reports/supertrend_regime_discovery_dashboard.html
```

### Current blocking issue

The current work is not finished until chart verification is consistent.

Observed issue from user review:

```text
Even after analyzer warm-up correction, the dashboard still visually shows the same problem:
strong early morning rise appears excluded,
and ST shaded segment can appear after the real early surge.
```

Root cause:

```text
The analyzer was corrected to use previous intraday warmup candles,
but the dashboard was still using current-day-only candles or had incomplete ST line rendering.
```

The next session must first verify and finish the dashboard correction.

---

## 3. Critical technical rule: SuperTrend needs prior intraday warm-up

For early-session SuperTrend/ATR testing, current-day-only candles are invalid.

Wrong method:

```text
Load 09:00~15:30 current-day candles only
calculate ATR/SuperTrend from 09:00
```

Why wrong:

```text
ATR/SuperTrend needs prior bars.
Without prior bars, the first several 5-minute bars become warm-up noise.
The real early strong move can be missed or marked late.
```

Correct method:

```text
Load previous intraday 5-minute candles before current-day 09:00
append current-day candles
calculate ATR/SuperTrend on warmup + current-day candles
store/evaluate only current-day segments
```

Current intended parameter:

```text
warmup_bars = 80
```

This provides enough prior 5-minute candles to stabilize ST(7), ST(10), ST(14) in early session.

---

## 4. Analyzer status

`src/analysis/build_supertrend_regime_discovery.py` was corrected to use warm-up candles.

Expected behavior:

```text
load_warmup_day_candles(conn, trade_date, code, warmup_bars)
    -> previous candles before 09:00 DESC LIMIT warmup_bars
    -> reverse previous candles
    -> append current-day 09:00~15:30 candles
```

Then:

```text
calculate ATR/SuperTrend on warmup + current-day rows
extract segments only from current_start_idx onward
start-state features are calculated from current-day rows only
```

Expected command:

```powershell
cd E:\2026\Leader_Lab
.\scripts\build_supertrend_regime_discovery.ps1
```

Expected output marker:

```text
warmup_bars=80
=== DONE build_supertrend_regime_discovery ===
=== supertrend_regime_summary ===
```

User uploaded a run log after analyzer warm-up correction. Representative results:

```text
ST(7,2.0) ALL:
segment_count = 5772
gain3_rate = 36.33%
gain5_rate = 22.54%
gain10_rate = 9.68%
fail1_rate = 35.57%
end_negative_rate = 51.87%

ST(7,2.0) GOOD_GAIN5:
segment_count = 1301
avg_st_up_bars = 29.74
avg_st_up_max_return_pct = 10.65%
median_st_up_max_return_pct = 9.12%

ST(7,2.0) GREAT_GAIN10:
segment_count = 559
avg_st_up_bars = 36.80
avg_st_up_max_return_pct = 15.38%
```

Important first-pass feature result:

```text
ST(7,2.0) segment_amount:
Good avg = 537.7억
Bad avg  = 102.1억
Diff     = 435.6억

ST(7,2.0) st_up_bars:
Good avg = 29.74 bars
Bad avg  = 13.09 bars
```

Interpretation:

```text
Good ST regimes are still strongly associated with high internal segment amount and longer trend duration.
Start cumulative amount is not a simple positive filter; Bad regimes can have larger start_cum_amount, likely because they are late/overheated or noisy after prior activity.
```

---

## 5. Dashboard status and next-session priority

The dashboard is the immediate priority.

The dashboard must use the exact same warm-up principle as the analyzer.

Required dashboard behavior:

```text
1. load warmup candles before 09:00 + current-day candles
2. render previous/warmup candles before current-day 09:00
3. mark current-day 09:00 with vertical dotted line
4. calculate SuperTrend on warmup + current-day candles in the browser or from precomputed data
5. draw ST Up and ST Down lines
6. draw stored DB segment shading over the same chart
7. draw capture time, ST start, ST end, ST max markers
```

The dashboard generator should contain:

```text
load_warmup_candles_for_segments(conn, segments, warmup_bars)
--warmup-bars argument
ST Up / ST Down line rendering
09:00 day-open vertical line
warmup region shading
```

The current GitHub state may include a recently updated dashboard generator commit. The next session must verify it actually exists locally after `git pull` and that the generated HTML reflects warm-up candles.

Expected command:

```powershell
cd E:\2026\Leader_Lab
git pull
.\scripts\build_supertrend_regime_discovery_dashboard.ps1
```

Expected dashboard output marker:

```text
=== DONE generate_supertrend_regime_discovery_dashboard ===
warmup_bars=80
Report: E:\2026\Leader_Lab\reports\supertrend_regime_discovery_dashboard.html
```

Visual validation checklist:

```text
1. The chart starts before 09:00 and includes prior/warmup candles.
2. 09:00 is marked with a dotted vertical line.
3. ST Up / ST Down lines are visible.
4. The green ST regime shading aligns with the visible ST Up line.
5. Strong early morning rise is no longer visually lost due to warm-up distortion.
6. If ST segment still begins late, inspect whether the stored DB segment itself starts late.
```

---

## 6. What was corrected conceptually

### Incorrect interpretation

SuperTrend was initially discussed too narrowly as:

```text
If SuperTrend turns down, sell.
```

That is not the intended research step.

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

## 7. Why this matters

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

## 8. Important conceptual rule

Do not hard-code a magic timestamp such as 09:30 for SuperTrend regime discovery.

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

## 9. SuperTrend parameters to test first

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

## 10. Required segment definition

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

## 11. Required segment fields

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

## 12. Required start-state features

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

## 13. Required internal segment features

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

## 14. Good ST vs Bad ST comparison

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

## 15. After chart verification is solved

Only after the dashboard shows correct warm-up-based ST lines and segment shading, proceed to:

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

## 16. Updated next-session instruction

If the next session starts from here:

```text
Do not implement new strategy logic first.
Do not start exit simulation first.
Do not build Good ST Similarity Score first.
```

Start with:

```text
Fix and verify SuperTrend warm-up chart consistency.
```

Recommended next-session commands:

```powershell
cd E:\2026\Leader_Lab
git pull

.\scripts\build_supertrend_regime_discovery.ps1
.\scripts\build_supertrend_regime_discovery_dashboard.ps1
```

Then visually inspect:

```text
reports/supertrend_regime_discovery_dashboard.html
```

If the dashboard still shows early strong rise excluded from ST segment:

```text
1. Compare DB st_up_start_time with visible ST Up line start.
2. If DB start is late, fix analyzer segment extraction.
3. If DB start is correct but chart is wrong, fix dashboard ST rendering.
4. If both are correct but ST itself naturally starts late, then document this as a property of the selected ST parameter and evaluate faster parameters or 1-minute/3-minute timeframe later.
```

---

## 17. Final current conclusion

The current research stack is now:

```text
Experiment Registry
Winner Pattern Discovery
Winner Feature Score v1
Time-Aware Winner Feature Score v2
SuperTrend Regime Discovery  <-- IN PROGRESS, chart consistency pending
Good ST Segment Similarity
Regime-aware entry/exit strategy
Macro/news/sector/LLM overlay
```

The immediate next step is not strategy expansion.

The immediate next step is:

```text
Make SuperTrend Regime Discovery visually trustworthy by aligning analyzer and dashboard warm-up logic.
```
