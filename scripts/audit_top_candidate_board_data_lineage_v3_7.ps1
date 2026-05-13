param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== AUDIT Top Candidate Board Data Lineage v3.7 ==='

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

$tmp = Join-Path $root '.tmp_audit_top_candidate_board_data_lineage_v3_7.py'
$code = @'
from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict, List
import pymysql

TABLES = [
    'supertrend_top_candidate_board_raw_view_v2_9',
    'supertrend_top_candidate_board_dedup_view_v2_9',
    'supertrend_top_candidate_board_raw_view_v3_4',
    'supertrend_top_candidate_board_dedup_view_v3_4',
    'supertrend_top_candidate_board_summary_v3_4',
]
DATE_CANDIDATES = ['trade_date','search_date','target_date','base_date','capture_date','candidate_date','realtime_snapshot_time','created_at','promotion_created_at_v3_4']
ACTION_CANDIDATES = ['board_action_v3_4','board_action_v2_8']
SOURCE_PATTERNS = ['performance','1516','condition','capture','candidate','supertrend_top','regime','board']


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


def conn():
    db = ev(['DB_NAME','MYSQL_DATABASE','MYSQL_DB'])
    if not db:
        raise RuntimeError('DB_NAME is required')
    return pymysql.connect(host=ev(['DB_HOST','MYSQL_HOST'],'127.0.0.1'), port=int(ev(['DB_PORT','MYSQL_PORT'],'3306')), user=ev(['DB_USER','MYSQL_USER'],'root'), password=ev(['DB_PASS','DB_PASSWORD','MYSQL_PASSWORD'],''), database=db, charset='utf8mb4', autocommit=True, cursorclass=pymysql.cursors.DictCursor)


def fetch(c, sql, args=None):
    with c.cursor() as cur:
        cur.execute(sql, args or ())
        return list(cur.fetchall())


def columns(c, table):
    rows = fetch(c, 'SELECT COLUMN_NAME, DATA_TYPE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION', (table,))
    return [(str(r['COLUMN_NAME']), str(r['DATA_TYPE'])) for r in rows]


def table_exists(c, table):
    rows = fetch(c, 'SELECT COUNT(*) AS cnt FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s', (table,))
    return int(rows[0]['cnt']) > 0


def count(c, table):
    rows = fetch(c, 'SELECT COUNT(*) AS cnt FROM `' + table + '`')
    return int(rows[0]['cnt'])


def print_date_distribution(c, table, col):
    print('--- date_distribution ' + table + '.' + col + ' ---')
    if col == 'realtime_snapshot_time' or col.endswith('_at'):
        sql = 'SELECT DATE(`' + col + '`) AS d, COUNT(*) AS cnt FROM `' + table + '` GROUP BY DATE(`' + col + '`) ORDER BY d DESC LIMIT 30'
    else:
        sql = 'SELECT `' + col + '` AS d, COUNT(*) AS cnt FROM `' + table + '` GROUP BY `' + col + '` ORDER BY d DESC LIMIT 30'
    rows = fetch(c, sql)
    for r in rows:
        print(str(r.get('d')) + '=' + str(r.get('cnt')))


def print_action_distribution(c, table, col):
    print('--- action_distribution ' + table + '.' + col + ' ---')
    rows = fetch(c, 'SELECT `' + col + '` AS action_name, COUNT(*) AS cnt FROM `' + table + '` GROUP BY `' + col + '` ORDER BY cnt DESC')
    for r in rows:
        print(str(r.get('action_name')) + '=' + str(r.get('cnt')))


def print_sample(c, table, cols):
    preferred = [x for x in ['trade_date','search_date','base_date','target_date','realtime_snapshot_time','promotion_created_at_v3_4','code','name','entry_time_text','entry_price','board_action_v2_8','board_action_v3_4','final_rank_no_v2_8','dedup_final_rank_no_v3_4'] if x in cols]
    if not preferred:
        return
    print('--- sample ' + table + ' ---')
    rows = fetch(c, 'SELECT ' + ','.join(['`'+x+'`' for x in preferred]) + ' FROM `' + table + '` LIMIT 10')
    for i, r in enumerate(rows, 1):
        print('row' + str(i) + ' ' + ' | '.join([x + '=' + str(r.get(x)) for x in preferred]))


def inspect_related_tables(c):
    print('=== RELATED TABLE SEARCH ===')
    like_sql = []
    args = []
    for p in SOURCE_PATTERNS:
        like_sql.append('LOWER(TABLE_NAME) LIKE %s')
        args.append('%' + p.lower() + '%')
    rows = fetch(c, 'SELECT TABLE_NAME, TABLE_TYPE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND (' + ' OR '.join(like_sql) + ') ORDER BY TABLE_NAME', tuple(args))
    for r in rows:
        print(str(r['TABLE_NAME']) + ' / ' + str(r['TABLE_TYPE']))


def main():
    load_env('.env')
    c = conn()
    try:
        print('schema=' + str(ev(['DB_NAME','MYSQL_DATABASE','MYSQL_DB'])))
        inspect_related_tables(c)
        for t in TABLES:
            print('\n=== TABLE ' + t + ' ===')
            if not table_exists(c, t):
                print('MISSING')
                continue
            cols_pairs = columns(c, t)
            cols = [x[0] for x in cols_pairs]
            print('row_count=' + str(count(c, t)))
            print('columns=' + ','.join(cols))
            for dc in DATE_CANDIDATES:
                if dc in cols:
                    print_date_distribution(c, t, dc)
            for ac in ACTION_CANDIDATES:
                if ac in cols:
                    print_action_distribution(c, t, ac)
            print_sample(c, t, cols)
        print('\n=== INTERPRETATION GUIDE ===')
        print('If trade_date/search_date is missing or mixed, this board is not a selected-day recommendation board.')
        print('If all rows have an old date or only realtime_snapshot_time build date, this is a stored research board, not today live recommendation.')
        print('A valid daily recommendation board must include selected_trade_date and source performance/candidate capture date filters.')
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
if ($LASTEXITCODE -ne 0) { throw 'data lineage audit failed' }
Remove-Item -LiteralPath $tmp -Force

Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE audit_top_candidate_board_data_lineage_v3_7.ps1 ==='
