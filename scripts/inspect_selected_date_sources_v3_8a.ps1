param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== INSPECT Selected-Date Sources v3.8a ==='

$required = @(
    'START_HERE.md',
    'docs/workflow_server_editing_v1.md',
    'docs/powershell_script_rule_v1.md',
    'docs/pre_edit_reading_rule_v1.md',
    'docs/todo_update_rule_v1.md',
    'todo_list.md'
)
foreach ($rel in $required) {
    $p = Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p)) { throw ('Missing required file: ' + $rel) }
    Write-Host ('OK ' + $rel)
}

$tmp = Join-Path $root '.tmp_inspect_selected_date_sources_v3_8a.py'
$code = @'
from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict, List, Sequence
import pymysql

TABLES = [
    'performance_result',
    'performance_results',
    'daily_captures',
    'condition_backtest_detail',
    'condition_backtest_summary',
    'condition_master',
    'v_grade_performance',
    'supertrend_regime_segment',
]
DATE_NAMES = ['trade_date','search_date','capture_date','date','base_date','target_date','created_at','updated_at']
CODE_NAMES = ['code','ticker','stock_code','jongmok_code']
TIME_NAMES = ['search_time','capture_time','entry_time','entry_time_text','time']
RETURN_NAMES = ['max_profit','max_return','max_return_pct','expected_return_pct','profit','return_pct','hour7','min1','min3']


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


def ev(names: Sequence[str], default: str = '') -> str:
    for n in names:
        v = os.environ.get(n)
        if v is not None and v.strip() != '':
            return v.strip()
    return default


def conn() -> Any:
    db = ev(['DB_NAME','MYSQL_DATABASE','MYSQL_DB'])
    if not db:
        raise RuntimeError('DB_NAME is required')
    return pymysql.connect(host=ev(['DB_HOST','MYSQL_HOST'],'127.0.0.1'), port=int(ev(['DB_PORT','MYSQL_PORT'],'3306')), user=ev(['DB_USER','MYSQL_USER'],'root'), password=ev(['DB_PASS','DB_PASSWORD','MYSQL_PASSWORD'],''), database=db, charset='utf8mb4', autocommit=True, cursorclass=pymysql.cursors.DictCursor)


def fetch(c: Any, sql: str, args: Sequence[Any] = ()) -> List[Dict[str, Any]]:
    with c.cursor() as cur:
        cur.execute(sql, args)
        return list(cur.fetchall())


def exists(c: Any, table: str) -> bool:
    rows = fetch(c, 'SELECT COUNT(*) AS cnt FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s', (table,))
    return int(rows[0]['cnt']) > 0


def cols(c: Any, table: str) -> List[str]:
    rows = fetch(c, 'SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION', (table,))
    return [str(r['COLUMN_NAME']) for r in rows]


def count(c: Any, table: str) -> int:
    rows = fetch(c, 'SELECT COUNT(*) AS cnt FROM `' + table + '`')
    return int(rows[0]['cnt'])


def first_existing(cols_list: List[str], names: List[str]) -> str:
    for n in names:
        if n in cols_list:
            return n
    return ''


def print_dist(c: Any, table: str, col: str) -> None:
    print('--- distribution ' + table + '.' + col + ' ---')
    if col.endswith('_at'):
        sql = 'SELECT DATE(`' + col + '`) AS d, COUNT(*) AS cnt FROM `' + table + '` GROUP BY DATE(`' + col + '`) ORDER BY d DESC LIMIT 40'
    else:
        sql = 'SELECT `' + col + '` AS d, COUNT(*) AS cnt FROM `' + table + '` GROUP BY `' + col + '` ORDER BY d DESC LIMIT 40'
    for r in fetch(c, sql):
        print(str(r.get('d')) + '=' + str(r.get('cnt')))


def print_sample(c: Any, table: str, cols_list: List[str]) -> None:
    wanted = []
    for group in [DATE_NAMES, TIME_NAMES, CODE_NAMES, ['name','stock_name','condition_name','condition_id'], RETURN_NAMES]:
        for x in group:
            if x in cols_list and x not in wanted:
                wanted.append(x)
    if not wanted:
        wanted = cols_list[:12]
    print('--- sample ' + table + ' ---')
    sql = 'SELECT ' + ','.join(['`' + x + '`' for x in wanted[:24]]) + ' FROM `' + table + '` LIMIT 10'
    rows = fetch(c, sql)
    for i, r in enumerate(rows, 1):
        print('row' + str(i) + ' ' + ' | '.join([x + '=' + str(r.get(x)) for x in wanted[:24]]))


def main() -> int:
    load_env('.env')
    c = conn()
    try:
        print('schema=' + ev(['DB_NAME','MYSQL_DATABASE','MYSQL_DB']))
        for t in TABLES:
            print('\n=== TABLE ' + t + ' ===')
            if not exists(c, t):
                print('MISSING')
                continue
            cs = cols(c, t)
            print('row_count=' + str(count(c, t)))
            print('columns=' + ','.join(cs))
            date_col = first_existing(cs, DATE_NAMES)
            code_col = first_existing(cs, CODE_NAMES)
            time_col = first_existing(cs, TIME_NAMES)
            ret_col = first_existing(cs, RETURN_NAMES)
            print('detected_date_col=' + date_col)
            print('detected_time_col=' + time_col)
            print('detected_code_col=' + code_col)
            print('detected_return_col=' + ret_col)
            for d in DATE_NAMES:
                if d in cs:
                    print_dist(c, t, d)
            print_sample(c, t, cs)
        print('\n=== DECISION GUIDE ===')
        print('Use the table that has selected date, capture/search time, code, and performance labels as SELECTED_DATE source.')
        print('Do not use mixed-date top board as live recommendation.')
        print('Next target: build_selected_date_candidate_board_v3_8 using explicit selected_trade_date filter.')
        return 0
    finally:
        c.close()

if __name__ == '__main__':
    raise SystemExit(main())
'@

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($tmp, $code, $utf8NoBom)

python -m py_compile $tmp
if ($LASTEXITCODE -ne 0) { throw 'py_compile failed' }
python $tmp
if ($LASTEXITCODE -ne 0) { throw 'selected-date source inspection failed' }
Remove-Item -LiteralPath $tmp -Force

Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE inspect_selected_date_sources_v3_8a.ps1 ==='
