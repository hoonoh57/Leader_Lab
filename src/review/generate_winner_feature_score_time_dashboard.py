# -*- coding: utf-8 -*-
"""Generate Time-Aware Winner Feature Score dashboard.

Output:
    reports/winner_feature_score_time_dashboard.html
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
            SELECT id, decision_time, search_date, search_time, code, name,
                   score_rank_time, winner_feature_score_time, actual_rank,
                   actual_max_after_return_pct, full_day_close_return_pct,
                   decision_candle_time, decision_price,
                   future_max_return_pct, future_close_return_pct, future_max_drawdown_pct,
                   leader_strength_score_time, pullback_structure_score_time, current_strength_score_time, overheat_penalty_time,
                   cum_amount_until_time, cum_volume_until_time,
                   current_close_from_open_pct, high_so_far_from_open_pct, high_so_far_from_low_pct, range_so_far_pct,
                   singlebar_2pct_exists_until_time, singlebar_3pct_exists_until_time, singlebar_4pct_exists_until_time,
                   singlebar_5pct_exists_until_time, singlebar_6pct_exists_until_time,
                   max_singlebar_return_until_time, max_singlebar_from_open_until_time, max_singlebar_from_low_until_time,
                   radar_pullback_exists_until_time, radar_pullback_best_max_return_until_time,
                   amount_score_time, high_score_time, range_score_time, singlebar_score_time, radar_pullback_score_time,
                   current_close_score_time, singlebar6_penalty_time, overheat_open_penalty_time, overheat_low_penalty_time,
                   score_bucket_time, actual_rank_bucket
            FROM winner_feature_score_time_result
            WHERE valid_flag = 1
              AND score_rank_time <= %s
            ORDER BY decision_time, search_date, score_rank_time, code
            """,
            (top_n,),
        )
        return list(cur.fetchall())


