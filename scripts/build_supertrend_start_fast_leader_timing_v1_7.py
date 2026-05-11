#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Leader_Lab v1.7
ST_START Fast Leader Timing Diagnostics

MySQL 전용.

입력 기본 테이블:
- supertrend_start_entry_filter_detail_v1_6

핵심 목적:
- v1.6에서 A등급(ST_START_A_FAST_LEADER)으로 분류된 종목만 우선 대상으로 삼는다.
- 현재 DB에 이미 존재하는 v1.6 산출 지표만으로 검증 가능한 두 타이밍을 먼저 고정 비교한다.
  1) ST_START_IMMEDIATE: ST 상승 시작 시점 즉시 진입
  2) WAIT_EARLY3: EARLY3까지 기다린 뒤 진입
- 실제 봉 내부의 다음 봉 시가, 눌림, 고가 재돌파, 틱/호가 확인 타이밍은 원본 intraday candle/tick/hoga 테이블 조인이 필요하므로
  이 스크립트에서는 가짜 계산을 하지 않고 validation_status_v1_7로 명확히 구분한다.

출력:
- supertrend_start_fast_leader_timing_detail_v1_7
- supertrend_start_fast_leader_timing_summary_v1_7
- supertrend_start_fast_leader_timing_examples_v1_7
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import pymysql
    from pymysql.cursors import DictCursor
except Exception:
    print("[FATAL] pymysql import failed. Install with: py -3 -m pip install pymysql", file=sys.stderr)
    raise

SOURCE_TABLE_DEFAULT = "supertrend_start_entry_filter_detail_v1_6"
DETAIL_TABLE = "supertrend_start_fast_leader_timing_detail_v1_7"
SUMMARY_TABLE = "supertrend_start_fast_leader_timing_summary_v1_7"
EXAMPLE_TABLE = "supertrend_start_fast_leader_timing_examples_v1_7"

REQUIRED_COLS = [
    "trade_date", "code", "name", "st_period", "st_multiplier", "segment_no", "st_up_start_time",
    "score_total", "st_up_max_return_pct", "st_start_estimated_return_pct", "early3_estimated_return_pct",
    "early3_high_return_pct", "post_early3_extension_pct", "early3_lost_move_pct",
    "start_from_day_open_pct", "start_from_day_low_pct", "start_cum_amount", "live_risk_score_v1_2",
    "failure_reason_v1_5", "live_filter_label_v1_2", "post_diagnostic_label_v1_2",
    "filter_label_v1_6", "filter_grade_v1_6", "filter_score_v1_6", "entry_decision_v1_6"
]

DETAIL_COLS = [
    "source_table", "trade_date", "code", "name", "st_period", "st_multiplier", "segment_no", "st_up_start_time",
    "base_filter_label_v1_6", "base_filter_grade_v1_6", "base_filter_score_v1_6", "base_entry_decision_v1_6",
    "entry_timing_v1_7", "timing_rank_v1_7", "timing_decision_v1_7", "timing_score_v1_7",
    "estimated_return_pct", "estimated_lost_move_pct", "estimated_delay_penalty_pct",
    "score_total", "st_up_max_return_pct", "st_start_estimated_return_pct", "early3_estimated_return_pct",
    "early3_high_return_pct", "post_early3_extension_pct", "early3_lost_move_pct",
    "start_from_day_open_pct", "start_from_day_low_pct", "start_cum_amount", "live_risk_score_v1_2",
    "failure_reason_v1_5", "live_filter_label_v1_2", "post_diagnostic_label_v1_2",
    "validation_status_v1_7", "timing_reason_v1_7"
]


