#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Leader_Lab v2.1
SuperTrend Realtime Entry Top Candidate Builder

Input:
- supertrend_realtime_entry_candidate_v2_0

Output:
- supertrend_realtime_entry_top_candidate_v2_1
- supertrend_realtime_entry_top_candidate_summary_v2_1
- supertrend_realtime_entry_top_candidate_examples_v2_1

This builder compresses v2.0 rows into one practical candidate per trade_date/code.
Priority: AUTO_BUY_NEXT_BAR > WAIT_PULLBACK > REQUIRE_HOGA_TICK_CONFIRM; SKIP is excluded.
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

SOURCE_TABLE_DEFAULT = "supertrend_realtime_entry_candidate_v2_0"
TOP_TABLE = "supertrend_realtime_entry_top_candidate_v2_1"
SUMMARY_TABLE = "supertrend_realtime_entry_top_candidate_summary_v2_1"
EXAMPLE_TABLE = "supertrend_realtime_entry_top_candidate_examples_v2_1"


def rank_score_expr() -> str:
    return """
    LEAST(120.0, GREATEST(0.0,
        IFNULL(entry_score_v2_0, 0)
        + CASE entry_action_v2_0
            WHEN 'AUTO_BUY_NEXT_BAR' THEN 12.0
            WHEN 'WAIT_PULLBACK' THEN 6.0
            WHEN 'REQUIRE_HOGA_TICK_CONFIRM' THEN 1.0
            ELSE 0.0
          END
        + GREATEST(-15.0, LEAST(10.0, IFNULL(selected_max_adverse_excursion_pct, -99.0) * 3.0))
        + GREATEST(0.0, LEAST(10.0, IFNULL(selected_estimated_return_pct, 0) * 0.35))
        + GREATEST(0.0, LEAST(5.0, (IFNULL(execution_score_v1_9, 0) - 80.0) * 0.15))
    ))
    """


