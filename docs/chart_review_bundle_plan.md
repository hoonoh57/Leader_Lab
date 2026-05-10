# Chart Review Bundle v1

## Purpose

Build a WYSIWYG review screen:

```text
What you see is what you get.
```

The goal is not to replace the planned buy logic. The goal is to verify visually why the planned buy point produces profit or loss.

## Reviewed buy logic

The first review target is the currently validated high-precision entry group:

```text
entry_filter_name = T_BREAK_RSI_GT60_FIRSTBREAK_BREAKFILL
threshold_pct = 5.5 or 6.0
```

Meaning:

```text
1. A 5-minute candle has open->close return >= threshold_pct.
2. A later candle first breaks the base candle high.
3. RSI14 > 60 at the first breakout candle.
4. Entry assumption is break-fill at base-high breakout price.
5. Exit simulation starts from the next 5-minute candle to avoid same-candle OHLC order ambiguity.
```

## Required visual evidence

For each case, show:

```text
5-minute candles
volume bars
day open line
+5%, +10%, +15%, +20% from day open
singlebar/base candle marker
base high / base low lines
first breakout marker
entry marker
intraday high marker
close marker
actual_rank / actual_max_after_return_pct
entry_from_day_open_pct
break_from_day_open_pct
singlebar_from_day_open_pct
```

## Review questions

```text
1. Is the entry already too overheated versus day open?
2. Does the breakout fail immediately?
3. Was there enough profit opportunity after entry but exit logic missed it?
4. Does the stock collapse into the close despite being an actual daily leader?
5. Does the visual chart agree with the computed result?
```

## First implementation

A static HTML dashboard is generated from DB data:

```text
scripts/build_chart_review_bundle.ps1
  -> build chart_review_case table
  -> generate reports/chart_review_dashboard.html
  -> open it in browser
```

No web server is required for v1.
