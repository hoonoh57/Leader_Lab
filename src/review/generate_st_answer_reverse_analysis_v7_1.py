# -*- coding: utf-8 -*-
"""Generate SuperTrend Answer Reverse Analysis dashboard v7-1.

v7-1 is intentionally small.
It does not create a new score formula. It overlays an existing causal submission
score/action, when available, on the existing SuperTrend answer dashboard.

Board guard:
    Board Type: EVALUATION_BOARD
    Answer source: supertrend_regime_segment
    Submission source: existing v2.0/v2.1 causal candidate tables
    Causal rank basis: selected causal score fields only
    Answer fields: display/evaluation only after join
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

FORBIDDEN_CAUSAL_RANK_COLUMNS: Sequence[str] = (
    "st_up_max_return_pct",
    "st_up_end_time",
    "st_up_max_price",
    "label_st_gain_3pct",
    "label_st_gain_5pct",
    "label_st_gain_10pct",
    "max_ret_in_period",
    "actual_rank_by_max_ret",
    "ret_1m",
    "ret_3m",
    "ret_7h",
    "expected_return_pct",
    "mae_risk_pct",
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
    "entry_action",
    "action_asof",
    "action",
)

RANK_COLUMNS_PRIORITY: Sequence[str] = (
    "causal_rank_v3_9",
    "top_rank_v2_1",
    "rank_asof",
    "rank",
)

DATE_COLUMNS_PRIORITY: Sequence[str] = (
    "trade_date",
    "selected_trade_date",
    "search_date",
    "capture_date",
)

TIME_COLUMNS_PRIORITY: Sequence[str] = (
    "search_time",
    "capture_time",
    "decision_time",
    "entry_time",
    "realtime_snapshot_time",
)

CODE_COLUMNS_PRIORITY: Sequence[str] = ("code", "ticker", "stock_code")
NAME_COLUMNS_PRIORITY: Sequence[str] = ("name", "stock_name", "code_name")

V7_STYLE_AND_SCRIPT = r"""
<style>
  .v7-box{border:1px solid #334155;background:#0b1220;border-radius:10px;padding:12px;margin:0 0 10px 0;color:#dbeafe;font-size:13px;line-height:1.5;}
  .v7-box b{color:#fbbf24;}
  .v7-badge{display:inline-block;border-radius:999px;padding:2px 7px;font-size:11px;font-weight:800;margin-right:4px;background:#1e293b;border:1px solid #475569;}
  .v7-hit-great{color:#fbbf24;border-color:#f59e0b;}
  .v7-missed-great{color:#fca5a5;border-color:#ef4444;}
  .v7-false-buy{color:#c4b5fd;border-color:#8b5cf6;}
  .v7-true-reject{color:#94a3b8;border-color:#64748b;}
  .v7-no-submission{color:#93c5fd;border-color:#3b82f6;}
  .v7-line{font-size:12px;color:#bfdbfe;margin-top:4px;line-height:1.35;}
  .v7-table-wrap{max-height:360px;overflow:auto;border:1px solid #334155;border-radius:10px;margin-bottom:12px;}
  .v7-table-wrap table{margin:0;}
  .v7-left{text-align:left !important;}
</style>
<script>
(function(){
  if (window.__leaderLabV71Applied) return;
  window.__leaderLabV71Applied = true;

  const EVAL_ROWS = window.ST_EVAL_V7_1 || [];
  const evalById = {};
  EVAL_ROWS.forEach(function(r){ evalById[Number(r.segment_id)] = r; });

  function clsOf(g){
    const x = String(g || '').toUpperCase();
    if (x === 'HIT_GREAT') return 'v7-hit-great';
    if (x === 'MISSED_GREAT') return 'v7-missed-great';
    if (x === 'FALSE_BUY') return 'v7-false-buy';
    if (x === 'TRUE_REJECT') return 'v7-true-reject';
    return 'v7-no-submission';
  }
  function fmt(v, d){
    if (v === null || v === undefined || v === '' || isNaN(Number(v))) return '-';
    return Number(v).toFixed(d || 2);
  }
  function isBuyLike(action){
    const a = String(action || '').toUpperCase();
    return a.indexOf('BUY') >= 0 || a.indexOf('WATCH') >= 0 || a.indexOf('AUTO') >= 0;
  }
  function insertPurpose(){
    const main = document.querySelector('.main') || document.querySelector('main');
    if (!main || document.getElementById('v7PurposeBox')) return;
    const box = document.createElement('div');
    box.id = 'v7PurposeBox';
    box.className = 'v7-box';
    box.innerHTML = '<b>v7-1 Why 분석:</b> 이 화면은 ST 고상승 정답지에 기존 causal 시험지 점수/행동을 겹쳐 보는 연구 대시보드입니다. 핵심은 새 매직공식이 아니라 <b>왜 GREAT를 놓쳤는지(MISSED_GREAT), 왜 오탐했는지(FALSE_BUY)</b>를 찾는 것입니다.';
    main.insertBefore(box, main.firstChild);
  }
  function groupOrder(g){
    const x = String(g || 'NO_SUBMISSION').toUpperCase();
    if (x === 'MISSED_GREAT') return 0;
    if (x === 'FALSE_BUY') return 1;
    if (x === 'HIT_GREAT') return 2;
    if (x === 'TRUE_REJECT') return 3;
    return 4;
  }
  function insertComparisonTable(){
    const feature = document.getElementById('featureTable');
    if (!feature || document.getElementById('v7ComparisonBlock')) return;
    const block = document.createElement('div');
    block.id = 'v7ComparisonBlock';
    const rows = EVAL_ROWS.slice().sort(function(a,b){
      const go = groupOrder(a.eval_group) - groupOrder(b.eval_group);
      if (go !== 0) return go;
      const as = Number(a.causal_score || -999999);
      const bs = Number(b.causal_score || -999999);
      return bs - as;
    }).slice(0, 300);
    let html = '<h3>Answer vs Submission: Why Review v7-1</h3>';
    html += '<div class="v7-table-wrap"><table><thead><tr>';
    ['Group','Date','Code','Name','Decision','Score','Rank','Action','Answer','Max%','End%','Why note'].forEach(function(h){ html += '<th>'+h+'</th>'; });
    html += '</tr></thead><tbody>';
    rows.forEach(function(r){
      html += '<tr>'+
        '<td class="v7-left"><span class="v7-badge '+clsOf(r.eval_group)+'">'+(r.eval_group||'NO_SUBMISSION')+'</span></td>'+
        '<td>'+r.trade_date+'</td><td>'+r.code+'</td><td class="v7-left">'+(r.name||'')+'</td>'+
        '<td>'+(r.decision_time||'-')+'</td><td>'+fmt(r.causal_score,2)+'</td><td>'+fmt(r.causal_rank,0)+'</td><td>'+(r.causal_action||'-')+'</td>'+
        '<td>'+(r.answer_quality||'-')+'</td><td>'+fmt(r.st_up_max_return_pct,2)+'</td><td>'+fmt(r.st_up_end_return_pct,2)+'</td>'+
        '<td class="v7-left">'+(r.why_note||'')+'</td></tr>';
    });
    html += '</tbody></table></div>';
    block.innerHTML = html;
    feature.parentNode.insertBefore(block, feature.nextSibling);
  }
  function decorateRows(){
    const list = document.getElementById('segmentList');
    if (!list) return;
    Array.from(list.querySelectorAll('[data-segment-id]')).forEach(function(el){
      if (el.__v71Decorated) return;
      const id = Number(el.getAttribute('data-segment-id'));
      const r = evalById[id];
      if (!r) return;
      const line = document.createElement('div');
      line.className = 'v7-line';
      line.innerHTML = '<span class="v7-badge '+clsOf(r.eval_group)+'">'+(r.eval_group||'NO_SUBMISSION')+'</span> score '+fmt(r.causal_score,2)+' / rank '+fmt(r.causal_rank,0)+' / '+(r.causal_action||'-')+' / '+(r.why_note||'');
      el.appendChild(line);
      el.__v71Decorated = true;
    });
  }
  function addInfoCard(seg){
    const panel = document.getElementById('infoPanel');
    if (!panel || !seg) return;
    const r = evalById[Number(seg.id)];
    const old = document.getElementById('v7InfoCard');
    if (old) old.remove();
    const card = document.createElement('div');
    card.id = 'v7InfoCard';
    card.className = 'card';
    if (!r) {
      card.innerHTML = '<div class="k">v7-1 Submission</div><div class="v"><span class="v7-badge v7-no-submission">NO_SUBMISSION</span> 기존 causal 제출지와 매칭되지 않음</div>';
    } else {
      card.innerHTML = '<div class="k">v7-1 Submission / Why</div><div class="v"><span class="v7-badge '+clsOf(r.eval_group)+'">'+r.eval_group+'</span> score '+fmt(r.causal_score,2)+' / rank '+fmt(r.causal_rank,0)+' / '+(r.causal_action||'-')+'<br><span style="font-size:13px;color:#cbd5e1">'+(r.why_note||'')+'</span></div>';
    }
    panel.insertBefore(card, panel.firstChild);
  }
  function overlayChart(seg){
    const r = evalById[Number(seg.id)];
    if (!r || !r.decision_time || typeof Plotly === 'undefined') return;
    const chart = document.getElementById('chart');
    if (!chart || !chart.data || !chart.layout) return;
    let y = null;
    const key = (typeof keyOf === 'function') ? keyOf(seg) : null;
    const arr = key && typeof candles !== 'undefined' ? (candles[key] || []) : [];
    for (let i = 0; i < arr.length; i++) {
      if (String(arr[i].t) === String(r.decision_time)) { y = Number(arr[i].c); break; }
    }
    if (y === null || isNaN(y)) y = Number(seg.st_up_start_price || seg.st_up_end_price || seg.st_up_max_price || 0);
    const markerSymbol = isBuyLike(r.causal_action) ? 'triangle-up' : 'x';
    const trace = {x:[r.decision_time], y:[y], mode:'markers+text', name:'v7-1 Submission', text:['S '+fmt(r.causal_score,1)+' / R '+fmt(r.causal_rank,0)+'<br>'+r.eval_group], textposition:'top center', marker:{size:14, symbol:markerSymbol, color:'#38bdf8'}, hoverinfo:'text'};
    Plotly.addTraces(chart, [trace]);
    const shapes = (chart.layout.shapes || []).slice();
    shapes.push({type:'line', xref:'x', x0:r.decision_time, x1:r.decision_time, yref:'paper', y0:0, y1:1, line:{width:2, dash:'dash', color:'#38bdf8'}});
    Plotly.relayout(chart, {shapes: shapes});
  }
  function patchSelectAndChart(){
    if (typeof selectSegment !== 'function' || typeof segments === 'undefined') return false;
    if (!window.__leaderLabV71SelectPatched) {
      window.__leaderLabV71SelectPatched = true;
      const originalSelect = selectSegment;
      selectSegment = function(id, rerender){
        originalSelect(id, rerender);
        const seg = segments.find(function(s){ return Number(s.id) === Number(id); });
        addInfoCard(seg);
        window.setTimeout(function(){ overlayChart(seg); decorateRows(); }, 80);
      };
      window.selectSegment = selectSegment;
    }
    return true;
  }
  function tick(){
    insertPurpose();
    insertComparisonTable();
    patchSelectAndChart();
    decorateRows();
    window.setTimeout(tick, 400);
  }
  tick();
})();
</script>
"""


def table_exists(conn: Any, table_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS n
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
              AND table_name = %s
            """,
            (table_name,),
        )
        row = cur.fetchone()
    return int(row.get("n", 0)) > 0


def table_columns(conn: Any, table_name: str) -> List[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = %s
            ORDER BY ordinal_position
            """,
            (table_name,),
        )
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
    if not d:
        return None
    if time_value is None:
        return None
    if isinstance(time_value, datetime):
        return time_value
    if isinstance(time_value, timedelta):
        seconds = int(time_value.total_seconds())
        hh = seconds // 3600
        mm = (seconds % 3600) // 60
        ss = seconds % 60
        text = f"{d} {hh:02d}:{mm:02d}:{ss:02d}"
    elif isinstance(time_value, time):
        text = f"{d} {time_value.isoformat()}"
    else:
        t = str(time_value)
        if "T" in t or ("-" in t and ":" in t):
            text = t.replace("T", " ")
        else:
            text = f"{d} {t}"
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


def answer_quality(seg: Dict[str, Any]) -> str:
    if int(seg.get("label_st_gain_10pct") or 0) == 1:
        return "GREAT"
    if int(seg.get("label_st_gain_5pct") or 0) == 1:
        return "GOOD"
    if int(seg.get("label_st_fail_1pct") or 0) == 1 or int(seg.get("label_st_end_negative") or 0) == 1:
        return "BAD"
    return "NEUTRAL"


def is_buy_like(action: Any) -> bool:
    text = str(action or "").upper()
    return "BUY" in text or "WATCH" in text or "AUTO" in text


def pick_causal_source(conn: Any) -> Tuple[Optional[str], List[str]]:
    for table_name in CAUSAL_SOURCE_CANDIDATES:
        if table_exists(conn, table_name):
            return table_name, table_columns(conn, table_name)
    return None, []


def load_causal_rows(conn: Any, segments: Sequence[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]], Dict[str, str]]:
    table_name, columns = pick_causal_source(conn)
    if table_name is None:
        return "NONE", [], {}

    code_col = first_existing(columns, CODE_COLUMNS_PRIORITY)
    date_col = first_existing(columns, DATE_COLUMNS_PRIORITY)
    time_col = first_existing(columns, TIME_COLUMNS_PRIORITY)
    score_col = first_existing(columns, SCORE_COLUMNS_PRIORITY)
    action_col = first_existing(columns, ACTION_COLUMNS_PRIORITY)
    rank_col = first_existing(columns, RANK_COLUMNS_PRIORITY)
    name_col = first_existing(columns, NAME_COLUMNS_PRIORITY)

    required = [code_col, date_col, time_col, score_col]
    if any(x is None for x in required):
        return table_name, [], {
            "reason": "missing_required_causal_columns",
            "columns": ",".join(columns),
        }

    selected_cols: List[str] = []
    for col in [code_col, name_col, date_col, time_col, score_col, action_col, rank_col]:
        if col and col not in selected_cols:
            selected_cols.append(col)

    forbidden_selected = [c for c in selected_cols if c in FORBIDDEN_CAUSAL_RANK_COLUMNS]
    if forbidden_selected:
        raise RuntimeError("Forbidden causal rank/display columns selected: " + ", ".join(forbidden_selected))

    dates = sorted({stringify_date(s.get("trade_date")) for s in segments if stringify_date(s.get("trade_date"))})
    codes = sorted({str(s.get("code")) for s in segments if s.get("code") is not None})
    if not dates or not codes:
        return table_name, [], {}

    date_placeholders = ",".join(["%s"] * len(dates))
    code_placeholders = ",".join(["%s"] * len(codes))
    col_sql = ", ".join("`" + c + "`" for c in selected_cols)
    sql = (
        "SELECT " + col_sql + " FROM `" + table_name + "` "
        "WHERE `" + date_col + "` IN (" + date_placeholders + ") "
        "AND `" + code_col + "` IN (" + code_placeholders + ")"
    )
    with conn.cursor() as cur:
        cur.execute(sql, tuple(dates + codes))
        rows = list(cur.fetchall())

    normalized: List[Dict[str, Any]] = []
    for row in rows:
        dvalue = row.get(date_col) if date_col else None
        tvalue = row.get(time_col) if time_col else None
        decision_dt = combine_date_time(dvalue, tvalue)
        normalized.append(
            {
                "source_table": table_name,
                "trade_date": stringify_date(dvalue),
                "code": str(row.get(code_col)) if code_col else "",
                "name": row.get(name_col) if name_col else None,
                "decision_dt": decision_dt,
                "decision_time": decision_dt.isoformat(sep=" ") if decision_dt else None,
                "causal_score": safe_float(row.get(score_col)) if score_col else None,
                "causal_action": str(row.get(action_col)) if action_col and row.get(action_col) is not None else None,
                "causal_rank": safe_float(row.get(rank_col)) if rank_col else None,
            }
        )

    meta = {
        "source_table": table_name,
        "code_col": str(code_col),
        "date_col": str(date_col),
        "time_col": str(time_col),
        "score_col": str(score_col),
        "action_col": str(action_col or ""),
        "rank_col": str(rank_col or ""),
    }
    return table_name, normalized, meta


def nearest_submission(seg: Dict[str, Any], submissions: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    trade_date = stringify_date(seg.get("trade_date"))
    code = str(seg.get("code"))
    start_dt = combine_date_time(trade_date, seg.get("st_up_start_time"))
    capture_dt = combine_date_time(trade_date, seg.get("capture_time"))
    target_dt = capture_dt or start_dt
    if target_dt is None:
        return None
    candidates: List[Tuple[float, Dict[str, Any]]] = []
    for row in submissions:
        if row.get("trade_date") != trade_date:
            continue
        if str(row.get("code")) != code:
            continue
        ddt = row.get("decision_dt")
        if not isinstance(ddt, datetime):
            continue
        diff_minutes = abs((ddt - target_dt).total_seconds()) / 60.0
        if diff_minutes <= 180.0:
            candidates.append((diff_minutes, row))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def why_note_for(eval_group: str, quality: str, sub: Optional[Dict[str, Any]]) -> str:
    if eval_group == "MISSED_GREAT":
        if sub is None:
            return "GREAT였으나 causal 제출지 매칭 없음: 일봉/장기분봉/섹터 구조 확인 필요"
        return "GREAT였으나 시험지 점수/행동 부족: 5분봉 밖 구조 feature 누락 가능"
    if eval_group == "FALSE_BUY":
        return "시험지는 BUY/WATCH였으나 정답 약함: 5분봉 표면 신호 또는 과열/저항 리스크 확인"
    if eval_group == "HIT_GREAT":
        return "시험지가 GREAT를 포착: 반복 feature 보존 후보"
    if eval_group == "TRUE_REJECT":
        return "정답 약하고 시험지도 거름: 현재 필터 보존 후보"
    if quality == "GOOD":
        return "GOOD 구간: GREAT와 BAD 사이 차이 확인"
    return "why review 필요"


def make_evaluation_rows(segments: Sequence[Dict[str, Any]], submissions: Sequence[Dict[str, Any]], source_meta: Dict[str, str]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for seg in segments:
        quality = answer_quality(seg)
        sub = nearest_submission(seg, submissions)
        buy_like = is_buy_like(sub.get("causal_action")) if sub is not None else False
        if quality == "GREAT" and buy_like:
            group = "HIT_GREAT"
        elif quality == "GREAT" and not buy_like:
            group = "MISSED_GREAT"
        elif quality != "GREAT" and buy_like:
            group = "FALSE_BUY"
        else:
            group = "TRUE_REJECT"
        row = {
            "segment_id": seg.get("id"),
            "trade_date": stringify_date(seg.get("trade_date")),
            "code": str(seg.get("code")),
            "name": seg.get("name"),
            "st_param": v2.param_key(seg.get("st_period"), seg.get("st_multiplier")),
            "segment_no": seg.get("segment_no"),
            "answer_quality": quality,
            "st_up_start_time": str(seg.get("st_up_start_time")),
            "st_up_end_time": str(seg.get("st_up_end_time")),
            "st_up_max_return_pct": safe_float(seg.get("st_up_max_return_pct")),
            "st_up_end_return_pct": safe_float(seg.get("st_up_end_return_pct")),
            "decision_time": sub.get("decision_time") if sub else None,
            "causal_score": sub.get("causal_score") if sub else None,
            "causal_rank": sub.get("causal_rank") if sub else None,
            "causal_action": sub.get("causal_action") if sub else None,
            "causal_source_table": sub.get("source_table") if sub else source_meta.get("source_table", "NONE"),
            "eval_group": group,
            "why_note": why_note_for(group, quality, sub),
            "leakage_status": "PASS_SELECTED_CAUSAL_COLUMNS_ONLY" if sub else "NO_SUBMISSION_MATCH",
        }
        result.append(row)
    return result


def write_eval_csv(rows: Sequence[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "segment_id", "trade_date", "code", "name", "st_param", "segment_no",
        "answer_quality", "st_up_start_time", "st_up_end_time", "st_up_max_return_pct", "st_up_end_return_pct",
        "decision_time", "causal_score", "causal_rank", "causal_action", "causal_source_table",
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
        source_table, causal_rows, source_meta = load_causal_rows(conn, segments)
        if "source_table" not in source_meta:
            source_meta["source_table"] = source_table
        eval_rows = make_evaluation_rows(segments, causal_rows, source_meta)
        write_eval_csv(eval_rows, Path(args.eval_output))

        html = v2.build_html(segments, candles, candle_meta, summary, feature_summary, args.warmup_bars, args.prev_display_start)
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
            key = str(row.get("eval_group"))
            counts[key] = counts.get(key, 0) + 1
        print("=== DONE generate_st_answer_reverse_analysis_v7_1 ===")
        print("Board Type=EVALUATION_BOARD")
        print("Answer Source=supertrend_regime_segment")
        print("Submission Source=" + str(source_table))
        print("Leakage Status=PASS_SELECTED_CAUSAL_COLUMNS_ONLY")
        print("eval_counts=" + json.dumps(counts, ensure_ascii=False, sort_keys=True))
        print("output=" + str(out.resolve()))
        print("eval_output=" + str(Path(args.eval_output).resolve()))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
