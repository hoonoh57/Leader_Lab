# -*- coding: utf-8 -*-
"""Generate SuperTrend Regime Discovery dashboard v5.

v5 fixes three review issues:

1. Compact trading-bar x-axis with readable labels.
   - Original candle_time values are preserved.
   - The chart uses Plotly category axis only for display compaction.
   - A date label is shown only when the trading date changes.
   - Other major ticks show only HH:MM.

2. User selection is respected.
   - The first load may auto-select a segment with previous-session display.
   - After that, clicking the left segment list always draws that exact segment.

3. Console report is expanded.
   - The generator prints segment counts, selected parameter summaries,
     chart-data coverage, previous-session coverage, and consistency counts.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.review import generate_supertrend_regime_discovery_dashboard_v2 as v2


PATCH_SCRIPT = r"""
<script>
(function(){
  if (window.__leaderLabDashboardV5Applied) return;
  window.__leaderLabDashboardV5Applied = true;

  function patchWhenReady(){
    if (typeof segments === 'undefined' || typeof candles === 'undefined' || typeof candleMeta === 'undefined') {
      window.setTimeout(patchWhenReady, 100);
      return;
    }
    if (typeof paramOf !== 'function' || typeof keyOf !== 'function' || typeof selectSegment !== 'function' || typeof fmt !== 'function') {
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

    function firstCurrentSessionRow(arr){
      for (let i = 0; i < arr.length; i++) {
        if (Number(arr[i].is_after_0900) === 1) return arr[i];
      }
      return null;
    }

    function timePart(ts){
      const text = String(ts || '');
      return text.length >= 16 ? text.slice(11,16) : text;
    }

    function datePart(ts){
      const text = String(ts || '');
      return text.length >= 10 ? text.slice(0,10) : text;
    }

    function buildReadableTicks(arr){
      const vals = [];
      const texts = [];
      let prevDate = '';
      const wanted = {'09:05':1, '10:00':1, '11:00':1, '12:00':1, '13:00':1, '14:00':1, '15:00':1, '15:30':1};
      for (let i = 0; i < arr.length; i++) {
        const ts = arr[i].t;
        const d = datePart(ts);
        const hm = timePart(ts);
        if (d !== prevDate) {
          vals.push(ts);
          texts.push(d.slice(5) + '<br>' + hm);
          prevDate = d;
        } else if (wanted[hm]) {
          vals.push(ts);
          texts.push(hm);
        }
      }
      return {vals: vals, texts: texts};
    }

    function renderSelectedChart(s){
      const key = keyOf(s);
      const arr = candles[key] || [];
      const meta = candleMeta[key] || {};
      const x = arr.map(function(r){ return r.t; });
      const open = arr.map(function(r){ return Number(r.o); });
      const high = arr.map(function(r){ return Number(r.h); });
      const low = arr.map(function(r){ return Number(r.l); });
      const close = arr.map(function(r){ return Number(r.c); });
      const vol = arr.map(function(r){ return Number(r.v); });
      const stUp = arr.map(function(r){ return r.st_up === null || r.st_up === undefined ? null : Number(r.st_up); });
      const stDown = arr.map(function(r){ return r.st_down === null || r.st_down === undefined ? null : Number(r.st_down); });
      const shapes = [];
      const annotations = [];
      const prevRows = arr.filter(function(r){ return Number(r.is_prev_session_display) === 1; });
      const firstCurrent = firstCurrentSessionRow(arr);
      const openX = firstCurrent ? firstCurrent.t : null;

      if (prevRows.length > 0) {
        shapes.push({type:'rect', xref:'x', yref:'paper', x0:prevRows[0].t, x1:prevRows[prevRows.length-1].t, y0:0, y1:1, fillcolor:'rgba(148,163,184,0.12)', line:{width:0}, layer:'below'});
        annotations.push({xref:'x', yref:'paper', x:prevRows[0].t, y:1, text:`prev ${meta.prev_date || ''}`, showarrow:false, font:{size:11, color:'#cbd5e1'}});
      }
      if (openX) {
        shapes.push({type:'line', xref:'x', x0:openX, x1:openX, yref:'paper', y0:0, y1:1, line:{width:2, dash:'dot', color:'#fbbf24'}});
        annotations.push({xref:'x', yref:'paper', x:openX, y:1, text:'09:00', showarrow:false, yanchor:'bottom', font:{size:12, color:'#fbbf24'}});
      }
      if (s.st_up_start_time && s.st_up_end_time) {
        shapes.push({type:'rect', xref:'x', yref:'paper', x0:s.st_up_start_time, x1:s.st_up_end_time, y0:0, y1:1, fillcolor:'rgba(34,197,94,0.14)', line:{width:0}, layer:'below'});
      }
      if (s.capture_time) {
        shapes.push({type:'line', xref:'x', x0:s.capture_time, x1:s.capture_time, yref:'paper', y0:0, y1:1, line:{width:1, dash:'dot', color:'#93c5fd'}});
      }
      if (s.st_up_start_time) {
        shapes.push({type:'line', xref:'x', x0:s.st_up_start_time, x1:s.st_up_start_time, yref:'paper', y0:0, y1:1, line:{width:2, dash:'dash', color:'#22c55e'}});
      }
      if (s.st_up_end_time) {
        shapes.push({type:'line', xref:'x', x0:s.st_up_end_time, x1:s.st_up_end_time, yref:'paper', y0:0, y1:1, line:{width:2, dash:'dashdot', color:'#ef4444'}});
      }
      if (firstCurrent && firstCurrent.o !== null && firstCurrent.o !== undefined && x.length > 0) {
        shapes.push({type:'line', xref:'x', x0:x[0], x1:x[x.length-1], yref:'y', y0:Number(firstCurrent.o), y1:Number(firstCurrent.o), line:{width:1, dash:'dot', color:'#a78bfa'}});
      }

      const ticks = buildReadableTicks(arr);
      const commonX = {type:'category', categoryorder:'array', categoryarray:x, tickmode:'array', tickvals:ticks.vals, ticktext:ticks.texts, tickangle:0, rangeslider:{visible:false}};
      const traces = [
        {type:'candlestick', x:x, open:open, high:high, low:low, close:close, name:'5m'},
        {type:'scatter', x:x, y:stUp, mode:'lines', name:'ST Up', connectgaps:false, line:{width:2, color:'#22c55e'}},
        {type:'scatter', x:x, y:stDown, mode:'lines', name:'ST Down', connectgaps:false, line:{width:2, color:'#f97316'}},
        {type:'scatter', mode:'markers+text', x:[s.st_up_start_time], y:[Number(s.st_up_start_price)], text:['ST Start'], textposition:'bottom center', marker:{size:11, color:'#f59e0b'}, name:'ST Start'},
        {type:'scatter', mode:'markers+text', x:[s.st_up_end_time], y:[Number(s.st_up_end_price)], text:['ST End'], textposition:'bottom center', marker:{size:11, color:'#22c55e'}, name:'ST End'},
        {type:'scatter', mode:'markers+text', x:[s.st_up_start_time], y:[Number(s.st_up_max_price)], text:[`Max ${fmt(s.st_up_max_return_pct)}%`], textposition:'top center', marker:{size:12, color:'#ef4444'}, name:'ST Max'}
      ];
      Plotly.react('chart', traces, {paper_bgcolor:'#0f172a', plot_bgcolor:'#0f172a', font:{color:'#e5e7eb'}, xaxis:commonX, yaxis:{title:'Price'}, shapes:shapes, annotations:annotations, margin:{l:50,r:20,t:28,b:48}}, {responsive:true});
      Plotly.react('volume', [{type:'bar', x:x, y:vol, name:'volume'}], {paper_bgcolor:'#0f172a', plot_bgcolor:'#0f172a', font:{color:'#e5e7eb'}, xaxis:commonX, yaxis:{title:'Volume'}, margin:{l:50,r:20,t:20,b:48}}, {responsive:true});
    }

    renderChart = renderSelectedChart;

    const originalSelectSegment = window.selectSegment;
    window.selectSegment = function(id, rerender=true){
      selectedId = id;
      const s = segments.find(function(x){ return x.id === id; });
      if (!s) return;
      renderInfo(s);
      renderChart(s);
      if (rerender) renderList();
    };

    const initial = firstPrevSessionSegmentForCurrentParam();
    if (initial) {
      window.selectSegment(initial.id, true);
    }

    const header = document.querySelector('header h1');
    if (header) {
      header.textContent = 'SuperTrend Regime Discovery Dashboard — compact bars / readable time labels / exact click selection';
    }
  }
  patchWhenReady();
})();
</script>
"""


def inject_patch(html: str) -> str:
    marker = "</body>"
    if marker not in html:
        return html + PATCH_SCRIPT
    return html.replace(marker, PATCH_SCRIPT + "\n" + marker)


def compact_base_axis(html: str) -> str:
    html = html.replace(
        "xaxis:{rangeslider:{visible:false}}, yaxis:{title:'Price'}, shapes, annotations, margin:{l:50,r:20,t:28,b:40}",
        "xaxis:{type:'category', categoryorder:'array', categoryarray:x, rangeslider:{visible:false}}, yaxis:{title:'Price'}, shapes, annotations, margin:{l:50,r:20,t:28,b:40}",
    )
    html = html.replace(
        "font:{color:'#e5e7eb'}, margin:{l:50,r:20,t:20,b:40}, yaxis:{title:'Volume'}",
        "font:{color:'#e5e7eb'}, margin:{l:50,r:20,t:20,b:40}, xaxis:{type:'category', categoryorder:'array', categoryarray:x}, yaxis:{title:'Volume'}",
    )
    return html


def build_report(segments: List[Dict[str, Any]], candles: Dict[str, List[Dict[str, Any]]], candle_meta: Dict[str, Dict[str, Any]], summary: List[Dict[str, Any]], feature_summary: List[Dict[str, Any]]) -> None:
    print("\n=== Dashboard v5 Data Report ===")
    print("segment_rows=" + str(len(segments)))
    print("chart_groups=" + str(len(candles)))
    prev_ok = 0
    st_up_ok = 0
    st_down_ok = 0
    min_display = None
    max_display = 0
    total_display = 0
    for key, arr in candles.items():
        n = len(arr)
        total_display += n
        if min_display is None or n < min_display:
            min_display = n
        if n > max_display:
            max_display = n
        if any(int(r.get("is_prev_session_display") or 0) == 1 for r in arr):
            prev_ok += 1
        if any(r.get("st_up") is not None for r in arr):
            st_up_ok += 1
        if any(r.get("st_down") is not None for r in arr):
            st_down_ok += 1
    avg_display = 0.0 if len(candles) == 0 else float(total_display) / float(len(candles))
    print("groups_with_prev_session=" + str(prev_ok))
    print("groups_with_st_up=" + str(st_up_ok))
    print("groups_with_st_down=" + str(st_down_ok))
    print("display_bars_min=" + str(min_display or 0))
    print("display_bars_avg=" + f"{avg_display:.2f}")
    print("display_bars_max=" + str(max_display))
    print("\n=== Summary by ST Parameter / Group ===")
    for row in summary:
        period = int(row.get("st_period") or 0)
        multiplier = float(row.get("st_multiplier") or 0.0)
        group = str(row.get("segment_group"))
        count = int(row.get("segment_count") or 0)
        bars = float(row.get("avg_st_up_bars") or 0.0)
        max_ret = float(row.get("avg_st_up_max_return_pct") or 0.0)
        end_ret = float(row.get("avg_st_up_end_return_pct") or 0.0)
        g5 = float(row.get("gain5_rate") or 0.0) * 100.0
        g10 = float(row.get("gain10_rate") or 0.0) * 100.0
        fail1 = float(row.get("fail1_rate") or 0.0) * 100.0
        print(f"ST {period}:{multiplier:.1f} {group:22s} N={count:5d} bars={bars:6.2f} max={max_ret:6.2f}% end={end_ret:6.2f}% G5={g5:6.2f}% G10={g10:6.2f}% Fail1={fail1:6.2f}%")
    print("\n=== Top Feature Differences ===")
    for row in feature_summary[:20]:
        feature = str(row.get("feature_name"))
        period = int(row.get("st_period") or 0)
        multiplier = float(row.get("st_multiplier") or 0.0)
        good = float(row.get("good_avg_value") or 0.0)
        bad = float(row.get("bad_avg_value") or 0.0)
        diff = float(row.get("diff_avg_value") or 0.0)
        if "amount" in feature:
            good = good / 100000000.0
            bad = bad / 100000000.0
            diff = diff / 100000000.0
            unit = "억"
        else:
            unit = ""
        print(f"ST {period}:{multiplier:.1f} {feature:34s} good={good:10.2f}{unit} bad={bad:10.2f}{unit} diff={diff:10.2f}{unit}")


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
        html = compact_base_axis(html)
        html = inject_patch(html)
        out.write_text(html, encoding="utf-8")
        print("=== DONE generate_supertrend_regime_discovery_dashboard_v5 ===")
        print("warmup_bars=" + str(args.warmup_bars))
        print("prev_display_start=" + str(args.prev_display_start))
        print("xaxis_mode=category_compact_readable_ticks")
        print("selection_mode=exact_click_after_initial_autoselect")
        print("output=" + str(out.resolve()))
        build_report(segments, candles, candle_meta, summary, feature_summary)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
