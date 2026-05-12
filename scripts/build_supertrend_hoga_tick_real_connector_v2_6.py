#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Leader_Lab v2.6
SuperTrend Real Hoga/Tick Connector Builder

Input:
- supertrend_hoga_tick_confirm_view_v2_5
- optional realtime table: supertrend_realtime_hoga_tick_snapshot

Output:
- supertrend_hoga_tick_real_contract_v2_6
- supertrend_hoga_tick_snapshot_template_v2_6
- supertrend_hoga_tick_real_confirm_view_v2_6
- supertrend_hoga_tick_real_confirm_summary_v2_6
- supertrend_hoga_tick_real_confirm_examples_v2_6

Purpose:
- Fix the real-time input contract before VB.NET Top Candidate Board integration.
- Join the v2.5 WATCH_HOGA_TICK confirmation board with live hoga/tick snapshots when available.
- Fall back to v2.5 proxy values deterministically when the live snapshot table is missing or incomplete.
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

SOURCE_TABLE_DEFAULT = "supertrend_hoga_tick_confirm_view_v2_5"
REALTIME_TABLE_DEFAULT = "supertrend_realtime_hoga_tick_snapshot"
CONTRACT_TABLE = "supertrend_hoga_tick_real_contract_v2_6"
TEMPLATE_TABLE = "supertrend_hoga_tick_snapshot_template_v2_6"
VIEW_TABLE = "supertrend_hoga_tick_real_confirm_view_v2_6"
SUMMARY_TABLE = "supertrend_hoga_tick_real_confirm_summary_v2_6"
EXAMPLE_TABLE = "supertrend_hoga_tick_real_confirm_examples_v2_6"

SOURCE_REQUIRED_COLUMNS = [
    "confirm_rank_no", "display_scope", "board_row_no", "ui_section", "trade_decision", "entry_action",
    "display_grade", "display_score", "trade_date", "code", "name", "ticker_label", "entry_time",
    "entry_time_text", "entry_price", "expected_return_pct", "mae_risk_pct", "start_cum_amount",
    "start_cum_amount_eok", "start_from_day_open_pct", "start_from_day_low_pct", "quantity_scale",
    "tick_intensity", "buy_tick_ratio", "large_trade_amount", "large_trade_amount_eok",
    "hoga_bid_pressure", "hoga_ask_absorption", "spread_risk", "tick_confirm_score",
    "tick_confirm_label", "next_action", "confirm_reason", "tick_data_mode",
]

REAL_REQUIRED_COLUMNS = [
    "code", "snapshot_time", "tick_intensity", "buy_tick_ratio", "large_trade_amount",
    "hoga_bid_pressure", "hoga_ask_absorption", "spread_risk",
]

