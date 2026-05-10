# -*- coding: utf-8 -*-
"""Generate a static WYSIWYG chart review dashboard.

Output:
    reports/chart_review_dashboard.html

The HTML uses Plotly CDN and embedded JSON data. No local web server is required.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pymysql


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


def json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def load_cases(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, search_date, search_time, code, name,
                   threshold_pct, entry_filter_name,
                   actual_rank, actual_max_after_return_pct,
                   day_open, day_high, day_low, day_close,
                   singlebar_time, singlebar_high, singlebar_low, singlebar_close_return_pct, singlebar_from_day_open_pct,
                   break_time, break_price, break_rsi14, break_from_day_open_pct,
                   entry_time, entry_price, entry_from_day_open_pct,
                   day_high_after_entry, max_return_after_entry_pct, close_return_from_entry_pct, max_drawdown_after_entry_pct
            FROM chart_review_case
            ORDER BY search_date, threshold_pct DESC, actual_rank IS NULL, actual_rank, code
            """
        )
        return list(cur.fetchall())


def load_candles_for_cases(conn: Any, cases: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    seen = set()
    for case in cases:
        search_date = case.get("search_date")
        code = str(case.get("code"))
        key = str(search_date) + "|" + code
        if key in seen:
            continue
        seen.add(key)
        start_dt = datetime.combine(search_date, time(9, 0, 0))
        end_dt = datetime.combine(search_date, time(15, 30, 0))
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT candle_time AS t,
                       open AS o,
                       high AS h,
                       low AS l,
                       close AS c,
                       volume AS v
                FROM minute5_candles
                WHERE code=%s
                  AND candle_time >= %s
                  AND candle_time <= %s
                ORDER BY candle_time
                """,
                (code, start_dt, end_dt),
            )
            grouped[key] = list(cur.fetchall())
    return grouped


def build_html(cases: List[Dict[str, Any]], candles: Dict[str, List[Dict[str, Any]]]) -> str:
    data_json = json.dumps({"cases": cases, "candles": candles}, ensure_ascii=False, default=json_default)
    return """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <title>Leader Lab Chart Review</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    body { margin:0; font-family: Segoe UI, Malgun Gothic, Arial, sans-serif; background:#111827; color:#e5e7eb; }
    header { padding:14px 18px; background:#0f172a; border-bottom:1px solid #334155; }
    h1 { margin:0; font-size:20px; }
    .wrap { display:grid; grid-template-columns: 390px 1fr; height:calc(100vh - 58px); }
    .side { border-right:1px solid #334155; overflow:auto; background:#111827; }
    .main { overflow:auto; padding:12px; }
    .filters { padding:12px; position:sticky; top:0; background:#111827; z-index:2; border-bottom:1px solid #334155; }
    label { display:block; font-size:12px; color:#cbd5e1; margin-top:8px; }
    select, input { width:100%; box-sizing:border-box; padding:7px; background:#0f172a; color:#e5e7eb; border:1px solid #475569; border-radius:6px; }
    .case { padding:9px 12px; border-bottom:1px solid #1f2937; cursor:pointer; }
    .case:hover { background:#1e293b; }
    .case.active { background:#334155; }
    .case .title { font-weight:700; font-size:13px; }
    .case .meta { font-size:12px; color:#cbd5e1; margin-top:4px; line-height:1.45; }
    .bad { color:#fca5a5; }
    .good { color:#86efac; }
    .pill { display:inline-block; padding:2px 6px; border-radius:999px; background:#1f2937; margin-right:4px; font-size:11px; }
    .panel { display:grid; grid-template-columns: repeat(4, minmax(160px, 1fr)); gap:8px; margin-bottom:10px; }
    .card { background:#0f172a; border:1px solid #334155; border-radius:10px; padding:10px; }
    .card .k { font-size:11px; color:#94a3b8; }
    .card .v { font-size:16px; font-weight:700; margin-top:3px; }
    #chart { height:620px; background:#0f172a; border:1px solid #334155; border-radius:10px; }
    #volume { height:210px; background:#0f172a; border:1px solid #334155; border-radius:10px; margin-top:10px; }
    .note { font-size:12px; color:#94a3b8; margin-top:8px; }
  </style>
</head>
<body>
<header><h1>Leader Lab Chart Review — What You See Is What You Get</h1></header>
<div class="wrap">
  <aside class="side">
    <div class="filters">
      <label>일자</label><select id="dateSelect"></select>
      <label>Threshold</label><select id="thresholdSelect"></select>
      <label>보기</label>
      <select id="viewSelect">
        <option value="all">전체</option>
        <option value="loss">손실/종가약세</option>
        <option value="top10">Actual Top10</option>
        <option value="overheat10">진입 시가대비 +10% 이상</option>
        <option value="overheat15">진입 시가대비 +15% 이상</option>
      </select>
      <label>검색</label><input id="searchInput" placeholder="코드/종목명" />
    </div>
    <div id="caseList"></div>
  </aside>
  <main class="main">
    <div class="panel" id="infoPanel"></div>
    <div id="chart"></div>
    <div id="volume"></div>
    <div class="note">참조선: 당일 시가, 시가대비 +5%, +10%, +15%, +20%. 기준봉 고가/저가와 첫 돌파/진입 위치를 함께 표시합니다.</div>
  </main>
</div>
<script>
const DATA = __DATA_JSON__;
const cases = DATA.cases;
const candles = DATA.candles;
let selectedCaseId = null;
function fmt(v, d=2){ if(v===null || v===undefined || isNaN(Number(v))) return '-'; return Number(v).toFixed(d); }
function keyOf(c){ return c.search_date + '|' + c.code; }
function unique(arr){ return Array.from(new Set(arr)); }
function initFilters(){
  const dates = unique(cases.map(c=>c.search_date)).sort();
  const ths = unique(cases.map(c=>String(c.threshold_pct))).sort((a,b)=>Number(b)-Number(a));
  dateSelect.innerHTML = dates.map(d=>`<option>${d}</option>`).join('');
  thresholdSelect.innerHTML = ['all', ...ths].map(t=>`<option value="${t}">${t==='all'?'전체':t}</option>`).join('');
  dateSelect.onchange = renderList; thresholdSelect.onchange = renderList; viewSelect.onchange = renderList; searchInput.oninput = renderList;
}
function filteredCases(){
  const d = dateSelect.value; const th = thresholdSelect.value; const view = viewSelect.value; const q = searchInput.value.trim().toLowerCase();
  return cases.filter(c=>{
    if(c.search_date !== d) return false;
    if(th !== 'all' && String(c.threshold_pct) !== th) return false;
    if(q && !(String(c.code).toLowerCase().includes(q) || String(c.name||'').toLowerCase().includes(q))) return false;
    const closeRet = Number(c.close_return_from_entry_pct);
    const entryOpen = Number(c.entry_from_day_open_pct);
    const rank = Number(c.actual_rank);
    if(view==='loss' && !(closeRet < 0)) return false;
    if(view==='top10' && !(rank >= 1 && rank <= 10)) return false;
    if(view==='overheat10' && !(entryOpen >= 10)) return false;
    if(view==='overheat15' && !(entryOpen >= 15)) return false;
    return true;
  });
}
function renderList(){
  const list = filteredCases();
  caseList.innerHTML = list.map(c=>{
    const cls = c.id===selectedCaseId ? 'case active' : 'case';
    const retCls = Number(c.close_return_from_entry_pct) >= 0 ? 'good' : 'bad';
    return `<div class="${cls}" onclick="selectCase(${c.id})">
      <div class="title">${c.code} ${c.name||''} <span class="pill">T${c.threshold_pct}</span> <span class="pill">R${c.actual_rank||'-'}</span></div>
      <div class="meta">max ${fmt(c.actual_max_after_return_pct)}% / entry-open ${fmt(c.entry_from_day_open_pct)}% / close-entry <span class="${retCls}">${fmt(c.close_return_from_entry_pct)}%</span></div>
    </div>`;
  }).join('');
  if(list.length && !list.some(c=>c.id===selectedCaseId)) selectCase(list[0].id, false);
}
function selectCase(id, rerender=true){ selectedCaseId = id; const c = cases.find(x=>x.id===id); if(!c) return; renderInfo(c); renderChart(c); if(rerender) renderList(); }
function renderInfo(c){
  const items = [
    ['종목', `${c.search_date} ${c.code} ${c.name||''}`],
    ['Actual Rank / Max', `${c.actual_rank||'-'} / ${fmt(c.actual_max_after_return_pct)}%`],
    ['단일봉 상승률', `${fmt(c.singlebar_close_return_pct)}%`],
    ['진입 시가대비', `${fmt(c.entry_from_day_open_pct)}%`],
    ['돌파 RSI14', `${fmt(c.break_rsi14)}`],
    ['진입 후 최고', `${fmt(c.max_return_after_entry_pct)}%`],
    ['진입 후 종가', `${fmt(c.close_return_from_entry_pct)}%`],
    ['진입 후 최대하락', `${fmt(c.max_drawdown_after_entry_pct)}%`]
  ];
  infoPanel.innerHTML = items.map(x=>`<div class="card"><div class="k">${x[0]}</div><div class="v">${x[1]}</div></div>`).join('');
}
function renderChart(c){
  const arr = candles[keyOf(c)] || [];
  const x = arr.map(r=>r.t);
  const open = arr.map(r=>Number(r.o)); const high = arr.map(r=>Number(r.h)); const low = arr.map(r=>Number(r.l)); const close = arr.map(r=>Number(r.c)); const vol = arr.map(r=>Number(r.v));
  const dayOpen = Number(c.day_open);
  const shapes = [];
  function hline(y, name){ shapes.push({type:'line', xref:'paper', x0:0, x1:1, yref:'y', y0:y, y1:y, line:{width:1, dash:'dot'}}); }
  [0,5,10,15,20].forEach(p=>hline(dayOpen*(1+p/100), `+${p}%`));
  if(c.singlebar_high) hline(Number(c.singlebar_high), 'base high');
  if(c.singlebar_low) hline(Number(c.singlebar_low), 'base low');
  const traces = [{type:'candlestick', x, open, high, low, close, name:'5m'}];
  const markers = [];
  function addMarker(t, y, label){ if(t && y){ markers.push({x:[t], y:[Number(y)], mode:'markers+text', text:[label], textposition:'top center', marker:{size:11}, name:label}); } }
  addMarker(c.singlebar_time, c.singlebar_high, '기준봉');
  addMarker(c.break_time, c.break_price, '첫돌파/진입');
  addMarker(c.entry_time, c.entry_price, 'entry');
  addMarker(x[high.indexOf(Math.max(...high))], Math.max(...high), '당일고가');
  traces.push(...markers);
  Plotly.react('chart', traces, {paper_bgcolor:'#0f172a', plot_bgcolor:'#0f172a', font:{color:'#e5e7eb'}, xaxis:{rangeslider:{visible:false}}, yaxis:{title:'Price'}, shapes, margin:{l:50,r:20,t:28,b:40}}, {responsive:true});
  Plotly.react('volume', [{type:'bar', x, y:vol, name:'volume'}], {paper_bgcolor:'#0f172a', plot_bgcolor:'#0f172a', font:{color:'#e5e7eb'}, margin:{l:50,r:20,t:20,b:40}, yaxis:{title:'Volume'}}, {responsive:true});
}
initFilters(); renderList();
</script>
</body>
</html>""".replace("__DATA_JSON__", data_json)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--output", default="reports/chart_review_dashboard.html")
    args = parser.parse_args()
    load_env(args.env)
    conn = open_conn()
    try:
        cases = load_cases(conn)
        candles = load_candles_for_cases(conn, cases)
        html = build_html(cases, candles)
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print("=== DONE generate_chart_review_dashboard ===")
        print("cases=" + str(len(cases)))
        print("candles_groups=" + str(len(candles)))
        print("output=" + str(out.resolve()))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
