param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== BUILD ST Candidate Overlap Report v3 Causal ==='

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

$tmp = Join-Path $root '.tmp_build_st_candidate_overlap_report_v3_causal.py'
$code = @'
from __future__ import annotations
import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import pymysql

BAR_SECONDS = 300
TOLERANCE_BARS = 2


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


def i(v: Any) -> int:
    try:
        return int(v or 0)
    except Exception:
        return 0


def quality(seg: Dict[str, Any]) -> str:
    if i(seg.get('label_st_gain_10pct')) == 1:
        return 'GREAT'
    if i(seg.get('label_st_gain_5pct')) == 1:
        return 'GOOD'
    if i(seg.get('label_st_fail_1pct')) == 1 or i(seg.get('label_st_end_negative')) == 1:
        return 'BAD'
    return 'NEUTRAL'


def candidate_date(row: Dict[str, Any]) -> str:
    for k in ['trade_date','search_date','base_date','target_date']:
        if row.get(k) is not None:
            return dt_date(row.get(k))
    return dt_date(row.get('realtime_snapshot_time'))


def load_candidates(conn) -> List[Dict[str, Any]]:
    view_name = 'supertrend_top_candidate_board_dedup_view_v2_9'
    have = set(cols(conn, view_name))
    wanted = ['code','name','board_action_v2_8','entry_time_text','entry_price','tick_confirm_score_v2_6','tick_intensity_v2_6','buy_tick_ratio_v2_6','hoga_bid_pressure_v2_6','hoga_ask_absorption_v2_6','spread_risk_v2_6','realtime_snapshot_time','trade_date','search_date','final_rank_no_v2_8','dedup_final_rank_no_v2_9']
    use = [c for c in wanted if c in have]
    order = 'dedup_final_rank_no_v2_9' if 'dedup_final_rank_no_v2_9' in have else 'final_rank_no_v2_8'
    sql = 'SELECT ' + ','.join(use) + ' FROM ' + view_name
    if order in have:
        sql += ' ORDER BY ' + order + ' ASC'
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = list(cur.fetchall())
    for n, r in enumerate(rows, 1):
        r['_candidate_no'] = n
        r['_candidate_date'] = candidate_date(r)
    return rows


def load_segments(conn) -> List[Dict[str, Any]]:
    sql = '''
    SELECT id, trade_date, code, name, st_period, st_multiplier, segment_no,
           st_up_start_time, st_up_end_time, st_up_start_price, st_up_max_price,
           st_up_max_return_pct, label_st_gain_5pct, label_st_gain_10pct,
           label_st_fail_1pct, label_st_end_negative
    FROM supertrend_regime_segment
    '''
    with conn.cursor() as cur:
        cur.execute(sql)
        return list(cur.fetchall())


