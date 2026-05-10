# GREAT ST Early Signature Discovery Plan

## Purpose

SuperTrend Regime Discovery created the answer labels:

```text
GREAT = ST uptrend segment reaches +10% or more
GOOD  = ST uptrend segment reaches +5% or more
BAD   = ST uptrend segment fails below +1% or ends negative
```

This next stage finds which features are visible at the start of the ST uptrend segment or within the first 1~3 bars and can separate GREAT/GOOD from BAD.

The goal is not to use full-segment future information such as total `segment_amount` directly as a trading rule.

The goal is:

```text
Convert the GREAT ST answer label into early-detectable real-time features.
```

---

## Key distinction

### Existing label

```text
st_up_max_return_pct >= 10
```

This is a post-event answer label.

### New early signature

```text
ST start + first 1~3 bars information
```

This is potentially usable in real time.

---

## Analysis unit

One row per:

```text
supertrend_regime_segment.id
```

Each row inherits:

```text
trade_date
code
name
st_period
st_multiplier
segment_no
quality_label: GREAT / GOOD / BAD / NEUTRAL
st_up_max_return_pct
st_up_end_return_pct
```

Then the script calculates early features from the first 1, 2, and 3 bars after `st_up_start_time`.

---

## Early feature groups

### 1-bar features

```text
early1_return_pct
early1_high_return_pct
early1_low_drawdown_pct
early1_amount
early1_volume
early1_singlebar_return_pct
early1_break_start_high
```

### 2-bar features

```text
early2_return_pct
early2_high_return_pct
early2_low_drawdown_pct
early2_cum_amount
early2_cum_volume
early2_avg_amount
early2_max_singlebar_return_pct
early2_break_start_high
early2_green_count
```

### 3-bar features

```text
early3_return_pct
early3_high_return_pct
early3_low_drawdown_pct
early3_cum_amount
early3_cum_volume
early3_avg_amount
early3_max_singlebar_return_pct
early3_break_start_high
early3_green_count
early3_amount_accel_ratio
```

### Start-state features copied from ST segment

```text
start_from_day_open_pct
start_from_day_low_pct
start_cum_amount
start_range_so_far_pct
max_singlebar_return_before_start
singlebar_3pct_exists_before_start
singlebar_5pct_exists_before_start
```

---

## What to compare

The main comparison is:

```text
GREAT vs BAD
GOOD_OR_GREAT vs BAD
```

Important questions:

```text
1. Does GREAT show stronger first 1~3 bar amount?
2. Does GREAT show stronger early high-return expansion?
3. Does GREAT avoid early low drawdown?
4. Does GREAT break the ST start bar high quickly?
5. Is start_from_day_open_pct too high in BAD segments?
6. Is start_cum_amount still misleading when used before early confirmation?
7. Which ST parameter gives the clearest early signature?
```

---

## Expected output tables

```text
great_st_early_signature
great_st_early_signature_summary
great_st_early_signature_feature_diff
```

---

## Important rule

Do not treat these as final trading conditions yet.

This stage is still discovery:

```text
answer label -> early feature extraction -> feature difference analysis
```

The next stage after this should be:

```text
GREAT ST Early Score v1
```

where early features are converted into a score.

---

## Expected next command

```powershell
cd E:\2026\Leader_Lab
git pull
.\scripts\build_great_st_early_signature.ps1
```
