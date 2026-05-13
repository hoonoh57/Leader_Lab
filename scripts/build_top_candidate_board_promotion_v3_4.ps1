param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== BUILD Top Candidate Board Promotion v3.4 ==='

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
    if (-not (Test-Path -LiteralPath $p)) { throw ('Missing required file: ' + $rel) }
    Write-Host ('OK ' + $rel)
}

$tmp = Join-Path $root '.tmp_build_top_candidate_board_promotion_v3_4.py'
$code = @'
from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
import pymysql

RAW29 = 'supertrend_top_candidate_board_raw_view_v2_9'
DEDUP29 = 'supertrend_top_candidate_board_dedup_view_v2_9'
RAW34 = 'supertrend_top_candidate_board_raw_view_v3_4'
DEDUP34 = 'supertrend_top_candidate_board_dedup_view_v3_4'
SUMMARY34 = 'supertrend_top_candidate_board_summary_v3_4'
EXAMPLES34 = 'supertrend_top_candidate_board_examples_v3_4'

TICK_MIN = 30.0
SPREAD_MAX = 35.0
BUY_MIN = 60.0
BID_MIN = 55.0
ASK_MIN = 55.0


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


def ev(names: Sequence[str], default: Optional[str] = None) -> Optional[str]:
    for n in names:
        v = os.environ.get(n)
        if v is not None and v.strip() != '':
            return v.strip()
    return default


def open_conn() -> Any:
    db = ev(['DB_NAME','MYSQL_DATABASE','MYSQL_DB'])
    if db is None:
        raise RuntimeError('DB_NAME is required')
    return pymysql.connect(host=ev(['DB_HOST','MYSQL_HOST'],'127.0.0.1'), port=int(ev(['DB_PORT','MYSQL_PORT'],'3306')), user=ev(['DB_USER','MYSQL_USER'],'root'), password=ev(['DB_PASS','DB_PASSWORD','MYSQL_PASSWORD'],''), database=db, charset='utf8mb4', autocommit=False, cursorclass=pymysql.cursors.DictCursor)


def q(name: str) -> str:
    return '`' + name.replace('`', '``') + '`'


def execute(conn: Any, sql: str) -> None:
    with conn.cursor() as cur:
        cur.execute(sql)


def fetch(conn: Any, sql: str) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(sql)
        return list(cur.fetchall())


def table_exists(conn: Any, name: str) -> bool:
    rows = fetch(conn, 'SELECT COUNT(*) AS cnt FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s' % repr(name))
    return bool(rows and int(rows[0].get('cnt', 0)) > 0)


def count(conn: Any, table: str, where_sql: str = '') -> int:
    sql = 'SELECT COUNT(*) AS cnt FROM ' + q(table)
    if where_sql:
        sql += ' WHERE ' + where_sql
    rows = fetch(conn, sql)
    return int(rows[0].get('cnt', 0)) if rows else 0


