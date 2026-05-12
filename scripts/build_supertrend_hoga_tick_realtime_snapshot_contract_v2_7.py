#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Leader_Lab v2.7
SuperTrend Hoga/Tick Realtime Snapshot Contract Builder

Purpose:
- Create and validate the real-time MySQL input table consumed by v2.6.
- Keep the server-side contract fixed for VB.NET/Kiwoom realtime producer integration.
- Optionally seed TEST_V2_7 snapshots from the current v2.6 board so the Top Candidate Board can be verified before real tick/hoga producer wiring.

Input:
- supertrend_hoga_tick_real_confirm_view_v2_6

Output:
- supertrend_realtime_hoga_tick_snapshot
- supertrend_hoga_tick_realtime_snapshot_contract_v2_7
- supertrend_hoga_tick_realtime_snapshot_validation_view_v2_7
- supertrend_hoga_tick_realtime_snapshot_summary_v2_7
- supertrend_hoga_tick_realtime_snapshot_examples_v2_7
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
REALTIME_TABLE_DEFAULT = "supertrend_realtime_hoga_tick_snapshot"
CONTRACT_TABLE = "supertrend_hoga_tick_realtime_snapshot_contract_v2_7"
VALIDATION_VIEW = "supertrend_hoga_tick_realtime_snapshot_validation_view_v2_7"
SUMMARY_TABLE = "supertrend_hoga_tick_realtime_snapshot_summary_v2_7"
EXAMPLE_TABLE = "supertrend_hoga_tick_realtime_snapshot_examples_v2_7"
TEST_SOURCE_TAG = "TEST_V2_7"

REQUIRED_SOURCE_COLUMNS = [
    "confirm_rank_no_v2_6", "trade_date", "code", "name", "ticker_label",
    "tick_confirm_label_v2_6", "next_action_v2_6", "tick_confirm_score_v2_6",
    "tick_intensity_v2_6", "buy_tick_ratio_v2_6", "large_trade_amount_v2_6",
    "hoga_bid_pressure_v2_6", "hoga_ask_absorption_v2_6", "spread_risk_v2_6",
    "expected_return_pct", "mae_risk_pct",
]

REQUIRED_REALTIME_COLUMNS = [
    "code", "snapshot_time", "tick_intensity", "buy_tick_ratio", "large_trade_amount",
    "hoga_bid_pressure", "hoga_ask_absorption", "spread_risk",
]

