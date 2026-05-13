param(
    [string]$TradeDate = '2026-04-30',
    [string]$ConditionName = '1516'
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== BUILD Selected-Date Candidate Board v3.8 ==='
Write-Host ('trade_date=' + $TradeDate)
Write-Host ('condition_name=' + $ConditionName)

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

$tmp = Join-Path $root '.tmp_build_selected_date_candidate_board_v3_8.py'
$code = @'
from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence
import pymysql

RAW = 'selected_date_candidate_board_raw_v3_8'
DEDUP = 'selected_date_candidate_board_dedup_v3_8'
SUMMARY = 'selected_date_candidate_board_summary_v3_8'


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
    return pymysql.connect(host=ev(['DB_HOST','MYSQL_HOST'],'127.0.0.1'), port=int(ev(['DB_PORT','MYSQL_PORT'],'3306')), user=ev(['DB_USER','MYSQL_USER'],'root'), password=ev(['DB_PASS','DB_PASSWORD','MYSQL_PASSWORD'],''), database=db, charset='utf8mb4', autocommit=False, cursorclass=pymysql.cursors.DictCursor)


def q(name: str) -> str:
    return '`' + name.replace('`', '``') + '`'


def execute(c: Any, sql: str, args: Sequence[Any] = ()) -> None:
    with c.cursor() as cur:
        cur.execute(sql, args)


def fetch(c: Any, sql: str, args: Sequence[Any] = ()) -> List[Dict[str, Any]]:
    with c.cursor() as cur:
        cur.execute(sql, args)
        return list(cur.fetchall())


def count(c: Any, table: str) -> int:
    rows = fetch(c, 'SELECT COUNT(*) AS cnt FROM ' + q(table))
    return int(rows[0]['cnt']) if rows else 0


def build(c: Any, trade_date: str, condition_name: str) -> None:
    execute(c, 'DROP TABLE IF EXISTS ' + q(RAW))
    execute(c, 'DROP TABLE IF EXISTS ' + q(DEDUP))
    execute(c, 'DROP TABLE IF EXISTS ' + q(SUMMARY))

    execute(c, f'''
CREATE TABLE {q(RAW)} AS
WITH perf AS (
    SELECT
        p.id AS performance_id,
        p.search_date,
        p.search_time,
        p.condition_name,
        p.code,
        p.name,
        p.ret_1m,
        p.ret_3m,
        p.ret_7h,
        p.max_ret_in_period,
        p.search_volume,
        p.label_3,
        p.label_5,
        p.label_10,
        p.actual_rank_by_max_ret
    FROM performance_result p
    WHERE p.search_date = %s
      AND p.condition_name = %s
), seg AS (
    SELECT
        s.*,
        ROW_NUMBER() OVER (
            PARTITION BY s.trade_date, s.search_time, s.code
            ORDER BY
                CASE WHEN s.label_st_gain_10pct = 1 THEN 1
                     WHEN s.label_st_gain_5pct = 1 THEN 2
                     WHEN s.label_st_gain_3pct = 1 THEN 3
                     WHEN s.label_st_end_negative = 1 OR s.label_st_fail_1pct = 1 THEN 9
                     ELSE 5 END ASC,
                s.st_up_max_return_pct DESC,
                s.st_up_bars DESC,
                s.st_period ASC,
                s.st_multiplier ASC,
                s.segment_no ASC
        ) AS seg_pick_rank
    FROM supertrend_regime_segment s
    WHERE s.trade_date = %s
)
SELECT
    ROW_NUMBER() OVER (
        ORDER BY
            COALESCE(s.st_up_max_return_pct, -999) DESC,
            COALESCE(p.max_ret_in_period, -999) DESC,
            p.code ASC
    ) AS selected_date_rank_v3_8,
    %s AS board_type_v3_8,
    p.search_date AS selected_trade_date_v3_8,
    p.condition_name AS source_condition_name_v3_8,
    p.performance_id,
    p.search_time,
    p.code,
    p.name,
    p.ret_1m,
    p.ret_3m,
    p.ret_7h,
    p.max_ret_in_period,
    p.search_volume,
    p.label_3,
    p.label_5,
    p.label_10,
    p.actual_rank_by_max_ret,
    s.id AS st_segment_id,
    s.timeframe,
    s.st_period,
    s.st_multiplier,
    s.segment_no,
    s.capture_time,
    s.already_up_at_capture,
    s.st_up_start_time,
    s.st_up_end_time,
    s.st_up_bars,
    s.st_up_start_price,
    s.st_up_max_price,
    s.st_up_end_price,
    s.st_up_min_price,
    s.st_up_max_return_pct,
    s.st_up_end_return_pct,
    s.st_up_max_drawdown_pct,
    s.start_from_day_open_pct,
    s.start_from_day_low_pct,
    s.start_cum_amount,
    s.start_cum_volume,
    s.segment_amount,
    s.segment_volume,
    s.segment_avg_amount_per_bar,
    s.segment_max_singlebar_return_pct,
    s.label_st_gain_3pct,
    s.label_st_gain_5pct,
    s.label_st_gain_10pct,
    s.label_st_fail_1pct,
    s.label_st_end_negative,
    CASE
        WHEN s.label_st_gain_10pct = 1 THEN 'GREAT'
        WHEN s.label_st_gain_5pct = 1 THEN 'GOOD'
        WHEN s.label_st_gain_3pct = 1 THEN 'WATCH'
        WHEN s.label_st_end_negative = 1 OR s.label_st_fail_1pct = 1 THEN 'BAD'
        ELSE 'NEUTRAL'
    END AS st_quality_v3_8,
    CASE
        WHEN s.id IS NULL THEN 'NO_ST_MATCH'
        WHEN s.label_st_gain_10pct = 1 THEN 'TOP_REVIEW_GREAT'
        WHEN s.label_st_gain_5pct = 1 THEN 'TOP_REVIEW_GOOD'
        WHEN s.label_st_gain_3pct = 1 THEN 'WATCH_ST_3PCT'
        WHEN s.label_st_end_negative = 1 OR s.label_st_fail_1pct = 1 THEN 'REJECT_BAD_ST'
        ELSE 'WATCH_NEUTRAL'
    END AS selected_date_action_v3_8,
    CURRENT_TIMESTAMP AS generated_at_v3_8
FROM perf p
LEFT JOIN seg s
  ON s.trade_date = p.search_date
 AND s.search_time = p.search_time
 AND s.code = p.code
 AND s.seg_pick_rank = 1
ORDER BY selected_date_rank_v3_8 ASC
''', (trade_date, condition_name, trade_date, 'SELECTED_DATE_COMPACT_V3_8'))

    execute(c, f'ALTER TABLE {q(RAW)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci')
    execute(c, f'ALTER TABLE {q(RAW)} ADD KEY ix_v38_raw_date_action (selected_trade_date_v3_8, selected_date_action_v3_8)')
    execute(c, f'ALTER TABLE {q(RAW)} ADD KEY ix_v38_raw_code (code)')

    execute(c, f'''
CREATE TABLE {q(DEDUP)} AS
SELECT * FROM {q(RAW)}
ORDER BY selected_date_rank_v3_8 ASC
''')
    execute(c, f'ALTER TABLE {q(DEDUP)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci')
    execute(c, f'ALTER TABLE {q(DEDUP)} ADD KEY ix_v38_dedup_rank (selected_date_rank_v3_8)')

    execute(c, f'''
CREATE TABLE {q(SUMMARY)} AS
SELECT
    board_type_v3_8,
    selected_trade_date_v3_8,
    source_condition_name_v3_8,
    COUNT(*) AS universe_count,
    SUM(CASE WHEN st_segment_id IS NOT NULL THEN 1 ELSE 0 END) AS st_matched_count,
    SUM(CASE WHEN selected_date_action_v3_8 IN ('TOP_REVIEW_GREAT','TOP_REVIEW_GOOD','WATCH_ST_3PCT') THEN 1 ELSE 0 END) AS review_candidate_count,
    SUM(CASE WHEN selected_date_action_v3_8 = 'TOP_REVIEW_GREAT' THEN 1 ELSE 0 END) AS great_count,
    SUM(CASE WHEN selected_date_action_v3_8 = 'TOP_REVIEW_GOOD' THEN 1 ELSE 0 END) AS good_count,
    SUM(CASE WHEN selected_date_action_v3_8 = 'WATCH_ST_3PCT' THEN 1 ELSE 0 END) AS watch_count,
    SUM(CASE WHEN selected_date_action_v3_8 = 'REJECT_BAD_ST' THEN 1 ELSE 0 END) AS bad_count,
    AVG(st_up_max_return_pct) AS avg_st_up_max_return_pct,
    MAX(st_up_max_return_pct) AS max_st_up_max_return_pct,
    CURRENT_TIMESTAMP AS generated_at_v3_8
FROM {q(RAW)}
GROUP BY board_type_v3_8, selected_trade_date_v3_8, source_condition_name_v3_8
''')
    execute(c, f'ALTER TABLE {q(SUMMARY)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci')


def main() -> int:
    if len(sys.argv) < 3:
        print('usage: script.py TRADE_DATE CONDITION_NAME')
        return 2
    trade_date = sys.argv[1]
    condition_name = sys.argv[2]
    load_env('.env')
    c = conn()
    try:
        build(c, trade_date, condition_name)
        c.commit()
        print('=== DONE build_selected_date_candidate_board_v3_8 ===')
        print('raw_rows=' + str(count(c, RAW)))
        print('dedup_rows=' + str(count(c, DEDUP)))
        print('summary_rows=' + str(count(c, SUMMARY)))
        rows = fetch(c, 'SELECT * FROM ' + q(SUMMARY))
        print('=== SUMMARY ===')
        for r in rows:
            print(dict(r))
        preview = fetch(c, 'SELECT selected_date_rank_v3_8, selected_trade_date_v3_8, search_time, code, name, selected_date_action_v3_8, st_quality_v3_8, max_ret_in_period, st_up_max_return_pct, st_up_start_time, st_up_end_time, st_up_bars, actual_rank_by_max_ret FROM ' + q(DEDUP) + ' ORDER BY selected_date_rank_v3_8 ASC LIMIT 30')
        print('=== PREVIEW ===')
        for r in preview:
            print(dict(r))
        return 0
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()

if __name__ == '__main__':
    raise SystemExit(main())
'@

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($tmp, $code, $utf8NoBom)

python -m py_compile $tmp
if ($LASTEXITCODE -ne 0) { throw 'py_compile failed' }
python $tmp $TradeDate $ConditionName
if ($LASTEXITCODE -ne 0) { throw 'selected-date board build failed' }
Remove-Item -LiteralPath $tmp -Force

Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE build_selected_date_candidate_board_v3_8.ps1 ==='
