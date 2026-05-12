#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Leader_Lab v2.4
SuperTrend Top Candidate Board UI Builder

Input:
- supertrend_realtime_trade_board_screen_v2_3

Output:
- supertrend_top_candidate_board_columns_v2_4
- supertrend_top_candidate_board_sections_v2_4
- supertrend_top_candidate_board_view_v2_4
- supertrend_top_candidate_board_summary_v2_4

Purpose:
- Fix the realtime Top Candidate Board column contract.
- Provide one normalized UI row table for two display modes:
  1) COMPACT_SCREEN
  2) TEST_WITH_HOGA_TICK_ALL
- Keep WATCH_HOGA_TICK rows selectable during verification without polluting the compact trading screen.
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

SOURCE_TABLE_DEFAULT = "supertrend_realtime_trade_board_screen_v2_3"
COLUMN_TABLE = "supertrend_top_candidate_board_columns_v2_4"
SECTION_TABLE = "supertrend_top_candidate_board_sections_v2_4"
VIEW_TABLE = "supertrend_top_candidate_board_view_v2_4"
SUMMARY_TABLE = "supertrend_top_candidate_board_summary_v2_4"

REQUIRED_SOURCE_COLUMNS = [
    "trade_date",
    "code",
    "name",
    "entry_action",
    "display_grade",
    "display_score",
    "entry_time",
    "entry_price",
    "expected_return_pct",
    "mae_risk_pct",
    "start_cum_amount",
    "start_from_day_open_pct",
    "start_from_day_low_pct",
    "quantity_scale",
    "trade_decision",
    "risk_message",
    "chart_open_priority",
    "ui_section",
    "ui_visibility_reason",
    "ui_sort_bucket",
    "compact_visible",
    "test_full_visible",
    "hoga_tick_test_visible",
]

