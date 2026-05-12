#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Leader_Lab v2.3
SuperTrend Realtime Trade Board Screen Builder

Input:
- supertrend_realtime_trade_board_v2_2

Output:
- supertrend_realtime_trade_board_screen_v2_3
- supertrend_realtime_trade_board_screen_summary_v2_3
- supertrend_realtime_trade_board_screen_examples_v2_3

Purpose:
- Keep the practical Top Candidate Board compact by default.
- Preserve all WATCH_HOGA_TICK rows for verification period.
- Let UI toggle between:
  1) COMPACT_SCREEN: real trading view
  2) TEST_WITH_HOGA_TICK_ALL: verification view including all WATCH_HOGA_TICK candidates

Design:
- One board table, one row per v2.2 candidate.
- compact_visible=1 means show on normal realtime trading board.
- test_full_visible=1 means show when the user enables verification/full WATCH_HOGA_TICK mode.
- hoga_tick_test_visible=1 marks WATCH_HOGA_TICK candidates that are hidden in compact mode but available for test display.
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

SOURCE_TABLE_DEFAULT = "supertrend_realtime_trade_board_v2_2"
SCREEN_TABLE = "supertrend_realtime_trade_board_screen_v2_3"
SUMMARY_TABLE = "supertrend_realtime_trade_board_screen_summary_v2_3"
EXAMPLE_TABLE = "supertrend_realtime_trade_board_screen_examples_v2_3"

REQUIRED_V22_COLUMNS = [
    "trade_date",
    "code",
    "name",
    "entry_action",
    "display_grade",
    "display_score",
    "expected_return_pct",
    "mae_risk_pct",
    "start_cum_amount",
    "start_from_day_open_pct",
    "start_from_day_low_pct",
    "quantity_scale",
    "trade_decision",
    "chart_open_priority",
    "entry_score_v2_0",
    "execution_score_v1_9",
    "next_bar_return_pct",
    "next_bar_mae_pct",
    "pullback_return_pct",
    "pullback_mae_pct",
]


def source_table_exists(conn, table_name: str) -> bool:
    rows = fetch_all(conn, """
SELECT COUNT(*) AS cnt
FROM information_schema.tables
WHERE table_schema = DATABASE()
  AND table_name = %s
""", (table_name,))
    return bool(rows and to_int(rows[0].get("cnt"), 0) > 0)


def get_table_columns(conn, table_name: str) -> set[str]:
    rows = fetch_all(conn, """
SELECT column_name AS column_name
FROM information_schema.columns
WHERE table_schema = DATABASE()
  AND table_name = %s
ORDER BY ordinal_position
""", (table_name,))
    cols: set[str] = set()
    for r in rows:
        cols.add(str(r.get("column_name")))
    return cols


def assert_v22_source_table(conn, table_name: str) -> None:
    if not source_table_exists(conn, table_name):
        raise RuntimeError("source table not found: " + table_name)
    cols = get_table_columns(conn, table_name)
    missing = []
    for c in REQUIRED_V22_COLUMNS:
        if c not in cols:
            missing.append(c)
    if missing:
        raise RuntimeError("v2.2 trade board source required columns missing: " + ", ".join(missing))


