# Session Handoff — 2026-05-10 Winner Feature Track

## 0. Why this document exists

The current research track has moved from a single magic-pattern strategy to a cumulative feature-asset strategy.

This document is the handoff map for the next session. It records:

```text
1. What data we have.
2. What experiments were implemented.
3. Which results were useful.
4. Which results were weak but must remain as reference assets.
5. What the current score means and does NOT mean.
6. What to implement next.
```

The next session must continue from this flow rather than restarting from a single candle idea.

---

## 1. Core project advantage

The main advantage is not a single indicator.

The real advantage is:

```text
1. We have about six months of same-condition-search captured stocks.
2. Each trading day has fewer than about 50 candidates.
3. Actual large movers are usually included inside this filtered universe.
4. We can compare winners and losers inside the same daily candidate pool.
5. We can connect every statistical result to a 5-minute chart review dashboard.
```

Therefore the correct research question is:

```text
Among condition-search candidates, which stocks are likely to become that day's large movers?
```

Not:

```text
Can one single 5-minute candle pattern become a complete trading system?
```

---

## 2. Research direction change

### Old direction

```text
Strong 5m singlebar event
    -> base high breakout
    -> RSI/volume condition
    -> direct buy simulation
```

Problem:

```text
The selected stocks often were actual leaders, but the entry point was frequently too high.
Direct breakout after a strong 5m move often became chase-buying.
```

### New direction

```text
Condition-search universe
    -> actual winners and losers
    -> extract features that explain winners
    -> preserve each logic as a feature asset
    -> score candidates
    -> review charts
    -> later build time-aware live score
```

Key principle:

```text
Failed strategies are not deleted. They become reference assets or avoidance features.
```

---

## 3. Current data assumptions

Existing tables used so far:

```text
analysis_5m_result
minute5_candles
radar_pullback_entry_result
radar_pullback_entry_summary
winner_pattern_case
winner_feature_score_result
```

Important fields from `analysis_5m_result`:

```text
search_date
search_time
code
name
max_after_return_pct
close_return_pct
history_grade
valid_analysis_flag
```

Important validity rule:

```text
valid_analysis_flag = 1
history_grade IN ('normal_intraday', 'partial_intraday', 'weak_intraday')
```

Market-closed rows were separated earlier and must not contaminate intraday analysis.

---

## 4. Experiments implemented and why they remain

### 4.1 Hypothesis Validation v1

Purpose:

```text
Validate whether a strong single 5m candle can identify real leaders.
```

Status:

```text
Useful as leader detection evidence.
Not sufficient as a direct buy trigger.
```

Main lesson:

```text
Strong singlebar events appear often in winners, but entry timing after such events is frequently late.
```

---

### 4.2 Singlebar Threshold Sweep

Purpose:

```text
Compare 3~6% singlebar thresholds instead of hardcoding 5%.
```

Status:

```text
Useful for mapping leader strength vs overheat risk.
```

Main lesson:

```text
2~5% singlebar events are useful leader features.
6%+ events are both leader strength and overheat risk.
```

---

### 4.3 Direct Entry / Exit Simulation

Variants:

```text
strict same-candle
next-open
break-fill next-bar exit
```

Status:

```text
Important failed-entry reference.
```

Main lesson:

```text
Even when the selected stock was a real winner, direct entry after a strong breakout often produced poor risk/reward.
```

Interpretation:

```text
Direct breakout is not discarded; it becomes a warning about entry position and overheat.
```

---

### 4.4 Chart Review Bundle

Purpose:

```text
Every statistical result must be visually inspectable.
```

Assets:

```text
chart_review_case
reports/chart_review_dashboard.html
```

Main lesson:

```text
Several numeric winners were visually late-entry or overheat cases.
WYSIWYG review is required before accepting any condition.
```

---

### 4.5 Radar Pullback Entry Evaluation

Purpose:

```text
Use relaxed 2~4% radar candles to detect leader candidates, then wait for pullback and re-expansion.
```

Assets:

