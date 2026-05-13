# Leader Reaccel + VIX Warning Overlay v1

Date: 2026-05-14
Repository: hoonoh57/Leader_Lab

## Purpose

Leader_Reaccel is promoted as the practical main strategy candidate.
VIX should not be discarded. It should be converted from a direct entry strategy into a reference / warning / confidence indicator.

Core idea:

```text
Leader_Reaccel = main actionable entry framework
VIX signal = auxiliary information layer
```

VIX becomes useful when a stock is near Leader_Reaccel boundary conditions:

```text
If Leader_Reaccel score is not yet fully confirmed,
but VIX-like strength appears,
raise an early warning / watch alert rather than immediate full-size entry.
```

## Why this is necessary

Raw VIX entry has live-trading risk:

```text
+10% breakout may not be observable early enough.
A stock can already be extended before 09:00 reliable 5-minute candle availability.
```

But VIX still has valuable information:

```text
It detects strong price impulse and market attention.
It can warn that a stock is becoming a leader candidate.
It can improve confidence when combined with cooldown/reacceleration logic.
```

## Role separation

```text
Leader_Reaccel:
    primary entry condition
    requires cooldown/reclaim/reacceleration
    better suited for reproducible live entries

VIX overlay:
    early warning signal
    extension risk detector
    confidence booster or penalty
    position sizing input
    watchlist elevation trigger
```

## VIX-derived indicators

### VIX impulse score

```text
vix_impulse_score = strength of +10% breakout / near-breakout move
```

Candidate components:

```text
return_from_prev_close_pct
is_near_10pct_zone
reached_10pct_flag
minutes_to_10pct
amount_to_10pct
amount_velocity_to_10pct
post_10pct_hold_ratio
```

### VIX extension risk score

```text
vix_extension_risk_score = risk that stock is already too extended when observable
```

Candidate components:

```text
first_available_bar_open_return_pct
first_available_bar_high_return_pct
first_available_bar_close_return_pct
open_extension_bucket
preobservable_breakout_risk_flag
```

### VIX early warning state

```text
VIX_WARNING_NONE
VIX_WATCH
VIX_ALERT
VIX_OVEREXTENDED_RISK
```

Initial rules:

```text
if return_from_prev_close >= 8 and amount_velocity strong:
    VIX_WATCH

if reached_10pct and Leader_Reaccel score is near threshold:
    VIX_ALERT

if first_available_bar_open_return >= 15:
    VIX_OVEREXTENDED_RISK
```

## Integration with Leader Reaccel

Leader_Reaccel score:

```text
leader_reaccel_score =
    trend_score
  + rsi_cooldown_reclaim_score
  + reaccel_candle_score
  + participation_score
  + basebar_context_score
  + market_theme_confidence_score
  - extension_risk_penalty
```

Add VIX overlay:

```text
final_score =
    leader_reaccel_score
  + vix_warning_bonus
  - vix_extension_risk_penalty
```

But VIX bonus must be capped:

```text
VIX can elevate a watch candidate,
but it should not override failed Leader_Reaccel core conditions.
```

## Boundary-case behavior

If Leader_Reaccel is close to entry threshold:

```text
Example:
RSI cooldown exists
close near MA20 reclaim
participation rising
but RSI has not crossed reclaim level yet
```

Then VIX overlay can:

```text
1. raise pre-alert
2. move stock to top watchlist
3. start tighter real-time monitoring
4. reduce confirmation delay
5. prepare order but not necessarily execute full entry
```

## Suggested UI labels

```text
Leader_Reaccel_READY
Leader_Reaccel_NEAR
VIX_EARLY_WARNING
VIX_OVEREXTENDED
THEME_CONFIRMED
FOLLOWER_CATCHUP
```

## Trading action mapping

```text
Leader_Reaccel_READY + VIX_ALERT + ThemeConfirmed:
    normal or high confidence entry

Leader_Reaccel_NEAR + VIX_ALERT:
    early warning / watch / small probe only after additional confirmation

VIX_ALERT but Leader_Reaccel not near:
    watch only, no main entry

VIX_OVEREXTENDED:
    avoid chase or sharply reduce size
```

## Benchmark modes

```text
A. Leader_Reaccel only
B. Leader_Reaccel + VIX warning bonus
C. Leader_Reaccel + VIX extension penalty
D. Leader_Reaccel + VIX warning + theme confidence
E. TopN by final_score
```

## Required outputs

```text
reports/leader_reaccel_vix_warning_overlay_detail_v1.csv
reports/leader_reaccel_vix_warning_overlay_summary_v1.csv
reports/leader_reaccel_vix_warning_overlay_daily_v1.csv
reports/leader_reaccel_vix_warning_overlay_topn_v1.csv
reports/leader_reaccel_vix_warning_overlay_v1.html
```

## Main validation question

```text
Can VIX be used as an early-warning/reference score that improves Leader_Reaccel TopN selection,
without reintroducing the live-trading risk of chasing already-extended stocks?
```

## Promotion rule

VIX overlay is promoted only if it improves:

```text
1. TopN daily performance,
2. avg realized PnL,
3. profit factor,
4. early detection of true leaders,
5. or reduces missed strong reacceleration cases,
```

while not increasing overextended chase losses.
