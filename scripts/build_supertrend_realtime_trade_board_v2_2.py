#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Leader_Lab v2.2
SuperTrend Realtime Trade Board Builder

Input:
- supertrend_realtime_entry_top_candidate_v2_1

Output:
- supertrend_realtime_trade_board_v2_2
- supertrend_realtime_trade_board_summary_v2_2
- supertrend_realtime_trade_board_examples_v2_2

Purpose:
- Convert v2.1 one-row-per-stock candidates into a practical realtime board table.
- Keep raw ranking scores for internal comparison, but expose display_score as 0~100.
- Produce simple trade decisions for UI / realtime dashboard:
  AUTO_BUY, AUTO_BUY_SMALL, WAIT_PULLBACK, WATCH_HOGA_TICK, HIDE
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
    assert_source_table,
)

SOURCE_TABLE_DEFAULT = "supertrend_realtime_entry_top_candidate_v2_1"
BOARD_TABLE = "supertrend_realtime_trade_board_v2_2"
SUMMARY_TABLE = "supertrend_realtime_trade_board_summary_v2_2"
EXAMPLE_TABLE = "supertrend_realtime_trade_board_examples_v2_2"


def display_score_expr() -> str:
    return """
    LEAST(100.0, GREATEST(0.0,
        IFNULL(entry_score_v2_0, 0.0)
        + CASE entry_action_v2_0
            WHEN 'AUTO_BUY_NEXT_BAR' THEN 4.0
            WHEN 'WAIT_PULLBACK' THEN 1.0
            WHEN 'REQUIRE_HOGA_TICK_CONFIRM' THEN -5.0
            ELSE -12.0
          END
        + CASE IFNULL(risk_band_v2_0, '')
            WHEN 'LOW' THEN 2.0
            WHEN 'PULLBACK_WAIT' THEN 1.0
            WHEN 'CONFIRM_REQUIRED' THEN -3.0
            ELSE 0.0
          END
        + GREATEST(0.0, LEAST(6.0, IFNULL(selected_estimated_return_pct, 0.0) * 0.20))
        + GREATEST(-8.0, LEAST(4.0, IFNULL(selected_max_adverse_excursion_pct, -10.0) * 1.50))
        + CASE
            WHEN IFNULL(start_cum_amount, 0.0) >= 10000000000 THEN 2.0
            WHEN IFNULL(start_cum_amount, 0.0) >= 5000000000 THEN 1.0
            WHEN IFNULL(start_cum_amount, 0.0) < 2000000000 THEN -3.0
            ELSE 0.0
          END
    ))
    """


