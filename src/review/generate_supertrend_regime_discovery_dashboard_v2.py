# -*- coding: utf-8 -*-
"""Generate SuperTrend Regime Discovery dashboard v2.

This version is designed for chart-consistency verification, not trading simulation.
It calculates SuperTrend with hidden warm-up bars and displays the previous trading
session afternoon candles plus the full current session so that the early-session
SuperTrend regime can be visually verified.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pymysql

from src.analysis.build_supertrend_regime_discovery import calculate_supertrend


DEFAULT_WARMUP_BARS = 80
DEFAULT_PREV_DISPLAY_START = "12:00"


def load_env(env_path: str) -> None:
    path = Path(env_path)
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def env_value(names: Sequence[str], default: Optional[str] = None) -> Optional[str]:
    for name in names:
        value = os.environ.get(name)
        if value is not None and value.strip() != "":
            return value.strip()
    return default


def open_conn() -> Any:
    db_name = env_value(["DB_NAME", "MYSQL_DATABASE", "MYSQL_DB"])
    if db_name is None:
        raise RuntimeError(".env에 DB_NAME 또는 MYSQL_DATABASE가 필요합니다.")
    return pymysql.connect(
        host=env_value(["DB_HOST", "MYSQL_HOST"], "127.0.0.1"),
        port=int(env_value(["DB_PORT", "MYSQL_PORT"], "3306") or "3306"),
        user=env_value(["DB_USER", "MYSQL_USER"], "root"),
        password=env_value(["DB_PASS", "DB_PASSWORD", "MYSQL_PASSWORD", "MYSQL_PASS"], ""),
        database=db_name,
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


def parse_hhmm(value: str) -> time:
    parts = value.strip().split(":")
    if len(parts) < 2:
        raise ValueError("time must be HH:MM or HH:MM:SS")
    hour = int(parts[0])
    minute = int(parts[1])
    second = int(parts[2]) if len(parts) >= 3 else 0
    return time(hour, minute, second)


def json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds())
        hour = total_seconds // 3600
        minute = (total_seconds % 3600) // 60
        second = total_seconds % 60
        return f"{hour:02d}:{minute:02d}:{second:02d}"
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        value = float(value)
    try:
        result = float(value)
    except Exception:
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def to_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, Decimal):
        return int(value)
    try:
        return int(float(value))
    except Exception:
        return 0


def amount_from_ohlcv(row: Dict[str, Any]) -> Optional[float]:
    o = to_float(row.get("open_price"))
    h = to_float(row.get("high_price"))
    l = to_float(row.get("low_price"))
    c = to_float(row.get("close_price"))
    v = to_float(row.get("volume"))
    if o is None or h is None or l is None or c is None or v is None:
        return None
    return ((o + h + l + c) / 4.0) * v


def param_key(period: Any, multiplier: Any) -> str:
    return str(int(period)) + ":" + f"{float(multiplier):.1f}"


def chart_key(trade_date: Any, code: Any, period: Any, multiplier: Any) -> str:
    return str(trade_date) + "|" + str(code) + "|" + param_key(period, multiplier)


def row_time(row: Dict[str, Any]) -> Optional[datetime]:
    value = row.get("candle_time")
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return None


def load_segments(conn: Any, limit: int) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, trade_date, search_time, code, name, timeframe,
                   st_period, st_multiplier, segment_no,
                   capture_time, already_up_at_capture,
                   st_up_start_time, st_up_end_time, st_up_bars,
                   st_up_start_price, st_up_max_price, st_up_end_price, st_up_min_price,
                   st_up_max_return_pct, st_up_end_return_pct, st_up_max_drawdown_pct,
                   start_from_day_open_pct, start_from_day_low_pct,
                   start_cum_amount, start_cum_volume,
                   start_range_so_far_pct, start_high_so_far_from_open_pct,
                   max_singlebar_return_before_start,
                   singlebar_3pct_exists_before_start, singlebar_5pct_exists_before_start,
                   segment_amount, segment_volume, segment_avg_amount_per_bar,
                   segment_max_singlebar_return_pct,
                   segment_green_bar_count, segment_red_bar_count,
                   label_st_gain_3pct, label_st_gain_5pct, label_st_gain_10pct,
                   label_st_fail_1pct, label_st_end_negative
            FROM supertrend_regime_segment
            ORDER BY st_period, st_multiplier, trade_date, code, segment_no
            LIMIT %s
            """,
            (limit,),
        )
        return list(cur.fetchall())