def build_top_table(conn, args: argparse.Namespace) -> int:
    execute(conn, "DROP TEMPORARY TABLE IF EXISTS _tmp_v21_ranked")
    execute(conn, "DROP TABLE IF EXISTS " + qident(EXAMPLE_TABLE))
    execute(conn, "DROP TABLE IF EXISTS " + qident(SUMMARY_TABLE))
    execute(conn, "DROP TABLE IF EXISTS " + qident(TOP_TABLE))

    where_parts = ["entry_action_v2_0 <> 'SKIP'"]
    if args.min_entry_score > 0:
        where_parts.append("entry_score_v2_0 >= " + str(float(args.min_entry_score)))
    if args.min_return_pct > 0:
        where_parts.append("selected_estimated_return_pct >= " + str(float(args.min_return_pct)))
    where_sql = " AND ".join(where_parts)

    execute(conn, f"""
CREATE TEMPORARY TABLE _tmp_v21_ranked AS
SELECT
    s.*,
    CASE s.entry_action_v2_0
        WHEN 'AUTO_BUY_NEXT_BAR' THEN 1
        WHEN 'WAIT_PULLBACK' THEN 2
        WHEN 'REQUIRE_HOGA_TICK_CONFIRM' THEN 3
        ELSE 9
    END AS top_rank_action_priority_v2_1,
    {rank_score_expr()} AS top_rank_score_v2_1,
    COUNT(*) OVER (PARTITION BY s.trade_date, s.code) AS candidate_count_same_code_v2_1,
    SUM(CASE WHEN s.entry_action_v2_0 = 'AUTO_BUY_NEXT_BAR' THEN 1 ELSE 0 END) OVER (PARTITION BY s.trade_date, s.code) AS auto_count_same_code_v2_1,
    SUM(CASE WHEN s.entry_action_v2_0 = 'WAIT_PULLBACK' THEN 1 ELSE 0 END) OVER (PARTITION BY s.trade_date, s.code) AS wait_count_same_code_v2_1,
    SUM(CASE WHEN s.entry_action_v2_0 = 'REQUIRE_HOGA_TICK_CONFIRM' THEN 1 ELSE 0 END) OVER (PARTITION BY s.trade_date, s.code) AS confirm_count_same_code_v2_1,
    MAX(CASE WHEN s.entry_action_v2_0 = 'AUTO_BUY_NEXT_BAR' THEN s.entry_score_v2_0 END) OVER (PARTITION BY s.trade_date, s.code) AS best_auto_entry_score_same_code_v2_1,
    MAX(CASE WHEN s.entry_action_v2_0 = 'WAIT_PULLBACK' THEN s.entry_score_v2_0 END) OVER (PARTITION BY s.trade_date, s.code) AS best_wait_entry_score_same_code_v2_1,
    MAX(CASE WHEN s.entry_action_v2_0 = 'REQUIRE_HOGA_TICK_CONFIRM' THEN s.entry_score_v2_0 END) OVER (PARTITION BY s.trade_date, s.code) AS best_confirm_entry_score_same_code_v2_1,
    ROW_NUMBER() OVER (
        PARTITION BY s.trade_date, s.code
        ORDER BY
            CASE s.entry_action_v2_0
                WHEN 'AUTO_BUY_NEXT_BAR' THEN 1
                WHEN 'WAIT_PULLBACK' THEN 2
                WHEN 'REQUIRE_HOGA_TICK_CONFIRM' THEN 3
                ELSE 9
            END ASC,
            CASE s.final_entry_grade_v2_0
                WHEN 'S' THEN 1
                WHEN 'A' THEN 2
                WHEN 'B' THEN 3
                WHEN 'C' THEN 4
                ELSE 9
            END ASC,
            s.entry_score_v2_0 DESC,
            s.selected_estimated_return_pct DESC,
            s.selected_max_adverse_excursion_pct DESC,
            s.execution_score_v1_9 DESC,
            s.st_period ASC,
            s.st_multiplier ASC
    ) AS rn_v2_1
FROM {qident(args.source_table)} s
WHERE {where_sql}
""")

    execute(conn, f"""
CREATE TABLE {qident(TOP_TABLE)} AS
SELECT
    source_table AS source_table_v2_0,
    trade_date, code, name, st_period, st_multiplier, segment_no, st_up_start_time,
    selected_entry_time, selected_entry_price,
    recommended_entry_policy_v1_9, execution_label_v1_9, execution_score_v1_9,
    selected_entry_timing_v1_8, selected_estimated_return_pct, selected_max_adverse_excursion_pct,
    selected_estimated_lost_move_pct, next_bar_return_pct, next_bar_mae_pct, pullback_return_pct, pullback_mae_pct,
    start_from_day_open_pct, start_from_day_low_pct, start_cum_amount,
    score_total, filter_label_v1_6, filter_grade_v1_6, filter_score_v1_6,
    final_entry_grade_v2_0, entry_action_v2_0, entry_score_v2_0, risk_band_v2_0, quantity_scale_v2_0,
    entry_reason_v2_0, policy_reason_v1_9,
    top_rank_action_priority_v2_1,
    top_rank_score_v2_1,
    CONCAT('v2.1 one-row-per-stock: priority=', top_rank_action_priority_v2_1,
           ', same_code_candidates=', candidate_count_same_code_v2_1,
           ', selected_st=', st_period, '/', st_multiplier) AS top_rank_reason_v2_1,
    candidate_count_same_code_v2_1,
    auto_count_same_code_v2_1,
    wait_count_same_code_v2_1,
    confirm_count_same_code_v2_1,
    best_auto_entry_score_same_code_v2_1,
    best_wait_entry_score_same_code_v2_1,
    best_confirm_entry_score_same_code_v2_1,
    CURRENT_TIMESTAMP AS created_at
FROM _tmp_v21_ranked
WHERE rn_v2_1 = 1
""")
    execute(conn, f"ALTER TABLE {qident(TOP_TABLE)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    execute(conn, f"ALTER TABLE {qident(TOP_TABLE)} ADD COLUMN id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST")
    execute(conn, f"ALTER TABLE {qident(TOP_TABLE)} ADD UNIQUE KEY ux_v21_date_code (trade_date, code)")
    execute(conn, f"ALTER TABLE {qident(TOP_TABLE)} ADD KEY ix_v21_action_grade (entry_action_v2_0, final_entry_grade_v2_0)")
    execute(conn, f"ALTER TABLE {qident(TOP_TABLE)} ADD KEY ix_v21_score (top_rank_score_v2_1)")

    rows = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(TOP_TABLE)}")
    return to_int(rows[0].get("cnt"), 0) if rows else 0