def build_board(conn, args: argparse.Namespace) -> int:
    execute(conn, "DROP TEMPORARY TABLE IF EXISTS _tmp_v22_scored")
    execute(conn, "DROP TABLE IF EXISTS " + qident(EXAMPLE_TABLE))
    execute(conn, "DROP TABLE IF EXISTS " + qident(SUMMARY_TABLE))
    execute(conn, "DROP TABLE IF EXISTS " + qident(BOARD_TABLE))

    where_parts = ["1 = 1"]
    if args.include_confirm <= 0:
        where_parts.append("entry_action_v2_0 <> 'REQUIRE_HOGA_TICK_CONFIRM'")
    if args.min_selected_return_pct > 0:
        where_parts.append("selected_estimated_return_pct >= " + str(float(args.min_selected_return_pct)))
    where_sql = " AND ".join(where_parts)

    execute(conn, f"""
CREATE TEMPORARY TABLE _tmp_v22_scored AS
SELECT
    s.*,
    {display_score_expr()} AS display_score_v2_2,
    CASE
        WHEN s.entry_action_v2_0 = 'AUTO_BUY_NEXT_BAR' AND s.final_entry_grade_v2_0 = 'S' THEN 'S'
        WHEN s.entry_action_v2_0 = 'AUTO_BUY_NEXT_BAR' AND s.final_entry_grade_v2_0 = 'A' THEN 'A'
        WHEN s.entry_action_v2_0 = 'WAIT_PULLBACK' THEN 'B'
        WHEN s.entry_action_v2_0 = 'REQUIRE_HOGA_TICK_CONFIRM' THEN 'C'
        ELSE 'D'
    END AS display_grade_v2_2
FROM {qident(args.source_table)} s
WHERE {where_sql}
""")

    execute(conn, f"""
CREATE TABLE {qident(BOARD_TABLE)} AS
SELECT
    trade_date,
    code,
    name,
    entry_action_v2_0 AS entry_action,
    display_grade_v2_2 AS display_grade,
    display_score_v2_2 AS display_score,
    selected_entry_time AS entry_time,
    selected_entry_price AS entry_price,
    selected_estimated_return_pct AS expected_return_pct,
    selected_max_adverse_excursion_pct AS mae_risk_pct,
    start_cum_amount,
    start_from_day_open_pct,
    start_from_day_low_pct,
    quantity_scale_v2_0 AS quantity_scale,
    CASE
        WHEN entry_action_v2_0 = 'AUTO_BUY_NEXT_BAR'
             AND display_grade_v2_2 IN ('S', 'A')
             AND display_score_v2_2 >= 90.0
            THEN 'AUTO_BUY'
        WHEN entry_action_v2_0 = 'AUTO_BUY_NEXT_BAR'
             AND display_grade_v2_2 IN ('S', 'A')
             AND display_score_v2_2 >= 85.0
            THEN 'AUTO_BUY_SMALL'
        WHEN entry_action_v2_0 = 'WAIT_PULLBACK'
            THEN 'WAIT_PULLBACK'
        WHEN entry_action_v2_0 = 'REQUIRE_HOGA_TICK_CONFIRM'
            THEN 'WATCH_HOGA_TICK'
        ELSE 'HIDE'
    END AS trade_decision,
    CASE
        WHEN entry_action_v2_0 = 'AUTO_BUY_NEXT_BAR'
             AND display_grade_v2_2 IN ('S', 'A')
             AND display_score_v2_2 >= 90.0
            THEN '자동진입 후보: 다음봉 시가 기준, 잔여수익/MAE/거래대금 통과'
        WHEN entry_action_v2_0 = 'AUTO_BUY_NEXT_BAR'
             AND display_grade_v2_2 IN ('S', 'A')
             AND display_score_v2_2 >= 85.0
            THEN '소액 자동진입 후보: 강도는 있으나 점수 여유가 작음'
        WHEN entry_action_v2_0 = 'WAIT_PULLBACK'
            THEN '눌림 대기 후보: 즉시 추격보다 첫 눌림 확인 우위'
        WHEN entry_action_v2_0 = 'REQUIRE_HOGA_TICK_CONFIRM'
            THEN '호가/틱 확인 후보: 차트 조건만으로는 자동진입 부족'
        ELSE '화면 하단 참고 또는 숨김 후보'
    END AS risk_message,
    CASE
        WHEN entry_action_v2_0 = 'AUTO_BUY_NEXT_BAR' AND display_grade_v2_2 IN ('S', 'A') THEN 1
        WHEN entry_action_v2_0 = 'WAIT_PULLBACK' THEN 2
        WHEN entry_action_v2_0 = 'REQUIRE_HOGA_TICK_CONFIRM' AND display_score_v2_2 >= 80.0 THEN 3
        ELSE 4
    END AS chart_open_priority,
    st_period,
    st_multiplier,
    segment_no,
    st_up_start_time,
    final_entry_grade_v2_0,
    entry_score_v2_0,
    execution_score_v1_9,
    top_rank_score_v2_1,
    top_rank_action_priority_v2_1,
    recommended_entry_policy_v1_9,
    selected_entry_timing_v1_8,
    next_bar_return_pct,
    next_bar_mae_pct,
    pullback_return_pct,
    pullback_mae_pct,
    score_total,
    filter_label_v1_6,
    filter_grade_v1_6,
    filter_score_v1_6,
    risk_band_v2_0,
    entry_reason_v2_0,
    policy_reason_v1_9,
    top_rank_reason_v2_1,
    candidate_count_same_code_v2_1,
    auto_count_same_code_v2_1,
    wait_count_same_code_v2_1,
    confirm_count_same_code_v2_1,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM _tmp_v22_scored
WHERE display_score_v2_2 >= {float(args.min_display_score)}
""")

    execute(conn, f"ALTER TABLE {qident(BOARD_TABLE)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    execute(conn, f"ALTER TABLE {qident(BOARD_TABLE)} ADD COLUMN id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST")
    execute(conn, f"ALTER TABLE {qident(BOARD_TABLE)} ADD UNIQUE KEY ux_v22_date_code (trade_date, code)")
    execute(conn, f"ALTER TABLE {qident(BOARD_TABLE)} ADD KEY ix_v22_decision_score (trade_decision, display_score)")
    execute(conn, f"ALTER TABLE {qident(BOARD_TABLE)} ADD KEY ix_v22_priority_score (chart_open_priority, display_score)")
    execute(conn, f"ALTER TABLE {qident(BOARD_TABLE)} ADD KEY ix_v22_code_date (code, trade_date)")

    rows = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(BOARD_TABLE)}")
    return to_int(rows[0].get("cnt"), 0) if rows else 0