def load_summary(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT st_period, st_multiplier, segment_group, segment_count, active_days,
                   avg_segments_per_day, avg_st_up_bars, avg_st_up_max_return_pct,
                   median_st_up_max_return_pct, avg_st_up_end_return_pct,
                   avg_st_up_max_drawdown_pct, gain3_rate, gain5_rate, gain10_rate,
                   fail1_rate, end_negative_rate,
                   avg_start_from_day_open_pct, avg_start_from_day_low_pct,
                   avg_start_cum_amount, avg_start_range_so_far_pct,
                   avg_segment_amount, avg_segment_max_singlebar_return_pct
            FROM supertrend_regime_summary
            ORDER BY st_period, st_multiplier,
                     FIELD(segment_group, 'ALL','GOOD_GAIN5','GREAT_GAIN10','BAD_FAIL_OR_NEG','ALREADY_UP_AT_CAPTURE')
            """
        )
        return list(cur.fetchall())


def load_feature_summary(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT st_period, st_multiplier, feature_name, good_group, bad_group,
                   good_count, bad_count, good_avg_value, bad_avg_value, diff_avg_value
            FROM supertrend_regime_feature_summary
            ORDER BY ABS(COALESCE(diff_avg_value, 0)) DESC
            LIMIT 120
            """
        )
        return list(cur.fetchall())