```text
radar_pullback_entry_result
radar_pullback_entry_summary
reports/radar_pullback_review_dashboard.html
reports/radar_pullback_quality_report.html
```

Important result:

```text
Radar-Pullback improves candidate count and reduces some chase risk, but is still not a complete standalone buy strategy.
```

Key interpretation:

```text
Radar-Pullback is a strong feature asset, not a final trading system.
```

---

### 4.6 Winner Pattern Discovery

Purpose:

```text
Start from actual winners and losers inside the same condition-search universe.
Find features that separate them.
```

Assets:

```text
winner_pattern_case
winner_pattern_feature_summary
reports/winner_pattern_discovery_report.html
```

Important findings:

```text
1. intraday_amount_proxy is the strongest separator.
2. first_hour_high_from_open_pct separates winners from losers.
3. day_range_pct separates winners from losers.
4. singlebar_3/4/5pct_exists are useful winner features.
5. radar_pullback_exists is much more frequent in winners than losers.
```

Main conclusion:

```text
Singlebar and Radar-Pullback are not failed logic. They are winner-explaining features.
```

---

### 4.7 Winner Feature Score v1

Purpose:

```text
Convert discovered feature assets into an explainable score.
```

Assets:

```text
winner_feature_score_result
winner_feature_score_summary
reports/winner_feature_score_dashboard.html
```

Score formula:

```text
WinnerFeatureScore
    = LeaderStrengthScore
    + PullbackStructureScore
    + CloseStrengthScore
    - OverheatPenalty
```

Current summary result:

```text
ALL:
    sample_count = 2622
    actual_top10_rate = 31.27%
    avg_actual_max_after_return_pct = 6.57%
    avg_close_return_pct = -0.65%

SCORE_TOP1_DAILY:
    sample_count = 82
    actual_top10_rate = 91.46%
    avg_actual_max_after_return_pct = 16.04%
    avg_close_return_pct = 9.58%

SCORE_TOP3_DAILY:
    sample_count = 246
    actual_top10_rate = 86.99%
    avg_actual_max_after_return_pct = 14.36%
    avg_close_return_pct = 7.05%

SCORE_TOP5_DAILY:
    sample_count = 410
    actual_top10_rate = 81.46%
    avg_actual_max_after_return_pct = 13.15%
    avg_close_return_pct = 5.22%
```

Interpretation:

```text
The score is very good at explaining actual winners.
But v1 is a discovery/explanation score, not yet a live trading score.
```

Reason:

```text
Some v1 features use future/full-day information:
- day_range_pct
- close_from_open_pct
- full-day intraday_amount_proxy
- full-day max singlebar information
- best_radar_pullback values that may occur after the intended decision time
```

Therefore:

```text
Do NOT treat v1 as a real-time buy score.
Use it as evidence that the feature direction is correct.
```

---

## 5. Key conceptual shift

The system now has a layered research architecture:

```text
Layer 1: Condition-search universe
Layer 2: Winner/Loser feature discovery
Layer 3: Feature asset registry
Layer 4: Explainable score
Layer 5: Chart review
Layer 6: Time-aware live-score conversion
Layer 7: Entry timing and exit simulation
Layer 8: News/sector/index/LLM macro overlay
```

This is the correct track.

---

## 6. Current score components

### LeaderStrengthScore

Current features:

```text
intraday_amount_proxy
first_hour_high_from_open_pct
day_range_pct
singlebar_3pct_exists
singlebar_4pct_exists
singlebar_5pct_exists
singlebar_6pct_exists small bonus
```

Meaning:

```text
Is this stock strongly participating in the market today?
```

---

### PullbackStructureScore

Current features:

```text
radar_pullback_exists
best_radar_pullback_max_return_pct
```

Meaning:

```text
Does the stock show a repeated winner-like pullback/re-expansion structure?
```

---

### CloseStrengthScore

Current features:

```text
close_from_open_pct
best_radar_pullback_close_return_pct
```

Meaning:

```text
Did the stock maintain strength into the close?
```

Warning:

```text
This is future data for live trading and must be replaced in v2.
```

---

### OverheatPenalty

