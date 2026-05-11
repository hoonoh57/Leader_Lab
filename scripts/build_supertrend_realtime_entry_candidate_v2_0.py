#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Leader_Lab v2.0
SuperTrend Realtime Entry Candidate Builder

MySQL 전용.

입력:
- supertrend_entry_execution_policy_detail_v1_9

출력:
- supertrend_realtime_entry_candidate_v2_0
- supertrend_realtime_entry_candidate_summary_v2_0
- supertrend_realtime_entry_candidate_examples_v2_0

수정 메모:
- MySQL INSERT INTO ... SELECT ... ORDER BY에서 집계 별칭을 명시하지 않으면
  1054 Unknown column 오류가 발생할 수 있으므로 모든 AVG 집계에 alias를 부여한다.
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

SOURCE_TABLE_DEFAULT = "supertrend_entry_execution_policy_detail_v1_9"
CANDIDATE_TABLE = "supertrend_realtime_entry_candidate_v2_0"
SUMMARY_TABLE = "supertrend_realtime_entry_candidate_summary_v2_0"
EXAMPLE_TABLE = "supertrend_realtime_entry_candidate_examples_v2_0"

ACTION_AUTO = "AUTO_BUY_NEXT_BAR"
ACTION_WAIT = "WAIT_PULLBACK"
ACTION_CONFIRM = "REQUIRE_HOGA_TICK_CONFIRM"
ACTION_SKIP = "SKIP"

SOURCE_REQUIRED_COLS = [
    "trade_date", "code", "name", "st_period", "st_multiplier", "segment_no", "st_up_start_time",
    "recommended_entry_policy_v1_9", "execution_label_v1_9", "execution_score_v1_9",
    "selected_entry_timing_v1_8", "selected_entry_time", "selected_entry_price",
    "selected_estimated_return_pct", "selected_max_adverse_excursion_pct", "selected_estimated_lost_move_pct",
    "next_bar_return_pct", "next_bar_mae_pct", "pullback_return_pct", "pullback_mae_pct",
    "start_from_day_open_pct", "start_from_day_low_pct", "start_cum_amount",
    "score_total", "filter_label_v1_6", "filter_grade_v1_6", "filter_score_v1_6",
    "policy_reason_v1_9"
]

OUTPUT_COLS = [
    "source_table", "trade_date", "code", "name", "st_period", "st_multiplier", "segment_no", "st_up_start_time",
    "selected_entry_time", "selected_entry_price",
    "recommended_entry_policy_v1_9", "execution_label_v1_9", "execution_score_v1_9",
    "selected_entry_timing_v1_8", "selected_estimated_return_pct", "selected_max_adverse_excursion_pct",
    "selected_estimated_lost_move_pct", "next_bar_return_pct", "next_bar_mae_pct", "pullback_return_pct", "pullback_mae_pct",
    "start_from_day_open_pct", "start_from_day_low_pct", "start_cum_amount",
    "score_total", "filter_label_v1_6", "filter_grade_v1_6", "filter_score_v1_6",
    "final_entry_grade_v2_0", "entry_action_v2_0", "entry_score_v2_0", "risk_band_v2_0", "quantity_scale_v2_0",
    "entry_reason_v2_0", "policy_reason_v1_9"
]


