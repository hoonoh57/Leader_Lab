# ST Dashboard Live Overlay Research v1

Date: 2026-05-13

## Principle

Keep the existing ST review dashboard.

The dashboard already provides useful reference metrics:

```text
Summary
Good vs Bad Feature Diff
GREAT / GOOD / BAD labels
ST Up / ST Down line
ST segment shade
ST Start / End / Max markers
09:00 baseline
previous-session warmup display
```

These are not the final live trading rules. They are the reference map.

## Research question

Overlay live-safe candidate outputs on this reference map and answer:

```text
Do current-time candidate rows overlap with the best ST zones?
How early do they appear before the max-profit zone?
Are they AUTO_BUY_READY, WATCH_HOGA_TICK, or REJECT?
What live-safe features make them overlap better?
```

## Do not remove successful metrics

Do not remove Summary or Good vs Bad Feature Diff.

Do not discard historical GREAT/GOOD/BAD labels.

Use them as the target coordinate system for measuring whether live-safe logic finds the good place and time.

## Live candidate source

Use the v2.9 Top Candidate Board contract:

```text
supertrend_top_candidate_board_raw_view_v2_9
supertrend_top_candidate_board_dedup_view_v2_9
```

## Overlay target

Overlay candidate markers on:

```text
reports/supertrend_regime_discovery_dashboard.html
```

Required marker groups:

```text
AUTO_BUY_READY
WATCH_HOGA_TICK
REJECT
```

## Measurement idea

For each candidate row, measure against the ST segment chart:

```text
candidate_time_to_st_start_bars
candidate_time_to_st_max_bars
candidate_after_entry_max_return_pct
candidate_inside_st_up_segment
candidate_action
candidate_tick_confirm_score
candidate_hoga_tick_features
```

The goal is not analysis for analysis.

The goal is to improve live-safe candidate logic until its points overlap the best historical ST zones as much as possible.
