param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== BUILD ST Candidate Overlap Report v1 ==='

$required = @(
    'START_HERE.md',
    'docs/workflow_server_editing_v1.md',
    'docs/powershell_script_rule_v1.md',
    'docs/pre_edit_reading_rule_v1.md',
    'docs/todo_update_rule_v1.md',
    'docs/st_dashboard_live_overlay_research_v1.md',
    'docs/live_candidate_overlay_on_st_dashboard_v1.md',
    'todo_list.md'
)
foreach ($rel in $required) {
    $p = Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p)) { throw ('Missing required file: ' + $rel) }
    Write-Host ('OK ' + $rel)
}

$tmp = Join-Path $root '.tmp_build_st_candidate_overlap_report_v1.py'
$code = @'
from __future__ import annotations
import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import pymysql


def load_env(path: str) -> None:
    p = Path(path)
    if not p.exists():
        return
    for raw in p.read_text(encoding='utf-8-sig').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        os.environ[k.strip()] = v.strip().strip('"').strip("'")


def ev(names, default=None):
    for n in names:
        v = os.environ.get(n)
        if v is not None and v.strip() != '':
            return v.strip()
    return default


def open_conn():
    db = ev(['DB_NAME','MYSQL_DATABASE','MYSQL_DB'])
    if db is None:
        raise RuntimeError('DB_NAME is required')
    return pymysql.connect(host=ev(['DB_HOST','MYSQL_HOST'],'127.0.0.1'), port=int(ev(['DB_PORT','MYSQL_PORT'],'3306')), user=ev(['DB_USER','MYSQL_USER'],'root'), password=ev(['DB_PASS','DB_PASSWORD','MYSQL_PASSWORD'],''), database=db, charset='utf8mb4', autocommit=True, cursorclass=pymysql.cursors.DictCursor)


def cols(conn, name: str) -> List[str]:
    db = ev(['DB_NAME','MYSQL_DATABASE','MYSQL_DB'])
    with conn.cursor() as cur:
        cur.execute('SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION', (db, name))
        return [str(r['COLUMN_NAME']) for r in cur.fetchall()]


def dt_date(v: Any) -> str:
    if v is None:
        return ''
    return str(v)[:10]


def parse_dt(date_text: str, time_text: Any) -> Optional[datetime]:
    if not date_text or time_text is None:
        return None
    t = str(time_text).strip()
    if not t:
        return None
    if 'T' in t:
        try:
            return datetime.fromisoformat(t)
        except Exception:
            return None
    if len(t) == 5:
        t += ':00'
    try:
        return datetime.fromisoformat(date_text + 'T' + t)
    except Exception:
        return None


def get_candidate_date(row: Dict[str, Any]) -> str:
    for k in ['trade_date','search_date','base_date','target_date']:
        if k in row and row.get(k) is not None:
            return dt_date(row.get(k))
    snap = row.get('realtime_snapshot_time')
    if snap is not None:
        return dt_date(snap)
    return ''


def load_candidates(conn, view_name: str) -> List[Dict[str, Any]]:
    have = set(cols(conn, view_name))
    wanted = ['code','name','board_action_v2_8','entry_time_text','entry_price','tick_confirm_score_v2_6','tick_intensity_v2_6','buy_tick_ratio_v2_6','hoga_bid_pressure_v2_6','hoga_ask_absorption_v2_6','spread_risk_v2_6','realtime_snapshot_time','trade_date','search_date','st_period','st_multiplier','final_rank_no_v2_8','dedup_final_rank_no_v2_9']
    use = [c for c in wanted if c in have]
    order = 'dedup_final_rank_no_v2_9' if 'dedup_final_rank_no_v2_9' in have else 'final_rank_no_v2_8'
    sql = 'SELECT ' + ','.join(use) + ' FROM ' + view_name
    if order in have:
        sql += ' ORDER BY ' + order + ' ASC'
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = list(cur.fetchall())
    for r in rows:
        r['_source_view'] = view_name
        r['_candidate_date'] = get_candidate_date(r)
    return rows


def load_segments(conn) -> List[Dict[str, Any]]:
    sql = '''
    SELECT id, trade_date, code, name, st_period, st_multiplier, segment_no,
           st_up_start_time, st_up_end_time, st_up_max_price, st_up_max_return_pct,
           label_st_gain_5pct, label_st_gain_10pct, label_st_fail_1pct, label_st_end_negative
    FROM supertrend_regime_segment
    '''
    with conn.cursor() as cur:
        cur.execute(sql)
        return list(cur.fetchall())