OPTIONAL_SOURCE_COLUMNS = [
    "st_period",
    "st_multiplier",
    "segment_no",
    "st_up_start_time",
    "final_entry_grade_v2_0",
    "entry_score_v2_0",
    "execution_score_v1_9",
    "top_rank_score_v2_1",
    "top_rank_action_priority_v2_1",
    "recommended_entry_policy_v1_9",
    "selected_entry_timing_v1_8",
    "next_bar_return_pct",
    "next_bar_mae_pct",
    "pullback_return_pct",
    "pullback_mae_pct",
    "score_total",
    "filter_label_v1_6",
    "filter_grade_v1_6",
    "filter_score_v1_6",
    "risk_band_v2_0",
    "entry_reason_v2_0",
    "policy_reason_v1_9",
    "top_rank_reason_v2_1",
    "candidate_count_same_code_v2_1",
    "auto_count_same_code_v2_1",
    "wait_count_same_code_v2_1",
    "confirm_count_same_code_v2_1",
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
    missing = []
    for c in REQUIRED_SOURCE_COLUMNS:
        if c not in cols:
            missing.append(c)
    if missing:
        raise RuntimeError("v2.4 source required columns missing: " + ", ".join(missing))
    return cols


def col_expr(cols: set[str], col_name: str, alias: str | None = None, default_sql: str = "NULL") -> str:
    target_alias = alias if alias else col_name
    if col_name in cols:
        return "b." + qident(col_name) + " AS " + qident(target_alias)
    return default_sql + " AS " + qident(target_alias)


def text_expr(cols: set[str], col_name: str, alias: str | None = None) -> str:
    return col_expr(cols, col_name, alias, "CAST(NULL AS CHAR)")


def numeric_expr(cols: set[str], col_name: str, alias: str | None = None) -> str:
    return col_expr(cols, col_name, alias, "CAST(NULL AS DECIMAL(20,6))")


def datetime_expr(cols: set[str], col_name: str, alias: str | None = None) -> str:
    return col_expr(cols, col_name, alias, "CAST(NULL AS DATETIME)")


def create_sections(conn) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(SECTION_TABLE))
    execute(conn, f"""
CREATE TABLE {qident(SECTION_TABLE)} (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    display_scope VARCHAR(64) NOT NULL,
    ui_section VARCHAR(64) NOT NULL,
    section_title_ko VARCHAR(100) NOT NULL,
    section_title_en VARCHAR(100) NOT NULL,
    section_order INT NOT NULL,
    default_expanded TINYINT NOT NULL,
    visible_in_compact TINYINT NOT NULL,
    visible_in_test TINYINT NOT NULL,
    row_limit_compact INT NULL,
    row_limit_test INT NULL,
    section_rule_ko VARCHAR(500) NOT NULL,
    section_color_key VARCHAR(40) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY ix_v24_section_scope (display_scope, section_order, ui_section)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
""")

    rows = [
        ("COMPACT_SCREEN", "AUTO_BUY_ZONE", "자동매수 후보", "Auto Buy", 1, 1, 1, 1, 20, 20, "다음봉 시가 자동진입 후보. display_score, expected_return_pct, mae_risk_pct, 거래대금 확인.", "AUTO_BUY"),
        ("COMPACT_SCREEN", "PULLBACK_ZONE", "눌림 대기 후보", "Pullback Wait", 2, 1, 1, 1, 10, 20, "즉시 추격보다 첫 눌림 확인 우위 후보. pullback_return_pct와 pullback_mae_pct 중심 확인.", "PULLBACK"),
        ("COMPACT_SCREEN", "HOGA_TICK_TEST_ZONE", "호가/틱 확인 후보", "Hoga Tick Confirm", 3, 0, 1, 1, 5, 120, "고품질 WATCH_HOGA_TICK만 압축 화면에 노출. 자동매수 전 호가/틱 확인 필수.", "HOGA"),
        ("TEST_WITH_HOGA_TICK_ALL", "AUTO_BUY_ZONE", "자동매수 후보", "Auto Buy", 1, 1, 1, 1, 20, 20, "검증 화면에서도 자동매수 후보는 항상 상단 고정.", "AUTO_BUY"),
        ("TEST_WITH_HOGA_TICK_ALL", "PULLBACK_ZONE", "눌림 대기 후보", "Pullback Wait", 2, 1, 1, 1, 20, 30, "검증 화면에서는 눌림 후보를 더 넓게 확인.", "PULLBACK"),
        ("TEST_WITH_HOGA_TICK_ALL", "HOGA_TICK_TEST_ZONE", "WATCH_HOGA_TICK 전체", "All Hoga Tick Watch", 3, 1, 0, 1, 0, 120, "테스트 기간 검증용. WATCH_HOGA_TICK 전체 후보를 표시하고 호가/틱 통과율을 추적.", "HOGA"),
    ]
    insert_sql = f"""
INSERT INTO {qident(SECTION_TABLE)}
(display_scope, ui_section, section_title_ko, section_title_en, section_order, default_expanded,
 visible_in_compact, visible_in_test, row_limit_compact, row_limit_test, section_rule_ko, section_color_key)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""
    with conn.cursor() as cur:
        cur.executemany(insert_sql, rows)


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
    sort_priority INT NOT NULL DEFAULT 0,
    color_rule_key VARCHAR(60) NOT NULL,
    tooltip_ko VARCHAR(500) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY ux_v24_col_key (column_key),
    KEY ix_v24_col_order (column_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
""")

    rows = [
        (10, "row_no", "board_row_no", "순위", "Rank", 54, "CENTER", "INT", 1, 1, 1, 1, "RANK", "현재 보드 정렬 기준 순위"),
        (20, "ticker", "ticker_label", "종목", "Ticker", 150, "LEFT", "TEXT", 1, 1, 1, 0, "TICKER", "종목코드와 종목명"),
        (30, "decision", "trade_decision", "판정", "Decision", 120, "CENTER", "BADGE", 1, 1, 0, 2, "DECISION", "AUTO_BUY / WAIT_PULLBACK / WATCH_HOGA_TICK"),
        (40, "grade", "display_grade", "등급", "Grade", 60, "CENTER", "BADGE", 1, 1, 0, 3, "GRADE", "S/A/B/C 표시 등급"),
        (50, "display_score", "display_score", "표시점수", "Display Score", 88, "RIGHT", "DECIMAL1", 1, 1, 0, 4, "SCORE_HEAT", "실시간 화면 표시용 최종 점수"),
        (60, "entry_action", "entry_action", "액션", "Action", 150, "CENTER", "BADGE", 1, 1, 0, 0, "ACTION", "실행 액션: 자동진입/눌림대기/호가틱확인"),
        (70, "entry_time", "entry_time_text", "진입시간", "Entry Time", 76, "CENTER", "TIME", 1, 1, 0, 0, "TIME", "선택된 진입 시각"),
        (80, "entry_price", "entry_price", "진입가", "Entry", 80, "RIGHT", "PRICE", 1, 1, 0, 0, "PRICE", "선택된 진입가"),
        (90, "expected_return", "expected_return_pct", "기대%", "Exp %", 78, "RIGHT", "PCT2", 1, 1, 0, 5, "RETURN", "선택 진입 기준 최대 기대 수익률"),
        (100, "mae_risk", "mae_risk_pct", "MAE%", "MAE %", 78, "RIGHT", "PCT2", 1, 1, 0, 6, "RISK", "진입 후 최대 역행 위험"),
        (110, "start_amount", "start_cum_amount_eok", "시작대금", "Start Amt", 88, "RIGHT", "EOK1", 1, 1, 0, 7, "AMOUNT", "ST 시작 시점 누적 거래대금, 억원 단위"),
        (120, "open_pct", "start_from_day_open_pct", "시가대비", "Open %", 78, "RIGHT", "PCT2", 1, 1, 0, 0, "OPEN_PCT", "ST 시작 시점의 당일 시가 대비 상승률"),
        (130, "low_pct", "start_from_day_low_pct", "저점대비", "Low %", 78, "RIGHT", "PCT2", 1, 1, 0, 0, "LOW_PCT", "ST 시작 시점의 당일 저점 대비 상승률"),
        (140, "qty_scale", "quantity_scale", "비중", "Size", 62, "RIGHT", "DECIMAL2", 1, 1, 0, 0, "SIZE", "권장 주문 비중 스케일"),
        (150, "risk_band", "risk_band_v2_0", "리스크", "Risk Band", 112, "CENTER", "BADGE", 1, 1, 0, 0, "RISK_BAND", "v2.0 리스크 밴드"),
        (160, "next_return", "next_bar_return_pct", "다음봉%", "Next %", 78, "RIGHT", "PCT2", 0, 1, 0, 0, "RETURN", "다음봉 시가 진입 기준 기대 수익률"),
        (170, "next_mae", "next_bar_mae_pct", "다음MAE", "Next MAE", 78, "RIGHT", "PCT2", 0, 1, 0, 0, "RISK", "다음봉 시가 진입 기준 MAE"),
        (180, "pullback_return", "pullback_return_pct", "눌림%", "Pullback %", 78, "RIGHT", "PCT2", 0, 1, 0, 0, "RETURN", "첫 눌림 진입 기준 기대 수익률"),
        (190, "pullback_mae", "pullback_mae_pct", "눌림MAE", "Pullback MAE", 78, "RIGHT", "PCT2", 0, 1, 0, 0, "RISK", "첫 눌림 진입 기준 MAE"),
        (200, "st_param", "st_param_text", "ST", "ST", 74, "CENTER", "TEXT", 0, 1, 0, 0, "PARAM", "SuperTrend period/multiplier"),
        (210, "same_code", "candidate_count_same_code_v2_1", "중복", "Dup", 58, "RIGHT", "INT", 0, 1, 0, 0, "COUNT", "동일 종목 후보 수"),
        (220, "reason", "short_reason", "근거", "Reason", 420, "LEFT", "TEXT", 1, 1, 0, 0, "REASON", "화면에 표시할 핵심 근거"),
    ]
    insert_sql = f"""
INSERT INTO {qident(COLUMN_TABLE)}
(column_order, column_key, source_column, header_text_ko, header_text_en, width_px, align_key,
 format_key, visible_compact, visible_test, pinned_left, sort_priority, color_rule_key, tooltip_ko)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""
    with conn.cursor() as cur:
        cur.executemany(insert_sql, rows)


def build_view(conn, source_table: str, cols: set[str]) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(VIEW_TABLE))

    optional_selects = [
        numeric_expr(cols, "st_period"),
        numeric_expr(cols, "st_multiplier"),
        numeric_expr(cols, "segment_no"),
        datetime_expr(cols, "st_up_start_time"),
        text_expr(cols, "final_entry_grade_v2_0"),
        numeric_expr(cols, "entry_score_v2_0"),
        numeric_expr(cols, "execution_score_v1_9"),
        numeric_expr(cols, "top_rank_score_v2_1"),
        numeric_expr(cols, "top_rank_action_priority_v2_1"),
        text_expr(cols, "recommended_entry_policy_v1_9"),
        text_expr(cols, "selected_entry_timing_v1_8"),
        numeric_expr(cols, "next_bar_return_pct"),
        numeric_expr(cols, "next_bar_mae_pct"),
        numeric_expr(cols, "pullback_return_pct"),
        numeric_expr(cols, "pullback_mae_pct"),
        numeric_expr(cols, "score_total"),
        text_expr(cols, "filter_label_v1_6"),
        text_expr(cols, "filter_grade_v1_6"),
        numeric_expr(cols, "filter_score_v1_6"),
        text_expr(cols, "risk_band_v2_0"),
        text_expr(cols, "entry_reason_v2_0"),
        text_expr(cols, "policy_reason_v1_9"),
        text_expr(cols, "top_rank_reason_v2_1"),
        numeric_expr(cols, "candidate_count_same_code_v2_1"),
        numeric_expr(cols, "auto_count_same_code_v2_1"),
        numeric_expr(cols, "wait_count_same_code_v2_1"),
        numeric_expr(cols, "confirm_count_same_code_v2_1"),
    ]

    optional_sql = ",\n        ".join(optional_selects)

    base_select = f"""