def build_summary(conn) -> None:
    execute(conn, f"""
CREATE TABLE {qident(SUMMARY_TABLE)} AS
SELECT
    final_entry_grade_v2_0,
    entry_action_v2_0,
    COUNT(*) AS row_count,
    AVG(top_rank_score_v2_1) AS avg_top_rank_score_v2_1,
    AVG(entry_score_v2_0) AS avg_entry_score_v2_0,
    AVG(execution_score_v1_9) AS avg_execution_score_v1_9,
    AVG(selected_estimated_return_pct) AS avg_selected_return_pct,
    AVG(selected_max_adverse_excursion_pct) AS avg_selected_mae_pct,
    AVG(next_bar_return_pct) AS avg_next_bar_return_pct,
    AVG(next_bar_mae_pct) AS avg_next_bar_mae_pct,
    AVG(pullback_return_pct) AS avg_pullback_return_pct,
    AVG(pullback_mae_pct) AS avg_pullback_mae_pct,
    AVG(start_from_day_open_pct) AS avg_start_from_day_open_pct,
    AVG(start_from_day_low_pct) AS avg_start_from_day_low_pct,
    AVG(start_cum_amount) AS avg_start_cum_amount,
    AVG(quantity_scale_v2_0) AS avg_quantity_scale_v2_0,
    AVG(candidate_count_same_code_v2_1) AS avg_candidate_count_same_code_v2_1,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM {qident(TOP_TABLE)}
GROUP BY final_entry_grade_v2_0, entry_action_v2_0
ORDER BY avg_top_rank_score_v2_1 DESC, avg_selected_return_pct DESC
""")
    execute(conn, f"ALTER TABLE {qident(SUMMARY_TABLE)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    execute(conn, f"ALTER TABLE {qident(SUMMARY_TABLE)} ADD COLUMN id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST")


def build_examples(conn, top_n: int) -> None:
    execute(conn, f"CREATE TABLE {qident(EXAMPLE_TABLE)} LIKE {qident(TOP_TABLE)}")
    execute(conn, f"""
INSERT INTO {qident(EXAMPLE_TABLE)}
SELECT * FROM {qident(TOP_TABLE)}
ORDER BY top_rank_action_priority_v2_1 ASC,
         top_rank_score_v2_1 DESC,
         selected_estimated_return_pct DESC,
         selected_max_adverse_excursion_pct DESC
LIMIT {int(top_n)}
""")


def print_rows(title: str, rows) -> None:
    print("\n=== " + title + " ===")
    for r in rows:
        print(dict(r))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build v2.1 one-row-per-stock realtime entry top candidates from v2.0.")
    p.add_argument("--host", default="")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--database", default="")
    p.add_argument("--user", default="")
    p.add_argument("--password", default="")
    p.add_argument("--charset", default="utf8mb4")
    p.add_argument("--mysql-conn", default="")
    p.add_argument("--source-table", default=SOURCE_TABLE_DEFAULT)
    p.add_argument("--example-top-n", type=int, default=120)
    p.add_argument("--min-entry-score", type=float, default=0.0)
    p.add_argument("--min-return-pct", type=float, default=0.0)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    print("=== BUILD v2.1 ST Realtime Entry Top Candidate ===")
    cfg = build_mysql_config(args)
    conn = pymysql.connect(**cfg)
    try:
        assert_source_table(conn, args.source_table)
        source_rows = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(args.source_table)} WHERE entry_action_v2_0 <> 'SKIP'")
        source_count = to_int(source_rows[0].get("cnt"), 0) if source_rows else 0
        inserted = build_top_table(conn, args)
        if inserted <= 0:
            raise RuntimeError("top candidate table row_count=0")
        build_summary(conn)
        build_examples(conn, args.example_top_n)
        conn.commit()
        print("source_table=", args.source_table)
        print("top_table=", TOP_TABLE)
        print("summary_table=", SUMMARY_TABLE)
        print("example_table=", EXAMPLE_TABLE)
        print("source_rows_non_skip=", source_count)
        print("inserted_top_rows=", inserted)
        print("compression_ratio=", float(inserted) / float(source_count) if source_count > 0 else 0.0)
        print_rows("v2.1 Realtime Entry Top Candidate Summary", fetch_all(conn, f"SELECT * FROM {qident(SUMMARY_TABLE)} ORDER BY avg_top_rank_score_v2_1 DESC LIMIT 40"))
        print_rows("v2.1 Realtime Entry Top Candidate Examples", fetch_all(conn, f"SELECT * FROM {qident(EXAMPLE_TABLE)} ORDER BY top_rank_action_priority_v2_1 ASC, top_rank_score_v2_1 DESC LIMIT 40"))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
