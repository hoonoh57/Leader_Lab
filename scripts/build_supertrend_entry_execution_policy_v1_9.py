#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Leader_Lab v1.9
ST_START Entry Execution Policy Builder

MySQL 전용.

목표:
- v1.8 intraday timing 결과를 실전 진입정책으로 압축한다.
- ST_START_A_FAST_LEADER 후보에 대해 NEXT_BAR_OPEN / WAIT_FIRST_PULLBACK /
  HOGA_TICK_CONFIRM_REQUIRED / SKIP_HIGH_REBREAK 를 분기한다.
- 핵심 기준은 잔여수익률, MAE, 지연손실, 장초반 과열도, 누적거래대금이다.

입력:
- supertrend_start_entry_intraday_timing_detail_v1_8

출력:
- supertrend_entry_execution_policy_detail_v1_9
- supertrend_entry_execution_policy_summary_v1_9
- supertrend_entry_execution_policy_examples_v1_9
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import pymysql
    from pymysql.cursors import DictCursor
except Exception:
    print("[FATAL] pymysql import failed. Install with: py -3 -m pip install pymysql", file=sys.stderr)
    raise

SOURCE_TABLE_DEFAULT = "supertrend_start_entry_intraday_timing_detail_v1_8"
DETAIL_TABLE = "supertrend_entry_execution_policy_detail_v1_9"
SUMMARY_TABLE = "supertrend_entry_execution_policy_summary_v1_9"
EXAMPLE_TABLE = "supertrend_entry_execution_policy_examples_v1_9"

TIMING_ST_START_CLOSE = "ST_START_CLOSE"
TIMING_NEXT_BAR_OPEN = "NEXT_BAR_OPEN"
TIMING_FIRST_PULLBACK = "FIRST_PULLBACK"
TIMING_HIGH_REBREAK = "HIGH_REBREAK"

POLICY_NEXT_AUTO = "NEXT_BAR_OPEN_AUTO"
POLICY_WAIT_PULLBACK = "WAIT_FIRST_PULLBACK"
POLICY_HOGA_CONFIRM = "HOGA_TICK_CONFIRM_REQUIRED"
POLICY_SKIP_REBREAK = "HIGH_REBREAK_SKIP"
POLICY_SKIP_WEAK = "SKIP_WEAK_TIMING"

SOURCE_REQUIRED_COLS = [
    "trade_date", "code", "name", "st_period", "st_multiplier", "segment_no", "st_up_start_time",
    "entry_timing_v1_8", "entry_time", "entry_price", "estimated_return_pct", "max_adverse_excursion_pct",
    "estimated_lost_move_pct", "delay_penalty_vs_st_start_pct", "timing_score_v1_8", "timing_label_v1_8",
    "timing_rank_v1_8", "score_total", "filter_label_v1_6", "filter_grade_v1_6", "filter_score_v1_6",
    "st_start_estimated_return_pct", "early3_estimated_return_pct", "early3_high_return_pct",
    "post_early3_extension_pct", "start_from_day_open_pct", "start_from_day_low_pct", "start_cum_amount",
    "live_risk_score_v1_2"
]

DETAIL_COLS = [
    "source_table", "trade_date", "code", "name", "st_period", "st_multiplier", "segment_no", "st_up_start_time",
    "recommended_entry_policy_v1_9", "execution_label_v1_9", "execution_score_v1_9", "selected_entry_timing_v1_8",
    "selected_entry_time", "selected_entry_price", "selected_estimated_return_pct", "selected_max_adverse_excursion_pct",
    "selected_estimated_lost_move_pct", "selected_delay_penalty_pct", "selected_timing_score_v1_8",
    "next_bar_return_pct", "next_bar_mae_pct", "next_bar_lost_move_pct", "next_bar_timing_score_v1_8",
    "pullback_return_pct", "pullback_mae_pct", "pullback_lost_move_pct", "pullback_timing_score_v1_8",
    "rebreak_return_pct", "rebreak_mae_pct", "rebreak_lost_move_pct", "rebreak_timing_score_v1_8",
    "start_close_return_pct", "start_close_mae_pct", "start_close_timing_score_v1_8",
    "overheat_score_v1_9", "liquidity_score_v1_9", "mae_risk_score_v1_9", "delay_risk_score_v1_9",
    "start_from_day_open_pct", "start_from_day_low_pct", "start_cum_amount", "score_total", "filter_label_v1_6",
    "filter_grade_v1_6", "filter_score_v1_6", "live_risk_score_v1_2", "policy_reason_v1_9"
]