SELECT
        %s AS display_scope,
        b.ui_section,
        b.ui_sort_bucket,
        b.chart_open_priority,
        b.trade_decision,
        b.entry_action,
        b.display_grade,
        b.display_score,
        b.trade_date,
        b.code,
        b.name,
        CONCAT(b.code, ' ', b.name) AS ticker_label,
        b.entry_time,
        DATE_FORMAT(b.entry_time, '%%H:%%i') AS entry_time_text,
        b.entry_price,
        b.expected_return_pct,
        b.mae_risk_pct,
        b.start_cum_amount,
        b.start_cum_amount / 100000000.0 AS start_cum_amount_eok,
        b.start_from_day_open_pct,
        b.start_from_day_low_pct,
        b.quantity_scale,
        b.risk_message,
        b.ui_visibility_reason,
        CASE
            WHEN b.trade_decision IN ('AUTO_BUY', 'AUTO_BUY_SMALL') THEN b.risk_message
            WHEN b.trade_decision = 'WAIT_PULLBACK' THEN b.risk_message
            WHEN b.trade_decision = 'WATCH_HOGA_TICK' THEN b.risk_message
            ELSE b.ui_visibility_reason
        END AS short_reason,
        CASE
            WHEN b.trade_decision IN ('AUTO_BUY', 'AUTO_BUY_SMALL') THEN 1
            WHEN b.trade_decision = 'WAIT_PULLBACK' THEN 2
            WHEN b.trade_decision = 'WATCH_HOGA_TICK' THEN 3
            ELSE 9
        END AS decision_sort_order,
        CASE
            WHEN b.display_grade = 'S' THEN 1
            WHEN b.display_grade = 'A' THEN 2
            WHEN b.display_grade = 'B' THEN 3
            WHEN b.display_grade = 'C' THEN 4
            ELSE 9
        END AS grade_sort_order,
        CONCAT(IFNULL(CAST({('b.st_period' if 'st_period' in cols else 'NULL')} AS CHAR), '-'), '/', IFNULL(CAST({('b.st_multiplier' if 'st_multiplier' in cols else 'NULL')} AS CHAR), '-')) AS st_param_text,
        {optional_sql},
        b.compact_visible,
        b.test_full_visible,
        b.hoga_tick_test_visible,
        CURRENT_TIMESTAMP AS ui_created_at,
        CURRENT_TIMESTAMP AS ui_updated_at