def abs_bars(a: Optional[datetime], b: Optional[datetime]) -> int:
    if a is None or b is None:
        return 999999
    return int(abs((a - b).total_seconds()) // BAR_SECONDS)


def signed_bars(a: Optional[datetime], b: Optional[datetime]) -> Optional[int]:
    if a is None or b is None:
        return None
    return int((a - b).total_seconds() // BAR_SECONDS)


def choose_causal_match(entry_dt: Optional[datetime], segs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if entry_dt is None or not segs:
        return None
    inside = [s for s in segs if s.get('st_up_start_time') is not None and s.get('st_up_end_time') is not None and s.get('st_up_start_time') <= entry_dt <= s.get('st_up_end_time')]
    if inside:
        inside.sort(key=lambda s: (abs_bars(entry_dt, s.get('st_up_start_time')), int(s.get('st_period') or 999), float(s.get('st_multiplier') or 999)))
        return inside[0]
    near = [s for s in segs if s.get('st_up_start_time') is not None and abs_bars(entry_dt, s.get('st_up_start_time')) <= TOLERANCE_BARS]
    if near:
        near.sort(key=lambda s: (abs_bars(entry_dt, s.get('st_up_start_time')), int(s.get('st_period') or 999), float(s.get('st_multiplier') or 999)))
        return near[0]
    before = [s for s in segs if s.get('st_up_start_time') is not None and s.get('st_up_start_time') > entry_dt]
    if before:
        before.sort(key=lambda s: (signed_bars(s.get('st_up_start_time'), entry_dt) or 999999, int(s.get('st_period') or 999), float(s.get('st_multiplier') or 999)))
        return before[0]
    after = [s for s in segs if s.get('st_up_end_time') is not None and s.get('st_up_end_time') < entry_dt]
    if after:
        after.sort(key=lambda s: (signed_bars(entry_dt, s.get('st_up_end_time')) or 999999, int(s.get('st_period') or 999), float(s.get('st_multiplier') or 999)))
        return after[0]
    return None


def summarize(rows: List[Dict[str, Any]]) -> List[str]:
    lines: List[str] = []
    actions = sorted(set(str(r.get('board_action')) for r in rows))
    for a in actions:
        part = [r for r in rows if str(r.get('board_action')) == a]
        total = len(part)
        great = sum(1 for r in part if r.get('causal_quality') == 'GREAT')
        good = sum(1 for r in part if r.get('causal_quality') in ('GREAT','GOOD'))
        inside = sum(1 for r in part if r.get('causal_inside_segment') == 1)
        near = sum(1 for r in part if r.get('causal_near_or_inside_segment') == 1)
        lines.append(a + ': total=' + str(total) + ', causal_great=' + str(great) + ', causal_good_or_great=' + str(good) + ', causal_inside=' + str(inside) + ', causal_near_or_inside=' + str(near))
    return lines


def main() -> int:
    load_env('.env')
    out_dir = Path('reports')
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / 'st_candidate_overlap_causal_v3.csv'
    out_md = out_dir / 'st_candidate_overlap_causal_summary_v3.md'
    conn = open_conn()
    try:
        candidates = load_candidates(conn)
        segments = load_segments(conn)
    finally:
        conn.close()

    idx: Dict[str, List[Dict[str, Any]]] = {}
    for s in segments:
        idx.setdefault(str(s.get('code')) + '|' + dt_date(s.get('trade_date')), []).append(s)

    rows: List[Dict[str, Any]] = []
    for c in candidates:
        cdate = str(c.get('_candidate_date') or '')
        entry_dt = parse_dt(cdate, c.get('entry_time_text'))
        segs = idx.get(str(c.get('code')) + '|' + cdate, [])
        seg = choose_causal_match(entry_dt, segs)
        q = 'NO_MATCH' if seg is None else quality(seg)
        start = None if seg is None else seg.get('st_up_start_time')
        end = None if seg is None else seg.get('st_up_end_time')
        inside = 0
        near = 0
        if entry_dt is not None and start is not None and end is not None:
            inside = 1 if start <= entry_dt <= end else 0
            near = 1 if inside == 1 or abs_bars(entry_dt, start) <= TOLERANCE_BARS else 0
        rows.append({
            'candidate_no': c.get('_candidate_no'),
            'code': c.get('code'),
            'name': c.get('name'),
            'candidate_date': cdate,
            'board_action': c.get('board_action_v2_8'),
            'entry_time_text': c.get('entry_time_text'),
            'entry_price': c.get('entry_price'),
            'tick_confirm_score': c.get('tick_confirm_score_v2_6'),
            'tick_intensity': c.get('tick_intensity_v2_6'),
            'buy_tick_ratio': c.get('buy_tick_ratio_v2_6'),
            'hoga_bid_pressure': c.get('hoga_bid_pressure_v2_6'),
            'hoga_ask_absorption': c.get('hoga_ask_absorption_v2_6'),
            'spread_risk': c.get('spread_risk_v2_6'),
            'candidate_segment_count': len(segs),
            'causal_segment_id': None if seg is None else seg.get('id'),
            'causal_segment_no': None if seg is None else seg.get('segment_no'),
            'causal_st_period': None if seg is None else seg.get('st_period'),
            'causal_st_multiplier': None if seg is None else seg.get('st_multiplier'),
            'causal_quality': q,
            'causal_inside_segment': inside,
            'causal_near_or_inside_segment': near,
            'causal_bars_from_st_start': signed_bars(entry_dt, start),
            'causal_bars_to_st_end': signed_bars(end, entry_dt),
            'causal_remain_to_max_pct': None if seg is None else pct(fnum(seg.get('st_up_max_price')), fnum(c.get('entry_price'))),
            'causal_st_up_max_return_pct': None if seg is None else seg.get('st_up_max_return_pct'),
        })

    fields = list(rows[0].keys()) if rows else []
    with out_csv.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    total = len(rows)
    causal_great = sum(1 for r in rows if r.get('causal_quality') == 'GREAT')
    causal_good = sum(1 for r in rows if r.get('causal_quality') in ('GREAT','GOOD'))
    causal_inside = sum(1 for r in rows if r.get('causal_inside_segment') == 1)
    causal_near = sum(1 for r in rows if r.get('causal_near_or_inside_segment') == 1)
    lines = []
    lines.append('# ST Candidate Overlap Causal Summary v3')
    lines.append('')
    lines.append('This report avoids selecting the best future-quality segment first.')
    lines.append('It chooses the time-causal nearest ST segment around the candidate entry time.')
    lines.append('')
    lines.append('total_candidates=' + str(total))
    lines.append('causal_great_candidates=' + str(causal_great))
    lines.append('causal_good_or_great_candidates=' + str(causal_good))
    lines.append('causal_inside_segment_candidates=' + str(causal_inside))
    lines.append('causal_near_or_inside_candidates=' + str(causal_near))
    lines.append('tolerance_bars=' + str(TOLERANCE_BARS))
    lines.append('')
    lines.append('## By action')
    lines.extend(summarize(rows))
    lines.append('')
    lines.append('csv=reports/st_candidate_overlap_causal_v3.csv')
    out_md.write_text('\n'.join(lines), encoding='utf-8')

    print('=== DONE build_st_candidate_overlap_report_v3_causal ===')
    for line in lines:
        if '=' in line or line.startswith('AUTO_') or line.startswith('WATCH_') or line.startswith('REJECT'):
            print(line)
    print('summary=' + str(out_md.resolve()))
    print('csv=' + str(out_csv.resolve()))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
'@

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($tmp, $code, $utf8NoBom)

python -m py_compile $tmp
if ($LASTEXITCODE -ne 0) { throw 'py_compile failed' }
python $tmp
if ($LASTEXITCODE -ne 0) { throw 'causal overlap report failed' }
Remove-Item -LiteralPath $tmp -Force

Write-Host '=== VERIFY OUTPUTS ==='
if (-not (Test-Path -LiteralPath (Join-Path $root 'reports/st_candidate_overlap_causal_v3.csv'))) { throw 'Missing v3 CSV output' }
if (-not (Test-Path -LiteralPath (Join-Path $root 'reports/st_candidate_overlap_causal_summary_v3.md'))) { throw 'Missing v3 summary output' }
Write-Host 'OK reports/st_candidate_overlap_causal_v3.csv'
Write-Host 'OK reports/st_candidate_overlap_causal_summary_v3.md'
Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE build_st_candidate_overlap_report_v3_causal.ps1 ==='
