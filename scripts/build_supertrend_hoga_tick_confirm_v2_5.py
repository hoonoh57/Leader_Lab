#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Leader_Lab v2.5
SuperTrend Hoga/Tick Confirmation Builder

Input:
- supertrend_top_candidate_board_view_v2_4

Output:
- supertrend_hoga_tick_confirm_columns_v2_5
- supertrend_hoga_tick_confirm_view_v2_5
- supertrend_hoga_tick_confirm_summary_v2_5
- supertrend_hoga_tick_confirm_examples_v2_5

Purpose:
- Convert WATCH_HOGA_TICK rows from the v2.4 Top Candidate Board into a confirmation board.
- Keep the live decision contract explicit:
  WATCH_HOGA_TICK -> HOGA_TICK_CONFIRMED_BUY / WAIT_MORE_TICK / HOGA_TICK_REJECT
- Use real hoga/tick columns when the source table has them.
- Use deterministic proxy features from v2.4 board columns when real hoga/tick columns are not yet attached.
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

SOURCE_TABLE_DEFAULT = "supertrend_top_candidate_board_view_v2_4"
COLUMN_TABLE = "supertrend_hoga_tick_confirm_columns_v2_5"
VIEW_TABLE = "supertrend_hoga_tick_confirm_view_v2_5"
SUMMARY_TABLE = "supertrend_hoga_tick_confirm_summary_v2_5"
EXAMPLE_TABLE = "supertrend_hoga_tick_confirm_examples_v2_5"

REQUIRED_SOURCE_COLUMNS = [
    "display_scope", "board_row_no", "ui_section", "trade_decision", "entry_action",
    "display_grade", "display_score", "trade_date", "code", "name", "ticker_label",
    "entry_time", "entry_time_text", "entry_price", "expected_return_pct", "mae_risk_pct",
    "start_cum_amount", "start_cum_amount_eok", "start_from_day_open_pct",
    "start_from_day_low_pct", "quantity_scale", "short_reason",
]

