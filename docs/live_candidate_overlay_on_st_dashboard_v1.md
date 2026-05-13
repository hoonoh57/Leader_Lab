# Live Candidate Overlay on ST Dashboard v1

Date: 2026-05-13

## Purpose

Do not remove the SuperTrend regime review dashboard.

Use it as a validation board and overlay the live-safe Top Candidate Board outputs on top of the historical ST regime chart.

## Why this is needed

The current ST dashboard is already useful because it shows:

```text
- previous session display area
- 09:00 baseline
- ST Up line
- ST Down line
- DB segment shade
- ST Start / End / Max markers
- Chart Consistency card
```

The next step is not to discard this board.

The next step is to overlay live candidate decisions from:

```text
supertrend_top_candidate_board_raw_view_v2_9
supertrend_top_candidate_board_dedup_view_v2_9
```

## Required overlay markers

```text
AUTO_BUY_READY marker
WATCH_HOGA_TICK marker
REJECT marker
entry price horizontal line
capture or entry time vertical line
expected return and risk labels as review-only values
```

## Layer separation

Historical regime layer:

```text
ST segment shade
ST Start marker
ST End marker
ST Max marker
GREAT / GOOD / BAD labels
```

Live candidate layer:

```text
AUTO_BUY_READY
WATCH_HOGA_TICK
REJECT
entry_time_text
entry_price
tick_confirm_score_v2_6
tick_intensity_v2_6
buy_tick_ratio_v2_6
large_trade_amount_eok_v2_6
hoga_bid_pressure_v2_6
hoga_ask_absorption_v2_6
spread_risk_v2_6
```

## Validation question

For each good ST regime segment, answer visually:

```text
Was a live-safe candidate generated before or near the profitable part?
Was the candidate AUTO_BUY_READY or only WATCH_HOGA_TICK?
Was the candidate too early, timely, or too late?
Was the max-profit area actually tradable?
```

## UI rule

The dashboard must clearly show two modes:

```text
REGIME_REVIEW_ONLY
LIVE_CANDIDATE_OVERLAY
```

Default can remain historical review, but the overlay mode must make the practical trading validation visible.

## Next implementation step

Build an inspection script that verifies the v2.9 Top Candidate Board views and checks whether each candidate row has enough timestamp and price fields to be plotted on the ST dashboard.