def parse_conn_string(conn_str: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    if not conn_str:
        return result
    for part in [p.strip() for p in conn_str.split(";") if p.strip()]:
        if "=" not in part:
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
    recommended_entry_policy_v1_9 VARCHAR(64) NOT NULL,
    execution_label_v1_9 VARCHAR(64) NOT NULL,
    execution_score_v1_9 DOUBLE NOT NULL,
    selected_entry_timing_v1_8 VARCHAR(64) NULL,
    selected_entry_time DATETIME NULL,
    selected_entry_price DOUBLE NULL,
    selected_estimated_return_pct DOUBLE NULL,
    selected_max_adverse_excursion_pct DOUBLE NULL,
    selected_estimated_lost_move_pct DOUBLE NULL,
    selected_delay_penalty_pct DOUBLE NULL,
    selected_timing_score_v1_8 DOUBLE NULL,
    next_bar_return_pct DOUBLE NULL,
    next_bar_mae_pct DOUBLE NULL,
    next_bar_lost_move_pct DOUBLE NULL,
    next_bar_timing_score_v1_8 DOUBLE NULL,
    pullback_return_pct DOUBLE NULL,
    pullback_mae_pct DOUBLE NULL,
    pullback_lost_move_pct DOUBLE NULL,
    pullback_timing_score_v1_8 DOUBLE NULL,
    rebreak_return_pct DOUBLE NULL,
    rebreak_mae_pct DOUBLE NULL,
    rebreak_lost_move_pct DOUBLE NULL,
    rebreak_timing_score_v1_8 DOUBLE NULL,
    start_close_return_pct DOUBLE NULL,
    start_close_mae_pct DOUBLE NULL,
    start_close_timing_score_v1_8 DOUBLE NULL,
    overheat_score_v1_9 DOUBLE NOT NULL,
    liquidity_score_v1_9 DOUBLE NOT NULL,
    mae_risk_score_v1_9 DOUBLE NOT NULL,
    delay_risk_score_v1_9 DOUBLE NOT NULL,
    start_from_day_open_pct DOUBLE NULL,
    start_from_day_low_pct DOUBLE NULL,
    start_cum_amount DOUBLE NULL,
    score_total DOUBLE NULL,
    filter_label_v1_6 VARCHAR(64) NULL,
    filter_grade_v1_6 VARCHAR(8) NULL,
    filter_score_v1_6 DOUBLE NULL,
    live_risk_score_v1_2 DOUBLE NULL,
    policy_reason_v1_9 VARCHAR(512) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY ix_v19_key (trade_date, code, st_period, st_multiplier, segment_no),
    KEY ix_v19_policy (recommended_entry_policy_v1_9, execution_label_v1_9),
    KEY ix_v19_score (execution_score_v1_9),
    KEY ix_v19_selected_time (selected_entry_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
""")
    execute(conn, f"""
CREATE TABLE {qident(SUMMARY_TABLE)} (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    filter_grade_v1_6 VARCHAR(8) NOT NULL,
    filter_label_v1_6 VARCHAR(64) NOT NULL,
    recommended_entry_policy_v1_9 VARCHAR(64) NOT NULL,
    execution_label_v1_9 VARCHAR(64) NOT NULL,
    row_count INT NOT NULL,
    avg_execution_score_v1_9 DOUBLE NULL,
    avg_selected_return_pct DOUBLE NULL,
    avg_selected_mae_pct DOUBLE NULL,
    avg_selected_lost_move_pct DOUBLE NULL,
    avg_next_bar_return_pct DOUBLE NULL,
    avg_next_bar_mae_pct DOUBLE NULL,
    avg_pullback_return_pct DOUBLE NULL,
    avg_pullback_mae_pct DOUBLE NULL,
    avg_overheat_score_v1_9 DOUBLE NULL,
    avg_liquidity_score_v1_9 DOUBLE NULL,
    avg_start_from_day_open_pct DOUBLE NULL,
    avg_start_from_day_low_pct DOUBLE NULL,
    avg_start_cum_amount DOUBLE NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY ix_v19_sum (st_period, st_multiplier, recommended_entry_policy_v1_9, execution_label_v1_9),
    KEY ix_v19_sum_score (avg_execution_score_v1_9)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
""")
    execute(conn, f"CREATE TABLE {qident(EXAMPLE_TABLE)} LIKE {qident(DETAIL_TABLE)}")


def load_source_rows(conn: Any, source_table: str, args: argparse.Namespace) -> List[Dict[str, Any]]:
    where_parts = ["filter_grade_v1_6 = %s"]
    params: List[Any] = [args.filter_grade]
    if args.filter_label:
        where_parts.append("filter_label_v1_6 = %s")
        params.append(args.filter_label)
    lim = "" if args.limit <= 0 else " LIMIT " + str(int(args.limit))
    sql = f"""
SELECT *
FROM {qident(source_table)}
WHERE {' AND '.join(where_parts)}
ORDER BY trade_date, code, st_period, st_multiplier, segment_no, timing_rank_v1_8, timing_score_v1_8 DESC
{lim}
"""
    return fetch_all(conn, sql, params)


def group_rows(rows: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    groups: List[List[Dict[str, Any]]] = []
    current_key: Optional[Tuple[Any, ...]] = None
    current: List[Dict[str, Any]] = []
    for r in rows:
        key = (r.get("trade_date"), r.get("code"), r.get("st_period"), r.get("st_multiplier"), r.get("segment_no"))
        if current_key is None:
            current_key = key
        if key != current_key:
            groups.append(current)
            current = []
            current_key = key
        current.append(r)
    if current:
        groups.append(current)
    return groups


def first_by_timing(group: List[Dict[str, Any]], timing: str) -> Optional[Dict[str, Any]]:
    selected: Optional[Dict[str, Any]] = None
    best_score = -1.0
    for r in group:
        if str(r.get("entry_timing_v1_8")) != timing:
            continue
        s = to_float(r.get("timing_score_v1_8"), -1.0)
        if selected is None or s > best_score:
            selected = r
            best_score = s
    return selected


def metric(row: Optional[Dict[str, Any]], key: str, default: Optional[float] = None) -> Optional[float]:
    if row is None:
        return default
    return to_float(row.get(key), 0.0)


def score_overheat(open_pct: float, low_pct: float) -> float:
    score = 100.0
    score -= max(0.0, open_pct - 2.0) * 8.0
    score -= max(0.0, low_pct - 4.0) * 5.0
    return max(0.0, min(100.0, score))


def score_liquidity(amount: float) -> float:
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


def score_mae(mae: Optional[float]) -> float:
    if mae is None:
        return 50.0
    risk = max(0.0, -mae)
    return max(0.0, min(100.0, 100.0 - risk * 12.0))


def score_delay(delay: Optional[float]) -> float:
    if delay is None:
        return 50.0
    return max(0.0, min(100.0, 100.0 - max(0.0, delay) * 14.0))


def execution_label(score: float, policy: str) -> str:
    if policy == POLICY_NEXT_AUTO and score >= 88.0:
        return "EXECUTION_AUTO_STRONG"
    if policy == POLICY_WAIT_PULLBACK and score >= 78.0:
        return "EXECUTION_WAIT_GOOD"
    if policy == POLICY_HOGA_CONFIRM:
        return "EXECUTION_CONFIRM_REQUIRED"
    if policy == POLICY_SKIP_REBREAK:
        return "EXECUTION_SKIP_REBREAK_RISK"
    if score >= 70.0:
        return "EXECUTION_WATCH"
    return "EXECUTION_SKIP_WEAK"


def choose_policy(group: List[Dict[str, Any]], args: argparse.Namespace) -> Tuple[str, str, float, Optional[Dict[str, Any]], str, float, float, float, float]:
    base = group[0]
    start = first_by_timing(group, TIMING_ST_START_CLOSE)
    next_bar = first_by_timing(group, TIMING_NEXT_BAR_OPEN)
    pullback = first_by_timing(group, TIMING_FIRST_PULLBACK)
    rebreak = first_by_timing(group, TIMING_HIGH_REBREAK)

    open_pct = to_float(base.get("start_from_day_open_pct"))
    low_pct = to_float(base.get("start_from_day_low_pct"))
    amount = to_float(base.get("start_cum_amount"))

    overheat = score_overheat(open_pct, low_pct)
    liquidity = score_liquidity(amount)
    next_mae = metric(next_bar, "max_adverse_excursion_pct")
    next_delay = metric(next_bar, "delay_penalty_vs_st_start_pct")
    mae_risk = score_mae(next_mae)
    delay_risk = score_delay(next_delay)

    next_ret = metric(next_bar, "estimated_return_pct", 0.0) or 0.0
    next_score = metric(next_bar, "timing_score_v1_8", 0.0) or 0.0
    pull_ret = metric(pullback, "estimated_return_pct", 0.0) or 0.0
    pull_mae = metric(pullback, "max_adverse_excursion_pct", -99.0) or -99.0
    pull_score = metric(pullback, "timing_score_v1_8", 0.0) or 0.0
    rb_mae = metric(rebreak, "max_adverse_excursion_pct", 0.0) or 0.0
    rb_score = metric(rebreak, "timing_score_v1_8", 0.0) or 0.0

    severe_overheat = open_pct >= args.severe_open_pct or low_pct >= args.severe_low_pct
    moderate_overheat = open_pct >= args.moderate_open_pct or low_pct >= args.moderate_low_pct
    poor_next_mae = next_mae is not None and next_mae < args.max_next_mae_pct
    weak_liquidity = amount < args.min_auto_amount
    rebreak_risky = rebreak is not None and (rb_mae <= args.rebreak_skip_mae_pct or rb_score < args.rebreak_min_score)

    selected: Optional[Dict[str, Any]] = None
    policy = POLICY_SKIP_WEAK
    reason_parts: List[str] = []

    if rebreak_risky and next_bar is None and pullback is None:
        policy = POLICY_SKIP_REBREAK
        selected = rebreak
        reason_parts.append("재돌파만 존재하지만 MAE/점수 기준 위험")
    elif next_bar is not None and next_ret >= args.min_auto_return_pct and next_score >= args.min_auto_timing_score and not poor_next_mae and not severe_overheat and not weak_liquidity:
        policy = POLICY_NEXT_AUTO
        selected = next_bar
        reason_parts.append("다음봉 시가 진입: 잔여수익/MAE/거래대금 통과")
        if moderate_overheat:
            reason_parts.append("다만 장초반 상승폭은 중간 과열권")
    elif pullback is not None and pull_ret >= args.min_pullback_return_pct and pull_mae >= args.max_pullback_mae_pct and pull_score >= args.min_pullback_timing_score:
        policy = POLICY_WAIT_PULLBACK
        selected = pullback
        reason_parts.append("눌림 진입 우위: 과열 또는 다음봉 리스크를 눌림으로 완화")
    elif next_bar is not None and next_ret >= args.min_confirm_return_pct:
        policy = POLICY_HOGA_CONFIRM
        selected = next_bar
        reason_parts.append("다음봉 수익 여지는 있으나 과열/MAE/거래대금 중 확인 필요")
    elif rebreak_risky:
        policy = POLICY_SKIP_REBREAK
        selected = rebreak
        reason_parts.append("고가 재돌파는 MAE가 커서 추격 제외")
    else:
        policy = POLICY_SKIP_WEAK
        selected = next_bar or pullback or start or rebreak
        reason_parts.append("잔여수익 또는 타이밍 품질 부족")

    selected_ret = metric(selected, "estimated_return_pct", 0.0) or 0.0
    selected_mae = metric(selected, "max_adverse_excursion_pct", -99.0) or -99.0
    selected_delay = metric(selected, "delay_penalty_vs_st_start_pct", 99.0) or 99.0
    selected_score = metric(selected, "timing_score_v1_8", 0.0) or 0.0

    exec_score = 0.0
    exec_score += min(35.0, selected_ret * 3.0)
    exec_score += max(0.0, min(25.0, selected_score * 0.25))
    exec_score += max(0.0, min(15.0, liquidity * 0.15))
    exec_score += max(0.0, min(15.0, mae_risk * 0.15))
    exec_score += max(0.0, min(10.0, delay_risk * 0.10))
    if severe_overheat:
        exec_score -= 12.0
    elif moderate_overheat:
        exec_score -= 5.0
    if policy == POLICY_HOGA_CONFIRM:
        exec_score -= 8.0
    if policy in (POLICY_SKIP_REBREAK, POLICY_SKIP_WEAK):
        exec_score = min(exec_score, 55.0)
    exec_score = max(0.0, min(100.0, exec_score))

    label = execution_label(exec_score, policy)
    reason = "; ".join(reason_parts)
    return policy, label, exec_score, selected, reason, overheat, liquidity, mae_risk, delay_risk


def make_detail_row(group: List[Dict[str, Any]], args: argparse.Namespace, source_table: str) -> Tuple[Any, ...]:
    base = group[0]
    start = first_by_timing(group, TIMING_ST_START_CLOSE)
    next_bar = first_by_timing(group, TIMING_NEXT_BAR_OPEN)
    pullback = first_by_timing(group, TIMING_FIRST_PULLBACK)
    rebreak = first_by_timing(group, TIMING_HIGH_REBREAK)
    policy, label, exec_score, selected, reason, overheat, liquidity, mae_risk, delay_risk = choose_policy(group, args)

    return (
        source_table, base.get("trade_date"), base.get("code"), base.get("name"), to_int(base.get("st_period")),
        to_float(base.get("st_multiplier")), to_int(base.get("segment_no")), base.get("st_up_start_time"),
        policy, label, exec_score,
        None if selected is None else selected.get("entry_timing_v1_8"),
        None if selected is None else selected.get("entry_time"),
        None if selected is None else selected.get("entry_price"),
        metric(selected, "estimated_return_pct"), metric(selected, "max_adverse_excursion_pct"),
        metric(selected, "estimated_lost_move_pct"), metric(selected, "delay_penalty_vs_st_start_pct"),
        metric(selected, "timing_score_v1_8"),
        metric(next_bar, "estimated_return_pct"), metric(next_bar, "max_adverse_excursion_pct"),
        metric(next_bar, "estimated_lost_move_pct"), metric(next_bar, "timing_score_v1_8"),
        metric(pullback, "estimated_return_pct"), metric(pullback, "max_adverse_excursion_pct"),
        metric(pullback, "estimated_lost_move_pct"), metric(pullback, "timing_score_v1_8"),
        metric(rebreak, "estimated_return_pct"), metric(rebreak, "max_adverse_excursion_pct"),
        metric(rebreak, "estimated_lost_move_pct"), metric(rebreak, "timing_score_v1_8"),
        metric(start, "estimated_return_pct"), metric(start, "max_adverse_excursion_pct"), metric(start, "timing_score_v1_8"),
        overheat, liquidity, mae_risk, delay_risk,
        to_float(base.get("start_from_day_open_pct")), to_float(base.get("start_from_day_low_pct")),
        to_float(base.get("start_cum_amount")), to_float(base.get("score_total")), base.get("filter_label_v1_6"),
        base.get("filter_grade_v1_6"), to_float(base.get("filter_score_v1_6")), to_float(base.get("live_risk_score_v1_2")),
        reason
    )


def build_detail(conn: Any, rows: List[Dict[str, Any]], args: argparse.Namespace, source_table: str) -> int:
    groups = group_rows(rows)
    values: List[Tuple[Any, ...]] = []
    for group in groups:
        values.append(make_detail_row(group, args, source_table))
    if not values:
        return 0
    col_csv = ", ".join(qident(c) for c in DETAIL_COLS)
    placeholders = ",".join(["%s"] * len(DETAIL_COLS))
    sql = f"INSERT INTO {qident(DETAIL_TABLE)} ({col_csv}) VALUES ({placeholders})"
    with conn.cursor() as cur:
        cur.executemany(sql, values)
        return int(cur.rowcount)


def build_summary(conn: Any) -> None:
    execute(conn, f"""
INSERT INTO {qident(SUMMARY_TABLE)} (
    st_period, st_multiplier, filter_grade_v1_6, filter_label_v1_6, recommended_entry_policy_v1_9, execution_label_v1_9,
    row_count, avg_execution_score_v1_9, avg_selected_return_pct, avg_selected_mae_pct, avg_selected_lost_move_pct,
    avg_next_bar_return_pct, avg_next_bar_mae_pct, avg_pullback_return_pct, avg_pullback_mae_pct,
    avg_overheat_score_v1_9, avg_liquidity_score_v1_9, avg_start_from_day_open_pct, avg_start_from_day_low_pct, avg_start_cum_amount
)
SELECT
    st_period, st_multiplier, filter_grade_v1_6, filter_label_v1_6, recommended_entry_policy_v1_9, execution_label_v1_9,
    COUNT(*) AS row_count,
    AVG(execution_score_v1_9), AVG(selected_estimated_return_pct), AVG(selected_max_adverse_excursion_pct), AVG(selected_estimated_lost_move_pct),
    AVG(next_bar_return_pct), AVG(next_bar_mae_pct), AVG(pullback_return_pct), AVG(pullback_mae_pct),
    AVG(overheat_score_v1_9), AVG(liquidity_score_v1_9), AVG(start_from_day_open_pct), AVG(start_from_day_low_pct), AVG(start_cum_amount)
FROM {qident(DETAIL_TABLE)}
GROUP BY st_period, st_multiplier, filter_grade_v1_6, filter_label_v1_6, recommended_entry_policy_v1_9, execution_label_v1_9
ORDER BY avg_execution_score_v1_9 DESC, avg_selected_return_pct DESC
""")


def build_examples(conn: Any, top_n: int) -> None:
    execute(conn, f"""
INSERT INTO {qident(EXAMPLE_TABLE)}
SELECT * FROM {qident(DETAIL_TABLE)}
ORDER BY execution_score_v1_9 DESC, selected_estimated_return_pct DESC, selected_max_adverse_excursion_pct DESC
LIMIT {int(top_n)}
""")


def print_rows(title: str, rows: List[Dict[str, Any]]) -> None:
    print("\n=== " + title + " ===")
    for r in rows:
        print(dict(r))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build v1.9 ST entry execution policy from v1.8 intraday timing table.")
    p.add_argument("--host", default="")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--database", default="")
    p.add_argument("--user", default="")
    p.add_argument("--password", default="")
    p.add_argument("--charset", default="utf8mb4")
    p.add_argument("--mysql-conn", default="")
    p.add_argument("--source-table", default=SOURCE_TABLE_DEFAULT)
    p.add_argument("--filter-grade", default="A")
    p.add_argument("--filter-label", default="ST_START_A_FAST_LEADER")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--example-top-n", type=int, default=120)
    p.add_argument("--min-auto-amount", type=float, default=3000000000.0)
    p.add_argument("--min-auto-return-pct", type=float, default=5.0)
    p.add_argument("--min-confirm-return-pct", type=float, default=2.0)
    p.add_argument("--min-auto-timing-score", type=float, default=96.0)
    p.add_argument("--max-next-mae-pct", type=float, default=-3.5)
    p.add_argument("--min-pullback-return-pct", type=float, default=5.0)
    p.add_argument("--min-pullback-timing-score", type=float, default=92.0)
    p.add_argument("--max-pullback-mae-pct", type=float, default=-4.5)
    p.add_argument("--moderate-open-pct", type=float, default=3.5)
    p.add_argument("--moderate-low-pct", type=float, default=6.0)
    p.add_argument("--severe-open-pct", type=float, default=5.5)
    p.add_argument("--severe-low-pct", type=float, default=8.0)
    p.add_argument("--rebreak-skip-mae-pct", type=float, default=-8.0)
    p.add_argument("--rebreak-min-score", type=float, default=70.0)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    print("=== BUILD v1.9 ST Entry Execution Policy ===")
    cfg = build_mysql_config(args)
    conn = pymysql.connect(**cfg)
    try:
        source_table = args.source_table
        assert_source_table(conn, source_table)
        create_output_tables(conn)
        rows = load_source_rows(conn, source_table, args)
        detail_count = build_detail(conn, rows, args, source_table)
        if detail_count <= 0:
            raise RuntimeError("detail table row_count=0 입니다. v1.8 source table/filter 조건을 확인하세요.")
        build_summary(conn)
        build_examples(conn, args.example_top_n)
        conn.commit()
        print("source_table=", source_table)
        print("detail_table=", DETAIL_TABLE)
        print("summary_table=", SUMMARY_TABLE)
        print("example_table=", EXAMPLE_TABLE)
        print("source_timing_rows=", len(rows))
        print("detail_rows=", detail_count)
        print_rows("v1.9 Execution Policy Summary", fetch_all(conn, f"SELECT * FROM {qident(SUMMARY_TABLE)} ORDER BY avg_execution_score_v1_9 DESC, avg_selected_return_pct DESC LIMIT 60"))
        print_rows("v1.9 Execution Policy Examples", fetch_all(conn, f"SELECT trade_date, code, name, st_period, st_multiplier, segment_no, st_up_start_time, recommended_entry_policy_v1_9, execution_label_v1_9, execution_score_v1_9, selected_entry_timing_v1_8, selected_entry_time, selected_entry_price, selected_estimated_return_pct, selected_max_adverse_excursion_pct, selected_estimated_lost_move_pct, next_bar_return_pct, next_bar_mae_pct, pullback_return_pct, pullback_mae_pct, start_from_day_open_pct, start_from_day_low_pct, start_cum_amount, policy_reason_v1_9 FROM {qident(EXAMPLE_TABLE)} ORDER BY execution_score_v1_9 DESC, selected_estimated_return_pct DESC LIMIT 80"))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
