# -*- coding: utf-8 -*-
"""Generate SuperTrend Regime Discovery dashboard v6.

v6 keeps v5 rendering and fixes the left-list click flow.

Principle:
    The chart must always be drawn from the same prepared candle bundle:
    previous-session afternoon candles + current-session full candles.

Behavior:
    - Initial ALL view lists only segments with previous-session display.
    - If the user explicitly chooses a specific date, that date is respected.
    - Clicking a row calls the exact same chart renderer used by the initial chart.
    - 2026-01-05 can still show only 77 current-session bars because it is the
      first cached date; no previous cached trading day exists before it.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.review import generate_supertrend_regime_discovery_dashboard_v2 as v2
from src.review import generate_supertrend_regime_discovery_dashboard_v5 as v5


CLICK_PATCH = r"""
<script>
(function(){
  if (window.__leaderLabDashboardV6ClickPatchApplied) return;
  window.__leaderLabDashboardV6ClickPatchApplied = true;

  function patchWhenReady(){
    if (typeof segments === 'undefined' || typeof candles === 'undefined' || typeof candleMeta === 'undefined') {
      window.setTimeout(patchWhenReady, 100);
      return;
    }
    if (typeof filteredSegments !== 'function' || typeof paramOf !== 'function' || typeof keyOf !== 'function' || typeof fmt !== 'function') {
      window.setTimeout(patchWhenReady, 100);
      return;
    }

    function hasPrevSessionDisplay(seg){
      const arr = candles[keyOf(seg)] || [];
      return arr.some(function(r){ return Number(r.is_prev_session_display) === 1; });
    }

    function firstPrevDateForParam(paramKey){
      for (let i = 0; i < segments.length; i++) {
        const s = segments[i];
        if (paramOf(s) !== paramKey) continue;
        if (hasPrevSessionDisplay(s)) return s.trade_date;
      }
      return 'ALL';
    }

    function segmentCssClass(s){
      return s.id === selectedId ? 'seg active' : 'seg';
    }

    function renderSegmentRow(s){
      const retCls = Number(s.st_up_max_return_pct) >= 5 ? 'good' : ((Number(s.label_st_fail_1pct)===1 || Number(s.label_st_end_negative)===1) ? 'bad' : 'warn');
      const prevBadge = hasPrevSessionDisplay(s) ? '<span class="pill">prev</span>' : '<span class="pill">no-prev</span>';
      return `<div class="${segmentCssClass(s)}" data-segment-id="${s.id}"><div class="title">${s.trade_date} ${s.code} ${s.name||''} <span class="pill">#${s.segment_no}</span><span class="pill">ST ${paramOf(s)}</span>${prevBadge}</div><div class="meta">max <span class="${retCls}">${fmt(s.st_up_max_return_pct)}%</span> / end ${fmt(s.st_up_end_return_pct)}% / bars ${s.st_up_bars} / startOpen ${fmt(s.start_from_day_open_pct)}% / segAmt ${fmt(Number(s.segment_amount)/100000000)}억</div></div>`;
    }

    selectSegment = function(id, rerender=true){
      selectedId = Number(id);
      const s = segments.find(function(x){ return Number(x.id) === Number(id); });
      if (!s) return;
      renderInfo(s);
      renderChart(s);
      if (rerender) renderList();
    };
    window.selectSegment = selectSegment;

    renderList = function(){
      const dateValue = document.getElementById('dateSelect') ? document.getElementById('dateSelect').value : 'ALL';
      let list = filteredSegments();
      if (dateValue === 'ALL') {
        list = list.filter(hasPrevSessionDisplay);
      }
      segmentList.innerHTML = list.map(renderSegmentRow).join('');
      const rows = Array.from(segmentList.querySelectorAll('[data-segment-id]'));
      rows.forEach(function(el){
        el.addEventListener('click', function(){
          const id = Number(el.getAttribute('data-segment-id'));
          selectSegment(id, true);
        });
      });
      if (list.length && !list.some(function(s){ return Number(s.id) === Number(selectedId); })) {
        selectSegment(list[0].id, false);
      }
    };
    window.renderList = renderList;

    // In ALL mode, opening on the first cached date makes the user think click
    // rendering failed. Start from the first date that has a previous-session
    // bundle, while still allowing explicit 2026-01-05 selection in the date box.
    const paramSelectEl = document.getElementById('paramSelect');
    const dateSelectEl = document.getElementById('dateSelect');
    if (paramSelectEl && dateSelectEl) {
      const wantedDate = firstPrevDateForParam(paramSelectEl.value);
      if (wantedDate !== 'ALL') {
        dateSelectEl.value = wantedDate;
      }
    }
    renderList();

    const header = document.querySelector('header h1');
    if (header) {
      header.textContent = 'SuperTrend Regime Discovery Dashboard — exact clicked row uses previous+current candle bundle';
    }
  }
  patchWhenReady();
})();
</script>
"""


def inject_click_patch(html: str) -> str:
    marker = "</body>"
    if marker not in html:
        return html + CLICK_PATCH
    return html.replace(marker, CLICK_PATCH + "\n" + marker)


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
        html = v5.compact_base_axis(html)
        html = v5.inject_patch(html)
        html = inject_click_patch(html)
        out.write_text(html, encoding="utf-8")
        print("=== DONE generate_supertrend_regime_discovery_dashboard_v6 ===")
        print("warmup_bars=" + str(args.warmup_bars))
        print("prev_display_start=" + str(args.prev_display_start))
        print("xaxis_mode=category_compact_readable_ticks")
        print("selection_mode=exact_click_same_previous_current_bundle")
        print("output=" + str(out.resolve()))
        v5.build_report(segments, candles, candle_meta, summary, feature_summary)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
