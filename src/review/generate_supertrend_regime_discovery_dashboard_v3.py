# -*- coding: utf-8 -*-
"""Generate SuperTrend Regime Discovery dashboard v3.

v3 is a thin, safe wrapper around dashboard v2.

Reason:
    The database can contain complete 5-minute candles from 2026-01-05 onward,
    but a selected 2026-01-05 segment cannot have a previous-session display
    because there is no earlier cached trading day before 2026-01-05.

    v2 already renders previous-session afternoon candles when they exist.
    v3 keeps that renderer and post-processes the generated HTML so the initial
    selected segment is the first segment whose chart data actually contains a
    previous-session display. This prevents the dashboard from opening on the
    first date and incorrectly looking as if previous-session rendering failed.

Local rule:
    Do not patch local files with PowerShell. Pull this GitHub change and run.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.review import generate_supertrend_regime_discovery_dashboard_v2 as v2


AUTO_SELECT_PATCH = r"""
<script>
(function(){
  if (window.__leaderLabPrevSessionAutoPatchApplied) return;
  window.__leaderLabPrevSessionAutoPatchApplied = true;

  function patchWhenReady(){
    if (typeof segments === 'undefined' || typeof candles === 'undefined' || typeof candleMeta === 'undefined') {
      window.setTimeout(patchWhenReady, 100);
      return;
    }
    if (typeof paramOf !== 'function' || typeof keyOf !== 'function' || typeof selectSegment !== 'function') {
      window.setTimeout(patchWhenReady, 100);
      return;
    }

    function hasPrevSessionDisplay(seg){
      const arr = candles[keyOf(seg)] || [];
      return arr.some(function(r){ return Number(r.is_prev_session_display) === 1; });
    }

    function firstPrevSessionSegmentForCurrentParam(){
      const p = document.getElementById('paramSelect') ? document.getElementById('paramSelect').value : null;
      for (let i = 0; i < segments.length; i++) {
        const s = segments[i];
        if (p && paramOf(s) !== p) continue;
        if (hasPrevSessionDisplay(s)) return s;
      }
      return null;
    }

    const originalRenderList = window.renderList;
    window.renderList = function(){
      originalRenderList();
      const current = segments.find(function(x){ return x.id === selectedId; });
      if (!current || !hasPrevSessionDisplay(current)) {
        const better = firstPrevSessionSegmentForCurrentParam();
        if (better && better.id !== selectedId) {
          selectSegment(better.id, true);
        }
      }
    };

    const better = firstPrevSessionSegmentForCurrentParam();
    if (better) {
      selectSegment(better.id, true);
    }

    const header = document.querySelector('header h1');
    if (header) {
      header.textContent = header.textContent + ' — v3 auto-selects first segment with previous session';
    }
  }
  patchWhenReady();
})();
</script>
"""


def inject_patch(html: str) -> str:
    marker = "</body>"
    if marker not in html:
        return html + AUTO_SELECT_PATCH
    return html.replace(marker, AUTO_SELECT_PATCH + "\n" + marker)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--output", default="reports/supertrend_regime_discovery_dashboard.html")
    parser.add_argument("--limit", type=int, default=12000)
    parser.add_argument("--warmup-bars", type=int, default=v2.DEFAULT_WARMUP_BARS)
    parser.add_argument("--prev-display-start", default=v2.DEFAULT_PREV_DISPLAY_START)
    args = parser.parse_args()

    rc = v2.main_with_args(args) if hasattr(v2, "main_with_args") else None
    if rc is None:
        # v2 does not expose main_with_args yet, so run the same flow directly.
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
            out.write_text(inject_patch(html), encoding="utf-8")
            print("=== DONE generate_supertrend_regime_discovery_dashboard_v3 ===")
            print("segments=" + str(len(segments)))
            print("candles_groups=" + str(len(candles)))
            print("warmup_bars=" + str(args.warmup_bars))
            print("prev_display_start=" + str(args.prev_display_start))
            print("output=" + str(out.resolve()))
            return 0
        finally:
            conn.close()

    out = Path(args.output)
    if out.exists():
        out.write_text(inject_patch(out.read_text(encoding="utf-8")), encoding="utf-8")
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