REAL_TICK_COLUMNS = [
    "tick_intensity", "buy_tick_ratio", "large_trade_amount",
    "hoga_bid_pressure", "hoga_ask_absorption", "spread_risk",
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
        result.add(str(row.get("column_name")))
    return result


def assert_source(conn, table_name: str) -> set[str]:
    if not table_exists(conn, table_name):
        raise RuntimeError("source table not found: " + table_name)
    cols = get_columns(conn, table_name)
    missing: list[str] = []
    for col_name in REQUIRED_SOURCE_COLUMNS:
        if col_name not in cols:
            missing.append(col_name)
    if missing:
        raise RuntimeError("v2.5 source required columns missing: " + ", ".join(missing))
    return cols


def create_columns(conn) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(COLUMN_TABLE))
    execute(conn, f"""
CREATE TABLE {qident(COLUMN_TABLE)} (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    column_order INT NOT NULL,
    column_key VARCHAR(80) NOT NULL,
    source_column VARCHAR(80) NOT NULL,
    header_text_ko VARCHAR(80) NOT NULL,
    header_text_en VARCHAR(80) NOT NULL,
    width_px INT NOT NULL,
    align_key VARCHAR(20) NOT NULL,
    format_key VARCHAR(40) NOT NULL,
    visible_compact TINYINT NOT NULL,
    visible_test TINYINT NOT NULL,
    pinned_left TINYINT NOT NULL,
    color_rule_key VARCHAR(60) NOT NULL,
    tooltip_ko VARCHAR(500) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY ux_v25_col_key (column_key),
    KEY ix_v25_col_order (column_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
""")

    rows = [
        (10, "confirm_rank", "confirm_rank_no", "확인순위", "Confirm Rank", 70, "CENTER", "INT", 1, 1, 1, "RANK", "호가/틱 확인 보드 순위"),
        (20, "ticker", "ticker_label", "종목", "Ticker", 150, "LEFT", "TEXT", 1, 1, 1, "TICKER", "종목코드와 종목명"),
        (30, "confirm_label", "tick_confirm_label", "틱판정", "Tick Label", 160, "CENTER", "BADGE", 1, 1, 0, "CONFIRM", "HOGA_TICK_CONFIRMED_BUY / WAIT_MORE_TICK / HOGA_TICK_REJECT"),
        (40, "confirm_score", "tick_confirm_score", "틱점수", "Tick Score", 82, "RIGHT", "DECIMAL1", 1, 1, 0, "SCORE_HEAT", "호가/틱 확인 종합 점수"),
        (50, "tick_intensity", "tick_intensity", "틱강도", "Tick Intensity", 80, "RIGHT", "DECIMAL1", 1, 1, 0, "TICK", "실제 tick_intensity가 있으면 실제값, 없으면 v2.4 기반 프록시"),
        (60, "buy_tick_ratio", "buy_tick_ratio", "매수틱%", "Buy Tick %", 82, "RIGHT", "PCT1", 1, 1, 0, "BUY_RATIO", "실제 buy_tick_ratio가 있으면 실제값, 없으면 v2.4 기반 프록시"),
        (70, "large_trade", "large_trade_amount_eok", "대량체결", "Large Trade", 90, "RIGHT", "EOK1", 1, 1, 0, "AMOUNT", "대량체결 추정 또는 실제값, 억원 단위"),
        (80, "bid_pressure", "hoga_bid_pressure", "매수압력", "Bid Pressure", 88, "RIGHT", "DECIMAL1", 1, 1, 0, "BID", "호가 매수 압력 실제값 또는 프록시"),
        (90, "ask_absorption", "hoga_ask_absorption", "매도흡수", "Ask Absorb", 88, "RIGHT", "DECIMAL1", 1, 1, 0, "ABSORB", "매도잔량 흡수 실제값 또는 프록시"),
        (100, "spread_risk", "spread_risk", "스프레드위험", "Spread Risk", 96, "RIGHT", "DECIMAL1", 1, 1, 0, "RISK", "스프레드/역행 위험 실제값 또는 프록시"),
        (110, "expected_return", "expected_return_pct", "기대%", "Exp %", 78, "RIGHT", "PCT2", 1, 1, 0, "RETURN", "v2.4 기준 기대수익"),
        (120, "mae", "mae_risk_pct", "MAE%", "MAE %", 78, "RIGHT", "PCT2", 1, 1, 0, "RISK", "진입 후 최대 역행 위험"),
        (130, "amount", "start_cum_amount_eok", "시작대금", "Start Amt", 88, "RIGHT", "EOK1", 1, 1, 0, "AMOUNT", "ST 시작 시점 누적 거래대금, 억원 단위"),
        (140, "open_pct", "start_from_day_open_pct", "시가대비", "Open %", 78, "RIGHT", "PCT2", 1, 1, 0, "OPEN_PCT", "당일 시가 대비 상승률"),
        (150, "action", "next_action", "다음액션", "Next Action", 170, "CENTER", "BADGE", 1, 1, 0, "ACTION", "확인 후 실행 액션"),
        (160, "reason", "confirm_reason", "판정근거", "Reason", 480, "LEFT", "TEXT", 1, 1, 0, "REASON", "호가/틱 확인 판정 근거"),
    ]

    insert_sql = f"""
INSERT INTO {qident(COLUMN_TABLE)}
(column_order, column_key, source_column, header_text_ko, header_text_en, width_px,
 align_key, format_key, visible_compact, visible_test, pinned_left, color_rule_key, tooltip_ko)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""
    with conn.cursor() as cur:
        cur.executemany(insert_sql, rows)


def expr_or_proxy(cols: set[str], real_col: str, proxy_sql: str) -> str:
    if real_col in cols:
        return "b." + qident(real_col)
    return proxy_sql


def build_view(conn, source_table: str, cols: set[str]) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(VIEW_TABLE))

    real_cols = [c for c in REAL_TICK_COLUMNS if c in cols]
    tick_data_mode_sql = "'REAL_OR_PARTIAL'" if real_cols else "'PROXY_FROM_V2_4'"

    tick_intensity_expr = expr_or_proxy(cols, "tick_intensity", "LEAST(100.0, GREATEST(0.0, IFNULL(b.display_score,0) * 0.35 + IFNULL(b.expected_return_pct,0) * 2.20 + LEAST(IFNULL(b.start_cum_amount_eok,0), 150) * 0.12 + GREATEST(IFNULL(b.mae_risk_pct,0), -8) * 1.50))")
    buy_tick_ratio_expr = expr_or_proxy(cols, "buy_tick_ratio", "LEAST(100.0, GREATEST(0.0, 48.0 + IFNULL(b.expected_return_pct,0) * 1.35 + IFNULL(b.start_from_day_low_pct,0) * 0.90 + GREATEST(IFNULL(b.mae_risk_pct,0), -10) * 1.80))")
    large_trade_amount_expr = expr_or_proxy(cols, "large_trade_amount", "IFNULL(b.start_cum_amount,0) * 0.18")
    hoga_bid_pressure_expr = expr_or_proxy(cols, "hoga_bid_pressure", "LEAST(100.0, GREATEST(0.0, 45.0 + IFNULL(b.start_from_day_low_pct,0) * 2.00 + IFNULL(b.expected_return_pct,0) * 0.75 - ABS(IFNULL(b.mae_risk_pct,0)) * 1.20))")
    hoga_ask_absorption_expr = expr_or_proxy(cols, "hoga_ask_absorption", "LEAST(100.0, GREATEST(0.0, 42.0 + LEAST(IFNULL(b.start_cum_amount_eok,0), 180) * 0.18 + IFNULL(b.expected_return_pct,0) * 0.85 - ABS(IFNULL(b.mae_risk_pct,0)) * 1.10))")
    spread_risk_expr = expr_or_proxy(cols, "spread_risk", "LEAST(100.0, GREATEST(0.0, ABS(IFNULL(b.mae_risk_pct,0)) * 8.0 + GREATEST(IFNULL(b.start_from_day_open_pct,0) - 8.0, 0) * 3.0))")

    execute(conn, f"""