REAL_OPTIONAL_COLUMNS = [
    "trade_date", "name", "last_price", "tick_count", "buy_tick_count", "sell_tick_count",
    "bid_total_qty", "ask_total_qty", "net_buy_amount", "source_tag", "created_at",
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
        col = row.get("column_name")
        if col is not None:
            result.add(str(col))
    return result


def assert_source(conn, table_name: str) -> set[str]:
    if not table_exists(conn, table_name):
        raise RuntimeError("source table not found: " + table_name)
    cols = get_columns(conn, table_name)
    missing: list[str] = []
    for col_name in SOURCE_REQUIRED_COLUMNS:
        if col_name not in cols:
            missing.append(col_name)
    if missing:
        raise RuntimeError("v2.6 source required columns missing: " + ", ".join(missing))
    return cols


def create_contract_table(conn) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(CONTRACT_TABLE))
    execute(conn, f"""
CREATE TABLE {qident(CONTRACT_TABLE)} (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    column_order INT NOT NULL,
    column_name VARCHAR(80) NOT NULL,
    required_flag TINYINT NOT NULL,
    data_type_hint VARCHAR(80) NOT NULL,
    producer_hint VARCHAR(160) NOT NULL,
    ui_usage VARCHAR(160) NOT NULL,
    validation_rule VARCHAR(300) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY ux_v26_contract_col (column_name),
    KEY ix_v26_contract_order (column_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
""")
    rows = [
        (10, "code", 1, "VARCHAR(20)", "VB.NET realtime ticker key", "join key", "must match candidate code"),
        (20, "snapshot_time", 1, "DATETIME", "tick/hoga snapshot timestamp", "freshness check", "latest row per code is used"),
        (30, "tick_intensity", 1, "DOUBLE", "recent tick count or normalized tick speed", "틱강도", "0..100 normalized preferred"),
        (40, "buy_tick_ratio", 1, "DOUBLE", "buy tick count / total tick count * 100", "매수틱%", "0..100"),
        (50, "large_trade_amount", 1, "DOUBLE", "large executions amount in KRW", "대량체결", ">=0"),
        (60, "hoga_bid_pressure", 1, "DOUBLE", "bid-side pressure score", "매수압력", "0..100 normalized preferred"),
        (70, "hoga_ask_absorption", 1, "DOUBLE", "ask-side absorption score", "매도흡수", "0..100 normalized preferred"),
        (80, "spread_risk", 1, "DOUBLE", "spread/slippage risk score", "스프레드위험", "0..100, lower is better"),
        (90, "trade_date", 0, "DATE", "market date", "optional strict join", "YYYY-MM-DD"),
        (100, "last_price", 0, "DOUBLE", "last traded price", "price sanity", ">0"),
        (110, "tick_count", 0, "INT", "recent tick count", "diagnostics", ">=0"),
        (120, "buy_tick_count", 0, "INT", "recent buy tick count", "diagnostics", ">=0"),
        (130, "sell_tick_count", 0, "INT", "recent sell tick count", "diagnostics", ">=0"),
        (140, "bid_total_qty", 0, "DOUBLE", "total bid quantity", "diagnostics", ">=0"),
        (150, "ask_total_qty", 0, "DOUBLE", "total ask quantity", "diagnostics", ">=0"),
        (160, "net_buy_amount", 0, "DOUBLE", "net buy amount in KRW", "diagnostics", "can be negative"),
        (170, "source_tag", 0, "VARCHAR(80)", "provider/module name", "audit", "e.g. KIWOOM_REALTIME"),
    ]
    with conn.cursor() as cur:
        cur.executemany(f"""
INSERT INTO {qident(CONTRACT_TABLE)}
(column_order, column_name, required_flag, data_type_hint, producer_hint, ui_usage, validation_rule)
VALUES (%s, %s, %s, %s, %s, %s, %s)
""", rows)


def create_template_table(conn) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(TEMPLATE_TABLE))
    execute(conn, f"""
CREATE TABLE {qident(TEMPLATE_TABLE)} (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(20) NOT NULL,
    trade_date DATE NULL,
    snapshot_time DATETIME NOT NULL,
    name VARCHAR(128) NULL,
    last_price DOUBLE NULL,
    tick_intensity DOUBLE NOT NULL,
    buy_tick_ratio DOUBLE NOT NULL,
    large_trade_amount DOUBLE NOT NULL,
    hoga_bid_pressure DOUBLE NOT NULL,
    hoga_ask_absorption DOUBLE NOT NULL,
    spread_risk DOUBLE NOT NULL,
    tick_count INT NULL,
    buy_tick_count INT NULL,
    sell_tick_count INT NULL,
    bid_total_qty DOUBLE NULL,
    ask_total_qty DOUBLE NULL,
    net_buy_amount DOUBLE NULL,
    source_tag VARCHAR(80) NOT NULL DEFAULT 'TEMPLATE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY ix_v26_template_code_time (code, snapshot_time),
    KEY ix_v26_template_trade_date (trade_date, code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
""")


def realtime_table_is_usable(conn, table_name: str) -> tuple[bool, set[str], list[str]]:
    if not table_exists(conn, table_name):
        return False, set(), REAL_REQUIRED_COLUMNS[:]
    cols = get_columns(conn, table_name)
    missing = [c for c in REAL_REQUIRED_COLUMNS if c not in cols]
    return len(missing) == 0, cols, missing


def optional_expr(cols: set[str], alias_name: str, col_name: str, default_sql: str) -> str:
    if col_name in cols:
        return alias_name + "." + qident(col_name)
    return default_sql


