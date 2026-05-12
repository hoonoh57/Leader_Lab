#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Leader_Lab v2.9
SuperTrend Top Candidate Board Contract Builder

Purpose:
- Freeze the UI query contract after v2.8.
- Provide two board layers:
  1) raw view table: preserves every candidate row from v2.8.
  2) dedup view table: keeps the best row per code for actual screen usage.
- Add explicit UI mode flags for the realtime board:
  LIVE_COMPACT, TEST_ALL, AUTO_BUY_ONLY, WATCH_ONLY, REJECT_ONLY.

Input:
- supertrend_realtime_final_board_view_v2_8

Output:
- supertrend_top_candidate_board_raw_view_v2_9
- supertrend_top_candidate_board_dedup_view_v2_9
- supertrend_top_candidate_board_summary_v2_9
- supertrend_top_candidate_board_examples_v2_9
"""

from __future__ import annotations

import argparse
import pymysql

from build_supertrend_realtime_entry_candidate_v2_0 import (
    build_mysql_config,
    fetch_all,
    execute,
    qident,
    to_int,
)

SOURCE_TABLE_DEFAULT = "supertrend_realtime_final_board_view_v2_8"
RAW_TABLE = "supertrend_top_candidate_board_raw_view_v2_9"
DEDUP_TABLE = "supertrend_top_candidate_board_dedup_view_v2_9"
SUMMARY_TABLE = "supertrend_top_candidate_board_summary_v2_9"
EXAMPLE_TABLE = "supertrend_top_candidate_board_examples_v2_9"

REQUIRED_SOURCE_COLUMNS = [
    "final_rank_no_v2_8",
    "action_rank_no_v2_8",
    "board_action_v2_8",
    "board_action_order_v2_8",
    "board_action_kr_v2_8",
    "ui_visibility_scope_v2_8",
    "compact_visible_flag_v2_8",
    "test_all_candidates_visible_flag_v2_8",
    "final_next_action_v2_8",
    "source_rank_no_v2_6",
    "trade_date",
    "code",
    "name",
    "ticker_label",
    "entry_time",
    "entry_time_text",
    "entry_price",
    "expected_return_pct",
    "mae_risk_pct",
    "start_cum_amount",
    "start_cum_amount_eok",
    "start_from_day_open_pct",
    "start_from_day_low_pct",
    "quantity_scale",
    "tick_confirm_label_v2_6",
    "next_action_v2_6",
    "tick_data_mode_v2_6",
    "realtime_snapshot_time",
    "realtime_source_tag",
    "tick_confirm_score_v2_6",
    "tick_intensity_v2_6",
    "buy_tick_ratio_v2_6",
    "large_trade_amount_eok_v2_6",
    "hoga_bid_pressure_v2_6",
    "hoga_ask_absorption_v2_6",
    "spread_risk_v2_6",
    "confirm_reason_v2_6",
    "board_reason_v2_8",
]


def table_exists(conn, table_name: str) -> bool:
    rows = fetch_all(conn, """
SELECT COUNT(*) AS cnt
FROM information_schema.tables
WHERE table_schema = DATABASE()
  AND table_name = %s
""", (table_name,))
    return bool(rows and to_int(rows[0].get("cnt"), 0) > 0)


def get_columns(conn, table_name: str) -> set[str]:
    rows = fetch_all(conn, """
SELECT column_name AS column_name
FROM information_schema.columns
WHERE table_schema = DATABASE()
  AND table_name = %s
ORDER BY ordinal_position
""", (table_name,))
    result: set[str] = set()
    for row in rows:
        value = row.get("column_name")
        if value is not None:
            result.add(str(value))
    return result


def assert_source(conn, source_table: str) -> None:
    if not table_exists(conn, source_table):
        raise RuntimeError("source table not found: " + source_table + "  먼저 v2.8을 정상 실행하세요.")
    cols = get_columns(conn, source_table)
    missing: list[str] = []
    for col_name in REQUIRED_SOURCE_COLUMNS:
        if col_name not in cols:
            missing.append(col_name)
    if missing:
        raise RuntimeError("v2.9 source required columns missing: " + ", ".join(missing))


def build_raw_table(conn, source_table: str) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(RAW_TABLE))
    execute(conn, f"""