REALTIME_COLUMN_DEFINITIONS = [
    ("id", "BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY"),
    ("code", "VARCHAR(20) NOT NULL"),
    ("trade_date", "DATE NULL"),
    ("snapshot_time", "DATETIME NOT NULL"),
    ("name", "VARCHAR(128) NULL"),
    ("last_price", "DOUBLE NULL"),
    ("tick_intensity", "DOUBLE NOT NULL DEFAULT 0"),
    ("buy_tick_ratio", "DOUBLE NOT NULL DEFAULT 0"),
    ("large_trade_amount", "DOUBLE NOT NULL DEFAULT 0"),
    ("hoga_bid_pressure", "DOUBLE NOT NULL DEFAULT 0"),
    ("hoga_ask_absorption", "DOUBLE NOT NULL DEFAULT 0"),
    ("spread_risk", "DOUBLE NOT NULL DEFAULT 100"),
    ("tick_count", "INT NULL"),
    ("buy_tick_count", "INT NULL"),
    ("sell_tick_count", "INT NULL"),
    ("bid_total_qty", "DOUBLE NULL"),
    ("ask_total_qty", "DOUBLE NULL"),
    ("net_buy_amount", "DOUBLE NULL"),
    ("source_tag", "VARCHAR(80) NOT NULL DEFAULT 'KIWOOM_REALTIME'"),
    ("created_at", "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"),
    ("updated_at", "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
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


def assert_source_view(conn, source_view: str) -> None:
    if not table_exists(conn, source_view):
        raise RuntimeError("source view/table not found: " + source_view + "  먼저 v2.6을 실행하세요.")
    cols = get_columns(conn, source_view)
    missing: list[str] = []
    for col_name in REQUIRED_SOURCE_COLUMNS:
        if col_name not in cols:
            missing.append(col_name)
    if missing:
        raise RuntimeError("v2.7 source required columns missing: " + ", ".join(missing))


def ensure_realtime_table(conn, table_name: str) -> None:
    if not table_exists(conn, table_name):
        column_sql: list[str] = []
        for name, ddl in REALTIME_COLUMN_DEFINITIONS:
            column_sql.append("    " + qident(name) + " " + ddl)
        create_columns_sql = ",\n".join(column_sql)
        create_sql = f"""
CREATE TABLE {qident(table_name)} (
{create_columns_sql},
    KEY ix_v27_realtime_code_time (code, snapshot_time),
    KEY ix_v27_realtime_trade_date_code (trade_date, code),
    KEY ix_v27_realtime_source_tag (source_tag, snapshot_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
"""
        execute(conn, create_sql)
        return

    existing_cols = get_columns(conn, table_name)
    for name, ddl in REALTIME_COLUMN_DEFINITIONS:
        if name not in existing_cols:
            execute(conn, f"ALTER TABLE {qident(table_name)} ADD COLUMN {qident(name)} {ddl}")
    execute(conn, f"ALTER TABLE {qident(table_name)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")


def create_contract_table(conn) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(CONTRACT_TABLE))
    execute(conn, f"""
CREATE TABLE {qident(CONTRACT_TABLE)} (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    column_order INT NOT NULL,
    column_name VARCHAR(80) NOT NULL,
    required_flag TINYINT NOT NULL,
    data_type_hint VARCHAR(80) NOT NULL,
    producer_hint VARCHAR(180) NOT NULL,
    ui_usage VARCHAR(180) NOT NULL,
    validation_rule VARCHAR(300) NOT NULL,
    vbnet_mapping_hint VARCHAR(240) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY ux_v27_contract_col (column_name),
    KEY ix_v27_contract_order (column_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
""")
    rows = [
        (10, "code", 1, "VARCHAR(20)", "Ticker.Code / 종목코드", "join key", "must match Top Candidate Board code", "ticker.Code"),
        (20, "snapshot_time", 1, "DATETIME", "latest tick/hoga snapshot time", "freshness", "latest row per code is used", "DateTime.Now or tick timestamp"),
        (30, "tick_intensity", 1, "DOUBLE", "normalized recent tick speed", "틱강도", "0..100 preferred, >=55 useful", "RecentTickCount normalized"),
        (40, "buy_tick_ratio", 1, "DOUBLE", "buy ticks / all ticks * 100", "매수틱%", "0..100, >=60 useful", "BuyTickCount / TickCount * 100"),
        (50, "large_trade_amount", 1, "DOUBLE", "large execution amount KRW", "대량체결", ">=0", "Sum large tick amount"),
        (60, "hoga_bid_pressure", 1, "DOUBLE", "bid-side pressure score", "매수압력", "0..100, >=56 useful", "Bid pressure score"),
        (70, "hoga_ask_absorption", 1, "DOUBLE", "ask-side absorption score", "매도흡수", "0..100, >=54 useful", "Ask absorption score"),
        (80, "spread_risk", 1, "DOUBLE", "spread/slippage risk", "스프레드위험", "0..100, lower is better, <=35 useful", "Spread risk score"),
        (90, "trade_date", 0, "DATE", "market date", "optional strict join", "YYYY-MM-DD", "Date.Today"),
        (100, "last_price", 0, "DOUBLE", "last trade price", "price sanity", ">0", "CurrentPrice"),
        (110, "tick_count", 0, "INT", "recent tick count", "diagnostic", ">=0", "TickCount"),
        (120, "buy_tick_count", 0, "INT", "recent buy tick count", "diagnostic", ">=0", "BuyTickCount"),
        (130, "sell_tick_count", 0, "INT", "recent sell tick count", "diagnostic", ">=0", "SellTickCount"),
        (140, "bid_total_qty", 0, "DOUBLE", "total bid quantity", "diagnostic", ">=0", "BidTotalQty"),
        (150, "ask_total_qty", 0, "DOUBLE", "total ask quantity", "diagnostic", ">=0", "AskTotalQty"),
        (160, "net_buy_amount", 0, "DOUBLE", "net buy amount KRW", "diagnostic", "can be negative", "NetBuyAmount"),
        (170, "source_tag", 0, "VARCHAR(80)", "producer name", "audit", "KIWOOM_REALTIME or TEST_V2_7", "constant"),
    ]
    with conn.cursor() as cur:
        cur.executemany(f"""
INSERT INTO {qident(CONTRACT_TABLE)}
(column_order, column_name, required_flag, data_type_hint, producer_hint, ui_usage, validation_rule, vbnet_mapping_hint)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
""", rows)


def seed_test_snapshots(conn, source_view: str, realtime_table: str, top_n: int) -> None:
    execute(conn, f"DELETE FROM {qident(realtime_table)} WHERE source_tag = %s", (TEST_SOURCE_TAG,))
    execute(conn, f"""
INSERT INTO {qident(realtime_table)} (
    code, trade_date, snapshot_time, name, last_price,
    tick_intensity, buy_tick_ratio, large_trade_amount,
    hoga_bid_pressure, hoga_ask_absorption, spread_risk,
    tick_count, buy_tick_count, sell_tick_count,
    bid_total_qty, ask_total_qty, net_buy_amount, source_tag
)
SELECT
    b.code,
    b.trade_date,
    NOW() AS snapshot_time,
    b.name,
    NULL AS last_price,
    CASE WHEN b.confirm_rank_no_v2_6 <= {int(top_n)}
         THEN GREATEST(IFNULL(b.tick_intensity_v2_6,0), 78.0)
         ELSE IFNULL(b.tick_intensity_v2_6,0)
    END AS tick_intensity,
    CASE WHEN b.confirm_rank_no_v2_6 <= {int(top_n)}
         THEN GREATEST(IFNULL(b.buy_tick_ratio_v2_6,0), 72.0)
         ELSE IFNULL(b.buy_tick_ratio_v2_6,0)
    END AS buy_tick_ratio,
    IFNULL(b.large_trade_amount_v2_6,0) AS large_trade_amount,
    CASE WHEN b.confirm_rank_no_v2_6 <= {int(top_n)}
         THEN GREATEST(IFNULL(b.hoga_bid_pressure_v2_6,0), 70.0)
         ELSE IFNULL(b.hoga_bid_pressure_v2_6,0)
    END AS hoga_bid_pressure,
    CASE WHEN b.confirm_rank_no_v2_6 <= {int(top_n)}
         THEN GREATEST(IFNULL(b.hoga_ask_absorption_v2_6,0), 68.0)
         ELSE IFNULL(b.hoga_ask_absorption_v2_6,0)
    END AS hoga_ask_absorption,
    CASE WHEN b.confirm_rank_no_v2_6 <= {int(top_n)}
         THEN LEAST(IFNULL(b.spread_risk_v2_6,100), 18.0)
         ELSE IFNULL(b.spread_risk_v2_6,100)
    END AS spread_risk,
    CASE WHEN b.confirm_rank_no_v2_6 <= {int(top_n)} THEN 80 ELSE 30 END AS tick_count,
    CASE WHEN b.confirm_rank_no_v2_6 <= {int(top_n)} THEN 58 ELSE 18 END AS buy_tick_count,
    CASE WHEN b.confirm_rank_no_v2_6 <= {int(top_n)} THEN 22 ELSE 12 END AS sell_tick_count,
    NULL AS bid_total_qty,
    NULL AS ask_total_qty,
    NULL AS net_buy_amount,
    %s AS source_tag
FROM {qident(source_view)} b
ORDER BY b.confirm_rank_no_v2_6 ASC
""", (TEST_SOURCE_TAG,))


def build_validation_view(conn, source_view: str, realtime_table: str) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(VALIDATION_VIEW))
    execute(conn, f"""
CREATE TABLE {qident(VALIDATION_VIEW)} AS
WITH latest_snapshot AS (
    SELECT
        r.*,
        ROW_NUMBER() OVER (PARTITION BY r.code ORDER BY r.snapshot_time DESC, r.id DESC) AS rn
    FROM {qident(realtime_table)} r
), joined AS (
    SELECT
        b.confirm_rank_no_v2_6 AS board_rank_no,
        b.trade_date,
        b.code,
        b.name,
        b.ticker_label,
        b.tick_confirm_label_v2_6 AS before_label_v2_6,
        b.tick_confirm_score_v2_6 AS before_score_v2_6,
        b.expected_return_pct,
        b.mae_risk_pct,
        s.snapshot_time,
        s.source_tag,
        s.tick_intensity,
        s.buy_tick_ratio,
        s.large_trade_amount,
        s.hoga_bid_pressure,
        s.hoga_ask_absorption,
        s.spread_risk,
        CASE WHEN s.code IS NULL THEN 'MISSING_SNAPSHOT' ELSE 'SNAPSHOT_READY' END AS snapshot_status,
        CASE
            WHEN s.code IS NOT NULL
             AND s.tick_intensity >= 55
             AND s.buy_tick_ratio >= 60
             AND s.hoga_bid_pressure >= 56
             AND s.hoga_ask_absorption >= 54
             AND s.spread_risk <= 35
                THEN 'REALTIME_INPUT_PASS'
            WHEN s.code IS NOT NULL THEN 'REALTIME_INPUT_WEAK'
            ELSE 'REALTIME_INPUT_MISSING'
        END AS realtime_input_label_v2_7,
        CURRENT_TIMESTAMP AS created_at,
        CURRENT_TIMESTAMP AS updated_at
    FROM {qident(source_view)} b
    LEFT JOIN latest_snapshot s
      ON s.code = b.code
     AND s.rn = 1
)
SELECT *
FROM joined
ORDER BY
    CASE realtime_input_label_v2_7
        WHEN 'REALTIME_INPUT_PASS' THEN 1
        WHEN 'REALTIME_INPUT_WEAK' THEN 2
        ELSE 3
    END ASC,
    before_score_v2_6 DESC,
    expected_return_pct DESC,
    board_rank_no ASC
""")
    execute(conn, f"ALTER TABLE {qident(VALIDATION_VIEW)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    execute(conn, f"ALTER TABLE {qident(VALIDATION_VIEW)} ADD KEY ix_v27_validation_code (code)")
    execute(conn, f"ALTER TABLE {qident(VALIDATION_VIEW)} ADD KEY ix_v27_validation_label (realtime_input_label_v2_7, before_score_v2_6)")


def build_summary(conn) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(SUMMARY_TABLE))
    execute(conn, f"""
CREATE TABLE {qident(SUMMARY_TABLE)} AS
SELECT
    realtime_input_label_v2_7,
    snapshot_status,
    source_tag,
    COUNT(*) AS row_count,
    AVG(tick_intensity) AS avg_tick_intensity,
    AVG(buy_tick_ratio) AS avg_buy_tick_ratio,
    AVG(large_trade_amount / 100000000.0) AS avg_large_trade_amount_eok,
    AVG(hoga_bid_pressure) AS avg_hoga_bid_pressure,
    AVG(hoga_ask_absorption) AS avg_hoga_ask_absorption,
    AVG(spread_risk) AS avg_spread_risk,
    AVG(expected_return_pct) AS avg_expected_return_pct,
    AVG(mae_risk_pct) AS avg_mae_risk_pct,
    MIN(board_rank_no) AS first_board_rank_no,
    MAX(board_rank_no) AS last_board_rank_no,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM {qident(VALIDATION_VIEW)}
GROUP BY realtime_input_label_v2_7, snapshot_status, source_tag
""")
    execute(conn, f"ALTER TABLE {qident(SUMMARY_TABLE)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    execute(conn, f"ALTER TABLE {qident(SUMMARY_TABLE)} ADD COLUMN id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST")


def build_examples(conn, top_n: int) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(EXAMPLE_TABLE))
    execute(conn, f"""
CREATE TABLE {qident(EXAMPLE_TABLE)} AS
SELECT *
FROM {qident(VALIDATION_VIEW)}
ORDER BY
    CASE realtime_input_label_v2_7
        WHEN 'REALTIME_INPUT_PASS' THEN 1
        WHEN 'REALTIME_INPUT_WEAK' THEN 2
        ELSE 3
    END ASC,
    before_score_v2_6 DESC,
    expected_return_pct DESC,
    board_rank_no ASC
LIMIT {int(top_n)}
""")
    execute(conn, f"ALTER TABLE {qident(EXAMPLE_TABLE)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    execute(conn, f"ALTER TABLE {qident(EXAMPLE_TABLE)} ADD KEY ix_v27_examples_code (code)")


def print_rows(title: str, rows) -> None:
    print("\n=== " + title + " ===")
    for row in rows:
        print(dict(row))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build v2.7 realtime hoga/tick snapshot contract.")
    p.add_argument("--host", default="")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--database", default="")
    p.add_argument("--user", default="")
    p.add_argument("--password", default="")
    p.add_argument("--charset", default="utf8mb4")
    p.add_argument("--mysql-conn", default="")
    p.add_argument("--source-view", default=SOURCE_VIEW_DEFAULT)
    p.add_argument("--realtime-table", default=REALTIME_TABLE_DEFAULT)
    p.add_argument("--seed-test-snapshots", action="store_true")
    p.add_argument("--no-seed-test-snapshots", action="store_true")
    p.add_argument("--test-promote-top-n", type=int, default=7)
    p.add_argument("--example-top-n", type=int, default=80)
    p.add_argument("--preview-limit", type=int, default=40)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    print("=== BUILD v2.7 ST Realtime Hoga/Tick Snapshot Contract ===")
    cfg = build_mysql_config(args)
    conn = pymysql.connect(**cfg)
    try:
        assert_source_view(conn, args.source_view)
        ensure_realtime_table(conn, args.realtime_table)
        create_contract_table(conn)
        do_seed = bool(args.seed_test_snapshots and not args.no_seed_test_snapshots)
        if do_seed:
            seed_test_snapshots(conn, args.source_view, args.realtime_table, args.test_promote_top_n)
        build_validation_view(conn, args.source_view, args.realtime_table)
        build_summary(conn)
        build_examples(conn, args.example_top_n)
        conn.commit()

        table_cols = get_columns(conn, args.realtime_table)
        missing = [c for c in REQUIRED_REALTIME_COLUMNS if c not in table_cols]
        total_snapshots = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(args.realtime_table)}")
        test_snapshots = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(args.realtime_table)} WHERE source_tag = %s", (TEST_SOURCE_TAG,))
        validation_rows = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(VALIDATION_VIEW)}")
        pass_rows = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(VALIDATION_VIEW)} WHERE realtime_input_label_v2_7 = 'REALTIME_INPUT_PASS'")

        print("source_view=", args.source_view)
        print("realtime_table=", args.realtime_table)
        print("contract_table=", CONTRACT_TABLE)
        print("validation_view=", VALIDATION_VIEW)
        print("summary_table=", SUMMARY_TABLE)
        print("example_table=", EXAMPLE_TABLE)
        print("seed_test_snapshots=", "YES" if do_seed else "NO")
        print("missing_realtime_columns=", ",".join(missing) if missing else "NONE")
        print("total_snapshot_rows=", to_int(total_snapshots[0].get("cnt"), 0) if total_snapshots else 0)
        print("test_snapshot_rows=", to_int(test_snapshots[0].get("cnt"), 0) if test_snapshots else 0)
        print("validation_rows=", to_int(validation_rows[0].get("cnt"), 0) if validation_rows else 0)
        print("realtime_input_pass_rows=", to_int(pass_rows[0].get("cnt"), 0) if pass_rows else 0)

        print_rows("v2.7 Realtime Snapshot Summary", fetch_all(conn, f"""
SELECT *
FROM {qident(SUMMARY_TABLE)}
ORDER BY first_board_rank_no ASC, row_count DESC
"""))
        print_rows("v2.7 Realtime Snapshot Contract", fetch_all(conn, f"""
SELECT column_order, column_name, required_flag, data_type_hint, producer_hint, ui_usage, validation_rule, vbnet_mapping_hint
FROM {qident(CONTRACT_TABLE)}
ORDER BY column_order ASC
"""))
        print_rows("v2.7 Realtime Snapshot Preview", fetch_all(conn, f"""
SELECT board_rank_no, ticker_label, before_label_v2_6, before_score_v2_6,
       realtime_input_label_v2_7, snapshot_status, source_tag, snapshot_time,
       tick_intensity, buy_tick_ratio, large_trade_amount / 100000000.0 AS large_trade_amount_eok,
       hoga_bid_pressure, hoga_ask_absorption, spread_risk,
       expected_return_pct, mae_risk_pct
FROM {qident(VALIDATION_VIEW)}
ORDER BY
    CASE realtime_input_label_v2_7
        WHEN 'REALTIME_INPUT_PASS' THEN 1
        WHEN 'REALTIME_INPUT_WEAK' THEN 2
        ELSE 3
    END ASC,
    before_score_v2_6 DESC,
    expected_return_pct DESC,
    board_rank_no ASC
LIMIT {int(args.preview_limit)}
"""))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
