# Leader Reacceleration Market / Theme Confidence Overlay v1

Date: 2026-05-14
Repository: hoonoh57/Leader_Lab

## Purpose

Leader reacceleration strategy should not rely only on 5-minute technical signals.

Confidence should rise when the signal is aligned with:

```text
1. market regime
2. sector/theme rotation
3. recent news/theme heat
4. leader-follower structure inside the sector
5. small-cap follow-up movement after a sector leader confirms strength
```

This overlay is not a standalone entry rule. It is a confidence and sizing layer applied to:

```text
Leader_Reaccel_Parametric_v1
```

## Core hypothesis

A high-quality reacceleration signal is strongest when:

```text
A theme or sector recently became hot.
A leader stock already moved first.
The stock cooled down or consolidated.
Then the same stock reaccelerates, or a smaller follower in the same theme starts to follow.
```

This structure can capture:

```text
1. leader re-ignition
2. follower stock catch-up
3. theme rotation continuation
4. second-wave buying after the first spike cools
```

## Market regime overlay

Market condition affects whether aggressive breakout/reacceleration entries should be trusted.

Variables:

```text
kospi_intraday_return_pct
kosdaq_intraday_return_pct
kosdaq_vs_kospi_relative_strength
market_open_gap_pct
market_trend_state_5m
market_st_state
market_jma_slope
market_breadth_proxy
```

Initial confidence rule:

```text
if KOSDAQ is positive and JMA/ST market state is rising:
    confidence += market_bonus
if KOSDAQ is sharply falling:
    confidence -= market_risk_penalty
```

## Theme / sector heat overlay

Theme heat should be measured from actual members, not only text labels.

Variables:

```text
sector_id
theme_id
sector_member_count
sector_avg_intraday_return_pct
sector_top_return_pct
sector_top_amount
sector_rising_member_ratio
sector_amount_velocity
sector_leader_count_over_threshold
```

Initial confidence rule:

```text
if sector rising member ratio is high and top sector amount is strong:
    confidence += sector_heat_bonus
```

## News / theme recency overlay

News and theme recency can add confidence if the stock/theme recently appeared in strong catalysts.

Variables:

```text
news_count_recent_1d
news_count_recent_3d
news_sentiment_score
theme_news_heat_score
catalyst_type
is_policy_theme
is_earnings_theme
is_supply_contract_theme
is_geopolitical_theme
```

Initial confidence rule:

```text
if theme/news heat score is high and price reaccelerates after cooling:
    confidence += news_theme_bonus
```

## Leader-follower structure overlay

The strategy should distinguish:

```text
leader_reaccel
= the same prior leader cools down and reignites.

follower_catchup
= a smaller related stock follows a confirmed leader.
```

Variables:

```text
sector_leader_code
sector_leader_return_pct
sector_leader_amount_rank
sector_leader_signal_time
candidate_market_cap_rank_in_sector
candidate_amount_rank_in_sector
candidate_lag_minutes_after_leader
candidate_relative_strength_vs_leader
```

Initial confidence rules:

```text
if candidate is the sector leader and reaccel signal appears:
    confidence += leader_reaccel_bonus

if candidate is smaller follower and leader is already strong:
    confidence += follower_catchup_bonus

if follower signal appears too late after leader exhaustion:
    confidence -= late_follower_penalty
```

## Composite confidence score

Initial formula:

```text
confidence_score =
    technical_reaccel_score
  + participation_score
  + basebar_context_score
  + market_regime_score
  + sector_theme_heat_score
  + news_theme_score
  + leader_follower_score
  - extension_risk_penalty
  - late_follower_penalty
```

All components must be displayed in the report to preserve WYSIWYT analysis.

## Integration with condition search

The condition search remains the source universe.

Pipeline:

```text
Kiwoom condition-captured universe
→ Leader_Reaccel technical signal
→ market/theme/news confidence overlay
→ TopN selection
→ VIX_JMA_PARTIAL_TRAIL_v1-style exit or safer derivative exit
```

## Required benchmark modes

```text
A. Leader_Reaccel technical only
B. Leader_Reaccel + market regime score
C. Leader_Reaccel + sector/theme score
D. Leader_Reaccel + leader/follower score
E. Full confidence overlay
F. TopN per day by confidence score
```

## Required output files

```text
reports/leader_reaccel_confidence_overlay_detail_v1.csv
reports/leader_reaccel_confidence_overlay_summary_v1.csv
reports/leader_reaccel_confidence_overlay_daily_v1.csv
reports/leader_reaccel_confidence_overlay_topn_v1.csv
reports/leader_reaccel_confidence_overlay_v1.html
```

## Main evaluation metrics

```text
entry_count
win_rate
loss_rate
avg_realized_pnl_pct
total_realized_pnl_pct
profit_factor
avg_mfe_pct
avg_mae_pct
daily_positive_rate
max_daily_loss
Top3/Top5/Top6 performance
```

## Implementation sequence

```text
Step 1. Add market index columns if available.
Step 2. Add sector/theme mapping columns from DB.
Step 3. Compute sector intraday heat from member returns and amount.
Step 4. Add leader/follower detection using sector leader code and lag.
Step 5. Add news/theme score placeholder, then replace with real news DB when available.
Step 6. Run TopN benchmark by confidence score.
```

## Promotion rule

A confidence overlay is useful only if it improves at least one of:

```text
1. TopN daily performance
2. profit factor
3. avg MAE reduction
4. daily positive rate
5. reduction of late/exhausted entries
```

without destroying total opportunity count too severely.