FROM {qident(source_table)} b
WHERE %s = 1
"""

    execute(conn, f"""
CREATE TABLE {qident(VIEW_TABLE)} AS
SELECT
    ROW_NUMBER() OVER (
        PARTITION BY display_scope
        ORDER BY ui_sort_bucket ASC,
                 chart_open_priority ASC,
                 display_score DESC,
                 expected_return_pct DESC,
                 mae_risk_pct DESC,
                 start_cum_amount DESC
    ) AS board_row_no,
    x.*
FROM (
    {base_select % ("'COMPACT_SCREEN'", "b.compact_visible")}
    UNION ALL
    {base_select % ("'TEST_WITH_HOGA_TICK_ALL'", "b.test_full_visible")}
) x
""")
    execute(conn, f"ALTER TABLE {qident(VIEW_TABLE)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    execute(conn, f"ALTER TABLE {qident(VIEW_TABLE)} ADD KEY ix_v24_scope_sort (display_scope, board_row_no)")
    execute(conn, f"ALTER TABLE {qident(VIEW_TABLE)} ADD KEY ix_v24_section_sort (display_scope, ui_sort_bucket, display_score)")
    execute(conn, f"ALTER TABLE {qident(VIEW_TABLE)} ADD KEY ix_v24_code (code, trade_date)")
    execute(conn, f"ALTER TABLE {qident(VIEW_TABLE)} ADD KEY ix_v24_decision (display_scope, trade_decision, display_grade)")


def build_summary(conn) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(SUMMARY_TABLE))
    execute(conn, f"""
