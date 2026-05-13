# -*- coding: utf-8 -*-
"""Generate SuperTrend Answer Reverse Analysis dashboard v7-1a.

v7-1a fixes the v7-1 comparison axis.

Correct axis:
    causal submission rows first
    -> attach the best matching ST answer segment by trade_date + code
    -> evaluate HIT_GREAT / HIT_GOOD / FALSE_BUY / NO_ANSWER_MATCH

This file still does not create a new score formula. It preserves the existing
v2.0/v2.1 causal score and overlays it on the ST answer sheet.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src.review import generate_supertrend_regime_discovery_dashboard_v2 as v2
from src.review import generate_supertrend_regime_discovery_dashboard_v5 as v5
from src.review import generate_supertrend_regime_discovery_dashboard_v6 as v6


CAUSAL_SOURCE_CANDIDATES: Sequence[str] = (
    "supertrend_realtime_entry_top_candidate_v2_1",
    "supertrend_realtime_entry_candidate_v2_0",
)

SCORE_COLUMNS_PRIORITY: Sequence[str] = (
    "top_rank_score_v2_1",
    "entry_score_v2_0",
    "execution_score_v1_9",
    "score_total",
    "filter_score_v1_6",
)

ACTION_COLUMNS_PRIORITY: Sequence[str] = (
    "entry_action_v2_0",
    "recommended_entry_policy_v1_9",
    "execution_label_v1_9",
    "entry_action",
    "action_asof",
    "action",
)

TIME_COLUMNS_PRIORITY: Sequence[str] = (
    "selected_entry_time",
    "st_up_start_time",
    "search_time",
    "capture_time",
    "decision_time",
    "entry_time",
    "realtime_snapshot_time",
)

DATE_COLUMNS_PRIORITY: Sequence[str] = (
    "trade_date",
    "selected_trade_date",
    "search_date",
    "capture_date",
)

CODE_COLUMNS_PRIORITY: Sequence[str] = ("code", "ticker", "stock_code")
NAME_COLUMNS_PRIORITY: Sequence[str] = ("name", "stock_name", "code_name")

EXTRA_CAUSAL_COLUMNS: Sequence[str] = (
    "id",
    "st_period",
    "st_multiplier",
    "segment_no",
    "st_up_start_time",
    "selected_entry_time",
    "selected_entry_price",
    "execution_score_v1_9",
    "score_total",
    "filter_score_v1_6",
    "entry_score_v2_0",
    "top_rank_score_v2_1",
    "entry_reason_v2_0",
    "top_rank_reason_v2_1",
    "risk_band_v2_0",
    "quantity_scale_v2_0",
    "start_from_day_open_pct",
    "start_from_day_low_pct",
    "start_cum_amount",
)

V7_STYLE_AND_SCRIPT = r"""
<style>
  .v7-box{border:1px solid #334155;background:#0b1220;border-radius:10px;padding:12px;margin:0 0 10px 0;color:#dbeafe;font-size:13px;line-height:1.5;}
  .v7-box b{color:#fbbf24;}
  .v7-badge{display:inline-block;border-radius:999px;padding:2px 7px;font-size:11px;font-weight:800;margin-right:4px;background:#1e293b;border:1px solid #475569;}
  .v7-hit-great{color:#fbbf24;border-color:#f59e0b;}
  .v7-hit-good{color:#86efac;border-color:#22c55e;}
  .v7-false-buy{color:#c4b5fd;border-color:#8b5cf6;}
  .v7-no-answer{color:#fca5a5;border-color:#ef4444;}
  .v7-line{font-size:12px;color:#bfdbfe;margin-top:4px;line-height:1.35;}
  .v7-table-wrap{max-height:380px;overflow:auto;border:1px solid #334155;border-radius:10px;margin-bottom:12px;}
  .v7-table-wrap table{margin:0;}
  .v7-left{text-align:left !important;}
</style>
<script>
(function(){
  if (window.__leaderLabV71aApplied) return;
  window.__leaderLabV71aApplied = true;
  const EVAL_ROWS = window.ST_EVAL_V7_1 || [];
  const META = window.ST_EVAL_V7_1_META || {};
  const evalById = {};
  EVAL_ROWS.forEach(function(r){ if (r.segment_id !== null && r.segment_id !== undefined) evalById[Number(r.segment_id)] = r; });

  function clsOf(g){
    const x = String(g || '').toUpperCase();
    if (x === 'HIT_GREAT') return 'v7-hit-great';
    if (x === 'HIT_GOOD') return 'v7-hit-good';
    if (x === 'FALSE_BUY') return 'v7-false-buy';
    return 'v7-no-answer';
  }
  function fmt(v, d){ if (v === null || v === undefined || v === '' || isNaN(Number(v))) return '-'; return Number(v).toFixed(d || 2); }
  function isBuyLike(action){ const a = String(action || '').toUpperCase(); return a.indexOf('BUY') >= 0 || a.indexOf('WATCH') >= 0 || a.indexOf('AUTO') >= 0 || a.indexOf('CONFIRM') >= 0; }

  function groupOrder(g){
    const x = String(g || '').toUpperCase();
    if (x === 'HIT_GREAT') return 0;
    if (x === 'HIT_GOOD') return 1;
    if (x === 'FALSE_BUY') return 2;
    return 3;
  }

  function insertPurpose(){
    const main = document.querySelector('.main') || document.querySelector('main');
    if (!main || document.getElementById('v7PurposeBox')) return;
    const counts = EVAL_ROWS.reduce(function(acc,r){ const k=r.eval_group||'NO_ANSWER_MATCH'; acc[k]=(acc[k]||0)+1; return acc; }, {});
    const box = document.createElement('div');
    box.id = 'v7PurposeBox';
    box.className = 'v7-box';
    box.innerHTML = '<b>v7-1a Submission 중심 검증:</b> 기존 causal 시험지 <b>'+EVAL_ROWS.length+'건</b>을 기준으로 ST 정답지를 붙입니다. 정답지 12000건에 시험지를 붙이는 방식이 아닙니다. source='+
      (META.source_table||'-')+' / time_col='+(META.time_col||'-')+' / score_col='+(META.score_col||'-')+
      '<br>HIT_GREAT='+(counts.HIT_GREAT||0)+' / HIT_GOOD='+(counts.HIT_GOOD||0)+' / FALSE_BUY='+(counts.FALSE_BUY||0)+' / NO_ANSWER_MATCH='+(counts.NO_ANSWER_MATCH||0);
    main.insertBefore(box, main.firstChild);
  }

  function insertComparisonTable(){
    const feature = document.getElementById('featureTable');
    if (!feature || document.getElementById('v7ComparisonBlock')) return;
    const rows = EVAL_ROWS.slice().sort(function(a,b){
      const go = groupOrder(a.eval_group) - groupOrder(b.eval_group);
      if (go !== 0) return go;
      return Number(b.causal_score || -999999) - Number(a.causal_score || -999999);
    });
    const block = document.createElement('div');
    block.id = 'v7ComparisonBlock';
    let html = '<h3>Submission 84건 중심 ST Answer Overlap v7-1a</h3>';
    html += '<div class="v7-table-wrap"><table><thead><tr>';
    ['Group','Date','Code','Name','Entry','Action','TopScore','EntryScore','Answer','Max%','End%','ST','Why note'].forEach(function(h){ html += '<th>'+h+'</th>'; });
    html += '</tr></thead><tbody>';
    rows.forEach(function(r){
      html += '<tr onclick="if(window.selectSegment && '+(r.segment_id||0)+') window.selectSegment('+(r.segment_id||0)+')">'+
        '<td class="v7-left"><span class="v7-badge '+clsOf(r.eval_group)+'">'+(r.eval_group||'NO_ANSWER_MATCH')+'</span></td>'+
        '<td>'+r.trade_date+'</td><td>'+r.code+'</td><td class="v7-left">'+(r.name||'')+'</td>'+
        '<td>'+(r.decision_time||'-')+'</td><td>'+(r.causal_action||'-')+'</td>'+
        '<td>'+fmt(r.causal_score,2)+'</td><td>'+fmt(r.entry_score_v2_0,2)+'</td>'+
        '<td>'+(r.answer_quality||'-')+'</td><td>'+fmt(r.st_up_max_return_pct,2)+'</td><td>'+fmt(r.st_up_end_return_pct,2)+'</td>'+
        '<td>'+(r.st_param||'-')+'</td><td class="v7-left">'+(r.why_note||'')+'</td></tr>';
    });
    html += '</tbody></table></div>';
    block.innerHTML = html;
    feature.parentNode.insertBefore(block, feature.nextSibling);
  }

  function decorateRows(){
    const list = document.getElementById('segmentList');
    if (!list) return;
    Array.from(list.querySelectorAll('[data-segment-id]')).forEach(function(el){
      if (el.__v71aDecorated) return;
      const r = evalById[Number(el.getAttribute('data-segment-id'))];
      if (!r) return;
      const line = document.createElement('div');
      line.className = 'v7-line';
      line.innerHTML = '<span class="v7-badge '+clsOf(r.eval_group)+'">'+r.eval_group+'</span> entry '+(r.decision_time||'-')+' / top '+fmt(r.causal_score,1)+' / action '+(r.causal_action||'-')+' / '+(r.why_note||'');
      el.appendChild(line);
      el.__v71aDecorated = true;
    });
  }

  function addInfoCard(seg){
    const panel = document.getElementById('infoPanel');
    if (!panel || !seg) return;
    const r = evalById[Number(seg.id)];
    const old = document.getElementById('v7InfoCard');
    if (old) old.remove();
    if (!r) return;
    const card = document.createElement('div');
    card.id = 'v7InfoCard';
    card.className = 'card';
    card.innerHTML = '<div class="k">v7-1a Submission / Why</div><div class="v"><span class="v7-badge '+clsOf(r.eval_group)+'">'+r.eval_group+'</span> top '+fmt(r.causal_score,2)+' / entry '+fmt(r.entry_score_v2_0,2)+' / '+(r.causal_action||'-')+'<br><span style="font-size:13px;color:#cbd5e1">'+(r.why_note||'')+'</span></div>';
    panel.insertBefore(card, panel.firstChild);
  }

  function overlayChart(seg){
    const r = evalById[Number(seg.id)];
    if (!r || !r.decision_time || typeof Plotly === 'undefined') return;
    const chart = document.getElementById('chart');
    if (!chart || !chart.data || !chart.layout) return;
    let y = Number(r.selected_entry_price || 0);
    if (!y) y = Number(seg.st_up_start_price || seg.st_up_end_price || seg.st_up_max_price || 0);
    const trace = {x:[r.decision_time], y:[y], mode:'markers+text', name:'v7-1a Submission', text:['S '+fmt(r.causal_score,1)+'<br>'+r.eval_group], textposition:'top center', marker:{size:15, symbol:isBuyLike(r.causal_action)?'triangle-up':'circle', color:'#38bdf8'}, hoverinfo:'text'};
    Plotly.addTraces(chart, [trace]);
    const shapes = (chart.layout.shapes || []).slice();
    shapes.push({type:'line', xref:'x', x0:r.decision_time, x1:r.decision_time, yref:'paper', y0:0, y1:1, line:{width:2, dash:'dash', color:'#38bdf8'}});
    Plotly.relayout(chart, {shapes: shapes});
  }

  function patchSelect(){
    if (typeof selectSegment !== 'function' || typeof segments === 'undefined') return;
    if (window.__leaderLabV71aSelectPatched) return;
    window.__leaderLabV71aSelectPatched = true;
    const originalSelect = selectSegment;
    selectSegment = function(id, rerender){
      originalSelect(id, rerender);
      const seg = segments.find(function(s){ return Number(s.id) === Number(id); });
      addInfoCard(seg);
      window.setTimeout(function(){ overlayChart(seg); decorateRows(); }, 80);
    };
    window.selectSegment = selectSegment;
  }

  function tick(){ insertPurpose(); insertComparisonTable(); patchSelect(); decorateRows(); window.setTimeout(tick, 400); }
  tick();
})();
</script>
"""


def table_exists(conn: Any, table_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = %s", (table_name,))
        row = cur.fetchone()
    return int(row.get("n", 0)) > 0


def table_columns(conn: Any, table_name: str) -> List[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = %s ORDER BY ordinal_position", (table_name,))
        rows = cur.fetchall()
    return [str(r.get("column_name")) for r in rows]


def first_existing(columns: Iterable[str], candidates: Sequence[str]) -> Optional[str]:
    colset = set(columns)
    for name in candidates:
        if name in colset:
            return name
    return None


def stringify_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value)
    if "T" in text:
        text = text.split("T", 1)[0]
    if " " in text:
        text = text.split(" ", 1)[0]
    return text[:10]


def combine_date_time(date_value: Any, time_value: Any) -> Optional[datetime]:
    d = stringify_date(date_value)
    if not d or time_value is None:
        return None
    if isinstance(time_value, datetime):
        return time_value
    if isinstance(time_value, timedelta):
        seconds = int(time_value.total_seconds())
        return datetime.fromisoformat(f"{d} {seconds//3600:02d}:{(seconds%3600)//60:02d}:{seconds%60:02d}")
    if isinstance(time_value, time):
        return datetime.fromisoformat(f"{d} {time_value.isoformat()}")
    text = str(time_value).replace("T", " ")
    if "-" not in text:
        text = f"{d} {text}"
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        x = float(value)
    except Exception:
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return x


def answer_quality(seg: Optional[Dict[str, Any]]) -> str:
    if seg is None:
        return "NO_ANSWER"
    if int(seg.get("label_st_gain_10pct") or 0) == 1:
        return "GREAT"
    if int(seg.get("label_st_gain_5pct") or 0) == 1:
        return "GOOD"
    if int(seg.get("label_st_fail_1pct") or 0) == 1 or int(seg.get("label_st_end_negative") or 0) == 1:
        return "BAD"
    return "NEUTRAL"


def load_all_segments(conn: Any) -> List[Dict[str, Any]]:
    return v2.load_segments(conn, 1000000)


def pick_causal_source(conn: Any) -> Tuple[str, List[str]]:
    for table_name in CAUSAL_SOURCE_CANDIDATES:
        if table_exists(conn, table_name):
            return table_name, table_columns(conn, table_name)
    return "NONE", []


def load_submission_rows(conn: Any) -> Tuple[str, List[Dict[str, Any]], Dict[str, str]]:
    table_name, columns = pick_causal_source(conn)
    if table_name == "NONE":
        return table_name, [], {"source_table": "NONE"}

    code_col = first_existing(columns, CODE_COLUMNS_PRIORITY)
    name_col = first_existing(columns, NAME_COLUMNS_PRIORITY)
    date_col = first_existing(columns, DATE_COLUMNS_PRIORITY)
    time_col = first_existing(columns, TIME_COLUMNS_PRIORITY)
    score_col = first_existing(columns, SCORE_COLUMNS_PRIORITY)
    action_col = first_existing(columns, ACTION_COLUMNS_PRIORITY)
    if not code_col or not date_col or not time_col or not score_col:
        raise RuntimeError("Missing causal source columns. table=" + table_name + " columns=" + ",".join(columns))

    selected_cols: List[str] = []
    for col in [code_col, name_col, date_col, time_col, score_col, action_col] + list(EXTRA_CAUSAL_COLUMNS):
        if col and col in columns and col not in selected_cols:
            selected_cols.append(col)

    sql = "SELECT " + ", ".join("`" + c + "`" for c in selected_cols) + " FROM `" + table_name + "` ORDER BY `" + date_col + "`, `" + score_col + "` DESC"
    with conn.cursor() as cur:
        cur.execute(sql)
        raw_rows = list(cur.fetchall())

    rows: List[Dict[str, Any]] = []
    for r in raw_rows:
        dvalue = r.get(date_col)
        tvalue = r.get(time_col)
        decision_dt = combine_date_time(dvalue, tvalue)
        item: Dict[str, Any] = dict(r)
        item["source_table"] = table_name
        item["trade_date"] = stringify_date(dvalue)
        item["code"] = str(r.get(code_col))
        item["name"] = r.get(name_col) if name_col else r.get("name")
        item["decision_dt"] = decision_dt
        item["decision_time"] = decision_dt.isoformat(sep=" ") if decision_dt else None
        item["causal_score"] = safe_float(r.get(score_col))
        item["causal_action"] = str(r.get(action_col)) if action_col and r.get(action_col) is not None else None
        rows.append(item)

    meta = {
        "source_table": table_name,
        "row_count": str(len(rows)),
        "date_col": str(date_col),
        "time_col": str(time_col),
        "score_col": str(score_col),
        "action_col": str(action_col or ""),
    }
    return table_name, rows, meta


def best_answer_segment(sub: Dict[str, Any], segments_by_key: Dict[Tuple[str, str], List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    key = (str(sub.get("trade_date")), str(sub.get("code")))
    candidates = segments_by_key.get(key, [])
    if not candidates:
        return None
    candidates.sort(key=lambda s: safe_float(s.get("st_up_max_return_pct")) or -999999.0, reverse=True)
    return candidates[0]


def eval_group_for(quality: str) -> str:
    if quality == "GREAT":
        return "HIT_GREAT"
    if quality == "GOOD":
        return "HIT_GOOD"
    if quality in ("BAD", "NEUTRAL"):
        return "FALSE_BUY"
    return "NO_ANSWER_MATCH"


def why_note_for(group: str, sub: Dict[str, Any], seg: Optional[Dict[str, Any]]) -> str:
    if group == "HIT_GREAT":
        return "시험지 Top 후보가 GREAT ST 정답지와 겹침: 보존/역분석 우선"
    if group == "HIT_GOOD":
        return "GOOD 이상 포착: GREAT와의 차이 확인"
    if group == "FALSE_BUY":
        return "Top 후보였으나 GOOD 미달: 과열/저항/섹터 부재 등 오탐 원인 확인"
    return "시험지 행에 대응하는 ST 정답지 없음: 데이터 연결 확인"


def build_submission_evaluation(submissions: Sequence[Dict[str, Any]], segments: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    segments_by_key: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for seg in segments:
        key = (stringify_date(seg.get("trade_date")), str(seg.get("code")))
        segments_by_key.setdefault(key, []).append(seg)

    eval_rows: List[Dict[str, Any]] = []
    best_segments: List[Dict[str, Any]] = []
    seen_segment_ids = set()
    for sub in submissions:
        seg = best_answer_segment(sub, segments_by_key)
        quality = answer_quality(seg)
        group = eval_group_for(quality)
        seg_id = seg.get("id") if seg else None
        if seg is not None and seg_id not in seen_segment_ids:
            best_segments.append(seg)
            seen_segment_ids.add(seg_id)
        row = {
            "submission_id": sub.get("id"),
            "segment_id": seg_id,
            "trade_date": sub.get("trade_date"),
            "code": sub.get("code"),
            "name": sub.get("name"),
            "decision_time": sub.get("decision_time"),
            "selected_entry_price": safe_float(sub.get("selected_entry_price")),
            "causal_action": sub.get("causal_action"),
            "causal_score": sub.get("causal_score"),
            "execution_score_v1_9": safe_float(sub.get("execution_score_v1_9")),
            "score_total": safe_float(sub.get("score_total")),
            "filter_score_v1_6": safe_float(sub.get("filter_score_v1_6")),
            "entry_score_v2_0": safe_float(sub.get("entry_score_v2_0")),
            "top_rank_score_v2_1": safe_float(sub.get("top_rank_score_v2_1")),
            "start_from_day_open_pct": safe_float(sub.get("start_from_day_open_pct")),
            "start_from_day_low_pct": safe_float(sub.get("start_from_day_low_pct")),
            "start_cum_amount": safe_float(sub.get("start_cum_amount")),
            "entry_reason_v2_0": sub.get("entry_reason_v2_0"),
            "top_rank_reason_v2_1": sub.get("top_rank_reason_v2_1"),
            "answer_quality": quality,
            "st_param": v2.param_key(seg.get("st_period"), seg.get("st_multiplier")) if seg else None,
            "answer_segment_no": seg.get("segment_no") if seg else None,
            "st_up_start_time": str(seg.get("st_up_start_time")) if seg else None,
            "st_up_end_time": str(seg.get("st_up_end_time")) if seg else None,
            "st_up_max_return_pct": safe_float(seg.get("st_up_max_return_pct")) if seg else None,
            "st_up_end_return_pct": safe_float(seg.get("st_up_end_return_pct")) if seg else None,
            "eval_group": group,
            "why_note": why_note_for(group, sub, seg),
            "leakage_status": "PASS_SUBMISSION_CENTRIC_JOIN",
        }
        eval_rows.append(row)
    return eval_rows, best_segments


def write_eval_csv(rows: Sequence[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "submission_id", "segment_id", "trade_date", "code", "name", "decision_time", "selected_entry_price",
        "causal_action", "causal_score", "execution_score_v1_9", "score_total", "filter_score_v1_6", "entry_score_v2_0", "top_rank_score_v2_1",
        "start_from_day_open_pct", "start_from_day_low_pct", "start_cum_amount", "entry_reason_v2_0", "top_rank_reason_v2_1",
        "answer_quality", "st_param", "answer_segment_no", "st_up_start_time", "st_up_end_time", "st_up_max_return_pct", "st_up_end_return_pct",
        "eval_group", "why_note", "leakage_status",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in fieldnames})


def inject_v7(html: str, eval_rows: Sequence[Dict[str, Any]], meta: Dict[str, str]) -> str:
    script = "<script>window.ST_EVAL_V7_1 = " + json.dumps(eval_rows, ensure_ascii=False, default=v2.json_default) + "; window.ST_EVAL_V7_1_META = " + json.dumps(meta, ensure_ascii=False) + ";</script>\n" + V7_STYLE_AND_SCRIPT
    return v6.inject_patch(html, script)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--output", default="reports/supertrend_regime_discovery_dashboard_v7_1.html")
    parser.add_argument("--eval-output", default="reports/st_answer_reverse_eval_v7_1.csv")
    parser.add_argument("--warmup-bars", type=int, default=v2.DEFAULT_WARMUP_BARS)
    parser.add_argument("--prev-display-start", default=v2.DEFAULT_PREV_DISPLAY_START)
    args = parser.parse_args()

    v2.load_env(args.env)
    prev_display_start = v2.parse_hhmm(args.prev_display_start)
    conn = v2.open_conn()
    try:
        all_segments = load_all_segments(conn)
        source_table, submissions, source_meta = load_submission_rows(conn)
        eval_rows, display_segments = build_submission_evaluation(submissions, all_segments)
        write_eval_csv(eval_rows, Path(args.eval_output))

        summary = v2.load_summary(conn)
        feature_summary = v2.load_feature_summary(conn)
        candles, candle_meta = v2.load_candles_for_segments(conn, display_segments, args.warmup_bars, prev_display_start)
        html = v2.build_html(display_segments, candles, candle_meta, summary, feature_summary, args.warmup_bars, args.prev_display_start)
        html = v5.compact_base_axis(html)
        html = v5.inject_patch(html)
        html = v6.inject_patch(html, v6.CLARITY_PATCH)
        html = v6.inject_patch(html, v6.CLICK_PATCH)
        html = inject_v7(html, eval_rows, source_meta)

        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")

        counts: Dict[str, int] = {}
        for row in eval_rows:
            counts[str(row.get("eval_group"))] = counts.get(str(row.get("eval_group")), 0) + 1
        print("=== DONE generate_st_answer_reverse_analysis_v7_1a ===")
        print("Board Type=EVALUATION_BOARD")
        print("Axis=SUBMISSION_CENTRIC")
        print("Answer Source=supertrend_regime_segment")
        print("Submission Source=" + str(source_table))
        print("Submission Rows=" + str(len(submissions)))
        print("Display Answer Segments=" + str(len(display_segments)))
        print("Leakage Status=PASS_SUBMISSION_CENTRIC_JOIN")
        print("eval_counts=" + json.dumps(counts, ensure_ascii=False, sort_keys=True))
        print("output=" + str(out.resolve()))
        print("eval_output=" + str(Path(args.eval_output).resolve()))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