CREATE TABLE {qident(RAW_TABLE)} AS
SELECT
    s.*,
    CASE WHEN s.compact_visible_flag_v2_8 = 1 THEN 1 ELSE 0 END AS ui_live_compact_flag_v2_9,
    CASE WHEN s.test_all_candidates_visible_flag_v2_8 = 1 THEN 1 ELSE 0 END AS ui_test_all_flag_v2_9,
    CASE WHEN s.board_action_v2_8 = 'AUTO_BUY_READY' THEN 1 ELSE 0 END AS ui_auto_buy_only_flag_v2_9,
    CASE WHEN s.board_action_v2_8 = 'WATCH_HOGA_TICK' THEN 1 ELSE 0 END AS ui_watch_only_flag_v2_9,
    CASE WHEN s.board_action_v2_8 = 'REJECT' THEN 1 ELSE 0 END AS ui_reject_only_flag_v2_9,
    CASE
        WHEN s.board_action_v2_8 = 'AUTO_BUY_READY' THEN 'LIVE_COMPACT,AUTO_BUY_ONLY,TEST_ALL'
        WHEN s.board_action_v2_8 = 'WATCH_HOGA_TICK' THEN 'LIVE_COMPACT,WATCH_ONLY,TEST_ALL'
        ELSE 'REJECT_ONLY,TEST_ALL'
    END AS ui_mode_list_v2_9,
    CONCAT(
        'LIVE_COMPACT=', CASE WHEN s.compact_visible_flag_v2_8 = 1 THEN 'Y' ELSE 'N' END,
        '; TEST_ALL=Y',
        '; AUTO_BUY_ONLY=', CASE WHEN s.board_action_v2_8 = 'AUTO_BUY_READY' THEN 'Y' ELSE 'N' END,
        '; WATCH_ONLY=', CASE WHEN s.board_action_v2_8 = 'WATCH_HOGA_TICK' THEN 'Y' ELSE 'N' END,
        '; REJECT_ONLY=', CASE WHEN s.board_action_v2_8 = 'REJECT' THEN 'Y' ELSE 'N' END
    ) AS ui_mode_reason_v2_9,
    CURRENT_TIMESTAMP AS contract_created_at_v2_9,
    CURRENT_TIMESTAMP AS contract_updated_at_v2_9
FROM {qident(source_table)} s
ORDER BY s.final_rank_no_v2_8 ASC
""")
    execute(conn, f"ALTER TABLE {qident(RAW_TABLE)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    execute(conn, f"ALTER TABLE {qident(RAW_TABLE)} ADD KEY ix_v29_raw_final_rank (final_rank_no_v2_8)")
    execute(conn, f"ALTER TABLE {qident(RAW_TABLE)} ADD KEY ix_v29_raw_action_rank (board_action_v2_8, action_rank_no_v2_8)")
    execute(conn, f"ALTER TABLE {qident(RAW_TABLE)} ADD KEY ix_v29_raw_code_rank (code, final_rank_no_v2_8)")
    execute(conn, f"ALTER TABLE {qident(RAW_TABLE)} ADD KEY ix_v29_raw_modes (ui_live_compact_flag_v2_9, ui_test_all_flag_v2_9, ui_auto_buy_only_flag_v2_9, ui_watch_only_flag_v2_9, ui_reject_only_flag_v2_9)")


def build_dedup_table(conn) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(DEDUP_TABLE))
    execute(conn, f"""
CREATE TABLE {qident(DEDUP_TABLE)} AS
WITH ranked AS (
    SELECT
        ROW_NUMBER() OVER (
            PARTITION BY r.code
            ORDER BY
                r.board_action_order_v2_8 ASC,
                r.tick_confirm_score_v2_6 DESC,
                r.expected_return_pct DESC,
                r.mae_risk_pct DESC,
                r.final_rank_no_v2_8 ASC
        ) AS code_dedup_rank_v2_9,
        r.*
    FROM {qident(RAW_TABLE)} r
), kept AS (
    SELECT *
    FROM ranked
    WHERE code_dedup_rank_v2_9 = 1
), final_ranked AS (
    SELECT
        ROW_NUMBER() OVER (
            ORDER BY
                k.board_action_order_v2_8 ASC,
                k.tick_confirm_score_v2_6 DESC,
                k.expected_return_pct DESC,
                k.mae_risk_pct DESC,
                k.final_rank_no_v2_8 ASC
        ) AS dedup_final_rank_no_v2_9,
        ROW_NUMBER() OVER (
            PARTITION BY k.board_action_v2_8
            ORDER BY
                k.tick_confirm_score_v2_6 DESC,
                k.expected_return_pct DESC,
                k.mae_risk_pct DESC,
                k.final_rank_no_v2_8 ASC
        ) AS dedup_action_rank_no_v2_9,
        k.*
    FROM kept k
)
SELECT *
FROM final_ranked
ORDER BY dedup_final_rank_no_v2_9 ASC
""")
    execute(conn, f"ALTER TABLE {qident(DEDUP_TABLE)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    execute(conn, f"ALTER TABLE {qident(DEDUP_TABLE)} ADD KEY ix_v29_dedup_final_rank (dedup_final_rank_no_v2_9)")
    execute(conn, f"ALTER TABLE {qident(DEDUP_TABLE)} ADD KEY ix_v29_dedup_action_rank (board_action_v2_8, dedup_action_rank_no_v2_9)")
    execute(conn, f"ALTER TABLE {qident(DEDUP_TABLE)} ADD KEY ix_v29_dedup_code (code)")
    execute(conn, f"ALTER TABLE {qident(DEDUP_TABLE)} ADD KEY ix_v29_dedup_modes (ui_live_compact_flag_v2_9, ui_test_all_flag_v2_9, ui_auto_buy_only_flag_v2_9, ui_watch_only_flag_v2_9, ui_reject_only_flag_v2_9)")


def build_summary(conn) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(SUMMARY_TABLE))
    execute(conn, f"""