def parse_conn_string(conn_str: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    if not conn_str:
        return result
    for raw_part in conn_str.split(";"):
        part = raw_part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        key = k.strip().lower().replace(" ", "").replace("_", "")
        val = v.strip()
        if key in ("server", "host", "datasource"):
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


def to_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


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
    return [str(r.get("column_name")) for r in rows if r.get("column_name") is not None]


def assert_source_table(conn: Any, table_name: str) -> None:
    if not table_exists(conn, table_name):
        raise RuntimeError("source table not found: " + table_name)
    cols = set(c.lower() for c in get_columns(conn, table_name))
    missing = [c for c in SOURCE_REQUIRED_COLS if c.lower() not in cols]
    if missing:
        raise RuntimeError("source table required columns missing: " + ", ".join(missing))


def create_output_tables(conn: Any) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(EXAMPLE_TABLE))
    execute(conn, "DROP TABLE IF EXISTS " + qident(SUMMARY_TABLE))
    execute(conn, "DROP TABLE IF EXISTS " + qident(CANDIDATE_TABLE))
    execute(conn, f"""
CREATE TABLE {qident(CANDIDATE_TABLE)} (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    source_table VARCHAR(128) NOT NULL,
    trade_date DATE NOT NULL,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(128) NULL,
    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    segment_no INT NOT NULL,
    st_up_start_time DATETIME NULL,
    selected_entry_time DATETIME NULL,
    selected_entry_price DOUBLE NULL,
    recommended_entry_policy_v1_9 VARCHAR(64) NOT NULL,
    execution_label_v1_9 VARCHAR(64) NOT NULL,
    execution_score_v1_9 DOUBLE NOT NULL,
    selected_entry_timing_v1_8 VARCHAR(64) NULL,
    selected_estimated_return_pct DOUBLE NULL,
    selected_max_adverse_excursion_pct DOUBLE NULL,
    selected_estimated_lost_move_pct DOUBLE NULL,
    next_bar_return_pct DOUBLE NULL,
    next_bar_mae_pct DOUBLE NULL,
    pullback_return_pct DOUBLE NULL,
    pullback_mae_pct DOUBLE NULL,
    start_from_day_open_pct DOUBLE NULL,
    start_from_day_low_pct DOUBLE NULL,
    start_cum_amount DOUBLE NULL,
    score_total DOUBLE NULL,
    filter_label_v1_6 VARCHAR(64) NULL,
    filter_grade_v1_6 VARCHAR(8) NULL,
    filter_score_v1_6 DOUBLE NULL,
    final_entry_grade_v2_0 VARCHAR(8) NOT NULL,
    entry_action_v2_0 VARCHAR(64) NOT NULL,
    entry_score_v2_0 DOUBLE NOT NULL,
    risk_band_v2_0 VARCHAR(32) NOT NULL,
    quantity_scale_v2_0 DOUBLE NOT NULL,
    entry_reason_v2_0 VARCHAR(768) NOT NULL,
    policy_reason_v1_9 VARCHAR(512) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY ix_v20_date_action (trade_date, entry_action_v2_0, final_entry_grade_v2_0),
    KEY ix_v20_code (code, trade_date),
    KEY ix_v20_score (entry_score_v2_0),
    KEY ix_v20_entry_time (selected_entry_time),
    KEY ix_v20_st (st_period, st_multiplier)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
""")
    execute(conn, f"""
CREATE TABLE {qident(SUMMARY_TABLE)} (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    final_entry_grade_v2_0 VARCHAR(8) NOT NULL,
    entry_action_v2_0 VARCHAR(64) NOT NULL,
    row_count INT NOT NULL,
    avg_entry_score_v2_0 DOUBLE NULL,
    avg_execution_score_v1_9 DOUBLE NULL,
    avg_selected_return_pct DOUBLE NULL,
    avg_selected_mae_pct DOUBLE NULL,
    avg_next_bar_return_pct DOUBLE NULL,
    avg_next_bar_mae_pct DOUBLE NULL,
    avg_pullback_return_pct DOUBLE NULL,
    avg_pullback_mae_pct DOUBLE NULL,
    avg_start_from_day_open_pct DOUBLE NULL,
    avg_start_from_day_low_pct DOUBLE NULL,
    avg_start_cum_amount DOUBLE NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY ix_v20_sum_score (avg_entry_score_v2_0),
    KEY ix_v20_sum_action (entry_action_v2_0, final_entry_grade_v2_0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
""")
    execute(conn, f"CREATE TABLE {qident(EXAMPLE_TABLE)} LIKE {qident(CANDIDATE_TABLE)}")


def score_amount(amount: float) -> float:
    if amount >= 10000000000.0:
        return 100.0
    if amount >= 5000000000.0:
        return 90.0
    if amount >= 3000000000.0:
        return 80.0
    if amount >= 2000000000.0:
        return 65.0
    if amount >= 1000000000.0:
        return 45.0
    return 20.0


def score_mae(mae: float) -> float:
    risk = max(0.0, -mae)
    return max(0.0, min(100.0, 100.0 - risk * 12.0))


def score_overheat(open_pct: float, low_pct: float) -> float:
    score = 100.0
    score -= max(0.0, open_pct - 2.0) * 8.0
    score -= max(0.0, low_pct - 4.0) * 5.0
    return max(0.0, min(100.0, score))