def build_view(conn, source_table: str, realtime_table: str, use_real: bool, real_cols: set[str], snapshot_max_age_minutes: int, strict_trade_date_join: bool) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(VIEW_TABLE))

    if use_real:
        age_where = ""
        if snapshot_max_age_minutes > 0:
            age_where = "WHERE snapshot_time >= DATE_SUB(NOW(), INTERVAL " + str(int(snapshot_max_age_minutes)) + " MINUTE)"
        trade_date_col = optional_expr(real_cols, "r", "trade_date", "NULL")
        name_col = optional_expr(real_cols, "r", "name", "NULL")
        last_price_col = optional_expr(real_cols, "r", "last_price", "NULL")
        tick_count_col = optional_expr(real_cols, "r", "tick_count", "NULL")
        buy_tick_count_col = optional_expr(real_cols, "r", "buy_tick_count", "NULL")
        sell_tick_count_col = optional_expr(real_cols, "r", "sell_tick_count", "NULL")
        bid_total_qty_col = optional_expr(real_cols, "r", "bid_total_qty", "NULL")
        ask_total_qty_col = optional_expr(real_cols, "r", "ask_total_qty", "NULL")
        net_buy_amount_col = optional_expr(real_cols, "r", "net_buy_amount", "NULL")
        source_tag_col = optional_expr(real_cols, "r", "source_tag", "'REALTIME_TABLE'")
        join_extra = ""
        if strict_trade_date_join and "trade_date" in real_cols:
            join_extra = " AND rt.trade_date = b.trade_date"
        latest_rt_cte = f"""
, rt_ranked AS (
    SELECT
        r.code,
        {trade_date_col} AS trade_date,
        r.snapshot_time,
        {name_col} AS realtime_name,
        {last_price_col} AS last_price,
        r.tick_intensity,
        r.buy_tick_ratio,
        r.large_trade_amount,
        r.hoga_bid_pressure,
        r.hoga_ask_absorption,
        r.spread_risk,
        {tick_count_col} AS tick_count,
        {buy_tick_count_col} AS buy_tick_count,
        {sell_tick_count_col} AS sell_tick_count,
        {bid_total_qty_col} AS bid_total_qty,
        {ask_total_qty_col} AS ask_total_qty,
        {net_buy_amount_col} AS net_buy_amount,
        {source_tag_col} AS source_tag,
        ROW_NUMBER() OVER (PARTITION BY r.code ORDER BY r.snapshot_time DESC) AS rn
    FROM {qident(realtime_table)} r
    {age_where}
), rt AS (
    SELECT * FROM rt_ranked WHERE rn = 1
)
"""
        join_sql = "LEFT JOIN rt ON rt.code = b.code" + join_extra
        snapshot_expr = "rt.snapshot_time"
        source_tag_expr = "rt.source_tag"
        tick_mode_expr = "CASE WHEN rt.code IS NOT NULL THEN 'REAL_HOGA_TICK_V2_6' ELSE CONCAT('FALLBACK_', b.tick_data_mode) END"
        tick_expr = "COALESCE(rt.tick_intensity, b.tick_intensity)"
        buy_expr = "COALESCE(rt.buy_tick_ratio, b.buy_tick_ratio)"
        large_expr = "COALESCE(rt.large_trade_amount, b.large_trade_amount)"
        bid_expr = "COALESCE(rt.hoga_bid_pressure, b.hoga_bid_pressure)"
        absorb_expr = "COALESCE(rt.hoga_ask_absorption, b.hoga_ask_absorption)"
        spread_expr = "COALESCE(rt.spread_risk, b.spread_risk)"
        realtime_cols_sql = "rt.last_price, rt.tick_count, rt.buy_tick_count, rt.sell_tick_count, rt.bid_total_qty, rt.ask_total_qty, rt.net_buy_amount,"
    else:
        latest_rt_cte = ""
        join_sql = ""
        snapshot_expr = "NULL"
        source_tag_expr = "'NO_REALTIME_TABLE'"
        tick_mode_expr = "CONCAT('FALLBACK_', b.tick_data_mode)"
        tick_expr = "b.tick_intensity"
        buy_expr = "b.buy_tick_ratio"
        large_expr = "b.large_trade_amount"
        bid_expr = "b.hoga_bid_pressure"
        absorb_expr = "b.hoga_ask_absorption"
        spread_expr = "b.spread_risk"
        realtime_cols_sql = "NULL AS last_price, NULL AS tick_count, NULL AS buy_tick_count, NULL AS sell_tick_count, NULL AS bid_total_qty, NULL AS ask_total_qty, NULL AS net_buy_amount,"

    execute(conn, f"""
CREATE TABLE {qident(VIEW_TABLE)} AS
WITH base AS (
    SELECT *
    FROM {qident(source_table)}
)
{latest_rt_cte}
, merged AS (
    SELECT
        b.confirm_rank_no AS source_confirm_rank_no,
        b.display_scope,
        b.board_row_no,
        b.ui_section,
        b.trade_decision,
        b.entry_action,
        b.display_grade,
        b.display_score,
        b.trade_date,
        b.code,
        b.name,
        b.ticker_label,
        b.entry_time,
        b.entry_time_text,
        b.entry_price,
        b.expected_return_pct,
        b.mae_risk_pct,
        b.start_cum_amount,
        b.start_cum_amount_eok,
        b.start_from_day_open_pct,
        b.start_from_day_low_pct,
        b.quantity_scale,
        {snapshot_expr} AS realtime_snapshot_time,
        {source_tag_expr} AS realtime_source_tag,
        {tick_mode_expr} AS tick_data_mode_v2_6,
        {realtime_cols_sql}
        {tick_expr} AS tick_intensity_v2_6,
        {buy_expr} AS buy_tick_ratio_v2_6,
        {large_expr} AS large_trade_amount_v2_6,
        ({large_expr}) / 100000000.0 AS large_trade_amount_eok_v2_6,
        {bid_expr} AS hoga_bid_pressure_v2_6,
        {absorb_expr} AS hoga_ask_absorption_v2_6,
        {spread_expr} AS spread_risk_v2_6,
        b.tick_confirm_score AS prior_tick_confirm_score_v2_5,
        b.tick_confirm_label AS prior_tick_confirm_label_v2_5,
        b.next_action AS prior_next_action_v2_5,
        b.confirm_reason AS prior_confirm_reason_v2_5
    FROM base b
    {join_sql}
), scored AS (
    SELECT
        merged.*,
        LEAST(100.0, GREATEST(0.0,
            IFNULL(merged.tick_intensity_v2_6,0) * 0.27
          + IFNULL(merged.buy_tick_ratio_v2_6,0) * 0.20
          + LEAST(IFNULL(merged.large_trade_amount_eok_v2_6,0), 100.0) * 0.10
          + IFNULL(merged.hoga_bid_pressure_v2_6,0) * 0.19
          + IFNULL(merged.hoga_ask_absorption_v2_6,0) * 0.18
          - IFNULL(merged.spread_risk_v2_6,0) * 0.22
          + IFNULL(merged.expected_return_pct,0) * 0.75
          + GREATEST(IFNULL(merged.mae_risk_pct,0), -6.0) * 0.80
        )) AS tick_confirm_score_v2_6
    FROM merged
), labeled AS (
    SELECT
        scored.*,
        CASE
            WHEN scored.tick_data_mode_v2_6 = 'REAL_HOGA_TICK_V2_6'
             AND scored.tick_confirm_score_v2_6 >= 76
             AND IFNULL(scored.tick_intensity_v2_6,0) >= 55
             AND IFNULL(scored.buy_tick_ratio_v2_6,0) >= 60
             AND IFNULL(scored.hoga_bid_pressure_v2_6,0) >= 56
             AND IFNULL(scored.hoga_ask_absorption_v2_6,0) >= 54
             AND IFNULL(scored.spread_risk_v2_6,0) <= 35
             AND IFNULL(scored.expected_return_pct,0) >= 6
             AND IFNULL(scored.mae_risk_pct,0) >= -4
                THEN 'HOGA_TICK_CONFIRMED_BUY'
            WHEN scored.tick_confirm_score_v2_6 >= 58
             AND IFNULL(scored.expected_return_pct,0) >= 5
             AND IFNULL(scored.spread_risk_v2_6,0) <= 65
                THEN 'WAIT_MORE_TICK'
            ELSE 'HOGA_TICK_REJECT'
        END AS tick_confirm_label_v2_6,
        CASE
            WHEN scored.tick_data_mode_v2_6 = 'REAL_HOGA_TICK_V2_6'
             AND scored.tick_confirm_score_v2_6 >= 76
             AND IFNULL(scored.tick_intensity_v2_6,0) >= 55
             AND IFNULL(scored.buy_tick_ratio_v2_6,0) >= 60
             AND IFNULL(scored.hoga_bid_pressure_v2_6,0) >= 56
             AND IFNULL(scored.hoga_ask_absorption_v2_6,0) >= 54
             AND IFNULL(scored.spread_risk_v2_6,0) <= 35
             AND IFNULL(scored.expected_return_pct,0) >= 6
             AND IFNULL(scored.mae_risk_pct,0) >= -4
                THEN 'PROMOTE_TO_AUTO_BUY_SMALL_REAL_CONFIRMED'
            WHEN scored.tick_confirm_score_v2_6 >= 58
             AND IFNULL(scored.expected_return_pct,0) >= 5
             AND IFNULL(scored.spread_risk_v2_6,0) <= 65
                THEN 'KEEP_WATCH_AND_REQUIRE_NEXT_REAL_TICK'
            ELSE 'REMOVE_FROM_TOP_BOARD'
        END AS next_action_v2_6,
        CONCAT(
            'mode=', scored.tick_data_mode_v2_6,
            ', snapshot=', IFNULL(CAST(scored.realtime_snapshot_time AS CHAR), 'NULL'),
            ', tick=', ROUND(IFNULL(scored.tick_intensity_v2_6,0),1),
            ', buyTick=', ROUND(IFNULL(scored.buy_tick_ratio_v2_6,0),1),
            ', bid=', ROUND(IFNULL(scored.hoga_bid_pressure_v2_6,0),1),
            ', absorb=', ROUND(IFNULL(scored.hoga_ask_absorption_v2_6,0),1),
            ', spreadRisk=', ROUND(IFNULL(scored.spread_risk_v2_6,0),1),
            ', exp=', ROUND(IFNULL(scored.expected_return_pct,0),2),
            ', mae=', ROUND(IFNULL(scored.mae_risk_pct,0),2)
        ) AS confirm_reason_v2_6
    FROM scored
)
SELECT
    ROW_NUMBER() OVER (
        ORDER BY
            CASE
                WHEN tick_confirm_label_v2_6 = 'HOGA_TICK_CONFIRMED_BUY' THEN 1
                WHEN tick_confirm_label_v2_6 = 'WAIT_MORE_TICK' THEN 2
                ELSE 3
            END ASC,
            tick_confirm_score_v2_6 DESC,
            expected_return_pct DESC,
            mae_risk_pct DESC,
            start_cum_amount DESC
    ) AS confirm_rank_no_v2_6,
    labeled.*,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM labeled
""")
    execute(conn, f"ALTER TABLE {qident(VIEW_TABLE)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    execute(conn, f"ALTER TABLE {qident(VIEW_TABLE)} ADD KEY ix_v26_rank (confirm_rank_no_v2_6)")
    execute(conn, f"ALTER TABLE {qident(VIEW_TABLE)} ADD KEY ix_v26_label (tick_confirm_label_v2_6, tick_confirm_score_v2_6)")
    execute(conn, f"ALTER TABLE {qident(VIEW_TABLE)} ADD KEY ix_v26_code_date (code, trade_date)")


def build_summary(conn) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(SUMMARY_TABLE))
    execute(conn, f"""
CREATE TABLE {qident(SUMMARY_TABLE)} AS
SELECT
    tick_confirm_label_v2_6,
    next_action_v2_6,
    tick_data_mode_v2_6,
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
    MIN(confirm_rank_no_v2_6) AS first_confirm_rank_no_v2_6,
    MAX(confirm_rank_no_v2_6) AS last_confirm_rank_no_v2_6,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM {qident(VIEW_TABLE)}
GROUP BY tick_confirm_label_v2_6, next_action_v2_6, tick_data_mode_v2_6
""")
    execute(conn, f"ALTER TABLE {qident(SUMMARY_TABLE)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    execute(conn, f"ALTER TABLE {qident(SUMMARY_TABLE)} ADD COLUMN id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST")
    execute(conn, f"ALTER TABLE {qident(SUMMARY_TABLE)} ADD KEY ix_v26_summary_rank (first_confirm_rank_no_v2_6, avg_tick_confirm_score_v2_6)")


def build_examples(conn, top_n: int) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(EXAMPLE_TABLE))
    execute(conn, f"""
CREATE TABLE {qident(EXAMPLE_TABLE)} AS
SELECT *
FROM {qident(VIEW_TABLE)}
ORDER BY confirm_rank_no_v2_6 ASC
LIMIT {int(top_n)}
""")
    execute(conn, f"ALTER TABLE {qident(EXAMPLE_TABLE)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    execute(conn, f"ALTER TABLE {qident(EXAMPLE_TABLE)} ADD KEY ix_v26_examples_rank (confirm_rank_no_v2_6)")
    execute(conn, f"ALTER TABLE {qident(EXAMPLE_TABLE)} ADD KEY ix_v26_examples_label (tick_confirm_label_v2_6, tick_confirm_score_v2_6)")


def print_rows(title: str, rows) -> None:
    print("\n=== " + title + " ===")
    for row in rows:
        print(dict(row))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build v2.6 real hoga/tick connector view.")
    p.add_argument("--host", default="")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--database", default="")
    p.add_argument("--user", default="")
    p.add_argument("--password", default="")
    p.add_argument("--charset", default="utf8mb4")
    p.add_argument("--mysql-conn", default="")
    p.add_argument("--source-table", default=SOURCE_TABLE_DEFAULT)
    p.add_argument("--realtime-table", default=REALTIME_TABLE_DEFAULT)
    p.add_argument("--snapshot-max-age-minutes", type=int, default=0)
    p.add_argument("--strict-trade-date-join", action="store_true")
    p.add_argument("--preview-limit", type=int, default=40)
    p.add_argument("--example-top-n", type=int, default=80)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    print("=== BUILD v2.6 ST Real Hoga/Tick Connector ===")
    cfg = build_mysql_config(args)
    conn = pymysql.connect(**cfg)
    try:
        assert_source(conn, args.source_table)
        use_real, real_cols, missing_real = realtime_table_is_usable(conn, args.realtime_table)
        create_contract_table(conn)
        create_template_table(conn)
        build_view(conn, args.source_table, args.realtime_table, use_real, real_cols, args.snapshot_max_age_minutes, args.strict_trade_date_join)
        build_summary(conn)
        build_examples(conn, args.example_top_n)
        conn.commit()

        source_rows = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(args.source_table)}")
        view_rows = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(VIEW_TABLE)}")
        real_join_rows = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(VIEW_TABLE)} WHERE tick_data_mode_v2_6 = 'REAL_HOGA_TICK_V2_6'")
        contract_rows = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(CONTRACT_TABLE)}")

        print("source_table=", args.source_table)
        print("realtime_table=", args.realtime_table)
        print("contract_table=", CONTRACT_TABLE)
        print("template_table=", TEMPLATE_TABLE)
        print("view_table=", VIEW_TABLE)
        print("summary_table=", SUMMARY_TABLE)
        print("example_table=", EXAMPLE_TABLE)
        print("source_rows=", to_int(source_rows[0].get("cnt"), 0) if source_rows else 0)
        print("view_rows=", to_int(view_rows[0].get("cnt"), 0) if view_rows else 0)
        print("real_join_rows=", to_int(real_join_rows[0].get("cnt"), 0) if real_join_rows else 0)
        print("contract_column_count=", to_int(contract_rows[0].get("cnt"), 0) if contract_rows else 0)
        print("realtime_table_usable=", "YES" if use_real else "NO")
        print("missing_realtime_columns=", ",".join(missing_real) if missing_real else "NONE")

        print_rows("v2.6 Real Hoga/Tick Contract", fetch_all(conn, f"""
SELECT column_order, column_name, required_flag, data_type_hint, producer_hint, ui_usage, validation_rule
FROM {qident(CONTRACT_TABLE)}
ORDER BY column_order ASC
"""))
        print_rows("v2.6 Real Hoga/Tick Summary", fetch_all(conn, f"""
SELECT *
FROM {qident(SUMMARY_TABLE)}
ORDER BY first_confirm_rank_no_v2_6 ASC, avg_tick_confirm_score_v2_6 DESC
LIMIT 80
"""))
        print_rows("v2.6 Real Hoga/Tick Preview", fetch_all(conn, f"""
SELECT confirm_rank_no_v2_6, ticker_label, tick_confirm_label_v2_6, next_action_v2_6,
       tick_data_mode_v2_6, realtime_snapshot_time, tick_confirm_score_v2_6,
       tick_intensity_v2_6, buy_tick_ratio_v2_6, large_trade_amount_eok_v2_6,
       hoga_bid_pressure_v2_6, hoga_ask_absorption_v2_6, spread_risk_v2_6,
       expected_return_pct, mae_risk_pct, confirm_reason_v2_6
FROM {qident(VIEW_TABLE)}
ORDER BY confirm_rank_no_v2_6 ASC
LIMIT {int(args.preview_limit)}
"""))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