CREATE TABLE {qident(SUMMARY_TABLE)} AS
SELECT
    display_scope,
    ui_section,
    trade_decision,
    display_grade,
    entry_action,
    COUNT(*) AS row_count,
    AVG(display_score) AS avg_display_score,
    AVG(expected_return_pct) AS avg_expected_return_pct,
    AVG(mae_risk_pct) AS avg_mae_risk_pct,
    AVG(start_cum_amount) AS avg_start_cum_amount,
    AVG(start_cum_amount_eok) AS avg_start_cum_amount_eok,
    AVG(start_from_day_open_pct) AS avg_start_from_day_open_pct,
    AVG(start_from_day_low_pct) AS avg_start_from_day_low_pct,
    AVG(quantity_scale) AS avg_quantity_scale,
    MIN(board_row_no) AS first_board_row_no,
    MAX(board_row_no) AS last_board_row_no,
    CURRENT_TIMESTAMP AS created_at,
    CURRENT_TIMESTAMP AS updated_at
FROM {qident(VIEW_TABLE)}
GROUP BY display_scope, ui_section, trade_decision, display_grade, entry_action
""")
    execute(conn, f"ALTER TABLE {qident(SUMMARY_TABLE)} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    execute(conn, f"ALTER TABLE {qident(SUMMARY_TABLE)} ADD COLUMN id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST")
    execute(conn, f"ALTER TABLE {qident(SUMMARY_TABLE)} ADD KEY ix_v24_summary_scope (display_scope, first_board_row_no, avg_display_score)")


def print_rows(title: str, rows) -> None:
    print("\n=== " + title + " ===")
    for row in rows:
        print(dict(row))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build v2.4 Top Candidate Board UI tables from v2.3 screen rows.")
    p.add_argument("--host", default="")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--database", default="")
    p.add_argument("--user", default="")
    p.add_argument("--password", default="")
    p.add_argument("--charset", default="utf8mb4")
    p.add_argument("--mysql-conn", default="")
    p.add_argument("--source-table", default=SOURCE_TABLE_DEFAULT)
    p.add_argument("--preview-limit", type=int, default=40)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    print("=== BUILD v2.4 ST Top Candidate Board UI ===")
    cfg = build_mysql_config(args)
    conn = pymysql.connect(**cfg)
    try:
        cols = assert_source(conn, args.source_table)
        create_sections(conn)
        create_columns(conn)
        build_view(conn, args.source_table, cols)
        build_summary(conn)
        conn.commit()

        source_rows = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(args.source_table)}")
        view_rows = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(VIEW_TABLE)}")
        col_rows = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(COLUMN_TABLE)}")
        section_rows = fetch_all(conn, f"SELECT COUNT(*) AS cnt FROM {qident(SECTION_TABLE)}")

        print("source_table=", args.source_table)
        print("column_table=", COLUMN_TABLE)
        print("section_table=", SECTION_TABLE)
        print("view_table=", VIEW_TABLE)
        print("summary_table=", SUMMARY_TABLE)
        print("source_rows=", to_int(source_rows[0].get("cnt"), 0) if source_rows else 0)
        print("view_rows=", to_int(view_rows[0].get("cnt"), 0) if view_rows else 0)
        print("column_count=", to_int(col_rows[0].get("cnt"), 0) if col_rows else 0)
        print("section_count=", to_int(section_rows[0].get("cnt"), 0) if section_rows else 0)
        print("ui_display_scopes= COMPACT_SCREEN / TEST_WITH_HOGA_TICK_ALL")

        print_rows(
            "v2.4 Board Summary",
            fetch_all(conn, f"""