def calc_entry_score(row: Dict[str, Any]) -> float:
    execution_score = to_float(row.get("execution_score_v1_9"), 0.0)
    selected_return = to_float(row.get("selected_estimated_return_pct"), 0.0)
    selected_mae = to_float(row.get("selected_max_adverse_excursion_pct"), -99.0)
    amount = to_float(row.get("start_cum_amount"), 0.0)
    open_pct = to_float(row.get("start_from_day_open_pct"), 0.0)
    low_pct = to_float(row.get("start_from_day_low_pct"), 0.0)
    ret_score = max(0.0, min(100.0, selected_return * 7.0))
    total = 0.0
    total += execution_score * 0.42
    total += ret_score * 0.24
    total += score_mae(selected_mae) * 0.16
    total += score_amount(amount) * 0.12
    total += score_overheat(open_pct, low_pct) * 0.06
    return max(0.0, min(100.0, total))


def decide_action(row: Dict[str, Any], args: argparse.Namespace) -> Tuple[str, str, str, float, str]:
    policy = to_str(row.get("recommended_entry_policy_v1_9"))
    label = to_str(row.get("execution_label_v1_9"))
    timing = to_str(row.get("selected_entry_timing_v1_8"))
    execution_score = to_float(row.get("execution_score_v1_9"), 0.0)
    selected_return = to_float(row.get("selected_estimated_return_pct"), 0.0)
    selected_mae = to_float(row.get("selected_max_adverse_excursion_pct"), -99.0)
    next_mae = to_float(row.get("next_bar_mae_pct"), selected_mae)
    amount = to_float(row.get("start_cum_amount"), 0.0)
    open_pct = to_float(row.get("start_from_day_open_pct"), 0.0)
    low_pct = to_float(row.get("start_from_day_low_pct"), 0.0)
    entry_score = calc_entry_score(row)

    auto_ok = (
        policy == "NEXT_BAR_OPEN_AUTO" and
        label == "EXECUTION_AUTO_STRONG" and
        timing == "NEXT_BAR_OPEN" and
        execution_score >= args.auto_min_execution_score and
        entry_score >= args.auto_min_entry_score and
        selected_return >= args.auto_min_return_pct and
        selected_mae >= args.auto_min_mae_pct and
        next_mae >= args.auto_min_mae_pct and
        amount >= args.auto_min_amount and
        open_pct <= args.auto_max_open_pct and
        low_pct <= args.auto_max_low_pct
    )
    wait_ok = (
        policy == "WAIT_FIRST_PULLBACK" and
        selected_return >= args.wait_min_return_pct and
        selected_mae >= args.wait_min_mae_pct and
        entry_score >= args.wait_min_entry_score
    )
    confirm_ok = (
        policy == "HOGA_TICK_CONFIRM_REQUIRED" or
        label == "EXECUTION_CONFIRM_REQUIRED" or
        (policy == "NEXT_BAR_OPEN_AUTO" and selected_return >= args.confirm_min_return_pct and entry_score >= args.confirm_min_entry_score) or
        (policy == "WAIT_FIRST_PULLBACK" and selected_return >= args.confirm_min_return_pct and entry_score >= args.confirm_min_entry_score)
    )

    reasons: List[str] = []
    if auto_ok:
        action = ACTION_AUTO
        if entry_score >= 93.0 and selected_return >= 12.0 and selected_mae >= -1.0 and amount >= 5000000000.0:
            grade = "S"
            qty = 1.0
        else:
            grade = "A"
            qty = 0.7
        risk = "LOW" if selected_mae >= -1.0 else "NORMAL"
        reasons.append("v1.9 자동진입 강등급 유지")
        reasons.append("다음봉시가 잔여수익/MAE/거래대금 통과")
    elif wait_ok:
        action = ACTION_WAIT
        grade = "B"
        risk = "PULLBACK_WAIT"
        qty = 0.5
        reasons.append("대장성은 있으나 즉시 추격보다 첫 눌림 대기 우위")
    elif confirm_ok:
        action = ACTION_CONFIRM
        grade = "C"
        risk = "CONFIRM_REQUIRED"
        qty = 0.3
        reasons.append("차트 조건만으로 자동진입 부족: 호가/틱 확인 필요")
    else:
        action = ACTION_SKIP
        grade = "D"
        risk = "SKIP"
        qty = 0.0
        reasons.append("잔여수익/MAE/과열/거래대금 기준 미달")

    if open_pct > args.auto_max_open_pct or low_pct > args.auto_max_low_pct:
        reasons.append("장초반 상승폭 과열 감점")
    if amount < args.auto_min_amount:
        reasons.append("시작 누적거래대금 부족")
    if selected_mae < args.auto_min_mae_pct:
        reasons.append("진입 후 MAE 리스크 큼")
    return grade, action, risk, qty, "; ".join(reasons)


