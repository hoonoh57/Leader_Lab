# -*- coding: utf-8 -*-
"""Generate a static Radar-Pullback chart review dashboard.

This dashboard intentionally does NOT connect to leader Top N logic.
It reviews only the Radar -> Pullback -> Re-expansion entry evidence.

Output:
    reports/radar_pullback_review_dashboard.html
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


def load_cases(conn: Any, limit: int) -> List[Dict[str, Any]]:
    sql = """
        SELECT id,
               radar_threshold_pct, pullback_depth_pct, max_pullback_bars, volume_shrink_ratio,
               search_date, search_time, code, name,
               actual_rank, actual_max_after_return_pct,
               day_open, day_low, day_high, day_close,
               radar_time, radar_open, radar_high, radar_low, radar_close, radar_volume,
               radar_close_return_pct, radar_from_day_open_pct, radar_from_day_low_pct,
               pullback_low_time, pullback_low_price, pullback_depth_from_radar_high_pct,
               pullback_bars, pullback_avg_volume, pullback_volume_ratio_to_radar,
               reaction_high_time, reaction_high_price,
               entry_time, entry_price, entry_from_day_open_pct, entry_from_day_low_pct,
               entry_volume, entry_amount, entry_rsi14,
               entry_after_max_time, entry_after_max_price,
               max_return_after_entry_pct, close_return_from_entry_pct, max_drawdown_after_entry_pct
        FROM radar_pullback_entry_result
        WHERE valid_flag = 1
        ORDER BY search_date, radar_threshold_pct, pullback_depth_pct DESC,
                 max_return_after_entry_pct DESC, code
    """
    params: List[Any] = []
    if limit > 0:
        sql += " LIMIT %s"
        params.append(limit)
    with conn.cursor() as cur:
        cur.execute(sql, tuple(params))
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
  <title>Radar Pullback Review</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    body { margin:0; font-family: Segoe UI, Malgun Gothic, Arial, sans-serif; background:#111827; color:#e5e7eb; }
    header { padding:14px 18px; background:#0f172a; border-bottom:1px solid #334155; }
    h1 { margin:0; font-size:20px; }
    .wrap { display:grid; grid-template-columns: 430px 1fr; height:calc(100vh - 58px); }
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
    #chart { height:640px; background:#0f172a; border:1px solid #334155; border-radius:10px; }
    #volume { height:210px; background:#0f172a; border:1px solid #334155; border-radius:10px; margin-top:10px; }
    .note { font-size:12px; color:#94a3b8; margin-top:8px; }
  </style>
</head>
<body>
<header><h1>Radar Pullback Review — Radar → Pullback → Re-expansion Entry</h1></header>
<div class="wrap">
  <aside class="side">
    <div class="filters">
      <label>일자</label><select id="dateSelect"></select>
      <label>Radar Threshold</label><select id="radarSelect"></select>
      <label>Pullback Depth</label><select id="depthSelect"></select>
      <label>보기</label>
      <select id="viewSelect">
        <option value="all">전체</option>
        <option value="profit3">진입 후 최고 +3% 이상</option>
        <option value="profit5">진입 후 최고 +5% 이상</option>
        <option value="lossclose">종가 손실</option>
        <option value="entryopen10">진입 시가대비 +10% 이상</option>
        <option value="top10">Actual Top10</option>
      </select>
      <label>검색</label><input id="searchInput" placeholder="코드/종목명" />
    </div>
    <div id="caseList"></div>
  </aside>
  <main class="main">
    <div class="panel" id="infoPanel"></div>
    <div id="chart"></div>
    <div id="volume"></div>
    <div class="note">이 대시보드는 Top N 로직과 연결하지 않고, Radar-Pullback 조건 자체만 검증합니다.</div>
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
  const radars = unique(cases.map(c=>String(c.radar_threshold_pct))).sort((a,b)=>Number(a)-Number(b));
  const depths = unique(cases.map(c=>String(c.pullback_depth_pct))).sort((a,b)=>Number(a)-Number(b));
  dateSelect.innerHTML = dates.map(d=>`<option>${d}</option>`).join('');
  radarSelect.innerHTML = ['all', ...radars].map(t=>`<option value="${t}">${t==='all'?'전체':t}</option>`).join('');
  depthSelect.innerHTML = ['all', ...depths].map(t=>`<option value="${t}">${t==='all'?'전체':t}</option>`).join('');
  dateSelect.onchange = renderList; radarSelect.onchange = renderList; depthSelect.onchange = renderList; viewSelect.onchange = renderList; searchInput.oninput = renderList;
}
function filteredCases(){
  const d = dateSelect.value; const rt = radarSelect.value; const depth = depthSelect.value; const view = viewSelect.value; const q = searchInput.value.trim().toLowerCase();
  return cases.filter(c=>{
    if(c.search_date !== d) return false;
    if(rt !== 'all' && String(c.radar_threshold_pct) !== rt) return false;
    if(depth !== 'all' && String(c.pullback_depth_pct) !== depth) return false;
    if(q && !(String(c.code).toLowerCase().includes(q) || String(c.name||'').toLowerCase().includes(q))) return false;
    const maxRet = Number(c.max_return_after_entry_pct);
    const closeRet = Number(c.close_return_from_entry_pct);
    const entryOpen = Number(c.entry_from_day_open_pct);
    const rank = Number(c.actual_rank);
    if(view==='profit3' && !(maxRet >= 3)) return false;
    if(view==='profit5' && !(maxRet >= 5)) return false;
    if(view==='lossclose' && !(closeRet < 0)) return false;
    if(view==='entryopen10' && !(entryOpen >= 10)) return false;
    if(view==='top10' && !(rank >= 1 && rank <= 10)) return false;
    return true;
  });
}
function renderList(){
  const list = filteredCases();
  caseList.innerHTML = list.map(c=>{
    const cls = c.id===selectedCaseId ? 'case active' : 'case';
    const retCls = Number(c.close_return_from_entry_pct) >= 0 ? 'good' : 'bad';
    return `<div class="${cls}" onclick="selectCase(${c.id})">
      <div class="title">${c.code} ${c.name||''} <span class="pill">R${c.radar_threshold_pct}</span><span class="pill">PB${c.pullback_depth_pct}</span><span class="pill">Rank ${c.actual_rank||'-'}</span></div>
      <div class="meta">max ${fmt(c.max_return_after_entry_pct)}% / close <span class="${retCls}">${fmt(c.close_return_from_entry_pct)}%</span> / entry-open ${fmt(c.entry_from_day_open_pct)}%</div>
    </div>`;
  }).join('');
  if(list.length && !list.some(c=>c.id===selectedCaseId)) selectCase(list[0].id, false);
}
function selectCase(id, rerender=true){ selectedCaseId = id; const c = cases.find(x=>x.id===id); if(!c) return; renderInfo(c); renderChart(c); if(rerender) renderList(); }
function renderInfo(c){
  const items = [
    ['종목', `${c.search_date} ${c.code} ${c.name||''}`],
    ['조건', `Radar ${c.radar_threshold_pct}% / PB ${c.pullback_depth_pct}% / ${c.max_pullback_bars}봉 / vol ${c.volume_shrink_ratio}`],
    ['Actual Rank / Max', `${c.actual_rank||'-'} / ${fmt(c.actual_max_after_return_pct)}%`],
    ['Radar 상승률', `${fmt(c.radar_close_return_pct)}%`],
    ['Pullback 깊이', `${fmt(c.pullback_depth_from_radar_high_pct)}% / ${c.pullback_bars}봉`],
    ['진입 시가대비', `${fmt(c.entry_from_day_open_pct)}%`],
    ['진입 후 최고', `${fmt(c.max_return_after_entry_pct)}%`],
    ['진입 후 종가', `${fmt(c.close_return_from_entry_pct)}%`]
  ];
  infoPanel.innerHTML = items.map(x=>`<div class="card"><div class="k">${x[0]}</div><div class="v">${x[1]}</div></div>`).join('');
}
function renderChart(c){
  const arr = candles[keyOf(c)] || [];
  const x = arr.map(r=>r.t);
  const open = arr.map(r=>Number(r.o)); const high = arr.map(r=>Number(r.h)); const low = arr.map(r=>Number(r.l)); const close = arr.map(r=>Number(r.c)); const vol = arr.map(r=>Number(r.v));
  const dayOpen = Number(c.day_open);
  const shapes = [];
  function hline(y, dash='dot'){ if(!isNaN(y)) shapes.push({type:'line', xref:'paper', x0:0, x1:1, yref:'y', y0:y, y1:y, line:{width:1, dash}}); }
  [0,5,10,15,20].forEach(p=>hline(dayOpen*(1+p/100)));
  hline(Number(c.radar_high), 'dash');
  hline(Number(c.reaction_high_price), 'solid');
  const traces = [{type:'candlestick', x, open, high, low, close, name:'5m'}];
  const markers = [];
  function addMarker(t, y, label){ if(t && y){ markers.push({x:[t], y:[Number(y)], mode:'markers+text', text:[label], textposition:'top center', marker:{size:11}, name:label}); } }
  addMarker(c.radar_time, c.radar_high, 'Radar');
  addMarker(c.pullback_low_time, c.pullback_low_price, 'PB Low');
  addMarker(c.reaction_high_time, c.reaction_high_price, 'Reaction High');
  addMarker(c.entry_time, c.entry_price, 'Entry');
  addMarker(c.entry_after_max_time, c.entry_after_max_price, 'After Max');
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
    parser.add_argument("--output", default="reports/radar_pullback_review_dashboard.html")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    load_env(args.env)
    conn = open_conn()
    try:
        cases = load_cases(conn, args.limit)
        candles = load_candles_for_cases(conn, cases)
        html = build_html(cases, candles)
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print("=== DONE generate_radar_pullback_review_dashboard ===")
        print("cases=" + str(len(cases)))
        print("candles_groups=" + str(len(candles)))
        print("output=" + str(out.resolve()))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
