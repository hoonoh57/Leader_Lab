param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== BUILD ST Candidate Overlap Report v2 ==='

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

$tmp = Join-Path $root '.tmp_build_st_candidate_overlap_report_v2.py'
$code = @'
from __future__ import annotations
import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pymysql

TOLERANCE_BARS = 2
BAR_SECONDS = 300


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


def safe_int(v: Any) -> int:
    try:
        return int(v or 0)
    except Exception:
        return 0


def quality(seg: Dict[str, Any]) -> str:
    if safe_int(seg.get('label_st_gain_10pct')) == 1:
        return 'GREAT'
    if safe_int(seg.get('label_st_gain_5pct')) == 1:
        return 'GOOD'
    if safe_int(seg.get('label_st_fail_1pct')) == 1 or safe_int(seg.get('label_st_end_negative')) == 1:
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
    for i, row in enumerate(rows, 1):
        row['_candidate_no'] = i
        row['_candidate_date'] = candidate_date(row)
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
        rows = list(cur.fetchall())
    return rows


def bars_between(a: Optional[datetime], b: Optional[datetime]) -> Optional[int]:
    if a is None or b is None:
        return None
    return int((a - b).total_seconds() // BAR_SECONDS)


def score_match(candidate: Dict[str, Any], seg: Dict[str, Any]) -> Dict[str, Any]:
    cdate = candidate.get('_candidate_date') or ''
    entry_dt = parse_dt(cdate, candidate.get('entry_time_text'))
    start_dt = seg.get('st_up_start_time')
    end_dt = seg.get('st_up_end_time')
    inside = 0
    near = 0
    bars_from_start = bars_between(entry_dt, start_dt)
    bars_to_end = bars_between(end_dt, entry_dt)
    if entry_dt is not None and start_dt is not None and end_dt is not None:
        inside = 1 if start_dt <= entry_dt <= end_dt else 0
        near_start = abs((entry_dt - start_dt).total_seconds()) <= TOLERANCE_BARS * BAR_SECONDS
        near_inside = (start_dt <= entry_dt <= end_dt) or near_start
        near = 1 if near_inside else 0
    q = quality(seg)
    remain = pct(fnum(seg.get('st_up_max_price')), fnum(candidate.get('entry_price')))
    q_score = {'GREAT': 4, 'GOOD': 3, 'NEUTRAL': 2, 'BAD': 1}.get(q, 0)
    inside_score = 2 if inside == 1 else (1 if near == 1 else 0)
    remain_score = -999.0 if remain is None else remain
    rank_score = q_score * 1000.0 + inside_score * 100.0 + remain_score
    return {
        'segment_id': seg.get('id'),
        'segment_no': seg.get('segment_no'),
        'st_period': seg.get('st_period'),
        'st_multiplier': seg.get('st_multiplier'),
        'segment_quality': q,
        'inside_segment': inside,
        'near_or_inside_segment': near,
        'bars_from_st_start': bars_from_start,
        'bars_to_st_end': bars_to_end,
        'remain_to_max_pct': remain,
        'st_up_max_return_pct': seg.get('st_up_max_return_pct'),
        '_rank_score': rank_score,
    }


def summarize_actions(rows: List[Dict[str, Any]]) -> List[str]:
    actions = sorted(set(str(r.get('board_action')) for r in rows))
    out = []
    for a in actions:
        part = [r for r in rows if str(r.get('board_action')) == a]
        total = len(part)
        great = sum(1 for r in part if r.get('best_quality') == 'GREAT')
        good = sum(1 for r in part if r.get('best_quality') in ('GREAT','GOOD'))
        inside_good = sum(1 for r in part if r.get('inside_good_or_great') == 1)
        near_good = sum(1 for r in part if r.get('near_good_or_great') == 1)
        out.append(a + ': total=' + str(total) + ', best_great=' + str(great) + ', best_good_or_great=' + str(good) + ', inside_good_or_great=' + str(inside_good) + ', near_good_or_great=' + str(near_good))
    return out


def main() -> int:
    load_env('.env')
    out_dir = Path('reports')
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / 'st_candidate_overlap_candidate_level_v2.csv'
    out_md = out_dir / 'st_candidate_overlap_candidate_level_summary_v2.md'
    conn = open_conn()
    try:
        candidates = load_candidates(conn)
        segments = load_segments(conn)
    finally:
        conn.close()

    seg_index: Dict[str, List[Dict[str, Any]]] = {}
    for seg in segments:
        key = str(seg.get('code')) + '|' + dt_date(seg.get('trade_date'))
        seg_index.setdefault(key, []).append(seg)

    rows: List[Dict[str, Any]] = []
    for cand in candidates:
        key = str(cand.get('code')) + '|' + str(cand.get('_candidate_date') or '')
        candidates_segments = seg_index.get(key, [])
        matches = [score_match(cand, s) for s in candidates_segments]
        matches.sort(key=lambda x: float(x.get('_rank_score') or -999999.0), reverse=True)
        best = matches[0] if matches else {}
        best_quality = str(best.get('segment_quality') or 'NO_MATCH')
        row = {
            'candidate_no': cand.get('_candidate_no'),
            'code': cand.get('code'),
            'name': cand.get('name'),
            'candidate_date': cand.get('_candidate_date'),
            'board_action': cand.get('board_action_v2_8'),
            'entry_time_text': cand.get('entry_time_text'),
            'entry_price': cand.get('entry_price'),
            'tick_confirm_score': cand.get('tick_confirm_score_v2_6'),
            'tick_intensity': cand.get('tick_intensity_v2_6'),
            'buy_tick_ratio': cand.get('buy_tick_ratio_v2_6'),
            'hoga_bid_pressure': cand.get('hoga_bid_pressure_v2_6'),
            'hoga_ask_absorption': cand.get('hoga_ask_absorption_v2_6'),
            'spread_risk': cand.get('spread_risk_v2_6'),
            'matched_segment_count': len(matches),
            'best_segment_id': best.get('segment_id'),
            'best_segment_no': best.get('segment_no'),
            'best_st_period': best.get('st_period'),
            'best_st_multiplier': best.get('st_multiplier'),
            'best_quality': best_quality,
            'best_inside_segment': best.get('inside_segment', 0),
            'best_near_or_inside_segment': best.get('near_or_inside_segment', 0),
            'best_bars_from_st_start': best.get('bars_from_st_start'),
            'best_bars_to_st_end': best.get('bars_to_st_end'),
            'best_remain_to_max_pct': best.get('remain_to_max_pct'),
            'best_st_up_max_return_pct': best.get('st_up_max_return_pct'),
            'has_any_great_match': 1 if any(m.get('segment_quality') == 'GREAT' for m in matches) else 0,
            'has_any_good_or_great_match': 1 if any(m.get('segment_quality') in ('GREAT','GOOD') for m in matches) else 0,
            'inside_good_or_great': 1 if any(m.get('inside_segment') == 1 and m.get('segment_quality') in ('GREAT','GOOD') for m in matches) else 0,
            'near_good_or_great': 1 if any(m.get('near_or_inside_segment') == 1 and m.get('segment_quality') in ('GREAT','GOOD') for m in matches) else 0,
        }
        rows.append(row)

    fields = list(rows[0].keys()) if rows else []
    with out_csv.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    total = len(rows)
    best_great = sum(1 for r in rows if r.get('best_quality') == 'GREAT')
    best_good = sum(1 for r in rows if r.get('best_quality') in ('GREAT','GOOD'))
    any_great = sum(1 for r in rows if r.get('has_any_great_match') == 1)
    any_good = sum(1 for r in rows if r.get('has_any_good_or_great_match') == 1)
    inside_good = sum(1 for r in rows if r.get('inside_good_or_great') == 1)
    near_good = sum(1 for r in rows if r.get('near_good_or_great') == 1)
    lines = []
    lines.append('# ST Candidate Overlap Candidate-Level Summary v2')
    lines.append('')
    lines.append('This is not a perfect-rule report. It allows tolerance and keeps candidate-level ambiguity to reduce overfit pressure.')
    lines.append('')
    lines.append('total_candidates=' + str(total))
    lines.append('best_great_candidates=' + str(best_great))
    lines.append('best_good_or_great_candidates=' + str(best_good))
    lines.append('any_great_match_candidates=' + str(any_great))
    lines.append('any_good_or_great_match_candidates=' + str(any_good))
    lines.append('inside_good_or_great_candidates=' + str(inside_good))
    lines.append('near_good_or_great_candidates=' + str(near_good))
    lines.append('tolerance_bars=' + str(TOLERANCE_BARS))
    lines.append('')
    lines.append('## By action')
    lines.extend(summarize_actions(rows))
    lines.append('')
    lines.append('csv=reports/st_candidate_overlap_candidate_level_v2.csv')
    out_md.write_text('\n'.join(lines), encoding='utf-8')

    print('=== DONE build_st_candidate_overlap_report_v2 ===')
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
if ($LASTEXITCODE -ne 0) { throw 'candidate-level overlap report failed' }
Remove-Item -LiteralPath $tmp -Force

Write-Host '=== VERIFY OUTPUTS ==='
if (-not (Test-Path -LiteralPath (Join-Path $root 'reports/st_candidate_overlap_candidate_level_v2.csv'))) { throw 'Missing v2 CSV output' }
if (-not (Test-Path -LiteralPath (Join-Path $root 'reports/st_candidate_overlap_candidate_level_summary_v2.md'))) { throw 'Missing v2 summary output' }
Write-Host 'OK reports/st_candidate_overlap_candidate_level_v2.csv'
Write-Host 'OK reports/st_candidate_overlap_candidate_level_summary_v2.md'
Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE build_st_candidate_overlap_report_v2.ps1 ==='