CREATE TABLE {qident(VIEW_TABLE)} AS
WITH base AS (
    SELECT
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
        b.short_reason,
        {tick_intensity_expr} AS tick_intensity,
        {buy_tick_ratio_expr} AS buy_tick_ratio,
        {large_trade_amount_expr} AS large_trade_amount,
        {hoga_bid_pressure_expr} AS hoga_bid_pressure,
        {hoga_ask_absorption_expr} AS hoga_ask_absorption,
        {spread_risk_expr} AS spread_risk,
        {tick_data_mode_sql} AS tick_data_mode
    FROM {qident(source_table)} b
    WHERE b.display_scope = 'TEST_WITH_HOGA_TICK_ALL'
      AND b.trade_decision = 'WATCH_HOGA_TICK'
), scored AS (
    SELECT
        base.*,
        base.large_trade_amount / 100000000.0 AS large_trade_amount_eok,
        LEAST(100.0, GREATEST(0.0,
            IFNULL(base.tick_intensity,0) * 0.25
          + IFNULL(base.buy_tick_ratio,0) * 0.18
          + LEAST(IFNULL(base.large_trade_amount,0) / 100000000.0, 100.0) * 0.12
          + IFNULL(base.hoga_bid_pressure,0) * 0.18
          + IFNULL(base.hoga_ask_absorption,0) * 0.17
          - IFNULL(base.spread_risk,0) * 0.20
          + IFNULL(base.expected_return_pct,0) * 0.80
        )) AS tick_confirm_score
    FROM base
), labeled AS (
    SELECT
        scored.*,
        CASE
            WHEN scored.tick_confirm_score >= 78
             AND IFNULL(scored.buy_tick_ratio,0) >= 62
             AND IFNULL(scored.hoga_bid_pressure,0) >= 58
             AND IFNULL(scored.hoga_ask_absorption,0) >= 55
             AND IFNULL(scored.spread_risk,0) <= 35
             AND IFNULL(scored.expected_return_pct,0) >= 7
             AND IFNULL(scored.mae_risk_pct,0) >= -4
                THEN 'HOGA_TICK_CONFIRMED_BUY'
            WHEN scored.tick_confirm_score >= 58
             AND IFNULL(scored.expected_return_pct,0) >= 5
             AND IFNULL(scored.spread_risk,0) <= 65
                THEN 'WAIT_MORE_TICK'
            ELSE 'HOGA_TICK_REJECT'
        END AS tick_confirm_label,
        CASE
            WHEN scored.tick_confirm_score >= 78
             AND IFNULL(scored.buy_tick_ratio,0) >= 62
             AND IFNULL(scored.hoga_bid_pressure,0) >= 58
             AND IFNULL(scored.hoga_ask_absorption,0) >= 55
             AND IFNULL(scored.spread_risk,0) <= 35
             AND IFNULL(scored.expected_return_pct,0) >= 7
             AND IFNULL(scored.mae_risk_pct,0) >= -4
                THEN 'PROMOTE_TO_AUTO_BUY_SMALL'
            WHEN scored.tick_confirm_score >= 58
             AND IFNULL(scored.expected_return_pct,0) >= 5
             AND IFNULL(scored.spread_risk,0) <= 65
                THEN 'KEEP_WATCH_AND_REQUIRE_NEXT_TICK'
            ELSE 'REMOVE_FROM_TOP_BOARD'
        END AS next_action,
        CONCAT(
            'tick=', ROUND(IFNULL(scored.tick_intensity,0),1),
            ', buyTick=', ROUND(IFNULL(scored.buy_tick_ratio,0),1),
            ', bid=', ROUND(IFNULL(scored.hoga_bid_pressure,0),1),
            ', absorb=', ROUND(IFNULL(scored.hoga_ask_absorption,0),1),
            ', spreadRisk=', ROUND(IFNULL(scored.spread_risk,0),1),
            ', exp=', ROUND(IFNULL(scored.expected_return_pct,0),2),
            ', mae=', ROUND(IFNULL(scored.mae_risk_pct,0),2),
            ', mode=', scored.tick_data_mode
        ) AS confirm_reason
    FROM scored
)
SELECT
    ROW_NUMBER() OVER (
        ORDER BY
            CASE
                WHEN tick_confirm_label = 'HOGA_TICK_CONFIRMED_BUY' THEN 1
                WHEN tick_confirm_label = 'WAIT_MORE_TICK' THEN 2
                ELSE 3
            END ASC,
            tick_confirm_score DESC,
            expected_return_pct DESC,
            mae_risk_pct DESC,
            start_cum_amount DESC
    ) AS confirm_rank_no,
    labeled.*,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM labeled