CREATE TABLE {qident(SUMMARY_TABLE)} AS
SELECT
    'RAW' AS board_layer_v2_9,
    board_action_v2_8,
    board_action_kr_v2_8,
    COUNT(*) AS row_count,
    COUNT(DISTINCT code) AS distinct_code_count,
    SUM(ui_live_compact_flag_v2_9) AS live_compact_count,
    SUM(ui_test_all_flag_v2_9) AS test_all_count,
    SUM(ui_auto_buy_only_flag_v2_9) AS auto_buy_only_count,
    SUM(ui_watch_only_flag_v2_9) AS watch_only_count,
    SUM(ui_reject_only_flag_v2_9) AS reject_only_count,
    AVG(tick_confirm_score_v2_6) AS avg_tick_confirm_score_v2_6,
    AVG(tick_intensity_v2_6) AS avg_tick_intensity_v2_6,
    AVG(buy_tick_ratio_v2_6) AS avg_buy_tick_ratio_v2_6,
    AVG(hoga_bid_pressure_v2_6) AS avg_hoga_bid_pressure_v2_6,
    AVG(hoga_ask_absorption_v2_6) AS avg_hoga_ask_absorption_v2_6,
    AVG(spread_risk_v2_6) AS avg_spread_risk_v2_6,
    AVG(expected_return_pct) AS avg_expected_return_pct,
    AVG(mae_risk_pct) AS avg_mae_risk_pct,
    MIN(final_rank_no_v2_8) AS first_rank_no,
    MAX(final_rank_no_v2_8) AS last_rank_no,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM {qident(RAW_TABLE)}
GROUP BY board_action_v2_8, board_action_kr_v2_8
UNION ALL
SELECT
    'DEDUP' AS board_layer_v2_9,
    board_action_v2_8,
    board_action_kr_v2_8,
    COUNT(*) AS row_count,
    COUNT(DISTINCT code) AS distinct_code_count,
    SUM(ui_live_compact_flag_v2_9) AS live_compact_count,
    SUM(ui_test_all_flag_v2_9) AS test_all_count,
    SUM(ui_auto_buy_only_flag_v2_9) AS auto_buy_only_count,
    SUM(ui_watch_only_flag_v2_9) AS watch_only_count,
    SUM(ui_reject_only_flag_v2_9) AS reject_only_count,
    AVG(tick_confirm_score_v2_6) AS avg_tick_confirm_score_v2_6,
    AVG(tick_intensity_v2_6) AS avg_tick_intensity_v2_6,
    AVG(buy_tick_ratio_v2_6) AS avg_buy_tick_ratio_v2_6,
    AVG(hoga_bid_pressure_v2_6) AS avg_hoga_bid_pressure_v2_6,
    AVG(hoga_ask_absorption_v2_6) AS avg_hoga_ask_absorption_v2_6,
    AVG(spread_risk_v2_6) AS avg_spread_risk_v2_6,
    AVG(expected_return_pct) AS avg_expected_return_pct,
    AVG(mae_risk_pct) AS avg_mae_risk_pct,
    MIN(dedup_final_rank_no_v2_9) AS first_rank_no,
    MAX(dedup_final_rank_no_v2_9) AS last_rank_no,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM {qident(DEDUP_TABLE)}
GROUP BY board_action_v2_8, board_action_kr_v2_8
""")
    execute(conn, f"ALTER TABLE {qident(SUMMARY_TABLE)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    execute(conn, f"ALTER TABLE {qident(SUMMARY_TABLE)} ADD COLUMN id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST")
    execute(conn, f"ALTER TABLE {qident(SUMMARY_TABLE)} ADD KEY ix_v29_summary_layer_action (board_layer_v2_9, board_action_v2_8)")


def build_examples(conn, example_top_n: int) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(EXAMPLE_TABLE))
    execute(conn, f"""
CREATE TABLE {qident(EXAMPLE_TABLE)} AS
SELECT
    'DEDUP_TOP' AS example_scope_v2_9,
    d.*