def fnum(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def pct(new_v: Optional[float], base_v: Optional[float]) -> Optional[float]:
    if new_v is None or base_v is None or base_v == 0:
        return None
    return (new_v - base_v) / base_v * 100.0


def classify(seg: Dict[str, Any]) -> str:
    if int(seg.get('label_st_gain_10pct') or 0) == 1:
        return 'GREAT'
    if int(seg.get('label_st_gain_5pct') or 0) == 1:
        return 'GOOD'
    if int(seg.get('label_st_fail_1pct') or 0) == 1 or int(seg.get('label_st_end_negative') or 0) == 1:
        return 'BAD'
    return 'NEUTRAL'


def main() -> int:
    load_env('.env')
    out_dir = Path('reports')
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / 'st_candidate_overlap_report_v1.csv'
    out_md = out_dir / 'st_candidate_overlap_summary_v1.md'
    conn = open_conn()
    try:
        candidates = load_candidates(conn, 'supertrend_top_candidate_board_dedup_view_v2_9')
        segments = load_segments(conn)
    finally:
        conn.close()

    seg_by_code_date: Dict[str, List[Dict[str, Any]]] = {}
    for s in segments:
        key = str(s.get('code')) + '|' + dt_date(s.get('trade_date'))
        seg_by_code_date.setdefault(key, []).append(s)

    rows: List[Dict[str, Any]] = []
    for c in candidates:
        cdate = c.get('_candidate_date') or ''
        key = str(c.get('code')) + '|' + cdate
        entry_dt = parse_dt(cdate, c.get('entry_time_text'))
        matched = seg_by_code_date.get(key, [])
        if not matched:
            rows.append({'code': c.get('code'), 'name': c.get('name'), 'candidate_date': cdate, 'board_action': c.get('board_action_v2_8'), 'entry_time_text': c.get('entry_time_text'), 'entry_price': c.get('entry_price'), 'match_status': 'NO_SEGMENT_SAME_CODE_DATE', 'segment_id': '', 'segment_quality': '', 'inside_segment': '', 'bars_to_start': '', 'bars_to_end': '', 'remain_to_max_pct': '', 'st_up_max_return_pct': '', 'tick_confirm_score': c.get('tick_confirm_score_v2_6')})
            continue
        for s in matched:
            start = s.get('st_up_start_time')
            end = s.get('st_up_end_time')
            inside = False
            bars_to_start = None
            bars_to_end = None
            if entry_dt is not None and start is not None and end is not None:
                inside = start <= entry_dt <= end
                bars_to_start = int((entry_dt - start).total_seconds() // 300)
                bars_to_end = int((end - entry_dt).total_seconds() // 300)
            remain = pct(fnum(s.get('st_up_max_price')), fnum(c.get('entry_price')))
            rows.append({'code': c.get('code'), 'name': c.get('name'), 'candidate_date': cdate, 'board_action': c.get('board_action_v2_8'), 'entry_time_text': c.get('entry_time_text'), 'entry_price': c.get('entry_price'), 'match_status': 'MATCHED_SEGMENT', 'segment_id': s.get('id'), 'segment_no': s.get('segment_no'), 'segment_quality': classify(s), 'inside_segment': 1 if inside else 0, 'bars_to_start': bars_to_start, 'bars_to_end': bars_to_end, 'remain_to_max_pct': remain, 'st_up_max_return_pct': s.get('st_up_max_return_pct'), 'tick_confirm_score': c.get('tick_confirm_score_v2_6')})

    fields = ['code','name','candidate_date','board_action','entry_time_text','entry_price','match_status','segment_id','segment_no','segment_quality','inside_segment','bars_to_start','bars_to_end','remain_to_max_pct','st_up_max_return_pct','tick_confirm_score']
    with out_csv.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    total_candidates = len(candidates)
    matched_rows = [r for r in rows if r.get('match_status') == 'MATCHED_SEGMENT']
    inside_rows = [r for r in matched_rows if r.get('inside_segment') == 1]
    great_inside = [r for r in inside_rows if r.get('segment_quality') == 'GREAT']
    good_inside = [r for r in inside_rows if r.get('segment_quality') in ('GREAT','GOOD')]
    lines = []
    lines.append('# ST Candidate Overlap Summary v1')
    lines.append('')
    lines.append('total_candidates=' + str(total_candidates))
    lines.append('matched_segment_rows=' + str(len(matched_rows)))
    lines.append('inside_segment_rows=' + str(len(inside_rows)))
    lines.append('inside_good_or_great_rows=' + str(len(good_inside)))
    lines.append('inside_great_rows=' + str(len(great_inside)))
    lines.append('')
    lines.append('csv=reports/st_candidate_overlap_report_v1.csv')
    out_md.write_text('\n'.join(lines), encoding='utf-8')
    print('=== DONE build_st_candidate_overlap_report_v1 ===')
    print('total_candidates=' + str(total_candidates))
    print('matched_segment_rows=' + str(len(matched_rows)))
    print('inside_segment_rows=' + str(len(inside_rows)))
    print('inside_good_or_great_rows=' + str(len(good_inside)))
    print('inside_great_rows=' + str(len(great_inside)))
    print('csv=' + str(out_csv.resolve()))
    print('summary=' + str(out_md.resolve()))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
'@

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($tmp, $code, $utf8NoBom)

python -m py_compile $tmp
if ($LASTEXITCODE -ne 0) { throw 'py_compile failed' }
python $tmp
if ($LASTEXITCODE -ne 0) { throw 'overlap report failed' }
Remove-Item -LiteralPath $tmp -Force

Write-Host '=== VERIFY OUTPUTS ==='
if (-not (Test-Path -LiteralPath (Join-Path $root 'reports/st_candidate_overlap_report_v1.csv'))) { throw 'Missing CSV output' }
if (-not (Test-Path -LiteralPath (Join-Path $root 'reports/st_candidate_overlap_summary_v1.md'))) { throw 'Missing summary output' }
Write-Host 'OK reports/st_candidate_overlap_report_v1.csv'
Write-Host 'OK reports/st_candidate_overlap_summary_v1.md'
Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE build_st_candidate_overlap_report_v1.ps1 ==='