""")
    execute(conn, f"ALTER TABLE {qident(VIEW_TABLE)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    execute(conn, f"ALTER TABLE {qident(VIEW_TABLE)} ADD KEY ix_v25_confirm_rank (confirm_rank_no)")
    execute(conn, f"ALTER TABLE {qident(VIEW_TABLE)} ADD KEY ix_v25_confirm_label (tick_confirm_label, tick_confirm_score)")
    execute(conn, f"ALTER TABLE {qident(VIEW_TABLE)} ADD KEY ix_v25_code_date (code, trade_date)")


def build_summary(conn) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(SUMMARY_TABLE))
    execute(conn, f"""
CREATE TABLE {qident(SUMMARY_TABLE)} AS
SELECT
    tick_confirm_label,
    next_action,
    tick_data_mode,
    COUNT(*) AS row_count,
    AVG(tick_confirm_score) AS avg_tick_confirm_score,
    AVG(tick_intensity) AS avg_tick_intensity,
    AVG(buy_tick_ratio) AS avg_buy_tick_ratio,
    AVG(large_trade_amount_eok) AS avg_large_trade_amount_eok,
    AVG(hoga_bid_pressure) AS avg_hoga_bid_pressure,
    AVG(hoga_ask_absorption) AS avg_hoga_ask_absorption,
    AVG(spread_risk) AS avg_spread_risk,
    AVG(expected_return_pct) AS avg_expected_return_pct,
    AVG(mae_risk_pct) AS avg_mae_risk_pct,
    AVG(start_cum_amount_eok) AS avg_start_cum_amount_eok,
    MIN(confirm_rank_no) AS first_confirm_rank_no,
    MAX(confirm_rank_no) AS last_confirm_rank_no,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM {qident(VIEW_TABLE)}
