# -*- coding: utf-8 -*-
"""Generate SuperTrend dashboard v7 with live candidate overlay.

v7 preserves the historical ST regime review dashboard and overlays
Top Candidate Board v2.9 candidate markers.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Sequence

from src.review import generate_supertrend_regime_discovery_dashboard_v2 as v2
from src.review import generate_supertrend_regime_discovery_dashboard_v5 as v5
from src.review import generate_supertrend_regime_discovery_dashboard_v6 as v6


RAW_VIEW = "supertrend_top_candidate_board_raw_view_v2_9"
DEDUP_VIEW = "supertrend_top_candidate_board_dedup_view_v2_9"


CANDIDATE_COLUMNS: Sequence[str] = (
    "code",
    "name",
    "board_action_v2_8",
    "final_next_action_v2_8",
    "entry_time_text",
    "entry_price",
    "expected_return_pct",
    "mae_risk_pct",
    "tick_confirm_score_v2_6",
    "tick_intensity_v2_6",
    "buy_tick_ratio_v2_6",
    "large_trade_amount_eok_v2_6",
    "hoga_bid_pressure_v2_6",
    "hoga_ask_absorption_v2_6",
    "spread_risk_v2_6",
    "realtime_snapshot_time",
    "realtime_source_tag",
    "trade_date",
    "search_date",
    "st_period",
    "st_multiplier",
)


def table_columns(conn: Any, table_name: str) -> List[str]:
    db_name = v2.env_value(["DB_NAME", "MYSQL_DATABASE", "MYSQL_DB"])
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COLUMN_NAME
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA=%s
              AND TABLE_NAME=%s
            ORDER BY ORDINAL_POSITION
            """,
            (db_name, table_name),
        )
        return [str(row["COLUMN_NAME"]) for row in cur.fetchall()]


def load_candidate_rows(conn: Any, table_name: str, limit: int) -> List[Dict[str, Any]]:
    cols = table_columns(conn, table_name)
    colset = set(cols)
    selected = [c for c in CANDIDATE_COLUMNS if c in colset]
    if not selected:
        return []
    order_col = "dedup_final_rank_no_v2_9" if "dedup_final_rank_no_v2_9" in colset else "final_rank_no_v2_8"
    where_col = "ui_test_all_flag_v2_9" if "ui_test_all_flag_v2_9" in colset else "ui_live_compact_flag_v2_9"
    sql = "SELECT " + ",".join(selected) + " FROM " + table_name
    if where_col in colset:
        sql += " WHERE " + where_col + " = 1"
    if order_col in colset:
        sql += " ORDER BY " + order_col + " ASC"
    sql += " LIMIT %s"
    with conn.cursor() as cur:
        cur.execute(sql, (limit,))
        rows = list(cur.fetchall())
    result: List[Dict[str, Any]] = []
    for row in rows:
        item: Dict[str, Any] = dict(row)
        item["_source_view"] = table_name
        result.append(item)
    return result


