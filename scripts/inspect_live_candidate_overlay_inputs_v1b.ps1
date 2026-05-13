param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== INSPECT Live Candidate Overlay Inputs v1b ==='

$required = @(
    'START_HERE.md',
    'docs/workflow_server_editing_v1.md',
    'docs/powershell_script_rule_v1.md',
    'docs/pre_edit_reading_rule_v1.md',
    'docs/todo_update_rule_v1.md',
    'docs/st_dashboard_live_overlay_research_v1.md',
    'docs/live_candidate_overlay_on_st_dashboard_v1.md',
    'docs/top_candidate_board_contract_v3_0.md',
    'todo_list.md'
)

foreach ($rel in $required) {
    $p = Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p)) {
        throw ('Missing required file: ' + $rel)
    }
    Write-Host ('OK ' + $rel)
}

$tmp = Join-Path $root '.tmp_inspect_live_overlay_inputs_v1b.py'
$code = @'
from __future__ import annotations
import os
from pathlib import Path
import pymysql

def load_env(path):
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
    if db is None:
        raise RuntimeError('DB_NAME is required')
    return pymysql.connect(host=ev(['DB_HOST','MYSQL_HOST'],'127.0.0.1'), port=int(ev(['DB_PORT','MYSQL_PORT'],'3306')), user=ev(['DB_USER','MYSQL_USER'],'root'), password=ev(['DB_PASS','DB_PASSWORD','MYSQL_PASSWORD'],''), database=db, charset='utf8mb4', autocommit=True, cursorclass=pymysql.cursors.DictCursor)

def cols(c, schema, name):
    with c.cursor() as cur:
        cur.execute('SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION', (schema, name))
        return [str(r['COLUMN_NAME']) for r in cur.fetchall()]

def count(c, name):
    with c.cursor() as cur:
        cur.execute('SELECT COUNT(*) AS cnt FROM ' + name)
        return int(cur.fetchone()['cnt'])

def check(title, have, need):
    print('\n=== ' + title + ' ===')
    s = set(have)
    miss = []
    for n in need:
        if n in s:
            print('OK ' + n)
        else:
            print('MISS ' + n)
            miss.append(n)
    print('missing_count=' + str(len(miss)))

def actions(c, view, have):
    if 'board_action_v2_8' not in set(have):
        print('NO_ACTION_COLUMN ' + view)
        return
    print('\n=== action counts ' + view + ' ===')
    with c.cursor() as cur:
        cur.execute('SELECT board_action_v2_8 AS action_name, COUNT(*) AS cnt FROM ' + view + ' GROUP BY board_action_v2_8 ORDER BY cnt DESC')
        for r in cur.fetchall():
            print(str(r['action_name']) + '=' + str(r['cnt']))

def sample(c, view, have):
    wanted = ['code','name','board_action_v2_8','entry_time_text','entry_price','tick_confirm_score_v2_6','tick_intensity_v2_6','buy_tick_ratio_v2_6','hoga_bid_pressure_v2_6','hoga_ask_absorption_v2_6','spread_risk_v2_6','realtime_snapshot_time']
    use = [x for x in wanted if x in set(have)]
    print('\n=== sample ' + view + ' ===')
    if not use:
        print('NO_SAMPLE_COLUMNS')
        return
    with c.cursor() as cur:
        cur.execute('SELECT ' + ','.join(use) + ' FROM ' + view + ' LIMIT 5')
        rows = cur.fetchall()
    for i, r in enumerate(rows, 1):
        print('row' + str(i) + ' ' + ' | '.join([x + '=' + str(r.get(x)) for x in use]))

load_env('.env')
schema = ev(['DB_NAME','MYSQL_DATABASE','MYSQL_DB'])
raw = 'supertrend_top_candidate_board_raw_view_v2_9'
dedup = 'supertrend_top_candidate_board_dedup_view_v2_9'
seg = 'supertrend_regime_segment'
need_overlay = ['code','name','board_action_v2_8','entry_time_text','entry_price','tick_confirm_score_v2_6','tick_intensity_v2_6','buy_tick_ratio_v2_6','hoga_bid_pressure_v2_6','hoga_ask_absorption_v2_6','spread_risk_v2_6','realtime_snapshot_time']
need_seg = ['code','name','st_period','st_multiplier','st_up_start_time','st_up_end_time','st_up_max_return_pct','label_st_gain_5pct','label_st_gain_10pct']
with conn() as c:
    print('schema=' + str(schema))
    rc = cols(c, schema, raw)
    dc = cols(c, schema, dedup)
    sc = cols(c, schema, seg)
    print('row_count_raw=' + str(count(c, raw)))
    print('row_count_dedup=' + str(count(c, dedup)))
    print('row_count_segment=' + str(count(c, seg)))
    check('RAW overlay columns', rc, need_overlay)
    check('DEDUP overlay columns', dc, need_overlay)
    check('ST reference columns', sc, need_seg)
    actions(c, raw, rc)
    actions(c, dedup, dc)
    sample(c, raw, rc)
    sample(c, dedup, dc)
print('\n=== conclusion ===')
print('Keep ST dashboard reference metrics.')
print('Overlay Top Candidate Board v2.9 live candidate markers on the same chart.')
'@

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($tmp, $code, $utf8NoBom)

python -m py_compile $tmp
if ($LASTEXITCODE -ne 0) {
    throw 'py_compile failed'
}

python $tmp
if ($LASTEXITCODE -ne 0) {
    throw 'overlay input inspection failed'
}

Remove-Item -LiteralPath $tmp -Force

Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE inspect_live_candidate_overlay_inputs_v1b.ps1 ==='