GROUP BY tick_confirm_label, next_action, tick_data_mode
""")
    execute(conn, f"ALTER TABLE {qident(SUMMARY_TABLE)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    execute(conn, f"ALTER TABLE {qident(SUMMARY_TABLE)} ADD COLUMN id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST")
    execute(conn, f"ALTER TABLE {qident(SUMMARY_TABLE)} ADD KEY ix_v25_summary_rank (first_confirm_rank_no, avg_tick_confirm_score)")


def build_examples(conn, example_top_n: int) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(EXAMPLE_TABLE))
    execute(conn, f"""
CREATE TABLE {qident(EXAMPLE_TABLE)} AS
SELECT *
FROM {qident(VIEW_TABLE)}
ORDER BY confirm_rank_no ASC
LIMIT {int(example_top_n)}
""")
    execute(conn, f"ALTER TABLE {qident(EXAMPLE_TABLE)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    execute(conn, f"ALTER TABLE {qident(EXAMPLE_TABLE)} ADD KEY ix_v25_examples_rank (confirm_rank_no)")
    execute(conn, f"ALTER TABLE {qident(EXAMPLE_TABLE)} ADD KEY ix_v25_examples_label (tick_confirm_label, tick_confirm_score)")


def print_rows(title: str, rows) -> None:
    print("\n=== " + title + " ===")
    for row in rows:
        print(dict(row))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build v2.5 Hoga/Tick confirmation board from v2.4 Top Candidate Board.")
    p.add_argument("--host", default="")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--database", default="")
    p.add_argument("--user", default="")
    p.add_argument("--password", default="")
    p.add_argument("--charset", default="utf8mb4")
    p.add_argument("--mysql-conn", default="")
    p.add_argument("--source-table", default=SOURCE_TABLE_DEFAULT)
    p.add_argument("--preview-limit", type=int, default=40)
    p.add_argument("--example-top-n", type=int, default=80)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    print("=== BUILD v2.5 ST Hoga/Tick Confirmation ===")
    cfg = build_mysql_config(args)
    conn = pymysql.connect(**cfg)
    try:
        cols = assert_source(conn, args.source_table)
        real_cols = [c for c in REAL_TICK_COLUMNS if c in cols]
        create_columns(conn)
        build_view(conn, args.source_table, cols)
        build_summary(conn)
        build_examples(conn, args.example_top_n)
        conn.commit()

        source_rows = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(args.source_table)}")
        view_rows = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(VIEW_TABLE)}")
        column_rows = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(COLUMN_TABLE)}")

        print("source_table=", args.source_table)
        print("view_table=", VIEW_TABLE)
        print("summary_table=", SUMMARY_TABLE)
        print("example_table=", EXAMPLE_TABLE)
        print("column_table=", COLUMN_TABLE)
        print("source_rows=", to_int(source_rows[0].get("cnt"), 0) if source_rows else 0)
        print("watch_hoga_tick_rows=", to_int(view_rows[0].get("cnt"), 0) if view_rows else 0)
        print("column_count=", to_int(column_rows[0].get("cnt"), 0) if column_rows else 0)
        print("real_tick_columns_found=", ",".join(real_cols) if real_cols else "NONE_PROXY_FROM_V2_4")

        print_rows("v2.5 Hoga/Tick Confirm Summary", fetch_all(conn, f"""
SELECT *
FROM {qident(SUMMARY_TABLE)}
ORDER BY first_confirm_rank_no ASC, avg_tick_confirm_score DESC
LIMIT 80
"""))
        print_rows("v2.5 Hoga/Tick Confirm Column Spec", fetch_all(conn, f"""
SELECT column_order, column_key, source_column, header_text_ko, width_px,
       visible_compact, visible_test, pinned_left, format_key, color_rule_key
FROM {qident(COLUMN_TABLE)}
ORDER BY column_order ASC
"""))
        print_rows("v2.5 Hoga/Tick Confirm Preview", fetch_all(conn, f"""
SELECT confirm_rank_no, ticker_label, tick_confirm_label, next_action,
       tick_confirm_score, tick_intensity, buy_tick_ratio, large_trade_amount_eok,
       hoga_bid_pressure, hoga_ask_absorption, spread_risk,
       expected_return_pct, mae_risk_pct, start_cum_amount_eok, confirm_reason
FROM {qident(VIEW_TABLE)}
ORDER BY confirm_rank_no ASC
LIMIT {int(args.preview_limit)}
"""))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