def build_raw(conn: Any) -> None:
    execute(conn, 'DROP TABLE IF EXISTS ' + q(RAW34))
    execute(conn, f'''
CREATE TABLE {q(RAW34)} AS
SELECT
    r.*,
    CASE
        WHEN r.board_action_v2_8 = 'REJECT'
         AND COALESCE(r.tick_confirm_score_v2_6, 0) >= {TICK_MIN}
         AND COALESCE(r.spread_risk_v2_6, 999999) <= {SPREAD_MAX}
         AND COALESCE(r.buy_tick_ratio_v2_6, 0) >= {BUY_MIN}
         AND COALESCE(r.hoga_bid_pressure_v2_6, 0) >= {BID_MIN}
         AND COALESCE(r.hoga_ask_absorption_v2_6, 0) >= {ASK_MIN}
        THEN 1 ELSE 0 END AS promote_reject_to_watch_flag_v3_4,
    CASE
        WHEN r.board_action_v2_8 = 'REJECT'
         AND COALESCE(r.tick_confirm_score_v2_6, 0) >= {TICK_MIN}
         AND COALESCE(r.spread_risk_v2_6, 999999) <= {SPREAD_MAX}
         AND COALESCE(r.buy_tick_ratio_v2_6, 0) >= {BUY_MIN}
         AND COALESCE(r.hoga_bid_pressure_v2_6, 0) >= {BID_MIN}
         AND COALESCE(r.hoga_ask_absorption_v2_6, 0) >= {ASK_MIN}
        THEN 'PROMOTE_REJECT_TO_WATCH'
        ELSE r.board_action_v2_8
    END AS board_action_v3_4,
    CASE
        WHEN r.board_action_v2_8 = 'AUTO_BUY_READY' THEN 1
        WHEN r.board_action_v2_8 = 'WATCH_HOGA_TICK' THEN 2
        WHEN r.board_action_v2_8 = 'REJECT'
         AND COALESCE(r.tick_confirm_score_v2_6, 0) >= {TICK_MIN}
         AND COALESCE(r.spread_risk_v2_6, 999999) <= {SPREAD_MAX}
         AND COALESCE(r.buy_tick_ratio_v2_6, 0) >= {BUY_MIN}
         AND COALESCE(r.hoga_bid_pressure_v2_6, 0) >= {BID_MIN}
         AND COALESCE(r.hoga_ask_absorption_v2_6, 0) >= {ASK_MIN}
        THEN 3
        ELSE 4
    END AS board_action_order_v3_4,
    CASE
        WHEN r.board_action_v2_8 = 'REJECT'
         AND COALESCE(r.tick_confirm_score_v2_6, 0) >= {TICK_MIN}
         AND COALESCE(r.spread_risk_v2_6, 999999) <= {SPREAD_MAX}
         AND COALESCE(r.buy_tick_ratio_v2_6, 0) >= {BUY_MIN}
         AND COALESCE(r.hoga_bid_pressure_v2_6, 0) >= {BID_MIN}
         AND COALESCE(r.hoga_ask_absorption_v2_6, 0) >= {ASK_MIN}
        THEN CONCAT('PROMOTE gate: tick>=30 spread<=35 buy>=60 bid>=55 askAbsorb>=55; original=', r.board_action_v2_8)
        ELSE CONCAT('KEEP original action=', r.board_action_v2_8)
    END AS promotion_reason_v3_4,
    CASE WHEN r.board_action_v2_8 = 'AUTO_BUY_READY' THEN 1 ELSE 0 END AS ui_auto_buy_only_flag_v3_4,
    CASE WHEN r.board_action_v2_8 = 'WATCH_HOGA_TICK' THEN 1 ELSE 0 END AS ui_watch_only_flag_v3_4,
    CASE WHEN r.board_action_v2_8 = 'REJECT'
         AND COALESCE(r.tick_confirm_score_v2_6, 0) >= {TICK_MIN}
         AND COALESCE(r.spread_risk_v2_6, 999999) <= {SPREAD_MAX}
         AND COALESCE(r.buy_tick_ratio_v2_6, 0) >= {BUY_MIN}
         AND COALESCE(r.hoga_bid_pressure_v2_6, 0) >= {BID_MIN}
         AND COALESCE(r.hoga_ask_absorption_v2_6, 0) >= {ASK_MIN}
         THEN 1 ELSE 0 END AS ui_promoted_watch_flag_v3_4,
    CASE WHEN r.board_action_v2_8 = 'REJECT'
         AND NOT (
             COALESCE(r.tick_confirm_score_v2_6, 0) >= {TICK_MIN}
             AND COALESCE(r.spread_risk_v2_6, 999999) <= {SPREAD_MAX}
             AND COALESCE(r.buy_tick_ratio_v2_6, 0) >= {BUY_MIN}
             AND COALESCE(r.hoga_bid_pressure_v2_6, 0) >= {BID_MIN}
             AND COALESCE(r.hoga_ask_absorption_v2_6, 0) >= {ASK_MIN}
         ) THEN 1 ELSE 0 END AS ui_reject_only_flag_v3_4,
    CASE WHEN r.board_action_v2_8 IN ('AUTO_BUY_READY','WATCH_HOGA_TICK')
           OR (
             r.board_action_v2_8 = 'REJECT'
             AND COALESCE(r.tick_confirm_score_v2_6, 0) >= {TICK_MIN}
             AND COALESCE(r.spread_risk_v2_6, 999999) <= {SPREAD_MAX}
             AND COALESCE(r.buy_tick_ratio_v2_6, 0) >= {BUY_MIN}
             AND COALESCE(r.hoga_bid_pressure_v2_6, 0) >= {BID_MIN}
             AND COALESCE(r.hoga_ask_absorption_v2_6, 0) >= {ASK_MIN}
           ) THEN 1 ELSE 0 END AS ui_live_compact_flag_v3_4,
    1 AS ui_test_all_flag_v3_4,
    CURRENT_TIMESTAMP AS promotion_created_at_v3_4
FROM {q(RAW29)} r
ORDER BY board_action_order_v3_4 ASC, r.tick_confirm_score_v2_6 DESC, r.final_rank_no_v2_8 ASC
''')
    execute(conn, f'ALTER TABLE {q(RAW34)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci')
    execute(conn, f'ALTER TABLE {q(RAW34)} ADD KEY ix_v34_raw_action (board_action_v3_4, board_action_order_v3_4)')
    execute(conn, f'ALTER TABLE {q(RAW34)} ADD KEY ix_v34_raw_code (code)')
    execute(conn, f'ALTER TABLE {q(RAW34)} ADD KEY ix_v34_raw_flags (ui_live_compact_flag_v3_4, ui_promoted_watch_flag_v3_4, ui_reject_only_flag_v3_4)')