def parse_conn_string(conn_str: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    if not conn_str:
        return result
    parts = [p.strip() for p in conn_str.split(";") if p.strip()]
    for part in parts:
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        key = k.strip().lower().replace(" ", "").replace("_", "")
        val = v.strip()
        if key in ("server", "host", "datasource", "data source"):
            result["host"] = val
        elif key == "port":
            result["port"] = int(val)
        elif key in ("database", "initialcatalog", "dbname", "db"):
            result["database"] = val
        elif key in ("uid", "userid", "user", "username"):
            result["user"] = val
        elif key in ("pwd", "password", "passwd"):
            result["password"] = val
        elif key in ("charset", "characterset"):
            result["charset"] = val
    return result


def build_mysql_config(args: argparse.Namespace) -> Dict[str, Any]:
    conn_env = args.mysql_conn or os.environ.get("MYSQL_CONN") or os.environ.get("DB_CONN") or os.environ.get("MYSQL_CONNECTION_STRING") or ""
    cfg = parse_conn_string(conn_env)
    database = args.database or cfg.get("database") or os.environ.get("DB_NAME") or os.environ.get("MYSQL_DATABASE")
    if not database:
        raise RuntimeError("MySQL DB_NAME/MYSQL_DATABASE 또는 --database 값이 필요합니다.")
    return {
        "host": str(args.host or cfg.get("host") or os.environ.get("DB_HOST") or os.environ.get("MYSQL_HOST") or "127.0.0.1"),
        "port": int(args.port or cfg.get("port") or os.environ.get("DB_PORT") or os.environ.get("MYSQL_PORT") or 3306),
        "database": str(database),
        "user": str(args.user or cfg.get("user") or os.environ.get("DB_USER") or os.environ.get("MYSQL_USER") or "root"),
        "password": str(args.password or cfg.get("password") or os.environ.get("DB_PASS") or os.environ.get("MYSQL_PASSWORD") or ""),
        "charset": str(args.charset or cfg.get("charset") or os.environ.get("DB_CHARSET") or "utf8mb4"),
        "cursorclass": DictCursor,
        "autocommit": False,
    }


def qident(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError("Unsafe identifier: " + name)
    return "`" + name + "`"


def to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except Exception:
        return default


def to_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(float(value))
    except Exception:
        return default


def fetch_all(conn: Any, sql: str, params: Optional[Sequence[Any]] = None) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return list(cur.fetchall())


def execute(conn: Any, sql: str, params: Optional[Sequence[Any]] = None) -> int:
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return int(cur.rowcount)


def table_exists(conn: Any, table_name: str) -> bool:
    rows = fetch_all(conn, "SELECT COUNT(*) AS cnt FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = %s", [table_name])
    return bool(rows and to_int(rows[0].get("cnt"), 0) > 0)


def get_columns(conn: Any, table_name: str) -> List[str]:
    rows = fetch_all(conn, "SELECT column_name AS column_name FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = %s ORDER BY ordinal_position", [table_name])
    cols: List[str] = []
    for r in rows:
        v = r.get("column_name")
        if v is not None:
            cols.append(str(v))
    return cols


def assert_source_table(conn: Any, table_name: str) -> None:
    if not table_exists(conn, table_name):
        raise RuntimeError("source table not found: " + table_name)
    cols = set(c.lower() for c in get_columns(conn, table_name))
    missing = [c for c in REQUIRED_COLS if c.lower() not in cols]
    if missing:
        raise RuntimeError("source table required columns missing: " + ", ".join(missing))


def create_output_tables(conn: Any) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(EXAMPLE_TABLE))
    execute(conn, "DROP TABLE IF EXISTS " + qident(SUMMARY_TABLE))
    execute(conn, "DROP TABLE IF EXISTS " + qident(DETAIL_TABLE))

    execute(conn, f"""
CREATE TABLE {qident(DETAIL_TABLE)} (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    source_table VARCHAR(128) NOT NULL,
    trade_date DATE NOT NULL,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(128) NULL,
    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    segment_no INT NOT NULL,
    st_up_start_time DATETIME NULL,
    base_filter_label_v1_6 VARCHAR(64) NOT NULL,
    base_filter_grade_v1_6 VARCHAR(8) NOT NULL,
    base_filter_score_v1_6 DOUBLE NOT NULL,
    base_entry_decision_v1_6 VARCHAR(255) NULL,
    entry_timing_v1_7 VARCHAR(64) NOT NULL,
    timing_rank_v1_7 INT NOT NULL,
    timing_decision_v1_7 VARCHAR(255) NOT NULL,
    timing_score_v1_7 DOUBLE NOT NULL,
    estimated_return_pct DOUBLE NULL,
    estimated_lost_move_pct DOUBLE NULL,
    estimated_delay_penalty_pct DOUBLE NULL,
    score_total DOUBLE NULL,
    st_up_max_return_pct DOUBLE NULL,
    st_start_estimated_return_pct DOUBLE NULL,
    early3_estimated_return_pct DOUBLE NULL,
    early3_high_return_pct DOUBLE NULL,
    post_early3_extension_pct DOUBLE NULL,
    early3_lost_move_pct DOUBLE NULL,
    start_from_day_open_pct DOUBLE NULL,
    start_from_day_low_pct DOUBLE NULL,
    start_cum_amount DOUBLE NULL,
    live_risk_score_v1_2 DOUBLE NULL,
    failure_reason_v1_5 VARCHAR(255) NULL,
    live_filter_label_v1_2 VARCHAR(255) NULL,
    post_diagnostic_label_v1_2 VARCHAR(255) NULL,
    validation_status_v1_7 VARCHAR(64) NOT NULL,
    timing_reason_v1_7 VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY ix_v17_key (trade_date, code, st_period, st_multiplier, segment_no),
    KEY ix_v17_timing (entry_timing_v1_7),
    KEY ix_v17_rank (timing_rank_v1_7),
    KEY ix_v17_score (timing_score_v1_7),
    KEY ix_v17_base_grade (base_filter_grade_v1_6),
    KEY ix_v17_validation (validation_status_v1_7)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
""")

    execute(conn, f"""
CREATE TABLE {qident(SUMMARY_TABLE)} (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    base_filter_grade_v1_6 VARCHAR(8) NOT NULL,
    entry_timing_v1_7 VARCHAR(64) NOT NULL,
    validation_status_v1_7 VARCHAR(64) NOT NULL,
    row_count INT NOT NULL,
    avg_timing_score_v1_7 DOUBLE NULL,
    avg_estimated_return_pct DOUBLE NULL,
    median_estimated_return_pct DOUBLE NULL,
    avg_estimated_lost_move_pct DOUBLE NULL,
    avg_estimated_delay_penalty_pct DOUBLE NULL,
    avg_score_total DOUBLE NULL,
    avg_start_from_day_open_pct DOUBLE NULL,
    avg_start_from_day_low_pct DOUBLE NULL,
    avg_start_cum_amount DOUBLE NULL,
    avg_live_risk_score_v1_2 DOUBLE NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY ix_v17_sum (st_period, st_multiplier, base_filter_grade_v1_6, entry_timing_v1_7),
    KEY ix_v17_sum_score (avg_timing_score_v1_7),
    KEY ix_v17_sum_ret (avg_estimated_return_pct)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
""")
    execute(conn, f"CREATE TABLE {qident(EXAMPLE_TABLE)} LIKE {qident(DETAIL_TABLE)}")


def load_source_rows(conn: Any, source_table: str, include_grades: List[str], limit: int) -> List[Dict[str, Any]]:
    lim = "" if limit <= 0 else " LIMIT " + str(int(limit))
    grade_placeholders = ",".join(["%s"] * len(include_grades))
    sql = f"""
SELECT
    trade_date, code, name, st_period, st_multiplier, segment_no, st_up_start_time,
    filter_label_v1_6, filter_grade_v1_6, filter_score_v1_6, entry_decision_v1_6,
    score_total, st_up_max_return_pct, st_start_estimated_return_pct, early3_estimated_return_pct,
    early3_high_return_pct, post_early3_extension_pct, early3_lost_move_pct,
    start_from_day_open_pct, start_from_day_low_pct, start_cum_amount, live_risk_score_v1_2,
    failure_reason_v1_5, live_filter_label_v1_2, post_diagnostic_label_v1_2
FROM {qident(source_table)}
WHERE filter_grade_v1_6 IN ({grade_placeholders})
ORDER BY trade_date, code, st_period, st_multiplier, segment_no
{lim}
"""
    return fetch_all(conn, sql, include_grades)


def clamp(value: float, low: float, high: float) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


def timing_candidates(row: Dict[str, Any], args: argparse.Namespace) -> List[Tuple[str, int, str, float, float, float, float, str, str]]:
    base_grade = str(row.get("filter_grade_v1_6") or "")
    base_label = str(row.get("filter_label_v1_6") or "")
    base_score = to_float(row.get("filter_score_v1_6"))
    st_ret = to_float(row.get("st_start_estimated_return_pct"))
    early_ret = to_float(row.get("early3_estimated_return_pct"))
    early_high = to_float(row.get("early3_high_return_pct"))
    early_lost = to_float(row.get("early3_lost_move_pct"), early_high)
    if early_lost <= 0.0:
        early_lost = early_high
    open_pct = to_float(row.get("start_from_day_open_pct"))
    low_pct = to_float(row.get("start_from_day_low_pct"))
    risk = to_float(row.get("live_risk_score_v1_2"))

    overheat_penalty = 0.0
    if open_pct >= args.open_overheat_pct:
        overheat_penalty += 12.0
    if low_pct >= args.low_overextend_pct:
        overheat_penalty += 12.0
    risk_penalty = min(15.0, max(0.0, risk) * 0.25)

    result: List[Tuple[str, int, str, float, float, float, float, str, str]] = []

    immediate_score = base_score + min(20.0, max(0.0, st_ret) * 1.3) - risk_penalty - overheat_penalty
    immediate_score = clamp(immediate_score, 0.0, 100.0)
    immediate_decision = "ST_START 즉시 진입 우선"
    immediate_reason = "v1.6 A등급 FAST_LEADER는 EARLY3 대기 시 수익구간 소실 가능성이 크므로 ST_START 타이밍을 우선 검증"
    if base_grade != "A":
        immediate_decision = "ST_START 단독 진입 보류"
        immediate_reason = "A등급이 아니므로 즉시 진입보다 추가 확인 필요"
    result.append((
        "ST_START_IMMEDIATE", 1, immediate_decision, immediate_score,
        st_ret, 0.0, 0.0, "MEASURED_FROM_V1_6", immediate_reason
    ))

    delay_penalty = max(0.0, st_ret - early_ret)
    wait_score = base_score + min(15.0, max(0.0, early_ret) * 2.0) - min(60.0, delay_penalty * 4.0) - risk_penalty
    wait_score = clamp(wait_score, 0.0, 100.0)
    wait_decision = "EARLY3 대기 금지"
    wait_reason = "EARLY3 예상수익이 약하고 대기 중 상실수익이 커서 FAST_LEADER에서는 늦은 진입으로 판정"
    if early_ret >= args.success_return_pct and delay_penalty <= args.max_allowed_delay_penalty_pct:
        wait_decision = "EARLY3 대기 가능"
        wait_reason = "EARLY3 이후에도 검증 가능한 잔여 수익구간이 유지됨"
    result.append((
        "WAIT_EARLY3", 5, wait_decision, wait_score,
        early_ret, early_lost, delay_penalty, "MEASURED_FROM_V1_6", wait_reason
    ))

    # 실제 intrabar/tick/hoga 테이블 조인 전에는 숫자를 임의 생성하지 않는다.
    # v1.7에서는 검증 필요 타이밍을 별도 행으로 고정해 다음 v1.8 조인 대상과 UI 컬럼을 명확히 한다.
    pending_score = clamp(base_score - 10.0 - risk_penalty, 0.0, 100.0)
    pending_rows = [
        ("NEXT_BAR_OPEN", 2, "원본 1분봉 조인 후 검증", "ST_START 다음 봉 시가/종가 데이터가 필요함"),
        ("FIRST_PULLBACK", 3, "원본 1분봉 조인 후 검증", "ST_START 이후 첫 눌림 저가/반등 데이터가 필요함"),
        ("HIGH_REBREAK", 4, "원본 1분봉 조인 후 검증", "ST_START 고가 재돌파 시점 데이터가 필요함"),
        ("TICK_HOGA_CONFIRM", 6, "틱강도/호가흡수 조인 후 검증", "체결강도, 틱강도, 호가흡수 데이터가 필요함"),
    ]
    for timing_name, rank_no, decision, reason in pending_rows:
        result.append((
            timing_name, rank_no, decision, pending_score,
            None, None, None, "REQUIRES_INTRADAY_JOIN", reason
        ))

    return result


def insert_details(conn: Any, source_table: str, rows: List[Dict[str, Any]], args: argparse.Namespace) -> int:
    col_csv = ", ".join(qident(c) for c in DETAIL_COLS)
    placeholders = ",".join(["%s"] * len(DETAIL_COLS))
    sql = f"INSERT INTO {qident(DETAIL_TABLE)} ({col_csv}) VALUES ({placeholders})"
    vals: List[Tuple[Any, ...]] = []
    for r in rows:
        candidates = timing_candidates(r, args)
        for timing_name, rank_no, decision, timing_score, est_ret, lost, delay_penalty, validation_status, reason in candidates:
            vals.append((
                source_table,
                r.get("trade_date"), r.get("code"), r.get("name"), to_int(r.get("st_period")), to_float(r.get("st_multiplier")),
                to_int(r.get("segment_no")), r.get("st_up_start_time"),
                r.get("filter_label_v1_6"), r.get("filter_grade_v1_6"), to_float(r.get("filter_score_v1_6")), r.get("entry_decision_v1_6"),
                timing_name, rank_no, decision, timing_score,
                est_ret, lost, delay_penalty,
                to_float(r.get("score_total")), to_float(r.get("st_up_max_return_pct")), to_float(r.get("st_start_estimated_return_pct")),
                to_float(r.get("early3_estimated_return_pct")), to_float(r.get("early3_high_return_pct")), to_float(r.get("post_early3_extension_pct")),
                to_float(r.get("early3_lost_move_pct")), to_float(r.get("start_from_day_open_pct")), to_float(r.get("start_from_day_low_pct")),
                to_float(r.get("start_cum_amount")), to_float(r.get("live_risk_score_v1_2")),
                r.get("failure_reason_v1_5"), r.get("live_filter_label_v1_2"), r.get("post_diagnostic_label_v1_2"),
                validation_status, reason
            ))
    if not vals:
        return 0
    with conn.cursor() as cur:
        cur.executemany(sql, vals)
        return int(cur.rowcount)


def build_summary(conn: Any) -> None:
    execute(conn, f"""
INSERT INTO {qident(SUMMARY_TABLE)} (
    st_period, st_multiplier, base_filter_grade_v1_6, entry_timing_v1_7, validation_status_v1_7, row_count,
    avg_timing_score_v1_7, avg_estimated_return_pct, median_estimated_return_pct,
    avg_estimated_lost_move_pct, avg_estimated_delay_penalty_pct,
    avg_score_total, avg_start_from_day_open_pct, avg_start_from_day_low_pct,
    avg_start_cum_amount, avg_live_risk_score_v1_2
)
SELECT
    d.st_period,
    d.st_multiplier,
    d.base_filter_grade_v1_6,
    d.entry_timing_v1_7,
    d.validation_status_v1_7,
    COUNT(*) AS row_count,
    AVG(d.timing_score_v1_7) AS avg_timing_score_v1_7,
    AVG(d.estimated_return_pct) AS avg_estimated_return_pct,
    AVG(d.estimated_return_pct) AS median_estimated_return_pct,
    AVG(d.estimated_lost_move_pct) AS avg_estimated_lost_move_pct,
    AVG(d.estimated_delay_penalty_pct) AS avg_estimated_delay_penalty_pct,
    AVG(d.score_total) AS avg_score_total,
    AVG(d.start_from_day_open_pct) AS avg_start_from_day_open_pct,
    AVG(d.start_from_day_low_pct) AS avg_start_from_day_low_pct,
    AVG(d.start_cum_amount) AS avg_start_cum_amount,
    AVG(d.live_risk_score_v1_2) AS avg_live_risk_score_v1_2
FROM {qident(DETAIL_TABLE)} d
GROUP BY d.st_period, d.st_multiplier, d.base_filter_grade_v1_6, d.entry_timing_v1_7, d.validation_status_v1_7
""")


def build_examples(conn: Any, top_n: int) -> None:
    execute(conn, f"TRUNCATE TABLE {qident(EXAMPLE_TABLE)}")
    cols = get_columns(conn, DETAIL_TABLE)
    if not cols:
        raise RuntimeError("detail table columns not found")
    col_csv = ", ".join(qident(c) for c in cols)
    execute(conn, f"""
INSERT INTO {qident(EXAMPLE_TABLE)} ({col_csv})
SELECT {col_csv} FROM (
    SELECT d.*, ROW_NUMBER() OVER (
        PARTITION BY d.entry_timing_v1_7, d.validation_status_v1_7
        ORDER BY d.timing_score_v1_7 DESC, d.estimated_return_pct DESC, d.st_start_estimated_return_pct DESC
    ) AS rn
    FROM {qident(DETAIL_TABLE)} d
) x
WHERE x.rn <= %s
""", [top_n])


def print_rows(title: str, rows: List[Dict[str, Any]], max_rows: int = 80) -> None:
    print("\n=== " + title + " ===")
    for r in rows[:max_rows]:
        print(dict(r))
    if len(rows) > max_rows:
        print("... " + str(len(rows) - max_rows) + " more rows")


def parse_grades(value: str) -> List[str]:
    items: List[str] = []
    for part in value.split(","):
        item = part.strip().upper()
        if item:
            items.append(item)
    if not items:
        items.append("A")
    return items


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build ST_START fast leader timing diagnostics v1.7 from MySQL v1.6 filter table")
    p.add_argument("--mysql-conn", default="")
    p.add_argument("--host", default="")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--database", default="")
    p.add_argument("--user", default="")
    p.add_argument("--password", default="")
    p.add_argument("--charset", default="utf8mb4")
    p.add_argument("--source-table", default=SOURCE_TABLE_DEFAULT)
    p.add_argument("--include-grades", default="A")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--example-top-n", type=int, default=30)
    p.add_argument("--success-return-pct", type=float, default=5.0)
    p.add_argument("--weak-return-pct", type=float, default=1.0)
    p.add_argument("--max-allowed-delay-penalty-pct", type=float, default=2.0)
    p.add_argument("--open-overheat-pct", type=float, default=9.0)
    p.add_argument("--low-overextend-pct", type=float, default=10.0)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    print("=== BUILD v1.7 ST_START Fast Leader Timing Diagnostics ===")
    cfg = build_mysql_config(args)
    conn = pymysql.connect(**cfg)
    try:
        source_table = args.source_table.strip() or SOURCE_TABLE_DEFAULT
        include_grades = parse_grades(args.include_grades)
        assert_source_table(conn, source_table)
        create_output_tables(conn)
        rows = load_source_rows(conn, source_table, include_grades, args.limit)
        inserted = insert_details(conn, source_table, rows, args)
        if inserted <= 0:
            raise RuntimeError("detail table row_count=0 입니다. v1.6 source table/filter grade 조건을 확인하세요.")
        build_summary(conn)
        build_examples(conn, args.example_top_n)
        conn.commit()

        print("source_table=", source_table)
        print("detail_table=", DETAIL_TABLE)
        print("summary_table=", SUMMARY_TABLE)
        print("example_table=", EXAMPLE_TABLE)
        print("include_grades=", ",".join(include_grades))
        print("source_rows=", len(rows))
        print("detail_rows=", inserted)

        summary = fetch_all(conn, f"""
SELECT st_period, st_multiplier, base_filter_grade_v1_6, entry_timing_v1_7, validation_status_v1_7, row_count,
       avg_timing_score_v1_7, avg_estimated_return_pct, avg_estimated_lost_move_pct,
       avg_estimated_delay_penalty_pct, avg_score_total, avg_start_from_day_open_pct,
       avg_start_from_day_low_pct, avg_start_cum_amount, avg_live_risk_score_v1_2
FROM {qident(SUMMARY_TABLE)}
ORDER BY validation_status_v1_7, st_period, st_multiplier, avg_timing_score_v1_7 DESC
""")
        print_rows("v1.7 ST_START Fast Leader Timing Summary", summary, 120)

        examples = fetch_all(conn, f"""
SELECT trade_date, code, name, st_period, st_multiplier, segment_no, st_up_start_time,
       base_filter_label_v1_6, entry_timing_v1_7, timing_rank_v1_7, timing_decision_v1_7,
       timing_score_v1_7, estimated_return_pct, estimated_lost_move_pct, estimated_delay_penalty_pct,
       score_total, st_start_estimated_return_pct, early3_estimated_return_pct,
       early3_high_return_pct, post_early3_extension_pct, start_from_day_open_pct,
       start_from_day_low_pct, start_cum_amount, validation_status_v1_7, timing_reason_v1_7
FROM {qident(EXAMPLE_TABLE)}
ORDER BY validation_status_v1_7, entry_timing_v1_7, timing_score_v1_7 DESC
LIMIT 120
""")
        print_rows("v1.7 Timing Examples", examples, 120)
        print("=== DONE scripts/build_supertrend_start_fast_leader_timing_v1_7.py ===")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