def load_summary(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT decision_time, score_group, sample_count, active_days, avg_candidates_per_day,
                   actual_top1_count, actual_top3_count, actual_top5_count, actual_top10_count, actual_top10_rate,
                   avg_future_max_return_pct, median_future_max_return_pct,
                   avg_future_close_return_pct, avg_future_max_drawdown_pct,
                   win_rate_future_3pct, win_rate_future_5pct, win_rate_future_10pct,
                   loss_rate_future_close_m3pct, loss_rate_future_close_m5pct,
                   avg_winner_feature_score_time, avg_leader_strength_score_time,
                   avg_pullback_structure_score_time, avg_current_strength_score_time,
                   avg_overheat_penalty_time
            FROM winner_feature_score_time_summary
            ORDER BY decision_time,
                     FIELD(score_group, 'SCORE_TOP1_DAILY','SCORE_TOP3_DAILY','SCORE_TOP5_DAILY','SCORE_BUCKET_S80','SCORE_BUCKET_A65','SCORE_BUCKET_B50','ALL')
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
  <title>Time-Aware Winner Score Dashboard</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    body { margin:0; font-family: Segoe UI, Malgun Gothic, Arial, sans-serif; background:#111827; color:#e5e7eb; }
    header { padding:14px 18px; background:#0f172a; border-bottom:1px solid #334155; }
    h1 { margin:0; font-size:20px; }
    .wrap { display:grid; grid-template-columns: 470px 1fr; height:calc(100vh - 58px); }
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
<header><h1>Time-Aware Winner Feature Score v2 — No Future Data</h1></header>
<div class="wrap">
  <aside class="side">
    <div class="filters">
      <label>Decision Time</label><select id="timeSelect"></select>
      <label>일자</label><select id="dateSelect"></select>
      <label>보기</label>
      <select id="viewSelect">
        <option value="all">전체</option>
        <option value="scoretop1">Score Rank 1</option>
        <option value="actualtop10">Actual Top10</option>
        <option value="future3">이후 최고 +3% 이상</option>
        <option value="future5">이후 최고 +5% 이상</option>
        <option value="lossclose">이후 종가 손실</option>
        <option value="overheat">과열Penalty 있음</option>
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
    <div class="note">이 화면은 선택한 decision time 이전 데이터만으로 계산된 점수와 그 이후 실제 결과를 비교합니다.</div>
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
  const times = unique(cases.map(c=>c.decision_time)).sort();
  timeSelect.innerHTML = times.map(t=>`<option>${t}</option>`).join('');
  timeSelect.onchange = function(){ refreshDates(); renderSummary(); renderList(); };
  dateSelect.onchange = renderList; viewSelect.onchange = renderList; searchInput.oninput = renderList;
  refreshDates(); renderSummary();
}
function refreshDates(){
  const t = timeSelect.value;
  const dates = unique(cases.filter(c=>c.decision_time===t).map(c=>c.search_date)).sort();
  dateSelect.innerHTML = dates.map(d=>`<option>${d}</option>`).join('');
}
function renderSummary(){
  const t = timeSelect.value;
  const rows = summary.filter(s=>s.decision_time===t);
  const headers = ['Group','N','/Day','Top10%','FMax','FMed','FClose','FDD','Win3','Win5','Loss-5','Score','Leader','Pull','Cur','Risk'];
  let html = '<table><thead><tr>' + headers.map(h=>`<th>${h}</th>`).join('') + '</tr></thead><tbody>';
  rows.forEach(s=>{
    html += `<tr><td style="text-align:left">${s.score_group}</td><td>${s.sample_count}</td><td>${fmt(s.avg_candidates_per_day)}</td><td>${fmt(Number(s.actual_top10_rate)*100)}</td><td>${fmt(s.avg_future_max_return_pct)}</td><td>${fmt(s.median_future_max_return_pct)}</td><td>${fmt(s.avg_future_close_return_pct)}</td><td>${fmt(s.avg_future_max_drawdown_pct)}</td><td>${fmt(Number(s.win_rate_future_3pct)*100)}</td><td>${fmt(Number(s.win_rate_future_5pct)*100)}</td><td>${fmt(Number(s.loss_rate_future_close_m5pct)*100)}</td><td>${fmt(s.avg_winner_feature_score_time)}</td><td>${fmt(s.avg_leader_strength_score_time)}</td><td>${fmt(s.avg_pullback_structure_score_time)}</td><td>${fmt(s.avg_current_strength_score_time)}</td><td>${fmt(s.avg_overheat_penalty_time)}</td></tr>`;
  });
  html += '</tbody></table>';
  summaryTable.innerHTML = html;
}
function filteredCases(){
  const t = timeSelect.value; const d = dateSelect.value; const view = viewSelect.value; const q = searchInput.value.trim().toLowerCase();
  return cases.filter(c=>{
    if(c.decision_time !== t || c.search_date !== d) return false;
    if(q && !(String(c.code).toLowerCase().includes(q) || String(c.name||'').toLowerCase().includes(q))) return false;
    if(view==='scoretop1' && Number(c.score_rank_time)!==1) return false;
    if(view==='actualtop10' && !(Number(c.actual_rank)>=1 && Number(c.actual_rank)<=10)) return false;
    if(view==='future3' && !(Number(c.future_max_return_pct)>=3)) return false;
    if(view==='future5' && !(Number(c.future_max_return_pct)>=5)) return false;
    if(view==='lossclose' && !(Number(c.future_close_return_pct)<0)) return false;
    if(view==='overheat' && !(Number(c.overheat_penalty_time)>0)) return false;
    return true;
  });
}
function renderList(){
  const list = filteredCases();
  caseList.innerHTML = list.map(c=>{
    const cls = c.id===selectedCaseId ? 'case active' : 'case';
    const retCls = Number(c.future_max_return_pct) >= 3 ? 'good' : 'bad';
    return `<div class="${cls}" onclick="selectCase(${c.id})">
      <div class="title">#${c.score_rank_time} ${c.code} ${c.name||''} <span class="pill">Score ${fmt(c.winner_feature_score_time)}</span><span class="pill">Actual ${c.actual_rank||'-'}</span></div>
      <div class="meta">future max <span class="${retCls}">${fmt(c.future_max_return_pct)}%</span> / close ${fmt(c.future_close_return_pct)}% / leader ${fmt(c.leader_strength_score_time)} / current ${fmt(c.current_strength_score_time)} / risk ${fmt(c.overheat_penalty_time)}</div>
    </div>`;
  }).join('');
  if(list.length && !list.some(c=>c.id===selectedCaseId)) selectCase(list[0].id, false);
}
function selectCase(id, rerender=true){ selectedCaseId = id; const c = cases.find(x=>x.id===id); if(!c) return; renderInfo(c); renderChart(c); if(rerender) renderList(); }
function renderInfo(c){
  const items = [
    ['종목', `${c.search_date} ${c.decision_time} #${c.score_rank_time} ${c.code} ${c.name||''}`],
    ['TimeScore', `${fmt(c.winner_feature_score_time)} = L${fmt(c.leader_strength_score_time)} + P${fmt(c.pullback_structure_score_time)} + C${fmt(c.current_strength_score_time)} - Risk${fmt(c.overheat_penalty_time)}`],
    ['Actual / Future', `Actual ${c.actual_rank||'-'} / future max ${fmt(c.future_max_return_pct)}% / close ${fmt(c.future_close_return_pct)}%`],
    ['Decision', `${c.decision_candle_time} / price ${fmt(c.decision_price)}`],
    ['CumAmount', `${fmt(Number(c.cum_amount_until_time)/100000000)}억 / score ${fmt(c.amount_score_time)}`],
    ['Current Position', `close-open ${fmt(c.current_close_from_open_pct)}% / high-open ${fmt(c.high_so_far_from_open_pct)}% / range ${fmt(c.range_so_far_pct)}%`],
    ['Singlebar until T', `max ${fmt(c.max_singlebar_return_until_time)}% / 3:${c.singlebar_3pct_exists_until_time} 4:${c.singlebar_4pct_exists_until_time} 5:${c.singlebar_5pct_exists_until_time} 6:${c.singlebar_6pct_exists_until_time}`],
    ['Risk', `p6 ${fmt(c.singlebar6_penalty_time)} / open ${fmt(c.overheat_open_penalty_time)} / low ${fmt(c.overheat_low_penalty_time)}`]
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
  if(c.decision_candle_time){ shapes.push({type:'line', xref:'x', x0:c.decision_candle_time, x1:c.decision_candle_time, yref:'paper', y0:0, y1:1, line:{width:2, dash:'dash'}}); }
  const traces = [{type:'candlestick', x, open, high, low, close, name:'5m'}];
  if(c.decision_candle_time && c.decision_price){ traces.push({x:[c.decision_candle_time], y:[Number(c.decision_price)], mode:'markers+text', text:['Decision'], textposition:'top center', marker:{size:12}, name:'Decision'}); }
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
    parser.add_argument("--output", default="reports/winner_feature_score_time_dashboard.html")
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
        print("=== DONE generate_winner_feature_score_time_dashboard ===")
        print("cases=" + str(len(cases)))
        print("candles_groups=" + str(len(candles)))
        print("output=" + str(out.resolve()))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