def build_dedup(conn: Any) -> None:
    execute(conn, 'DROP TABLE IF EXISTS ' + q(DEDUP34))
    execute(conn, f'''
CREATE TABLE {q(DEDUP34)} AS
WITH ranked AS (
    SELECT
        ROW_NUMBER() OVER (
            PARTITION BY r.code
            ORDER BY r.board_action_order_v3_4 ASC, r.tick_confirm_score_v2_6 DESC, r.expected_return_pct DESC, r.final_rank_no_v2_8 ASC
        ) AS code_dedup_rank_v3_4,
        r.*
    FROM {q(RAW34)} r
), kept AS (
    SELECT * FROM ranked WHERE code_dedup_rank_v3_4 = 1
), final_ranked AS (
    SELECT
        ROW_NUMBER() OVER (ORDER BY board_action_order_v3_4 ASC, tick_confirm_score_v2_6 DESC, expected_return_pct DESC, final_rank_no_v2_8 ASC) AS dedup_final_rank_no_v3_4,
        ROW_NUMBER() OVER (PARTITION BY board_action_v3_4 ORDER BY tick_confirm_score_v2_6 DESC, expected_return_pct DESC, final_rank_no_v2_8 ASC) AS dedup_action_rank_no_v3_4,
        k.*
    FROM kept k
)
SELECT * FROM final_ranked
ORDER BY dedup_final_rank_no_v3_4 ASC
''')
    execute(conn, f'ALTER TABLE {q(DEDUP34)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci')
    execute(conn, f'ALTER TABLE {q(DEDUP34)} ADD KEY ix_v34_dedup_rank (dedup_final_rank_no_v3_4)')
    execute(conn, f'ALTER TABLE {q(DEDUP34)} ADD KEY ix_v34_dedup_action (board_action_v3_4, dedup_action_rank_no_v3_4)')
    execute(conn, f'ALTER TABLE {q(DEDUP34)} ADD KEY ix_v34_dedup_code (code)')


