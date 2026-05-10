# -*- coding: utf-8 -*-
"""Generate SuperTrend Regime Discovery dashboard v4.

v4 fixes the visual gap between previous-session afternoon candles and the
current session without changing any candle timestamp.

Plotly's default date axis displays the real overnight clock gap. That is not
useful for this review screen because the goal is to compare contiguous trading
bars: previous-session afternoon bars + current-session bars. v4 therefore keeps
all original candle_time values but renders the x-axis as a category axis so the
existing ordered bars are drawn contiguously.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.review import generate_supertrend_regime_discovery_dashboard_v2 as v2
from src.review import generate_supertrend_regime_discovery_dashboard_v3 as v3


def compact_trading_axis(html: str) -> str:
    """Use category x-axis so non-trading overnight gaps are not rendered."""
    html = html.replace(
        "xaxis:{rangeslider:{visible:false}}, yaxis:{title:'Price'}, shapes, annotations, margin:{l:50,r:20,t:28,b:40}",
        "xaxis:{type:'category', categoryorder:'array', categoryarray:x, rangeslider:{visible:false}}, yaxis:{title:'Price'}, shapes, annotations, margin:{l:50,r:20,t:28,b:40}",
    )
    html = html.replace(
        "font:{color:'#e5e7eb'}, margin:{l:50,r:20,t:20,b:40}, yaxis:{title:'Volume'}",
        "font:{color:'#e5e7eb'}, margin:{l:50,r:20,t:20,b:40}, xaxis:{type:'category', categoryorder:'array', categoryarray:x}, yaxis:{title:'Volume'}",
    )
    html = html.replace(
        "Previous Session + Current Session ST Consistency",
        "Previous Session + Current Session ST Consistency — compact trading bars",
    )
    return html


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--output", default="reports/supertrend_regime_discovery_dashboard.html")
    parser.add_argument("--limit", type=int, default=12000)
    parser.add_argument("--warmup-bars", type=int, default=v2.DEFAULT_WARMUP_BARS)
    parser.add_argument("--prev-display-start", default=v2.DEFAULT_PREV_DISPLAY_START)
    args = parser.parse_args()

    v2.load_env(args.env)
    prev_display_start = v2.parse_hhmm(args.prev_display_start)
    conn = v2.open_conn()
    try:
        segments = v2.load_segments(conn, args.limit)
        summary = v2.load_summary(conn)
        feature_summary = v2.load_feature_summary(conn)
        candles, candle_meta = v2.load_candles_for_segments(conn, segments, args.warmup_bars, prev_display_start)
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        html = v2.build_html(segments, candles, candle_meta, summary, feature_summary, args.warmup_bars, args.prev_display_start)
        html = compact_trading_axis(html)
        html = v3.inject_patch(html)
        out.write_text(html, encoding="utf-8")
        print("=== DONE generate_supertrend_regime_discovery_dashboard_v4 ===")
        print("segments=" + str(len(segments)))
        print("candles_groups=" + str(len(candles)))
        print("warmup_bars=" + str(args.warmup_bars))
        print("prev_display_start=" + str(args.prev_display_start))
        print("xaxis_mode=category_compact_trading_bars")
        print("output=" + str(out.resolve()))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
