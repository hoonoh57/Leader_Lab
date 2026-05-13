param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== AUDIT Existing v3 Test Logic v3.8c ==='

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

$tmp = Join-Path $root '.tmp_audit_existing_v3_test_logic_v3_8c.py'
$code = @'
from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict, List, Sequence
import pymysql

TARGET_TABLES = [
    'supertrend_realtime_entry_candidate_v2_0',
    'supertrend_realtime_entry_top_candidate_v2_1',
    'supertrend_realtime_trade_board_v2_2',
    'supertrend_realtime_trade_board_screen_v2_3',
    'supertrend_realtime_final_board_view_v2_8',
    'supertrend_top_candidate_board_raw_view_v2_9',
    'supertrend_top_candidate_board_dedup_view_v2_9',
    'supertrend_top_candidate_board_raw_view_v3_4',
    'supertrend_top_candidate_board_dedup_view_v3_4',
]

FUTURE_COLS = [
    'expected_return_pct',
    'mae_risk_pct',
    'max_ret_in_period',
    'actual_rank_by_max_ret',
    'ret_1m',
    'ret_3m',
    'ret_7h',
    'st_up_max_return_pct',
    'st_up_end_return_pct',
    'st_up_max_price',
    'st_up_end_price',
    'st_up_end_time',
    'label_st_gain_3pct',
    'label_st_gain_5pct',
    'label_st_gain_10pct',
    'label_st_fail_1pct',
    'label_st_end_negative',
]

CAUSAL_HINTS = [
    'source_rank_no_v2_6',
    'tick_confirm_score_v2_6',
    'tick_intensity_v2_6',
    'buy_tick_ratio_v2_6',
    'large_trade_amount_eok_v2_6',
    'hoga_bid_pressure_v2_6',
    'hoga_ask_absorption_v2_6',
    'spread_risk_v2_6',
    'start_cum_amount',
    'start_cum_amount_eok',
    'start_from_day_open_pct',
    'start_from_day_low_pct',
    'entry_time',
    'entry_price',
]


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


def print_sample(c: Any, table: str, cs: List[str]) -> None:
    wanted = []
    for x in ['final_rank_no_v2_8','dedup_final_rank_no_v2_9','dedup_final_rank_no_v3_4','source_rank_no_v2_6','board_action_v2_8','board_action_v3_4','trade_date','search_time','entry_time_text','code','name']:
        if x in cs:
            wanted.append(x)
    for x in CAUSAL_HINTS:
        if x in cs and x not in wanted:
            wanted.append(x)
    for x in FUTURE_COLS:
        if x in cs and x not in wanted:
            wanted.append(x)
    if not wanted:
        return
    sql = 'SELECT ' + ','.join(['`'+x+'`' for x in wanted[:36]]) + ' FROM `' + table + '` LIMIT 12'
    print('--- sample ' + table + ' ---')
    for i, r in enumerate(fetch(c, sql), 1):
        print('row' + str(i) + ' ' + ' | '.join([x + '=' + str(r.get(x)) for x in wanted[:36]]))


def static_file_audit() -> None:
    print('\n=== STATIC FILE AUDIT excluding selected_date answer scripts ===')
    files = []
    for base in ['scripts','src','docs','vbnet']:
        p = Path(base)
        if p.exists():
            for f in p.rglob('*'):
                if f.is_file() and f.suffix.lower() in ['.ps1','.py','.md','.vb','.sql']:
                    name = f.name.lower()
                    if 'selected_date' in name or 'v3_8' in name or 'lineage' in name or 'leakage' in name:
                        continue
                    low = str(f).lower().replace('\\','/')
                    if 'top_candidate' in low or 'supertrend_realtime' in low or 'candidate_board' in low or 'promotion' in low:
                        files.append(f)
    print('scan_file_count=' + str(len(files)))
    hit_count = 0
    rank_hit_count = 0
    for f in sorted(files):
        text = f.read_text(encoding='utf-8-sig', errors='replace')
        lines = text.splitlines()
        for idx, line in enumerate(lines):
            low = line.lower()
            for tok in FUTURE_COLS:
                if tok.lower() in low:
                    hit_count += 1
                    rankish = any(k in line.upper() for k in ['ORDER BY','ROW_NUMBER','FINAL_RANK','BOARD_ACTION','EXPECTED_RETURN','PROMOTE','WATCH','REJECT'])
                    if rankish:
                        rank_hit_count += 1
                        start = max(0, idx - 2)
                        end = min(len(lines), idx + 3)
                        print('--- STATIC_RANK_RISK token=' + tok + ' file=' + str(f) + ':' + str(idx+1) + ' ---')
                        for i in range(start, end):
                            print(str(i+1) + ': ' + lines[i].rstrip())
    print('static_forbidden_hits=' + str(hit_count))
    print('static_rank_risk_hits=' + str(rank_hit_count))


def main() -> int:
    load_env('.env')
    c = conn()
    try:
        print('schema=' + ev(['DB_NAME','MYSQL_DATABASE','MYSQL_DB']))
        print('\n=== TABLE COLUMN AUDIT ===')
        for t in TARGET_TABLES:
            print('\n--- table ' + t + ' ---')
            if not exists(c, t):
                print('MISSING')
                continue
            cs = cols(c, t)
            print('row_count=' + str(count(c, t)))
            present_future = [x for x in FUTURE_COLS if x in cs]
            present_causal = [x for x in CAUSAL_HINTS if x in cs]
            print('future_or_answer_columns_present=' + ','.join(present_future))
            print('causal_hint_columns_present=' + ','.join(present_causal))
            rank_cols = [x for x in cs if 'rank' in x.lower() or 'action' in x.lower() or 'score' in x.lower()]
            print('rank_action_score_columns=' + ','.join(rank_cols))
            print_sample(c, t, cs)
        static_file_audit()
        print('\n=== VERDICT GUIDE ===')
        print('If existing v2.9/v3.4 files rank by expected_return_pct or future/ST result columns, the existing test board is contaminated.')
        print('If tables contain future columns only for display but ranks/actions are based on causal columns, keep the logic and rename columns clearly.')
        print('If builder source is missing and only materialized tables exist, reconstruct a clean selected-date causal board from performance_result + causal ST/capture-time fields.')
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
if ($LASTEXITCODE -ne 0) { throw 'existing v3 logic audit failed' }
Remove-Item -LiteralPath $tmp -Force

Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE audit_existing_v3_test_logic_v3_8c.ps1 ==='