def build_summary(conn: Any) -> None:
    execute(conn, 'DROP TABLE IF EXISTS ' + q(SUMMARY34))
    execute(conn, f'''
CREATE TABLE {q(SUMMARY34)} AS
SELECT 'RAW' AS board_layer_v3_4, board_action_v3_4, COUNT(*) AS row_count, COUNT(DISTINCT code) AS distinct_code_count,
       SUM(ui_live_compact_flag_v3_4) AS live_compact_count,
       SUM(ui_promoted_watch_flag_v3_4) AS promoted_watch_count,
       AVG(tick_confirm_score_v2_6) AS avg_tick_confirm_score,
       AVG(spread_risk_v2_6) AS avg_spread_risk,
       AVG(expected_return_pct) AS avg_expected_return_pct
FROM {q(RAW34)}
GROUP BY board_action_v3_4
UNION ALL
SELECT 'DEDUP' AS board_layer_v3_4, board_action_v3_4, COUNT(*) AS row_count, COUNT(DISTINCT code) AS distinct_code_count,
       SUM(ui_live_compact_flag_v3_4) AS live_compact_count,
       SUM(ui_promoted_watch_flag_v3_4) AS promoted_watch_count,
       AVG(tick_confirm_score_v2_6) AS avg_tick_confirm_score,
       AVG(spread_risk_v2_6) AS avg_spread_risk,
       AVG(expected_return_pct) AS avg_expected_return_pct
FROM {q(DEDUP34)}
GROUP BY board_action_v3_4
''')
    execute(conn, f'ALTER TABLE {q(SUMMARY34)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci')


def build_examples(conn: Any) -> None:
    execute(conn, 'DROP TABLE IF EXISTS ' + q(EXAMPLES34))
    execute(conn, f'''
CREATE TABLE {q(EXAMPLES34)} AS
SELECT * FROM {q(DEDUP34)}
ORDER BY dedup_final_rank_no_v3_4 ASC
LIMIT 120
''')
    execute(conn, f'ALTER TABLE {q(EXAMPLES34)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci')


def main() -> int:
    load_env('.env')
    conn = open_conn()
    try:
        if not table_exists(conn, RAW29):
            raise RuntimeError('missing ' + RAW29)
        if not table_exists(conn, DEDUP29):
            raise RuntimeError('missing ' + DEDUP29)
        build_raw(conn)
        build_dedup(conn)
        build_summary(conn)
        build_examples(conn)
        conn.commit()
        print('=== DONE build_top_candidate_board_promotion_v3_4 ===')
        for t in [RAW34, DEDUP34, SUMMARY34, EXAMPLES34]:
            print(t + '_rows=' + str(count(conn, t)))
        rows = fetch(conn, f'SELECT board_layer_v3_4, board_action_v3_4, row_count, distinct_code_count, live_compact_count, promoted_watch_count, avg_tick_confirm_score, avg_spread_risk FROM {q(SUMMARY34)} ORDER BY board_layer_v3_4, board_action_v3_4')
        print('=== SUMMARY v3.4 ===')
        for r in rows:
            print(dict(r))
        preview = fetch(conn, f'SELECT dedup_final_rank_no_v3_4, board_action_v3_4, board_action_v2_8, promote_reject_to_watch_flag_v3_4, code, name, entry_time_text, entry_price, tick_confirm_score_v2_6, buy_tick_ratio_v2_6, hoga_bid_pressure_v2_6, hoga_ask_absorption_v2_6, spread_risk_v2_6, promotion_reason_v3_4 FROM {q(DEDUP34)} WHERE ui_live_compact_flag_v3_4=1 ORDER BY dedup_final_rank_no_v3_4 ASC LIMIT 40')
        print('=== LIVE COMPACT v3.4 PREVIEW ===')
        for r in preview:
            print(dict(r))
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    raise SystemExit(main())
'@

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($tmp, $code, $utf8NoBom)

python -m py_compile $tmp
if ($LASTEXITCODE -ne 0) { throw 'py_compile failed' }
python $tmp
if ($LASTEXITCODE -ne 0) { throw 'v3.4 promotion builder failed' }
Remove-Item -LiteralPath $tmp -Force

Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE build_top_candidate_board_promotion_v3_4.ps1 ==='