SELECT *
FROM {qident(SUMMARY_TABLE)}
ORDER BY display_scope ASC, first_board_row_no ASC, avg_display_score DESC
LIMIT 80
"""),
        )
        print_rows(
            "v2.4 Column Spec",
            fetch_all(conn, f"""
SELECT column_order, column_key, source_column, header_text_ko, width_px,
       visible_compact, visible_test, pinned_left, format_key, color_rule_key
FROM {qident(COLUMN_TABLE)}
ORDER BY column_order ASC
"""),
        )
        print_rows(
            "v2.4 Compact Board Preview",
            fetch_all(conn, f"""
SELECT board_row_no, ticker_label, trade_decision, display_grade, display_score,
       entry_action, entry_time_text, entry_price, expected_return_pct, mae_risk_pct,
       start_cum_amount_eok, start_from_day_open_pct, quantity_scale, short_reason
FROM {qident(VIEW_TABLE)}
WHERE display_scope = 'COMPACT_SCREEN'
ORDER BY board_row_no ASC
LIMIT {int(args.preview_limit)}
"""),
        )
        print_rows(
            "v2.4 WATCH_HOGA_TICK Verification Preview",
            fetch_all(conn, f"""
SELECT board_row_no, ticker_label, trade_decision, display_grade, display_score,
       entry_action, expected_return_pct, mae_risk_pct, start_cum_amount_eok,
       start_from_day_open_pct, start_from_day_low_pct, short_reason
FROM {qident(VIEW_TABLE)}
WHERE display_scope = 'TEST_WITH_HOGA_TICK_ALL'
  AND trade_decision = 'WATCH_HOGA_TICK'
ORDER BY board_row_no ASC
LIMIT {int(args.preview_limit)}
"""),
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