def query_warmup_plus_day_rows(conn: Any, trade_date: Any, code: str, warmup_bars: int) -> Tuple[List[Dict[str, Any]], int]:
    current_start = datetime.combine(trade_date, time(9, 0, 0))
    current_end = datetime.combine(trade_date, time(15, 30, 0))
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT candle_time AS candle_time,
                   open AS open_price,
                   high AS high_price,
                   low AS low_price,
                   close AS close_price,
                   volume AS volume
            FROM minute5_candles
            WHERE code=%s
              AND candle_time < %s
            ORDER BY candle_time DESC
            LIMIT %s
            """,
            (code, current_start, warmup_bars),
        )
        prev_rows = list(cur.fetchall())
        prev_rows.reverse()
        cur.execute(
            """
            SELECT candle_time AS candle_time,
                   open AS open_price,
                   high AS high_price,
                   low AS low_price,
                   close AS close_price,
                   volume AS volume
            FROM minute5_candles
            WHERE code=%s
              AND candle_time >= %s
              AND candle_time <= %s
            ORDER BY candle_time
            """,
            (code, current_start, current_end),
        )
        day_rows = list(cur.fetchall())
    return prev_rows + day_rows, len(prev_rows)


def previous_session_date(rows: List[Dict[str, Any]], trade_date: Any) -> Optional[date]:
    dates: List[date] = []
    for row in rows:
        ts = row_time(row)
        if ts is not None and ts.date() < trade_date:
            dates.append(ts.date())
    if not dates:
        return None
    return max(dates)


def should_display_row(row: Dict[str, Any], trade_date: Any, prev_date: Optional[date], prev_display_start: time) -> bool:
    ts = row_time(row)
    if ts is None:
        return False
    if ts.date() == trade_date:
        return True
    if prev_date is not None and ts.date() == prev_date and ts.time() >= prev_display_start:
        return True
    return False


def decorate_chart_rows(rows: List[Dict[str, Any]], prev_count: int, trade_date: Any, period: int, multiplier: float, prev_display_start: time) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    st_line, direction = calculate_supertrend(rows, period, multiplier)
    prev_date = previous_session_date(rows, trade_date)
    display: List[Dict[str, Any]] = []
    hidden_before_display = 0
    first_display_index: Optional[int] = None
    for i, row in enumerate(rows):
        if should_display_row(row, trade_date, prev_date, prev_display_start):
            first_display_index = i
            break
    if first_display_index is not None:
        hidden_before_display = first_display_index
    for i, row in enumerate(rows):
        if not should_display_row(row, trade_date, prev_date, prev_display_start):
            continue
        st_value = to_float(st_line[i]) if i < len(st_line) else None
        st_dir = int(direction[i]) if i < len(direction) else 0
        ts = row_time(row)
        is_prev_display = 1 if ts is not None and prev_date is not None and ts.date() == prev_date else 0
        item: Dict[str, Any] = {
            "t": row.get("candle_time"),
            "o": to_float(row.get("open_price")),
            "h": to_float(row.get("high_price")),
            "l": to_float(row.get("low_price")),
            "c": to_float(row.get("close_price")),
            "v": to_int(row.get("volume")),
            "amount": amount_from_ohlcv(row),
            "st_value": st_value,
            "st_dir": st_dir,
            "st_up": st_value if st_dir == 1 else None,
            "st_down": st_value if st_dir == -1 else None,
            "is_warmup": 1 if i < prev_count else 0,
            "is_prev_session_display": is_prev_display,
            "is_after_0900": 1 if ts is not None and ts.date() == trade_date else 0,
        }
        display.append(item)
    meta = {
        "prev_date": prev_date.isoformat() if prev_date is not None else None,
        "hidden_warmup_bars": hidden_before_display,
        "indicator_input_bars": len(rows),
        "display_bars": len(display),
        "prev_display_start": prev_display_start.isoformat(),
    }
    return display, meta


def load_candles_for_segments(conn: Any, segments: List[Dict[str, Any]], warmup_bars: int, prev_display_start: time) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    meta_by_key: Dict[str, Dict[str, Any]] = {}
    raw_cache: Dict[str, Tuple[List[Dict[str, Any]], int]] = {}
    seen = set()
    for seg in segments:
        trade_date = seg.get("trade_date")
        code = str(seg.get("code"))
        period = int(seg.get("st_period"))
        multiplier = float(seg.get("st_multiplier"))
        ckey = chart_key(trade_date, code, period, multiplier)
        if ckey in seen:
            continue
        seen.add(ckey)
        raw_key = str(trade_date) + "|" + code
        if raw_key not in raw_cache:
            raw_cache[raw_key] = query_warmup_plus_day_rows(conn, trade_date, code, warmup_bars)
        rows, prev_count = raw_cache[raw_key]
        display, meta = decorate_chart_rows(rows, prev_count, trade_date, period, multiplier, prev_display_start)
        grouped[ckey] = display
        meta_by_key[ckey] = meta
    return grouped, meta_by_key


def build_html(segments: List[Dict[str, Any]], candles: Dict[str, List[Dict[str, Any]]], candle_meta: Dict[str, Dict[str, Any]], summary: List[Dict[str, Any]], feature_summary: List[Dict[str, Any]], warmup_bars: int, prev_display_start: str) -> str:
    data_json = json.dumps({"segments": segments, "candles": candles, "candleMeta": candle_meta, "summary": summary, "featureSummary": feature_summary, "warmupBars": warmup_bars, "prevDisplayStart": prev_display_start}, ensure_ascii=False, default=json_default)
    return """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <title>SuperTrend Regime Discovery Dashboard</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    body { margin:0; font-family: Segoe UI, Malgun Gothic, Arial, sans-serif; background:#111827; color:#e5e7eb; }
    header { padding:14px 18px; background:#0f172a; border-bottom:1px solid #334155; }
    h1 { margin:0; font-size:20px; }
    .wrap { display:grid; grid-template-columns: 490px 1fr; height:calc(100vh - 58px); }
    .side { border-right:1px solid #334155; overflow:auto; background:#111827; }
    .main { overflow:auto; padding:12px; }
    .filters { padding:12px; position:sticky; top:0; background:#111827; z-index:2; border-bottom:1px solid #334155; }
    label { display:block; font-size:12px; color:#cbd5e1; margin-top:8px; }
    select, input { width:100%; box-sizing:border-box; padding:7px; background:#0f172a; color:#e5e7eb; border:1px solid #475569; border-radius:6px; }
    .seg { padding:9px 12px; border-bottom:1px solid #1f2937; cursor:pointer; }
    .seg:hover { background:#1e293b; }
    .seg.active { background:#334155; }
    .seg .title { font-weight:700; font-size:13px; }
    .seg .meta { font-size:12px; color:#cbd5e1; margin-top:4px; line-height:1.45; }
    .good { color:#86efac; } .bad { color:#fca5a5; } .warn { color:#fde68a; } .info { color:#93c5fd; }
    .pill { display:inline-block; padding:2px 6px; border-radius:999px; background:#1f2937; margin-right:4px; font-size:11px; }
    .panel { display:grid; grid-template-columns: repeat(4, minmax(160px, 1fr)); gap:8px; margin-bottom:10px; }
    .card { background:#0f172a; border:1px solid #334155; border-radius:10px; padding:10px; }
    .card .k { font-size:11px; color:#94a3b8; }
    .card .v { font-size:15px; font-weight:700; margin-top:3px; }
    .gate-pass { color:#86efac; }
    .gate-fail { color:#fca5a5; }
    #chart { height:720px; background:#0f172a; border:1px solid #334155; border-radius:10px; }
    #volume { height:190px; background:#0f172a; border:1px solid #334155; border-radius:10px; margin-top:10px; }
    table { border-collapse:collapse; width:100%; font-size:12px; background:#0f172a; margin-bottom:12px; }
    th,td { border:1px solid #334155; padding:5px 6px; text-align:right; }
    th { background:#1e293b; color:#cbd5e1; }
  </style>
</head>
<body>
<header><h1>SuperTrend Regime Discovery Dashboard — Previous Session + Current Session ST Consistency</h1></header>
<div class="wrap">
  <aside class="side">
    <div class="filters">
      <label>ST Parameter</label><select id="paramSelect"></select>
      <label>보기</label>
      <select id="viewSelect">
        <option value="all">전체</option>
        <option value="good5">Good >= 5%</option>
        <option value="great10">Great >= 10%</option>
        <option value="bad">Bad fail/negative</option>
        <option value="already">Already Up At Capture</option>
        <option value="lowstartgreat">Great + low start</option>
      </select>
      <label>일자</label><select id="dateSelect"></select>
      <label>검색</label><input id="searchInput" placeholder="코드/종목명" />
    </div>
    <div id="segmentList"></div>
  </aside>
  <main class="main">
    <h3>Summary</h3><div id="summaryTable"></div>
    <h3>Good vs Bad Feature Diff</h3><div id="featureTable"></div>
    <div class="panel" id="infoPanel"></div>
    <div id="chart"></div>
    <div id="volume"></div>
  </main>
</div>
<script>
const DATA = __DATA_JSON__;
const segments = DATA.segments;
const candles = DATA.candles;
const candleMeta = DATA.candleMeta || {};
const summary = DATA.summary;
const featureSummary = DATA.featureSummary;
const warmupBars = DATA.warmupBars || 80;
const prevDisplayStart = DATA.prevDisplayStart || '12:00';
let selectedId = null;
function fmt(v, d=2){ if(v===null || v===undefined || isNaN(Number(v))) return '-'; return Number(v).toFixed(d); }
function paramOf(s){ return `${s.st_period}:${Number(s.st_multiplier).toFixed(1)}`; }
function keyOf(s){ return s.trade_date + '|' + s.code + '|' + paramOf(s); }
function unique(arr){ return Array.from(new Set(arr)); }
function marketOpenTs(s){ return s.trade_date + 'T09:00:00'; }
function initFilters(){
  const params = unique(segments.map(paramOf)).sort();
  paramSelect.innerHTML = params.map(p=>`<option>${p}</option>`).join('');
  paramSelect.value = params.includes('7:2.0') ? '7:2.0' : params[0];
  paramSelect.onchange = function(){ refreshDates(); renderSummary(); renderFeatureSummary(); renderList(); };
  viewSelect.onchange = renderList; dateSelect.onchange = renderList; searchInput.oninput = renderList;
  refreshDates(); renderSummary(); renderFeatureSummary(); renderList();
}
function refreshDates(){
  const p = paramSelect.value;
  const dates = unique(segments.filter(s=>paramOf(s)===p).map(s=>s.trade_date)).sort();
  dateSelect.innerHTML = ['ALL'].concat(dates).map(d=>`<option>${d}</option>`).join('');
}
function renderSummary(){
  const [period, mult] = paramSelect.value.split(':');
  const rows = summary.filter(s=>Number(s.st_period)===Number(period) && Number(s.st_multiplier)===Number(mult));
  const headers = ['Group','N','/Day','Bars','Max','MedMax','End','G3','G5','G10','Fail1','EndNeg','StartOpen','StartAmt(억)','SegAmt(억)'];
  let html = '<table><thead><tr>' + headers.map(h=>`<th>${h}</th>`).join('') + '</tr></thead><tbody>';
  rows.forEach(s=>{
    html += `<tr><td style="text-align:left">${s.segment_group}</td><td>${s.segment_count}</td><td>${fmt(s.avg_segments_per_day)}</td><td>${fmt(s.avg_st_up_bars)}</td><td>${fmt(s.avg_st_up_max_return_pct)}</td><td>${fmt(s.median_st_up_max_return_pct)}</td><td>${fmt(s.avg_st_up_end_return_pct)}</td><td>${fmt(Number(s.gain3_rate)*100)}</td><td>${fmt(Number(s.gain5_rate)*100)}</td><td>${fmt(Number(s.gain10_rate)*100)}</td><td>${fmt(Number(s.fail1_rate)*100)}</td><td>${fmt(Number(s.end_negative_rate)*100)}</td><td>${fmt(s.avg_start_from_day_open_pct)}</td><td>${fmt(Number(s.avg_start_cum_amount)/100000000)}</td><td>${fmt(Number(s.avg_segment_amount)/100000000)}</td></tr>`;
  });
  html += '</tbody></table>'; summaryTable.innerHTML = html;
}
function renderFeatureSummary(){
  const [period, mult] = paramSelect.value.split(':');
  const rows = featureSummary.filter(s=>Number(s.st_period)===Number(period) && Number(s.st_multiplier)===Number(mult)).slice(0, 20);
  let html = '<table><thead><tr><th>Feature</th><th>GoodN</th><th>BadN</th><th>GoodAvg</th><th>BadAvg</th><th>Diff</th></tr></thead><tbody>';
  rows.forEach(r=>{
    const isAmt = String(r.feature_name).includes('amount');
    const ga = isAmt ? Number(r.good_avg_value)/100000000 : Number(r.good_avg_value);
    const ba = isAmt ? Number(r.bad_avg_value)/100000000 : Number(r.bad_avg_value);
    const df = isAmt ? Number(r.diff_avg_value)/100000000 : Number(r.diff_avg_value);
    html += `<tr><td style="text-align:left">${r.feature_name}</td><td>${r.good_count}</td><td>${r.bad_count}</td><td>${fmt(ga)}</td><td>${fmt(ba)}</td><td>${fmt(df)}</td></tr>`;
  });
  html += '</tbody></table>'; featureTable.innerHTML = html;
}
function filteredSegments(){
  const p = paramSelect.value; const view = viewSelect.value; const d = dateSelect.value; const q = searchInput.value.trim().toLowerCase();
  return segments.filter(s=>{
    if(paramOf(s)!==p) return false;
    if(d !== 'ALL' && s.trade_date !== d) return false;
    if(q && !(String(s.code).toLowerCase().includes(q) || String(s.name||'').toLowerCase().includes(q))) return false;
    if(view==='good5' && Number(s.label_st_gain_5pct)!==1) return false;
    if(view==='great10' && Number(s.label_st_gain_10pct)!==1) return false;
    if(view==='bad' && !(Number(s.label_st_fail_1pct)===1 || Number(s.label_st_end_negative)===1)) return false;
    if(view==='already' && Number(s.already_up_at_capture)!==1) return false;
    if(view==='lowstartgreat' && !(Number(s.label_st_gain_10pct)===1 && Number(s.start_from_day_open_pct)<=3)) return false;
    return true;
  });
}
function renderList(){
  const list = filteredSegments();
  segmentList.innerHTML = list.map(s=>{
    const cls = s.id===selectedId ? 'seg active' : 'seg';
    const retCls = Number(s.st_up_max_return_pct) >= 5 ? 'good' : ((Number(s.label_st_fail_1pct)===1 || Number(s.label_st_end_negative)===1) ? 'bad' : 'warn');
    return `<div class="${cls}" onclick="selectSegment(${s.id})"><div class="title">${s.trade_date} ${s.code} ${s.name||''} <span class="pill">#${s.segment_no}</span><span class="pill">ST ${paramOf(s)}</span></div><div class="meta">max <span class="${retCls}">${fmt(s.st_up_max_return_pct)}%</span> / end ${fmt(s.st_up_end_return_pct)}% / bars ${s.st_up_bars} / startOpen ${fmt(s.start_from_day_open_pct)}% / segAmt ${fmt(Number(s.segment_amount)/100000000)}억</div></div>`;
  }).join('');
  if(list.length && !list.some(s=>s.id===selectedId)) selectSegment(list[0].id, false);
}
function selectSegment(id, rerender=true){ selectedId = id; const s = segments.find(x=>x.id===id); if(!s) return; renderInfo(s); renderChart(s); if(rerender) renderList(); }
function consistencyFor(s, arr, meta){
  const hasPrevDisplay = arr.some(r=>Number(r.is_prev_session_display)===1);
  const hasWarmup = arr.some(r=>Number(r.is_warmup)===1);
  const firstTs = arr.length ? arr[0].t : null;
  const hasStUp = arr.some(r=>r.st_up !== null && r.st_up !== undefined);
  const hasStDown = arr.some(r=>r.st_down !== null && r.st_down !== undefined);
  const startHit = arr.some(r=>String(r.t) === String(s.st_up_start_time) && r.st_up !== null && r.st_up !== undefined);
  const endHit = arr.some(r=>String(r.t) === String(s.st_up_end_time) && r.st_up !== null && r.st_up !== undefined);
  let fail = [];
  if(!hasPrevDisplay) fail.push('NO_PREV_SESSION_DISPLAY');
  if(!hasWarmup) fail.push('NO_VISIBLE_WARMUP');
  if(!hasStUp) fail.push('NO_ST_UP');
  if(!hasStDown) fail.push('NO_ST_DOWN');
  if(!startHit) fail.push('START_MISMATCH');
  if(!endHit) fail.push('END_MISMATCH');
  const earlyRisk = (!hasPrevDisplay || String(s.st_up_start_time).slice(11,16) <= '09:30') ? (hasPrevDisplay ? 'CHECK' : 'HIGH') : 'LOW';
  return {hasPrevDisplay, hasWarmup, firstTs, hasStUp, hasStDown, startHit, endHit, earlyRisk, pass: fail.length===0, failReason: fail.join(', '), meta};
}
function renderInfo(s){
  const key = keyOf(s);
  const arr = candles[key] || [];
  const meta = candleMeta[key] || {};
  const gate = consistencyFor(s, arr, meta);
  const gateClass = gate.pass ? 'gate-pass' : 'gate-fail';
  const items = [
    ['Chart Consistency', `<span class="${gateClass}">${gate.pass ? 'PASS' : 'CHECK/FAIL'}</span> / ${gate.failReason || 'OK'} / Early ${gate.earlyRisk}`],
    ['Prev/Warmup/ST', `first ${gate.firstTs || '-'} / prev ${gate.hasPrevDisplay ? 'OK' : 'NO'} / warmup ${gate.hasWarmup ? 'OK' : 'NO'} / ST up ${gate.hasStUp ? 'OK' : 'NO'} / down ${gate.hasStDown ? 'OK' : 'NO'}`],
    ['Indicator Input', `input ${meta.indicator_input_bars || 0} bars / hidden ${meta.hidden_warmup_bars || 0} / display ${meta.display_bars || 0} / prev ${meta.prev_date || '-'}`],
    ['Segment', `${s.trade_date} ${s.code} ${s.name||''} / ST ${paramOf(s)} / #${s.segment_no}`],
    ['Outcome', `max ${fmt(s.st_up_max_return_pct)}% / end ${fmt(s.st_up_end_return_pct)}% / dd ${fmt(s.st_up_max_drawdown_pct)}% / bars ${s.st_up_bars}`],
    ['Times', `${s.st_up_start_time} → ${s.st_up_end_time}`],
    ['Capture', `${s.capture_time} / alreadyUp ${s.already_up_at_capture}`],
    ['Start Position', `open ${fmt(s.start_from_day_open_pct)}% / low ${fmt(s.start_from_day_low_pct)}% / range ${fmt(s.start_range_so_far_pct)}%`],
    ['Segment Amount', `${fmt(Number(s.segment_amount)/100000000)}억 / avgBar ${fmt(Number(s.segment_avg_amount_per_bar)/100000000)}억`],
    ['Singlebar', `before ${fmt(s.max_singlebar_return_before_start)}% / inside ${fmt(s.segment_max_singlebar_return_pct)}%`]
  ];
  infoPanel.innerHTML = items.map(x=>`<div class="card"><div class="k">${x[0]}</div><div class="v">${x[1]}</div></div>`).join('');
}
function renderChart(s){
  const key = keyOf(s);
  const arr = candles[key] || [];
  const meta = candleMeta[key] || {};
  const x = arr.map(r=>r.t);
  const open = arr.map(r=>Number(r.o)); const high = arr.map(r=>Number(r.h)); const low = arr.map(r=>Number(r.l)); const close = arr.map(r=>Number(r.c)); const vol = arr.map(r=>Number(r.v));
  const stUp = arr.map(r=>r.st_up === null || r.st_up === undefined ? null : Number(r.st_up));
  const stDown = arr.map(r=>r.st_down === null || r.st_down === undefined ? null : Number(r.st_down));
  const shapes = [];
  const annotations = [];
  const openTs = marketOpenTs(s);
  const prevRows = arr.filter(r=>Number(r.is_prev_session_display)===1);
  if(prevRows.length > 0){
    shapes.push({type:'rect', xref:'x', yref:'paper', x0:prevRows[0].t, x1:prevRows[prevRows.length-1].t, y0:0, y1:1, fillcolor:'rgba(148,163,184,0.12)', line:{width:0}, layer:'below'});
    annotations.push({xref:'x', yref:'paper', x:prevRows[0].t, y:1, text:`prev session ${meta.prev_date || ''} ${prevDisplayStart}~`, showarrow:false, font:{size:11, color:'#cbd5e1'}});
  }
  shapes.push({type:'line', xref:'x', x0:openTs, x1:openTs, yref:'paper', y0:0, y1:1, line:{width:2, dash:'dot', color:'#fbbf24'}});
  annotations.push({xref:'x', yref:'paper', x:openTs, y:1, text:'09:00', showarrow:false, yanchor:'bottom', font:{size:12, color:'#fbbf24'}});
  if(s.st_up_start_time && s.st_up_end_time){ shapes.push({type:'rect', xref:'x', yref:'paper', x0:s.st_up_start_time, x1:s.st_up_end_time, y0:0, y1:1, fillcolor:'rgba(34,197,94,0.14)', line:{width:0}, layer:'below'}); }
  if(s.capture_time){ shapes.push({type:'line', xref:'x', x0:s.capture_time, x1:s.capture_time, yref:'paper', y0:0, y1:1, line:{width:1, dash:'dot', color:'#93c5fd'}}); }
  if(s.st_up_start_time){ shapes.push({type:'line', xref:'x', x0:s.st_up_start_time, x1:s.st_up_start_time, yref:'paper', y0:0, y1:1, line:{width:2, dash:'dash', color:'#22c55e'}}); }
  if(s.st_up_end_time){ shapes.push({type:'line', xref:'x', x0:s.st_up_end_time, x1:s.st_up_end_time, yref:'paper', y0:0, y1:1, line:{width:2, dash:'dashdot', color:'#ef4444'}}); }
  if(arr.length > 0){
    const firstDay = arr.find(r=>Number(r.is_after_0900)===1);
    if(firstDay && firstDay.o !== null && firstDay.o !== undefined){
      shapes.push({type:'line', xref:'x', x0:x[0], x1:x[x.length-1], yref:'y', y0:Number(firstDay.o), y1:Number(firstDay.o), line:{width:1, dash:'dot', color:'#a78bfa'}});
    }
  }
  const traces = [
    {type:'candlestick', x, open, high, low, close, name:'5m'},
    {type:'scatter', x, y:stUp, mode:'lines', name:'ST Up', connectgaps:false, line:{width:2, color:'#22c55e'}},
    {type:'scatter', x, y:stDown, mode:'lines', name:'ST Down', connectgaps:false, line:{width:2, color:'#f97316'}},
    {type:'scatter', mode:'markers+text', x:[s.st_up_start_time], y:[Number(s.st_up_start_price)], text:['ST Start'], textposition:'bottom center', marker:{size:11, color:'#f59e0b'}, name:'ST Start'},
    {type:'scatter', mode:'markers+text', x:[s.st_up_end_time], y:[Number(s.st_up_end_price)], text:['ST End'], textposition:'bottom center', marker:{size:11, color:'#22c55e'}, name:'ST End'},
    {type:'scatter', mode:'markers+text', x:[s.st_up_start_time], y:[Number(s.st_up_max_price)], text:[`Max ${fmt(s.st_up_max_return_pct)}%`], textposition:'top center', marker:{size:12, color:'#ef4444'}, name:'ST Max'}
  ];
  const layout = {paper_bgcolor:'#0f172a', plot_bgcolor:'#0f172a', font:{color:'#e5e7eb'}, xaxis:{rangeslider:{visible:false}}, yaxis:{title:'Price'}, shapes, annotations, margin:{l:50,r:20,t:28,b:40}};
  Plotly.react('chart', traces, layout, {responsive:true});
  Plotly.react('volume', [{type:'bar', x, y:vol, name:'volume'}], {paper_bgcolor:'#0f172a', plot_bgcolor:'#0f172a', font:{color:'#e5e7eb'}, margin:{l:50,r:20,t:20,b:40}, yaxis:{title:'Volume'}}, {responsive:true});
}
initFilters();
</script>
</body>
</html>""".replace("__DATA_JSON__", data_json)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--output", default="reports/supertrend_regime_discovery_dashboard.html")
    parser.add_argument("--limit", type=int, default=12000)
    parser.add_argument("--warmup-bars", type=int, default=DEFAULT_WARMUP_BARS)
    parser.add_argument("--prev-display-start", default=DEFAULT_PREV_DISPLAY_START)
    args = parser.parse_args()
    load_env(args.env)
    prev_display_start = parse_hhmm(args.prev_display_start)
    conn = open_conn()
    try:
        segments = load_segments(conn, args.limit)
        summary = load_summary(conn)
        feature_summary = load_feature_summary(conn)
        candles, candle_meta = load_candles_for_segments(conn, segments, args.warmup_bars, prev_display_start)
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(build_html(segments, candles, candle_meta, summary, feature_summary, args.warmup_bars, args.prev_display_start), encoding="utf-8")
        print("=== DONE generate_supertrend_regime_discovery_dashboard_v2 ===")
        print("segments=" + str(len(segments)))
        print("candles_groups=" + str(len(candles)))
        print("warmup_bars=" + str(args.warmup_bars))
        print("prev_display_start=" + str(args.prev_display_start))
        print("output=" + str(out.resolve()))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