Current features:

```text
singlebar_6pct_exists
max_5m_singlebar_from_open_pct
max_5m_singlebar_from_low_pct
```

Meaning:

```text
Does the stock look strong but too high to chase?
```

---

## 7. Next required implementation: Time-Aware Winner Feature Score v2

This is the most important next step.

### Problem to solve

V1 uses full-day information. V2 must compute score using only data available at a specific decision timestamp.

### Required decision timestamps

Start with:

```text
09:20
09:30
10:00
10:30
11:00
13:00
```

### Allowed v2 features at each timestamp

```text
cum_amount_until_time
cum_volume_until_time
current_high_from_open_pct
current_high_from_low_pct
current_close_from_open_pct
current_day_range_pct_so_far
singlebar_2pct_exists_until_time
singlebar_3pct_exists_until_time
singlebar_4pct_exists_until_time
singlebar_5pct_exists_until_time
singlebar_6pct_exists_until_time
radar_pullback_exists_until_time
radar_pullback_entry_quality_until_time
current_overheat_from_open_pct
current_overheat_from_low_pct
```

### Forbidden v2 features

```text
full-day close
full-day high after decision time
full-day range after decision time
full-day total amount
future singlebar events
future Radar-Pullback events
future best_radar_pullback_max_return_pct
future best_radar_pullback_close_return_pct
```

### v2 evaluation target

For each timestamp:

```text
Score Top1 / Top3 / Top5
    -> actual_rank
    -> actual_max_after_return_pct from that timestamp forward
    -> close return from that timestamp
    -> max drawdown after timestamp
```

The key question:

```text
At 09:30 or 10:00, can the score identify the day's actual winners before the move is finished?
```

---

## 8. Next file plan

Create the next bundle:

```text
Time-Aware Winner Feature Score v2
```

Suggested files:

```text
docs/winner_feature_score_v2_time_aware_plan.md
sql/create_winner_feature_score_time.sql
src/analysis/build_winner_feature_score_time.py
scripts/build_winner_feature_score_time.ps1
src/review/generate_winner_feature_score_time_dashboard.py
scripts/build_winner_feature_score_time_dashboard.ps1
```

Expected tables:

```text
winner_feature_score_time_result
winner_feature_score_time_summary
```

Expected dashboard:

```text
reports/winner_feature_score_time_dashboard.html
```

---

## 9. How to continue next session

### Step 1. Pull latest code

```powershell
cd E:\2026\Leader_Lab
git pull
```

### Step 2. Rebuild current baseline if needed

```powershell
.\scripts\build_winner_pattern_discovery.ps1
.\scripts\build_winner_feature_score.ps1
.\scripts\build_winner_feature_score_dashboard.ps1
```

### Step 3. Inspect current v1 summary

Look at:

```text
winner_feature_score_summary
reports/winner_feature_score_dashboard.html
```

Expected key result:

```text
Score Top1 daily should show about 90%+ actual Top10 inclusion.
```

### Step 4. Implement Time-Aware Score v2

Do NOT add news/sector/LLM yet.

First remove time leakage.

### Step 5. Only after v2 works

Then add macro/context features:

```text
news exposure
leading sector flag
theme strength
KOSPI/KOSDAQ state
program net buy
foreign/institution behavior
LLM final judgment
```

---

## 10. Design rules going forward

```text
1. Never throw away experiments.
2. Every weak logic becomes either a feature, penalty, or avoidance pattern.
3. Every summary table must connect to a chart dashboard.
4. Never accept a high score before checking whether it uses future data.
5. Build from feature assets toward live decision score.
6. Add macro/news/sector features only after time-aware intraday scoring is stable.
```

---

## 11. Current conclusion

The project is now on the correct track:

```text
single magic pattern
    -> feature asset registry
    -> winner/loser discovery
    -> explainable score
    -> time-aware score
    -> chart-validated trading logic
```

The immediate next milestone is:

```text
Time-Aware Winner Feature Score v2
```

That milestone decides whether the excellent v1 explanatory power can be converted into real-time tradable decision quality.