def load_source_rows(conn: Any, args: argparse.Namespace) -> List[Dict[str, Any]]:
    where_parts: List[str] = []
    params: List[Any] = []
    if args.only_filter_grade:
        where_parts.append("filter_grade_v1_6 = %s")
        params.append(args.only_filter_grade)
    if args.only_filter_label:
        where_parts.append("filter_label_v1_6 = %s")
        params.append(args.only_filter_label)
    if args.only_policy:
        where_parts.append("recommended_entry_policy_v1_9 = %s")
        params.append(args.only_policy)
    where_sql = ""
    if where_parts:
        where_sql = "WHERE " + " AND ".join(where_parts)
    limit_sql = "" if args.limit <= 0 else " LIMIT " + str(int(args.limit))
    sql = f"""
SELECT *
FROM {qident(args.source_table)}
{where_sql}
ORDER BY trade_date, code, st_period, st_multiplier, segment_no, execution_score_v1_9 DESC
{limit_sql}
"""
    return fetch_all(conn, sql, params)


def build_candidate_rows(rows: List[Dict[str, Any]], args: argparse.Namespace) -> List[Tuple[Any, ...]]:
    output: List[Tuple[Any, ...]] = []
    for r in rows:
        grade, action, risk, qty, reason = decide_action(r, args)
        entry_score = calc_entry_score(r)
        output.append((
            args.source_table,
            r.get("trade_date"), r.get("code"), r.get("name"), to_int(r.get("st_period")), to_float(r.get("st_multiplier")),
            to_int(r.get("segment_no")), r.get("st_up_start_time"), r.get("selected_entry_time"), r.get("selected_entry_price"),
            r.get("recommended_entry_policy_v1_9"), r.get("execution_label_v1_9"), to_float(r.get("execution_score_v1_9")),
            r.get("selected_entry_timing_v1_8"), r.get("selected_estimated_return_pct"), r.get("selected_max_adverse_excursion_pct"),
            r.get("selected_estimated_lost_move_pct"), r.get("next_bar_return_pct"), r.get("next_bar_mae_pct"),
            r.get("pullback_return_pct"), r.get("pullback_mae_pct"), r.get("start_from_day_open_pct"),
            r.get("start_from_day_low_pct"), r.get("start_cum_amount"), r.get("score_total"),
            r.get("filter_label_v1_6"), r.get("filter_grade_v1_6"), r.get("filter_score_v1_6"),
            grade, action, entry_score, risk, qty, reason, r.get("policy_reason_v1_9")
        ))
    return output


def insert_candidates(conn: Any, values: List[Tuple[Any, ...]]) -> int:
    if not values:
        return 0
    col_csv = ", ".join(qident(c) for c in OUTPUT_COLS)
    placeholders = ",".join(["%s"] * len(OUTPUT_COLS))
    sql = f"INSERT INTO {qident(CANDIDATE_TABLE)} ({col_csv}) VALUES ({placeholders})"
    with conn.cursor() as cur:
        cur.executemany(sql, values)
        return int(cur.rowcount)


def build_summary(conn: Any) -> None:
    execute(conn, f"""
INSERT INTO {qident(SUMMARY_TABLE)} (
    st_period, st_multiplier, final_entry_grade_v2_0, entry_action_v2_0,
    row_count, avg_entry_score_v2_0, avg_execution_score_v1_9, avg_selected_return_pct, avg_selected_mae_pct,
    avg_next_bar_return_pct, avg_next_bar_mae_pct, avg_pullback_return_pct, avg_pullback_mae_pct,
    avg_start_from_day_open_pct, avg_start_from_day_low_pct, avg_start_cum_amount
)
SELECT
    st_period,
    st_multiplier,
    final_entry_grade_v2_0,
    entry_action_v2_0,
    COUNT(*) AS row_count,
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
    AVG(start_cum_amount) AS avg_start_cum_amount
FROM {qident(CANDIDATE_TABLE)}
GROUP BY st_period, st_multiplier, final_entry_grade_v2_0, entry_action_v2_0
ORDER BY avg_entry_score_v2_0 DESC, avg_selected_return_pct DESC
""")


