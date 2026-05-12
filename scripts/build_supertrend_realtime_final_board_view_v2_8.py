#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Leader_Lab v2.8
SuperTrend Realtime Final Board View Builder

Purpose:
- Freeze the final DB object consumed by the realtime Top Candidate Board UI.
- Convert v2.6 hoga/tick confirmation labels into screen actions:
  * AUTO_BUY_READY
  * WATCH_HOGA_TICK
  * REJECT
- Keep all 69 test candidates selectable for verification through TEST_ALL_CANDIDATES visibility flags.

Input:
- supertrend_hoga_tick_real_confirm_view_v2_6

Output:
- supertrend_realtime_final_board_view_v2_8
- supertrend_realtime_final_board_summary_v2_8
- supertrend_realtime_final_board_examples_v2_8
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

SOURCE_VIEW_DEFAULT = "supertrend_hoga_tick_real_confirm_view_v2_6"
FINAL_VIEW_TABLE = "supertrend_realtime_final_board_view_v2_8"
SUMMARY_TABLE = "supertrend_realtime_final_board_summary_v2_8"
EXAMPLE_TABLE = "supertrend_realtime_final_board_examples_v2_8"

REQUIRED_SOURCE_COLUMNS = [
    "confirm_rank_no_v2_6",
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


def assert_source(conn, source_view: str) -> None:
    if not table_exists(conn, source_view):
        raise RuntimeError("source view/table not found: " + source_view + "  먼저 v2.7 실행 후 v2.6 재검증까지 완료하세요.")
    cols = get_columns(conn, source_view)
    missing: list[str] = []
    for col_name in REQUIRED_SOURCE_COLUMNS:
        if col_name not in cols:
            missing.append(col_name)
    if missing:
        raise RuntimeError("v2.8 source required columns missing: " + ", ".join(missing))


def build_final_view(conn, source_view: str) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(FINAL_VIEW_TABLE))
    execute(conn, f"""
CREATE TABLE {qident(FINAL_VIEW_TABLE)} AS
WITH base AS (
    SELECT
        s.*,
        CASE
            WHEN s.tick_confirm_label_v2_6 = 'HOGA_TICK_CONFIRMED_BUY' THEN 'AUTO_BUY_READY'
            WHEN s.tick_confirm_label_v2_6 = 'WAIT_MORE_TICK' THEN 'WATCH_HOGA_TICK'
            ELSE 'REJECT'
        END AS board_action_v2_8,
        CASE
            WHEN s.tick_confirm_label_v2_6 = 'HOGA_TICK_CONFIRMED_BUY' THEN 1
            WHEN s.tick_confirm_label_v2_6 = 'WAIT_MORE_TICK' THEN 2
            ELSE 3
        END AS board_action_order_v2_8,
        CASE
            WHEN s.tick_confirm_label_v2_6 = 'HOGA_TICK_CONFIRMED_BUY' THEN '즉시매수 후보'
            WHEN s.tick_confirm_label_v2_6 = 'WAIT_MORE_TICK' THEN '호가/틱 관찰 후보'
            ELSE '제거 후보'
        END AS board_action_kr_v2_8,
        CASE
            WHEN s.tick_confirm_label_v2_6 IN ('HOGA_TICK_CONFIRMED_BUY', 'WAIT_MORE_TICK') THEN 1
            ELSE 0
        END AS compact_visible_flag_v2_8,
        1 AS test_all_candidates_visible_flag_v2_8,
        CASE
            WHEN s.tick_confirm_label_v2_6 = 'HOGA_TICK_CONFIRMED_BUY' THEN 'COMPACT_AUTO_BUY'
            WHEN s.tick_confirm_label_v2_6 = 'WAIT_MORE_TICK' THEN 'COMPACT_WATCH'
            ELSE 'TEST_ALL_CANDIDATES_ONLY'
        END AS ui_visibility_scope_v2_8,
        CASE
            WHEN s.tick_confirm_label_v2_6 = 'HOGA_TICK_CONFIRMED_BUY' THEN 'PROMOTE_TO_AUTO_BUY_SMALL_REAL_CONFIRMED'
            WHEN s.tick_confirm_label_v2_6 = 'WAIT_MORE_TICK' THEN 'KEEP_WATCH_AND_REQUIRE_NEXT_REAL_TICK'
            ELSE 'REMOVE_FROM_COMPACT_BOARD'
        END AS final_next_action_v2_8
    FROM {qident(source_view)} s
), ranked AS (
    SELECT
        ROW_NUMBER() OVER (
            ORDER BY
                b.board_action_order_v2_8 ASC,
                b.tick_confirm_score_v2_6 DESC,
                b.expected_return_pct DESC,
                b.mae_risk_pct DESC,
                b.start_cum_amount DESC,
                b.confirm_rank_no_v2_6 ASC
        ) AS final_rank_no_v2_8,
        ROW_NUMBER() OVER (
            PARTITION BY b.board_action_v2_8
            ORDER BY
                b.tick_confirm_score_v2_6 DESC,
                b.expected_return_pct DESC,
                b.mae_risk_pct DESC,
                b.start_cum_amount DESC,
                b.confirm_rank_no_v2_6 ASC
        ) AS action_rank_no_v2_8,
        b.*
    FROM base b
)
SELECT
    r.final_rank_no_v2_8,
    r.action_rank_no_v2_8,
    r.board_action_v2_8,
    r.board_action_order_v2_8,
    r.board_action_kr_v2_8,
    r.ui_visibility_scope_v2_8,
    r.compact_visible_flag_v2_8,
    r.test_all_candidates_visible_flag_v2_8,
    r.final_next_action_v2_8,
    r.confirm_rank_no_v2_6 AS source_rank_no_v2_6,
    r.trade_date,
    r.code,
    r.name,
    r.ticker_label,
    r.entry_time,
    r.entry_time_text,
    r.entry_price,
    r.expected_return_pct,
    r.mae_risk_pct,
    r.start_cum_amount,
    r.start_cum_amount_eok,
    r.start_from_day_open_pct,
    r.start_from_day_low_pct,
    r.quantity_scale,
    r.tick_confirm_label_v2_6,
    r.next_action_v2_6,
    r.tick_data_mode_v2_6,
    r.realtime_snapshot_time,
    r.realtime_source_tag,
    r.tick_confirm_score_v2_6,
    r.tick_intensity_v2_6,
    r.buy_tick_ratio_v2_6,
    r.large_trade_amount_eok_v2_6,
    r.hoga_bid_pressure_v2_6,
    r.hoga_ask_absorption_v2_6,
    r.spread_risk_v2_6,
    r.confirm_reason_v2_6,
    CONCAT(
        'action=', r.board_action_v2_8,
        ', rank=', r.final_rank_no_v2_8,
        ', sourceRank=', r.confirm_rank_no_v2_6,
        ', score=', ROUND(IFNULL(r.tick_confirm_score_v2_6,0),2),
        ', tick=', ROUND(IFNULL(r.tick_intensity_v2_6,0),1),
        ', buyTick=', ROUND(IFNULL(r.buy_tick_ratio_v2_6,0),1),
        ', spreadRisk=', ROUND(IFNULL(r.spread_risk_v2_6,0),1),
        ', exp=', ROUND(IFNULL(r.expected_return_pct,0),2),
        ', mae=', ROUND(IFNULL(r.mae_risk_pct,0),2)
    ) AS board_reason_v2_8,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM ranked r
ORDER BY r.final_rank_no_v2_8 ASC
""")
    execute(conn, f"ALTER TABLE {qident(FINAL_VIEW_TABLE)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    execute(conn, f"ALTER TABLE {qident(FINAL_VIEW_TABLE)} ADD KEY ix_v28_final_rank (final_rank_no_v2_8)")
    execute(conn, f"ALTER TABLE {qident(FINAL_VIEW_TABLE)} ADD KEY ix_v28_action_rank (board_action_v2_8, action_rank_no_v2_8)")
    execute(conn, f"ALTER TABLE {qident(FINAL_VIEW_TABLE)} ADD KEY ix_v28_visible (compact_visible_flag_v2_8, test_all_candidates_visible_flag_v2_8)")
    execute(conn, f"ALTER TABLE {qident(FINAL_VIEW_TABLE)} ADD KEY ix_v28_code_date (code, trade_date)")


def build_summary(conn) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(SUMMARY_TABLE))
    execute(conn, f"""
CREATE TABLE {qident(SUMMARY_TABLE)} AS
SELECT
    board_action_v2_8,
    board_action_kr_v2_8,
    ui_visibility_scope_v2_8,
    compact_visible_flag_v2_8,
    test_all_candidates_visible_flag_v2_8,
    COUNT(*) AS row_count,
    AVG(tick_confirm_score_v2_6) AS avg_tick_confirm_score_v2_6,
    AVG(tick_intensity_v2_6) AS avg_tick_intensity_v2_6,
    AVG(buy_tick_ratio_v2_6) AS avg_buy_tick_ratio_v2_6,
    AVG(large_trade_amount_eok_v2_6) AS avg_large_trade_amount_eok_v2_6,
    AVG(hoga_bid_pressure_v2_6) AS avg_hoga_bid_pressure_v2_6,
    AVG(hoga_ask_absorption_v2_6) AS avg_hoga_ask_absorption_v2_6,
    AVG(spread_risk_v2_6) AS avg_spread_risk_v2_6,
    AVG(expected_return_pct) AS avg_expected_return_pct,
    AVG(mae_risk_pct) AS avg_mae_risk_pct,
    MIN(final_rank_no_v2_8) AS first_final_rank_no_v2_8,
    MAX(final_rank_no_v2_8) AS last_final_rank_no_v2_8,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM {qident(FINAL_VIEW_TABLE)}
GROUP BY
    board_action_v2_8,
    board_action_kr_v2_8,
    ui_visibility_scope_v2_8,
    compact_visible_flag_v2_8,
    test_all_candidates_visible_flag_v2_8
""")
    execute(conn, f"ALTER TABLE {qident(SUMMARY_TABLE)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    execute(conn, f"ALTER TABLE {qident(SUMMARY_TABLE)} ADD COLUMN id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST")
    execute(conn, f"ALTER TABLE {qident(SUMMARY_TABLE)} ADD KEY ix_v28_summary_rank (first_final_rank_no_v2_8, board_action_v2_8)")


def build_examples(conn, top_n: int) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(EXAMPLE_TABLE))
    execute(conn, f"""
CREATE TABLE {qident(EXAMPLE_TABLE)} AS
SELECT *
FROM {qident(FINAL_VIEW_TABLE)}
ORDER BY final_rank_no_v2_8 ASC
LIMIT {int(top_n)}
""")
    execute(conn, f"ALTER TABLE {qident(EXAMPLE_TABLE)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    execute(conn, f"ALTER TABLE {qident(EXAMPLE_TABLE)} ADD KEY ix_v28_examples_rank (final_rank_no_v2_8)")
    execute(conn, f"ALTER TABLE {qident(EXAMPLE_TABLE)} ADD KEY ix_v28_examples_action (board_action_v2_8, action_rank_no_v2_8)")


def print_rows(title: str, rows) -> None:
    print("\n=== " + title + " ===")
    for row in rows:
        print(dict(row))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build v2.8 realtime final board view.")
    p.add_argument("--host", default="")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--database", default="")
    p.add_argument("--user", default="")
    p.add_argument("--password", default="")
    p.add_argument("--charset", default="utf8mb4")
    p.add_argument("--mysql-conn", default="")
    p.add_argument("--source-view", default=SOURCE_VIEW_DEFAULT)
    p.add_argument("--preview-limit", type=int, default=80)
    p.add_argument("--example-top-n", type=int, default=120)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    print("=== BUILD v2.8 ST Realtime Final Board View ===")
    cfg = build_mysql_config(args)
    conn = pymysql.connect(**cfg)
    try:
        assert_source(conn, args.source_view)
        build_final_view(conn, args.source_view)
        build_summary(conn)
        build_examples(conn, args.example_top_n)
        conn.commit()

        total_rows = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(FINAL_VIEW_TABLE)}")
        compact_rows = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(FINAL_VIEW_TABLE)} WHERE compact_visible_flag_v2_8 = 1")
        test_rows = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(FINAL_VIEW_TABLE)} WHERE test_all_candidates_visible_flag_v2_8 = 1")
        auto_buy_rows = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(FINAL_VIEW_TABLE)} WHERE board_action_v2_8 = 'AUTO_BUY_READY'")
        watch_rows = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(FINAL_VIEW_TABLE)} WHERE board_action_v2_8 = 'WATCH_HOGA_TICK'")
        reject_rows = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(FINAL_VIEW_TABLE)} WHERE board_action_v2_8 = 'REJECT'")

        print("source_view=", args.source_view)
        print("final_view_table=", FINAL_VIEW_TABLE)
        print("summary_table=", SUMMARY_TABLE)
        print("example_table=", EXAMPLE_TABLE)
        print("total_board_rows=", to_int(total_rows[0].get("cnt"), 0) if total_rows else 0)
        print("compact_visible_rows=", to_int(compact_rows[0].get("cnt"), 0) if compact_rows else 0)
        print("test_all_candidates_rows=", to_int(test_rows[0].get("cnt"), 0) if test_rows else 0)
        print("auto_buy_ready_rows=", to_int(auto_buy_rows[0].get("cnt"), 0) if auto_buy_rows else 0)
        print("watch_hoga_tick_rows=", to_int(watch_rows[0].get("cnt"), 0) if watch_rows else 0)
        print("reject_rows=", to_int(reject_rows[0].get("cnt"), 0) if reject_rows else 0)

        print_rows("v2.8 Final Board Summary", fetch_all(conn, f"""
SELECT *
FROM {qident(SUMMARY_TABLE)}
ORDER BY first_final_rank_no_v2_8 ASC
"""))
        print_rows("v2.8 Final Board Preview", fetch_all(conn, f"""
SELECT
    final_rank_no_v2_8,
    action_rank_no_v2_8,
    board_action_v2_8,
    board_action_kr_v2_8,
    ui_visibility_scope_v2_8,
    compact_visible_flag_v2_8,
    test_all_candidates_visible_flag_v2_8,
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
FROM {qident(FINAL_VIEW_TABLE)}
ORDER BY final_rank_no_v2_8 ASC
LIMIT {int(args.preview_limit)}
"""))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
