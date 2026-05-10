# -*- coding: utf-8 -*-
"""Generate Winner Feature Score review dashboard.

Output:
    reports/winner_feature_score_dashboard.html

This dashboard reviews daily score-ranked candidates with 5-minute candles and score breakdown.
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


def load_cases(conn: Any, top_n: int) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, search_date, search_time, code, name,
                   score_rank, winner_feature_score, actual_rank,
                   actual_max_after_return_pct, close_return_pct,
                   leader_strength_score, pullback_structure_score, close_strength_score, overheat_penalty,
                   amount_score, first_hour_score, day_range_score, singlebar_score,
                   radar_pullback_score, radar_pullback_return_score,
                   close_from_open_score, singlebar6_penalty,
                   singlebar_open_overheat_penalty, singlebar_low_overheat_penalty,
                   intraday_amount_proxy, first_hour_high_from_open_pct, day_range_pct, close_from_open_pct,
                   max_5m_singlebar_return_pct, max_5m_singlebar_from_open_pct, max_5m_singlebar_from_low_pct,
                   best_radar_pullback_max_return_pct, best_radar_pullback_close_return_pct,
                   singlebar_2pct_exists, singlebar_3pct_exists, singlebar_4pct_exists,
                   singlebar_5pct_exists, singlebar_6pct_exists, radar_pullback_exists,
                   score_bucket, actual_rank_bucket
            FROM winner_feature_score_result
            WHERE score_rank <= %s
            ORDER BY search_date, score_rank, code
            """,
            (top_n,),
        )
        return list(cur.fetchall())