def build_examples(conn: Any, top_n: int) -> None:
    execute(conn, f"""
INSERT INTO {qident(EXAMPLE_TABLE)}
SELECT * FROM {qident(CANDIDATE_TABLE)}
WHERE entry_action_v2_0 <> 'SKIP'
ORDER BY
    CASE final_entry_grade_v2_0 WHEN 'S' THEN 1 WHEN 'A' THEN 2 WHEN 'B' THEN 3 WHEN 'C' THEN 4 ELSE 9 END,
    entry_score_v2_0 DESC,
    selected_estimated_return_pct DESC,
    selected_max_adverse_excursion_pct DESC
LIMIT {int(top_n)}
""")


def print_rows(title: str, rows: List[Dict[str, Any]]) -> None:
    print("\n=== " + title + " ===")
    for r in rows:
        print(dict(r))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build v2.0 realtime entry candidates from v1.9 execution policy table.")
    p.add_argument("--host", default="")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--database", default="")
    p.add_argument("--user", default="")
    p.add_argument("--password", default="")
    p.add_argument("--charset", default="utf8mb4")
    p.add_argument("--mysql-conn", default="")
    p.add_argument("--source-table", default=SOURCE_TABLE_DEFAULT)
    p.add_argument("--only-filter-grade", default="A")
    p.add_argument("--only-filter-label", default="ST_START_A_FAST_LEADER")
    p.add_argument("--only-policy", default="")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--example-top-n", type=int, default=120)
    p.add_argument("--auto-min-execution-score", type=float, default=90.0)
    p.add_argument("--auto-min-entry-score", type=float, default=88.0)
    p.add_argument("--auto-min-return-pct", type=float, default=10.0)
    p.add_argument("--auto-min-mae-pct", type=float, default=-1.5)
    p.add_argument("--auto-min-amount", type=float, default=3000000000.0)
    p.add_argument("--auto-max-open-pct", type=float, default=4.8)
    p.add_argument("--auto-max-low-pct", type=float, default=7.5)
    p.add_argument("--wait-min-entry-score", type=float, default=72.0)
    p.add_argument("--wait-min-return-pct", type=float, default=7.0)
    p.add_argument("--wait-min-mae-pct", type=float, default=-2.8)
    p.add_argument("--confirm-min-entry-score", type=float, default=60.0)
    p.add_argument("--confirm-min-return-pct", type=float, default=5.0)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    print("=== BUILD v2.0 ST Realtime Entry Candidate ===")
    cfg = build_mysql_config(args)
    conn = pymysql.connect(**cfg)
    try:
        assert_source_table(conn, args.source_table)
        create_output_tables(conn)
        rows = load_source_rows(conn, args)
        values = build_candidate_rows(rows, args)
        inserted = insert_candidates(conn, values)
        if inserted <= 0:
            raise RuntimeError("candidate table row_count=0 입니다. v1.9 source table 조건을 확인하세요.")
        build_summary(conn)
        build_examples(conn, args.example_top_n)
        conn.commit()

        print("source_table=", args.source_table)
        print("candidate_table=", CANDIDATE_TABLE)
        print("summary_table=", SUMMARY_TABLE)
        print("example_table=", EXAMPLE_TABLE)
        print("inserted_detail_rows=", inserted)
        print("auto_min_execution_score=", args.auto_min_execution_score)
        print("auto_min_return_pct=", args.auto_min_return_pct)
        print("auto_min_mae_pct=", args.auto_min_mae_pct)
        print("auto_min_amount=", args.auto_min_amount)

        summary = fetch_all(conn, f"SELECT * FROM {qident(SUMMARY_TABLE)} ORDER BY avg_entry_score_v2_0 DESC, avg_selected_return_pct DESC LIMIT 40")
        examples = fetch_all(conn, f"SELECT * FROM {qident(EXAMPLE_TABLE)} ORDER BY entry_score_v2_0 DESC, selected_estimated_return_pct DESC LIMIT 40")
        print_rows("v2.0 Realtime Entry Candidate Summary", summary)
        print_rows("v2.0 Realtime Entry Candidate Examples", examples)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