FROM {qident(DEDUP_TABLE)} d
ORDER BY d.dedup_final_rank_no_v2_9 ASC
LIMIT {int(example_top_n)}
""")
    execute(conn, f"ALTER TABLE {qident(EXAMPLE_TABLE)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    execute(conn, f"ALTER TABLE {qident(EXAMPLE_TABLE)} ADD KEY ix_v29_examples_rank (dedup_final_rank_no_v2_9)")
    execute(conn, f"ALTER TABLE {qident(EXAMPLE_TABLE)} ADD KEY ix_v29_examples_action (board_action_v2_8, dedup_action_rank_no_v2_9)")


def print_rows(title: str, rows) -> None:
    print("\n=== " + title + " ===")
    for row in rows:
        print(dict(row))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build v2.9 top candidate board contract.")
    p.add_argument("--host", default="")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--database", default="")
    p.add_argument("--user", default="")
    p.add_argument("--password", default="")
    p.add_argument("--charset", default="utf8mb4")
    p.add_argument("--mysql-conn", default="")
    p.add_argument("--source-table", default=SOURCE_TABLE_DEFAULT)
    p.add_argument("--preview-limit", type=int, default=80)
    p.add_argument("--example-top-n", type=int, default=120)
    return p.parse_args()


def count_rows(conn, table_name: str, where_sql: str = "") -> int:
    sql = "SELECT COUNT(*) AS cnt FROM " + qident(table_name)
    if where_sql.strip():
        sql += " WHERE " + where_sql
    rows = fetch_all(conn, sql)
    if not rows:
        return 0
    return to_int(rows[0].get("cnt"), 0)


def main() -> None:
    args = parse_args()
    print("=== BUILD v2.9 ST Top Candidate Board Contract ===")
    cfg = build_mysql_config(args)
    conn = pymysql.connect(**cfg)
    try:
        assert_source(conn, args.source_table)
        build_raw_table(conn, args.source_table)
        build_dedup_table(conn)
        build_summary(conn)
        build_examples(conn, args.example_top_n)
        conn.commit()

        print("source_table=", args.source_table)
        print("raw_table=", RAW_TABLE)
        print("dedup_table=", DEDUP_TABLE)
        print("summary_table=", SUMMARY_TABLE)
        print("example_table=", EXAMPLE_TABLE)
        print("raw_total_rows=", count_rows(conn, RAW_TABLE))
        print("raw_live_compact_rows=", count_rows(conn, RAW_TABLE, "ui_live_compact_flag_v2_9 = 1"))
        print("raw_test_all_rows=", count_rows(conn, RAW_TABLE, "ui_test_all_flag_v2_9 = 1"))
        print("dedup_total_rows=", count_rows(conn, DEDUP_TABLE))
        print("dedup_live_compact_rows=", count_rows(conn, DEDUP_TABLE, "ui_live_compact_flag_v2_9 = 1"))
        print("dedup_test_all_rows=", count_rows(conn, DEDUP_TABLE, "ui_test_all_flag_v2_9 = 1"))
        print("dedup_auto_buy_rows=", count_rows(conn, DEDUP_TABLE, "ui_auto_buy_only_flag_v2_9 = 1"))
        print("dedup_watch_rows=", count_rows(conn, DEDUP_TABLE, "ui_watch_only_flag_v2_9 = 1"))
        print("dedup_reject_rows=", count_rows(conn, DEDUP_TABLE, "ui_reject_only_flag_v2_9 = 1"))

        print_rows("v2.9 Board Contract Summary", fetch_all(conn, f"""
SELECT *
FROM {qident(SUMMARY_TABLE)}
ORDER BY board_layer_v2_9 ASC, first_rank_no ASC
"""))
        print_rows("v2.9 Dedup Board Preview", fetch_all(conn, f"""
SELECT
    dedup_final_rank_no_v2_9,
    dedup_action_rank_no_v2_9,
    final_rank_no_v2_8,
    board_action_v2_8,
    board_action_kr_v2_8,
    ui_mode_list_v2_9,
    ui_live_compact_flag_v2_9,
    ui_test_all_flag_v2_9,
    code,
    name,
    ticker_label,
    tick_confirm_score_v2_6,
    tick_intensity_v2_6,
    buy_tick_ratio_v2_6,
    large_trade_amount_eok_v2_6,
    hoga_bid_pressure_v2_6,
    hoga_ask_absorption_v2_6,
    spread_risk_v2_6,
    expected_return_pct,
    mae_risk_pct,
    realtime_snapshot_time,
    realtime_source_tag,
    board_reason_v2_8
FROM {qident(DEDUP_TABLE)}
ORDER BY dedup_final_rank_no_v2_9 ASC
LIMIT {int(args.preview_limit)}
"""))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