def load_summary(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT score_group, sample_count, active_days, avg_candidates_per_day,
                   actual_top1_count, actual_top3_count, actual_top5_count, actual_top10_count, actual_top10_rate,
                   avg_actual_max_after_return_pct, median_actual_max_after_return_pct, avg_close_return_pct,
                   avg_winner_feature_score, avg_leader_strength_score, avg_pullback_structure_score,
                   avg_close_strength_score, avg_overheat_penalty
            FROM winner_feature_score_summary
            ORDER BY FIELD(score_group, 'SCORE_TOP1_DAILY','SCORE_TOP3_DAILY','SCORE_TOP5_DAILY','SCORE_BUCKET_S80','SCORE_BUCKET_A65','SCORE_BUCKET_B50','ALL')
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


def build_html(cases: List[Dict[str, Any]], candles: Dict[str, List[Dict[str, Any]]], summary: List[Dict[str, Any]]) -> str:
    data_json = json.dumps({"cases": cases, "candles": candles, "summary": summary}, ensure_ascii=False, default=json_default)
    return """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <title>Winner Feature Score Dashboard</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    body { margin:0; font-family: Segoe UI, Malgun Gothic, Arial, sans-serif; background:#111827; color:#e5e7eb; }
    header { padding:14px 18px; background:#0f172a; border-bottom:1px solid #334155; }
    h1 { margin:0; font-size:20px; }
    .wrap { display:grid; grid-template-columns: 460px 1fr; height:calc(100vh - 58px); }
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
    #volume { height:180px; background:#0f172a; border:1px solid #334155; border-radius:10px; margin-top:10px; }
    table { border-collapse:collapse; width:100%; font-size:12px; background:#0f172a; margin-bottom:12px; }
    th,td { border:1px solid #334155; padding:5px 6px; text-align:right; }
    th { background:#1e293b; color:#cbd5e1; }
    .note { font-size:12px; color:#94a3b8; margin-top:8px; }
  </style>
</head>
<body>
<header><h1>Winner Feature Score Dashboard — Feature Asset Ranking</h1></header>
<div class="wrap">
  <aside class="side">
    <div class="filters">
      <label>일자</label><select id="dateSelect"></select>
      <label>보기</label>
      <select id="viewSelect">
        <option value="all">전체</option>
        <option value="scoretop1">Score Rank 1</option>
        <option value="actualtop10">Actual Top10</option>
        <option value="loser">실패/종가손실</option>
        <option value="overheat">과열Penalty 있음</option>
        <option value="radar">Radar-Pullback 있음</option>
      </select>
      <label>검색</label><input id="searchInput" placeholder="코드/종목명" />
    </div>
    <div id="caseList"></div>
  </aside>
  <main class="main">
    <h3>Summary</h3>
    <div id="summaryTable"></div>
    <div class="panel" id="infoPanel"></div>
    <div id="chart"></div>
    <div id="volume"></div>
    <div class="note">점수는 매수 신호가 아니라 조건식 포착 후보 내부의 설명 가능한 Winner 가능성 Rank입니다.</div>
  </main>
</div>
<script>
const DATA = __DATA_JSON__;
const cases = DATA.cases;
const candles = DATA.candles;
const summary = DATA.summary;
let selectedCaseId = null;
function fmt(v, d=2){ if(v===null || v===undefined || isNaN(Number(v))) return '-'; return Number(v).toFixed(d); }
function keyOf(c){ return c.search_date + '|' + c.code; }
function unique(arr){ return Array.from(new Set(arr)); }
function initFilters(){
  const dates = unique(cases.map(c=>c.search_date)).sort();
  dateSelect.innerHTML = dates.map(d=>`<option>${d}</option>`).join('');
  dateSelect.onchange = renderList; viewSelect.onchange = renderList; searchInput.oninput = renderList;
  renderSummary();
}
function renderSummary(){
  const headers = ['Group','N','/Day','Top10%','AvgRet','MedRet','Close','Score','Leader','Pullback','CloseStr','Penalty'];
  let html = '<table><thead><tr>' + headers.map(h=>`<th>${h}</th>`).join('') + '</tr></thead><tbody>';
  summary.forEach(s=>{
    html += `<tr><td style="text-align:left">${s.score_group}</td><td>${s.sample_count}</td><td>${fmt(s.avg_candidates_per_day)}</td><td>${fmt(Number(s.actual_top10_rate)*100)}</td><td>${fmt(s.avg_actual_max_after_return_pct)}</td><td>${fmt(s.median_actual_max_after_return_pct)}</td><td>${fmt(s.avg_close_return_pct)}</td><td>${fmt(s.avg_winner_feature_score)}</td><td>${fmt(s.avg_leader_strength_score)}</td><td>${fmt(s.avg_pullback_structure_score)}</td><td>${fmt(s.avg_close_strength_score)}</td><td>${fmt(s.avg_overheat_penalty)}</td></tr>`;
  });
  html += '</tbody></table>';
  summaryTable.innerHTML = html;
}
function filteredCases(){
  const d = dateSelect.value; const view = viewSelect.value; const q = searchInput.value.trim().toLowerCase();
  return cases.filter(c=>{
    if(c.search_date !== d) return false;
    if(q && !(String(c.code).toLowerCase().includes(q) || String(c.name||'').toLowerCase().includes(q))) return false;
    if(view==='scoretop1' && Number(c.score_rank)!==1) return false;
    if(view==='actualtop10' && !(Number(c.actual_rank)>=1 && Number(c.actual_rank)<=10)) return false;
    if(view==='loser' && !(Number(c.close_return_pct)<0 || Number(c.actual_max_after_return_pct)<3)) return false;
    if(view==='overheat' && !(Number(c.overheat_penalty)>0)) return false;
    if(view==='radar' && !(Number(c.radar_pullback_exists)===1)) return false;
    return true;
  });
}
function renderList(){
  const list = filteredCases();
  caseList.innerHTML = list.map(c=>{
    const cls = c.id===selectedCaseId ? 'case active' : 'case';
    const retCls = Number(c.actual_max_after_return_pct) >= 10 ? 'good' : 'bad';
    return `<div class="${cls}" onclick="selectCase(${c.id})">
      <div class="title">#${c.score_rank} ${c.code} ${c.name||''} <span class="pill">Score ${fmt(c.winner_feature_score)}</span><span class="pill">Actual ${c.actual_rank||'-'}</span></div>
      <div class="meta">max <span class="${retCls}">${fmt(c.actual_max_after_return_pct)}%</span> / close ${fmt(c.close_return_pct)}% / leader ${fmt(c.leader_strength_score)} / pullback ${fmt(c.pullback_structure_score)} / penalty ${fmt(c.overheat_penalty)}</div>
    </div>`;
  }).join('');
  if(list.length && !list.some(c=>c.id===selectedCaseId)) selectCase(list[0].id, false);
}
function selectCase(id, rerender=true){ selectedCaseId = id; const c = cases.find(x=>x.id===id); if(!c) return; renderInfo(c); renderChart(c); if(rerender) renderList(); }
function renderInfo(c){
  const items = [
    ['종목', `${c.search_date} #${c.score_rank} ${c.code} ${c.name||''}`],
    ['WinnerScore', `${fmt(c.winner_feature_score)} = L${fmt(c.leader_strength_score)} + P${fmt(c.pullback_structure_score)} + C${fmt(c.close_strength_score)} - Risk${fmt(c.overheat_penalty)}`],
    ['Actual Rank / Max', `${c.actual_rank||'-'} / ${fmt(c.actual_max_after_return_pct)}%`],
    ['거래대금Score', `${fmt(c.amount_score)} / proxy ${fmt(Number(c.intraday_amount_proxy)/100000000)}억`],
    ['오전강도/Range', `${fmt(c.first_hour_high_from_open_pct)}% / ${fmt(c.day_range_pct)}%`],
    ['Singlebar', `max ${fmt(c.max_5m_singlebar_return_pct)}% / 3:${c.singlebar_3pct_exists} 4:${c.singlebar_4pct_exists} 5:${c.singlebar_5pct_exists} 6:${c.singlebar_6pct_exists}`],
    ['RadarPullback', `${c.radar_pullback_exists} / max ${fmt(c.best_radar_pullback_max_return_pct)}% / close ${fmt(c.best_radar_pullback_close_return_pct)}%`],
    ['과열Penalty', `${fmt(c.singlebar6_penalty)} + ${fmt(c.singlebar_open_overheat_penalty)} + ${fmt(c.singlebar_low_overheat_penalty)}`]
  ];
  infoPanel.innerHTML = items.map(x=>`<div class="card"><div class="k">${x[0]}</div><div class="v">${x[1]}</div></div>`).join('');
}
function renderChart(c){
  const arr = candles[keyOf(c)] || [];
  const x = arr.map(r=>r.t);
  const open = arr.map(r=>Number(r.o)); const high = arr.map(r=>Number(r.h)); const low = arr.map(r=>Number(r.l)); const close = arr.map(r=>Number(r.c)); const vol = arr.map(r=>Number(r.v));
  const dayOpen = open.length ? open[0] : null;
  const shapes = [];
  function hline(y, dash='dot'){ if(y!==null && !isNaN(y)) shapes.push({type:'line', xref:'paper', x0:0, x1:1, yref:'y', y0:y, y1:y, line:{width:1, dash}}); }
  if(dayOpen){ [0,5,10,15,20].forEach(p=>hline(dayOpen*(1+p/100))); }
  const traces = [{type:'candlestick', x, open, high, low, close, name:'5m'}];
  const maxHigh = Math.max(...high); const maxIdx = high.indexOf(maxHigh);
  traces.push({x:[x[maxIdx]], y:[maxHigh], mode:'markers+text', text:['Day High'], textposition:'top center', marker:{size:11}, name:'Day High'});
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
    parser.add_argument("--output", default="reports/winner_feature_score_dashboard.html")
    parser.add_argument("--top-n", type=int, default=10)
    args = parser.parse_args()
    load_env(args.env)
    conn = open_conn()
    try:
        cases = load_cases(conn, args.top_n)
        summary = load_summary(conn)
        candles = load_candles_for_cases(conn, cases)
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(build_html(cases, candles, summary), encoding="utf-8")
        print("=== DONE generate_winner_feature_score_dashboard ===")
        print("cases=" + str(len(cases)))
        print("candles_groups=" + str(len(candles)))
        print("output=" + str(out.resolve()))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