def build_summary(conn) -> None:
    execute(conn, f"""
CREATE TABLE {qident(SUMMARY_TABLE)} AS
SELECT
    trade_decision,
    display_grade,
    entry_action,
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
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM {qident(BOARD_TABLE)}
GROUP BY trade_decision, display_grade, entry_action
ORDER BY best_chart_open_priority ASC, avg_display_score DESC, avg_expected_return_pct DESC
""")
    execute(conn, f"ALTER TABLE {qident(SUMMARY_TABLE)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    execute(conn, f"ALTER TABLE {qident(SUMMARY_TABLE)} ADD COLUMN id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST")


def build_examples(conn, top_n: int) -> None:
    execute(conn, f"CREATE TABLE {qident(EXAMPLE_TABLE)} LIKE {qident(BOARD_TABLE)}")
    execute(conn, f"""
INSERT INTO {qident(EXAMPLE_TABLE)}
SELECT * FROM {qident(BOARD_TABLE)}
ORDER BY chart_open_priority ASC,
         display_score DESC,
         expected_return_pct DESC,
         mae_risk_pct DESC,
         start_cum_amount DESC
LIMIT {int(top_n)}
""")


def print_rows(title: str, rows) -> None:
    print("\n=== " + title + " ===")
    for r in rows:
        print(dict(r))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build v2.2 realtime trade board from v2.1 top candidates.")
    p.add_argument("--host", default="")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--database", default="")
    p.add_argument("--user", default="")
    p.add_argument("--password", default="")
    p.add_argument("--charset", default="utf8mb4")
    p.add_argument("--mysql-conn", default="")
    p.add_argument("--source-table", default=SOURCE_TABLE_DEFAULT)
    p.add_argument("--example-top-n", type=int, default=120)
    p.add_argument("--include-confirm", type=int, default=1)
    p.add_argument("--min-display-score", type=float, default=0.0)
    p.add_argument("--min-selected-return-pct", type=float, default=0.0)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    print("=== BUILD v2.2 ST Realtime Trade Board ===")
    cfg = build_mysql_config(args)
    conn = pymysql.connect(**cfg)
    try:
        assert_source_table(conn, args.source_table)
        source_rows = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(args.source_table)}")
        source_count = to_int(source_rows[0].get("cnt"), 0) if source_rows else 0
        inserted = build_board(conn, args)
        if inserted <= 0:
            raise RuntimeError("trade board row_count=0")
        build_summary(conn)
        build_examples(conn, args.example_top_n)
        conn.commit()
        print("source_table=", args.source_table)
        print("board_table=", BOARD_TABLE)
        print("summary_table=", SUMMARY_TABLE)
        print("example_table=", EXAMPLE_TABLE)
        print("source_rows=", source_count)
        print("inserted_board_rows=", inserted)
        print("board_ratio=", float(inserted) / float(source_count) if source_count > 0 else 0.0)
        print_rows("v2.2 Realtime Trade Board Summary", fetch_all(conn, f"SELECT * FROM {qident(SUMMARY_TABLE)} ORDER BY best_chart_open_priority ASC, avg_display_score DESC LIMIT 40"))
        print_rows("v2.2 Realtime Trade Board Examples", fetch_all(conn, f"SELECT * FROM {qident(EXAMPLE_TABLE)} ORDER BY chart_open_priority ASC, display_score DESC LIMIT 60"))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