def build_screen_board(conn, args: argparse.Namespace) -> dict:
    execute(conn, "DROP TABLE IF EXISTS " + qident(EXAMPLE_TABLE))
    execute(conn, "DROP TABLE IF EXISTS " + qident(SUMMARY_TABLE))
    execute(conn, "DROP TABLE IF EXISTS " + qident(SCREEN_TABLE))

    wait_min_score = float(args.wait_min_display_score)
    hoga_min_score = float(args.hoga_compact_min_display_score)
    hoga_min_return = float(args.hoga_compact_min_return_pct)
    hoga_min_mae = float(args.hoga_compact_min_mae_pct)

    execute(conn, f"""
CREATE TABLE {qident(SCREEN_TABLE)} AS
SELECT
    b.*,
    CASE
        WHEN b.trade_decision IN ('AUTO_BUY', 'AUTO_BUY_SMALL') THEN 1
        WHEN b.trade_decision = 'WAIT_PULLBACK'
             AND IFNULL(b.display_score, 0.0) >= {wait_min_score} THEN 1
        WHEN b.trade_decision = 'WATCH_HOGA_TICK'
             AND IFNULL(b.display_score, 0.0) >= {hoga_min_score}
             AND IFNULL(b.expected_return_pct, -999.0) >= {hoga_min_return}
             AND IFNULL(b.mae_risk_pct, -999.0) >= {hoga_min_mae} THEN 1
        ELSE 0
    END AS compact_visible,
    1 AS test_full_visible,
    CASE WHEN b.trade_decision = 'WATCH_HOGA_TICK' THEN 1 ELSE 0 END AS hoga_tick_test_visible,
    CASE
        WHEN b.trade_decision IN ('AUTO_BUY', 'AUTO_BUY_SMALL') THEN 'AUTO_BUY_ZONE'
        WHEN b.trade_decision = 'WAIT_PULLBACK' THEN 'PULLBACK_ZONE'
        WHEN b.trade_decision = 'WATCH_HOGA_TICK' THEN 'HOGA_TICK_TEST_ZONE'
        ELSE 'HIDDEN_ZONE'
    END AS ui_section,
    CASE
        WHEN b.trade_decision IN ('AUTO_BUY', 'AUTO_BUY_SMALL') THEN '항상 표시: 자동매수 후보'
        WHEN b.trade_decision = 'WAIT_PULLBACK'
             AND IFNULL(b.display_score, 0.0) >= {wait_min_score} THEN '기본 표시: 눌림 대기 고점수 후보'
        WHEN b.trade_decision = 'WAIT_PULLBACK' THEN '검증 표시: 눌림 대기 저점수 후보'
        WHEN b.trade_decision = 'WATCH_HOGA_TICK'
             AND IFNULL(b.display_score, 0.0) >= {hoga_min_score}
             AND IFNULL(b.expected_return_pct, -999.0) >= {hoga_min_return}
             AND IFNULL(b.mae_risk_pct, -999.0) >= {hoga_min_mae} THEN '기본 표시 가능: 호가/틱 확인 고품질 후보'
        WHEN b.trade_decision = 'WATCH_HOGA_TICK' THEN '검증 표시 전용: WATCH_HOGA_TICK 전체 후보'
        ELSE '숨김 후보'
    END AS ui_visibility_reason,
    CASE
        WHEN b.trade_decision IN ('AUTO_BUY', 'AUTO_BUY_SMALL') THEN 1
        WHEN b.trade_decision = 'WAIT_PULLBACK' THEN 2
        WHEN b.trade_decision = 'WATCH_HOGA_TICK'
             AND IFNULL(b.display_score, 0.0) >= {hoga_min_score}
             AND IFNULL(b.expected_return_pct, -999.0) >= {hoga_min_return}
             AND IFNULL(b.mae_risk_pct, -999.0) >= {hoga_min_mae} THEN 3
        WHEN b.trade_decision = 'WATCH_HOGA_TICK' THEN 4
        ELSE 9
    END AS ui_sort_bucket,
    CURRENT_TIMESTAMP AS screen_created_at,
    CURRENT_TIMESTAMP AS screen_updated_at
FROM {qident(args.source_table)} b
""")

    execute(conn, f"ALTER TABLE {qident(SCREEN_TABLE)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    execute(conn, f"ALTER TABLE {qident(SCREEN_TABLE)} ADD KEY ix_v23_compact (compact_visible, ui_sort_bucket, display_score)")
    execute(conn, f"ALTER TABLE {qident(SCREEN_TABLE)} ADD KEY ix_v23_test_full (test_full_visible, ui_sort_bucket, display_score)")
    execute(conn, f"ALTER TABLE {qident(SCREEN_TABLE)} ADD KEY ix_v23_hoga_test (hoga_tick_test_visible, display_score)")
    execute(conn, f"ALTER TABLE {qident(SCREEN_TABLE)} ADD KEY ix_v23_trade_decision (trade_decision, display_grade, display_score)")

    rows = fetch_all(conn, f"""
SELECT
    COUNT(*) AS total_rows,
    SUM(CASE WHEN compact_visible = 1 THEN 1 ELSE 0 END) AS compact_rows,
    SUM(CASE WHEN test_full_visible = 1 THEN 1 ELSE 0 END) AS test_full_rows,
    SUM(CASE WHEN trade_decision = 'WATCH_HOGA_TICK' THEN 1 ELSE 0 END) AS hoga_total_rows,
    SUM(CASE WHEN trade_decision = 'WATCH_HOGA_TICK' AND compact_visible = 1 THEN 1 ELSE 0 END) AS hoga_compact_rows,
    SUM(CASE WHEN trade_decision = 'WATCH_HOGA_TICK' AND hoga_tick_test_visible = 1 THEN 1 ELSE 0 END) AS hoga_test_rows
FROM {qident(SCREEN_TABLE)}
""")
    if not rows:
        return {}
    return dict(rows[0])


def build_summary(conn) -> None:
    execute(conn, f"""
CREATE TABLE {qident(SUMMARY_TABLE)} AS
SELECT
    'COMPACT_SCREEN' AS display_scope,
    trade_decision,
    display_grade,
    entry_action,
    ui_section,
    COUNT(*) AS row_count,
    AVG(display_score) AS avg_display_score,
    AVG(entry_score_v2_0) AS avg_entry_score_v2_0,
    AVG(execution_score_v1_9) AS avg_execution_score_v1_9,
    AVG(expected_return_pct) AS avg_expected_return_pct,
    AVG(mae_risk_pct) AS avg_mae_risk_pct,
    AVG(next_bar_return_pct) AS avg_next_bar_return_pct,
    AVG(next_bar_mae_pct) AS avg_next_bar_mae_pct,
    AVG(pullback_return_pct) AS avg_pullback_return_pct,
    AVG(pullback_mae_pct) AS avg_pullback_mae_pct,
    AVG(start_from_day_open_pct) AS avg_start_from_day_open_pct,
    AVG(start_from_day_low_pct) AS avg_start_from_day_low_pct,
    AVG(start_cum_amount) AS avg_start_cum_amount,
    AVG(quantity_scale) AS avg_quantity_scale,
    MIN(chart_open_priority) AS best_chart_open_priority,
    MIN(ui_sort_bucket) AS best_ui_sort_bucket,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM {qident(SCREEN_TABLE)}
WHERE compact_visible = 1
GROUP BY trade_decision, display_grade, entry_action, ui_section
UNION ALL
SELECT
    'TEST_WITH_HOGA_TICK_ALL' AS display_scope,
    trade_decision,
    display_grade,
    entry_action,
    ui_section,
    COUNT(*) AS row_count,
    AVG(display_score) AS avg_display_score,
    AVG(entry_score_v2_0) AS avg_entry_score_v2_0,
    AVG(execution_score_v1_9) AS avg_execution_score_v1_9,
    AVG(expected_return_pct) AS avg_expected_return_pct,
    AVG(mae_risk_pct) AS avg_mae_risk_pct,
    AVG(next_bar_return_pct) AS avg_next_bar_return_pct,
    AVG(next_bar_mae_pct) AS avg_next_bar_mae_pct,
    AVG(pullback_return_pct) AS avg_pullback_return_pct,
    AVG(pullback_mae_pct) AS avg_pullback_mae_pct,
    AVG(start_from_day_open_pct) AS avg_start_from_day_open_pct,
    AVG(start_from_day_low_pct) AS avg_start_from_day_low_pct,
    AVG(start_cum_amount) AS avg_start_cum_amount,
    AVG(quantity_scale) AS avg_quantity_scale,
    MIN(chart_open_priority) AS best_chart_open_priority,
    MIN(ui_sort_bucket) AS best_ui_sort_bucket,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM {qident(SCREEN_TABLE)}
WHERE test_full_visible = 1
GROUP BY trade_decision, display_grade, entry_action, ui_section
""")
    execute(conn, f"ALTER TABLE {qident(SUMMARY_TABLE)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    execute(conn, f"ALTER TABLE {qident(SUMMARY_TABLE)} ADD COLUMN id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST")
    execute(conn, f"ALTER TABLE {qident(SUMMARY_TABLE)} ADD KEY ix_v23_summary_scope (display_scope, best_ui_sort_bucket, avg_display_score)")


def build_examples(conn, compact_top_n: int, test_hoga_top_n: int) -> None:
    execute(conn, f"""
CREATE TABLE {qident(EXAMPLE_TABLE)} AS
SELECT
    CAST('COMPACT_SCREEN' AS CHAR(64)) AS example_scope,
    b.*
FROM {qident(SCREEN_TABLE)} b
WHERE b.compact_visible = 1
ORDER BY b.ui_sort_bucket ASC,
         b.display_score DESC,
         b.expected_return_pct DESC,
         b.mae_risk_pct DESC,
         b.start_cum_amount DESC
LIMIT {int(compact_top_n)}
""")
    execute(conn, f"ALTER TABLE {qident(EXAMPLE_TABLE)} MODIFY COLUMN example_scope VARCHAR(64) NOT NULL")

    execute(conn, f"""
INSERT INTO {qident(EXAMPLE_TABLE)}
SELECT
    'TEST_HOGA_TICK_ALL_TOP' AS example_scope,
    b.*
FROM {qident(SCREEN_TABLE)} b
WHERE b.trade_decision = 'WATCH_HOGA_TICK'
ORDER BY b.display_score DESC,
         b.expected_return_pct DESC,
         b.mae_risk_pct DESC,
         b.start_cum_amount DESC
LIMIT {int(test_hoga_top_n)}
""")
    execute(conn, f"ALTER TABLE {qident(EXAMPLE_TABLE)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    execute(conn, f"ALTER TABLE {qident(EXAMPLE_TABLE)} ADD KEY ix_v23_examples_scope (example_scope, ui_sort_bucket, display_score)")


def print_rows(title: str, rows) -> None:
    print("\n=== " + title + " ===")
    for r in rows:
        print(dict(r))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build v2.3 realtime board screen flags from v2.2 trade board.")
    p.add_argument("--host", default="")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--database", default="")
    p.add_argument("--user", default="")
    p.add_argument("--password", default="")
    p.add_argument("--charset", default="utf8mb4")
    p.add_argument("--mysql-conn", default="")
    p.add_argument("--source-table", default=SOURCE_TABLE_DEFAULT)
    p.add_argument("--wait-min-display-score", type=float, default=85.0)
    p.add_argument("--hoga-compact-min-display-score", type=float, default=80.0)
    p.add_argument("--hoga-compact-min-return-pct", type=float, default=12.0)
    p.add_argument("--hoga-compact-min-mae-pct", type=float, default=-2.5)
    p.add_argument("--compact-example-top-n", type=int, default=80)
    p.add_argument("--test-hoga-example-top-n", type=int, default=120)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    print("=== BUILD v2.3 ST Realtime Trade Board Screen ===")
    cfg = build_mysql_config(args)
    conn = pymysql.connect(**cfg)
    try:
        assert_v22_source_table(conn, args.source_table)
        source_rows = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(args.source_table)}")
        source_count = to_int(source_rows[0].get("cnt"), 0) if source_rows else 0
        counts = build_screen_board(conn, args)
        total_rows = to_int(counts.get("total_rows"), 0)
        if total_rows <= 0:
            raise RuntimeError("v2.3 screen board row_count=0")
        build_summary(conn)
        build_examples(conn, args.compact_example_top_n, args.test_hoga_example_top_n)
        conn.commit()

        print("source_table=", args.source_table)
        print("screen_table=", SCREEN_TABLE)
        print("summary_table=", SUMMARY_TABLE)
        print("example_table=", EXAMPLE_TABLE)
        print("source_rows=", source_count)
        print("screen_rows=", total_rows)
        print("compact_rows=", to_int(counts.get("compact_rows"), 0))
        print("test_full_rows=", to_int(counts.get("test_full_rows"), 0))
        print("watch_hoga_tick_total_rows=", to_int(counts.get("hoga_total_rows"), 0))
        print("watch_hoga_tick_compact_rows=", to_int(counts.get("hoga_compact_rows"), 0))
        print("watch_hoga_tick_test_rows=", to_int(counts.get("hoga_test_rows"), 0))
        print("ui_toggle= COMPACT_SCREEN / TEST_WITH_HOGA_TICK_ALL")

        print_rows(
            "v2.3 Screen Summary",
            fetch_all(conn, f"""
SELECT *
FROM {qident(SUMMARY_TABLE)}
ORDER BY display_scope ASC, best_ui_sort_bucket ASC, avg_display_score DESC, avg_expected_return_pct DESC
LIMIT 80
"""),
        )
        print_rows(
            "v2.3 Compact Examples",
            fetch_all(conn, f"""
SELECT *
FROM {qident(EXAMPLE_TABLE)}
WHERE example_scope = 'COMPACT_SCREEN'
ORDER BY ui_sort_bucket ASC, display_score DESC, expected_return_pct DESC
LIMIT 40
"""),
        )
        print_rows(
            "v2.3 WATCH_HOGA_TICK Test Examples",
            fetch_all(conn, f"""
SELECT *
FROM {qident(EXAMPLE_TABLE)}
WHERE example_scope = 'TEST_HOGA_TICK_ALL_TOP'
ORDER BY display_score DESC, expected_return_pct DESC, mae_risk_pct DESC
LIMIT 40
"""),
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