def candidate_overlay_patch(candidates_json: str) -> str:
    return """
<style>
  .candidate-overlay-note-v7{
    border:1px solid #2563eb;
    background:#0b1220;
    border-radius:10px;
    padding:10px;
    margin:0 0 10px 0;
    color:#dbeafe;
    font-size:13px;
    line-height:1.5;
  }
  .candidate-overlay-note-v7 b{color:#fbbf24;}
</style>
<script>
window.LIVE_CANDIDATES_V7 = __CANDIDATES_JSON__;
(function(){
  if (window.__leaderLabCandidateOverlayV7Applied) return;
  window.__leaderLabCandidateOverlayV7Applied = true;

  function normDate(v){
    if (v === null || v === undefined) return '';
    return String(v).slice(0, 10);
  }
  function candidateDate(c){
    return normDate(c.trade_date || c.search_date || '');
  }
  function candidateX(c, seg){
    const d = candidateDate(c) || normDate(seg.trade_date);
    let t = String(c.entry_time_text || '').trim();
    if (t.length === 0) return null;
    if (t.length === 5) t = t + ':00';
    if (t.indexOf('T') >= 0) return t;
    return d + 'T' + t;
  }
  function candidateY(c){
    const y = Number(c.entry_price);
    return isNaN(y) ? null : y;
  }
  function sameCandidateScope(c, seg){
    if (String(c.code) !== String(seg.code)) return false;
    const cd = candidateDate(c);
    if (cd && cd !== normDate(seg.trade_date)) return false;
    if (c.st_period !== undefined && c.st_period !== null && Number(c.st_period) !== Number(seg.st_period)) return false;
    if (c.st_multiplier !== undefined && c.st_multiplier !== null && Number(c.st_multiplier).toFixed(1) !== Number(seg.st_multiplier).toFixed(1)) return false;
    return true;
  }
  function actionSymbol(action){
    if (action === 'AUTO_BUY_READY') return 'star';
    if (action === 'WATCH_HOGA_TICK') return 'diamond';
    return 'x';
  }
  function actionSize(action){
    if (action === 'AUTO_BUY_READY') return 18;
    if (action === 'WATCH_HOGA_TICK') return 14;
    return 10;
  }
  function actionName(action){
    if (action === 'AUTO_BUY_READY') return 'AUTO BUY READY';
    if (action === 'WATCH_HOGA_TICK') return 'WATCH HOGA TICK';
    return 'REJECT';
  }
  function actionColor(action){
    if (action === 'AUTO_BUY_READY') return '#fbbf24';
    if (action === 'WATCH_HOGA_TICK') return '#60a5fa';
    return '#94a3b8';
  }
  function buildCandidateTraces(seg){
    const rows = (window.LIVE_CANDIDATES_V7 || []).filter(function(c){ return sameCandidateScope(c, seg); });
    const groups = {'AUTO_BUY_READY': [], 'WATCH_HOGA_TICK': [], 'REJECT': []};
    rows.forEach(function(c){
      const action = String(c.board_action_v2_8 || 'REJECT');
      if (!groups[action]) groups[action] = [];
      groups[action].push(c);
    });
    const traces = [];
    Object.keys(groups).forEach(function(action){
      const arr = groups[action];
      if (!arr.length) return;
      const xs = [];
      const ys = [];
      const texts = [];
      arr.forEach(function(c){
        const x = candidateX(c, seg);
        const y = candidateY(c);
        if (x === null || y === null) return;
        xs.push(x);
        ys.push(y);
        texts.push(
          actionName(action) + '<br>' +
          String(c.code) + ' ' + String(c.name || '') + '<br>' +
          'entry=' + String(c.entry_time_text || '') + ' / price=' + String(c.entry_price || '') + '<br>' +
          'tickScore=' + Number(c.tick_confirm_score_v2_6 || 0).toFixed(2) +
          ' tickIntensity=' + Number(c.tick_intensity_v2_6 || 0).toFixed(2) + '<br>' +
          'buyTick=' + Number(c.buy_tick_ratio_v2_6 || 0).toFixed(2) +
          ' bidPressure=' + Number(c.hoga_bid_pressure_v2_6 || 0).toFixed(2) + '<br>' +
          'askAbsorb=' + Number(c.hoga_ask_absorption_v2_6 || 0).toFixed(2) +
          ' spreadRisk=' + Number(c.spread_risk_v2_6 || 0).toFixed(2)
        );
      });
      if (!xs.length) return;
      traces.push({
        type:'scatter',
        mode:'markers+text',
        x:xs,
        y:ys,
        text:arr.map(function(c){ return String(c.board_action_v2_8 || ''); }),
        hovertext:texts,
        hoverinfo:'text',
        textposition:'top center',
        name:'Candidate ' + actionName(action),
        marker:{size:actionSize(action), symbol:actionSymbol(action), color:actionColor(action), line:{width:1, color:'#111827'}}
      });
    });
    return traces;
  }
  function insertOverlayNote(){
    const main = document.querySelector('.main') || document.querySelector('main');
    if (!main || document.getElementById('candidateOverlayNoteV7')) return;
    const box = document.createElement('div');
    box.id = 'candidateOverlayNoteV7';
    box.className = 'candidate-overlay-note-v7';
    box.innerHTML = '<b>Live Candidate Overlay v7:</b> Summary / Good-vs-Bad / GREAT-BAD labels remain as the reference map. AUTO_BUY_READY / WATCH_HOGA_TICK / REJECT markers show where the live-safe v2.9 candidate logic appears on that map.';
    main.insertBefore(box, main.firstChild);
  }
  function patchRenderChart(){
    if (typeof renderChart !== 'function' || typeof segments === 'undefined') {
      window.setTimeout(patchRenderChart, 100);
      return;
    }
    if (window.__leaderLabRenderChartOverlayV7Patched) return;
    window.__leaderLabRenderChartOverlayV7Patched = true;
    const original = renderChart;
    renderChart = function(seg){
      original(seg);
      const extra = buildCandidateTraces(seg);
      if (extra.length) {
        Plotly.addTraces('chart', extra);
      }
    };
    window.renderChart = renderChart;
  }
  function tick(){
    insertOverlayNote();
    patchRenderChart();
    window.setTimeout(tick, 300);
  }
  tick();
})();
</script>
""".replace("__CANDIDATES_JSON__", candidates_json)


def inject_patch(html: str, patch: str) -> str:
    marker = "</body>"
    if marker not in html:
        return html + patch
    return html.replace(marker, patch + "\n" + marker)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--output", default="reports/supertrend_regime_discovery_dashboard_v7_overlay.html")
    parser.add_argument("--limit", type=int, default=12000)
    parser.add_argument("--candidate-limit", type=int, default=500)
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
        raw_candidates = load_candidate_rows(conn, RAW_VIEW, args.candidate_limit)
        dedup_candidates = load_candidate_rows(conn, DEDUP_VIEW, args.candidate_limit)
        candidates = raw_candidates + dedup_candidates
        html = v2.build_html(segments, candles, candle_meta, summary, feature_summary, args.warmup_bars, args.prev_display_start)
        html = v5.compact_base_axis(html)
        html = v5.inject_patch(html)
        html = v6.inject_patch(html, v6.CLARITY_PATCH)
        html = v6.inject_patch(html, v6.CLICK_PATCH)
        candidates_json = json.dumps(candidates, ensure_ascii=False, default=v2.json_default)
        html = inject_patch(html, candidate_overlay_patch(candidates_json))
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print("=== DONE generate_supertrend_regime_discovery_dashboard_v7 ===")
        print("segments=" + str(len(segments)))
        print("chart_groups=" + str(len(candles)))
        print("raw_candidates=" + str(len(raw_candidates)))
        print("dedup_candidates=" + str(len(dedup_candidates)))
        print("candidate_overlay=enabled")
        print("output=" + str(out.resolve()))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
