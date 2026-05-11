#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Leader_Lab v1.5
ST_START vs EARLY3 Failure Diagnostics

원칙:
- MySQL 전용
- SQLite / --db-path 사용 금지
- 기존 v1.2/v1.3 산출 테이블을 읽어 ST_START 진입과 EARLY3 진입의 성과 차이를 진단
- 로컬에서는 git pull 후 ps1 실행만 수행

권장 입력:
1) supertrend_continuation_entry_discovery_v1_3 계열 상세 테이블이 있으면 우선 사용
2) 없으면 supertrend_segment_ranking_discovery_v1_2 계열 상세 테이블을 사용하여 fallback 계산

필요 환경변수 우선순위:
- MYSQL_CONN / DB_CONN / MYSQL_CONNECTION_STRING
- DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS
- MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE, MYSQL_USER, MYSQL_PASSWORD
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import pymysql
    from pymysql.cursors import DictCursor
except Exception as exc:  # pragma: no cover
    print("[FATAL] pymysql import failed. Install with: py -3 -m pip install pymysql", file=sys.stderr)
    raise


DETAIL_TABLE = "supertrend_start_vs_early3_failure_diag_v1_5"
SUMMARY_TABLE = "supertrend_start_vs_early3_failure_summary_v1_5"

V13_REQUIRED = [
    "trade_date", "code", "name", "st_period", "st_multiplier", "segment_no", "st_up_start_time",
    "entry_type", "score_total", "st_up_max_return_pct", "early3_high_return_pct",
    "post_early3_extension_pct", "estimated_max_return_after_entry_pct",
    "estimated_lost_move_before_entry_pct", "continuation_score_v1_3",
    "continuation_label_v1_3", "live_filter_label_v1_2", "post_diagnostic_label_v1_2",
    "start_from_day_open_pct", "start_from_day_low_pct", "start_cum_amount"
]

V12_REQUIRED = [
    "trade_date", "code", "name", "st_period", "st_multiplier", "segment_no", "st_up_start_time",
    "score_total", "st_up_max_return_pct", "quality_label", "live_filter_label_v1_2",
    "post_diagnostic_label_v1_2", "rank_return_in_stock_param", "early3_high_return_pct",
    "post_early3_extension_pct", "start_from_day_open_pct", "start_from_day_low_pct",
    "start_cum_amount", "live_risk_score_v1_2"
]

V13_TABLE_HINTS = [
    "supertrend_continuation_entry_discovery_v1_3",
    "st_continuation_entry_discovery_v1_3",
    "supertrend_continuation_entry_detail_v1_3",
    "supertrend_continuation_entry_examples_v1_3",
]

V12_TABLE_HINTS = [
    "supertrend_segment_ranking_discovery_v1_2",
    "st_segment_ranking_discovery_v1_2",
    "supertrend_segment_ranking_detail_v1_2",
]


def norm_key(row: Dict[str, Any], key: str) -> Any:
    if key in row:
        return row[key]
    lk = key.lower()
    uk = key.upper()
    for k, v in row.items():
        ks = str(k)
        if ks == key or ks.lower() == lk or ks.upper() == uk:
            return v
    raise KeyError(key)


def get_first(row: Dict[str, Any], keys: Sequence[str], default: Any = None) -> Any:
    for key in keys:
        try:
            return norm_key(row, key)
        except KeyError:
            pass
    return default


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
        elif key in ("port",):
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
    conn_env = (
        args.mysql_conn
        or os.environ.get("MYSQL_CONN")
        or os.environ.get("DB_CONN")
        or os.environ.get("MYSQL_CONNECTION_STRING")
        or ""
    )
    cfg = parse_conn_string(conn_env)

    host = args.host or cfg.get("host") or os.environ.get("DB_HOST") or os.environ.get("MYSQL_HOST") or "127.0.0.1"
    port = args.port or cfg.get("port") or os.environ.get("DB_PORT") or os.environ.get("MYSQL_PORT") or 3306
    database = args.database or cfg.get("database") or os.environ.get("DB_NAME") or os.environ.get("MYSQL_DATABASE")
    user = args.user or cfg.get("user") or os.environ.get("DB_USER") or os.environ.get("MYSQL_USER") or "root"
    password = args.password or cfg.get("password") or os.environ.get("DB_PASS") or os.environ.get("MYSQL_PASSWORD") or ""
    charset = args.charset or cfg.get("charset") or os.environ.get("DB_CHARSET") or "utf8mb4"

    if not database:
        raise RuntimeError("MySQL DB_NAME/MYSQL_DATABASE 또는 --database 값이 필요합니다.")

    return {
        "host": str(host),
        "port": int(port),
        "database": str(database),
        "user": str(user),
        "password": str(password),
        "charset": str(charset),
        "cursorclass": DictCursor,
        "autocommit": False,
    }


def qident(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError(f"Unsafe identifier: {name}")
    return "`" + name + "`"


def fetch_all(conn: Any, sql: str, params: Optional[Sequence[Any]] = None) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return list(cur.fetchall())


def execute(conn: Any, sql: str, params: Optional[Sequence[Any]] = None) -> int:
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return int(cur.rowcount)


def list_tables(conn: Any) -> List[str]:
    rows = fetch_all(conn, "SELECT table_name AS table_name FROM information_schema.tables WHERE table_schema = DATABASE() ORDER BY table_name")
    out: List[str] = []
    for r in rows:
        val = get_first(r, ["table_name", "TABLE_NAME"])
        if val is not None:
            out.append(str(val))
    return out


def get_columns(conn: Any, table_name: str) -> List[str]:
    rows = fetch_all(
        conn,
        "SELECT column_name AS column_name FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = %s ORDER BY ordinal_position",
        [table_name],
    )
    out: List[str] = []
    for r in rows:
        val = get_first(r, ["column_name", "COLUMN_NAME"])
        if val is not None:
            out.append(str(val))
    return out


def has_required_columns(conn: Any, table_name: str, required: Sequence[str]) -> Tuple[bool, List[str]]:
    cols = get_columns(conn, table_name)
    colset = set(c.lower() for c in cols)
    missing = [c for c in required if c.lower() not in colset]
    return len(missing) == 0, missing


def table_exists(conn: Any, table_name: str) -> bool:
    rows = fetch_all(
        conn,
        "SELECT COUNT(*) AS cnt FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = %s",
        [table_name],
    )
    return to_int(get_first(rows[0], ["cnt", "COUNT(*)"], 0), 0) > 0 if rows else False


def auto_find_table(conn: Any, explicit: str, hints: Sequence[str], required: Sequence[str], label: str) -> Optional[str]:
    if explicit:
        ok, missing = has_required_columns(conn, explicit, required)
        if not ok:
            raise RuntimeError(f"지정한 {label} table={explicit} 에 필수 컬럼이 없습니다: {missing}")
        return explicit

    tables = list_tables(conn)
    lower_to_real = {t.lower(): t for t in tables}

    for hint in hints:
        real = lower_to_real.get(hint.lower())
        if real:
            ok, _ = has_required_columns(conn, real, required)
            if ok:
                return real

    # Wider scan: prefer names containing supertrend and version marker.
    scored: List[Tuple[int, str]] = []
    for t in tables:
        tl = t.lower()
        score = 0
        if "supertrend" in tl or "st_" in tl:
            score += 10
        if "v1_3" in tl and label == "v1.3":
            score += 20
        if "v1_2" in tl and label == "v1.2":
            score += 20
        if "continuation" in tl and label == "v1.3":
            score += 15
        if "segment" in tl and label == "v1.2":
            score += 15
        if score <= 0:
            continue
        ok, _ = has_required_columns(conn, t, required)
        if ok:
            scored.append((score, t))
    if scored:
        scored.sort(key=lambda x: (-x[0], x[1]))
        return scored[0][1]

    return None


def create_tables(conn: Any) -> None:
    execute(conn, f"DROP TABLE IF EXISTS {qident(SUMMARY_TABLE)}")
    execute(conn, f"DROP TABLE IF EXISTS {qident(DETAIL_TABLE)}")

    execute(conn, f"""
CREATE TABLE {qident(DETAIL_TABLE)} (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    source_mode VARCHAR(16) NOT NULL,
    source_table VARCHAR(128) NOT NULL,
    trade_date DATE NOT NULL,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(128) NULL,
    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    segment_no INT NOT NULL,
    st_up_start_time DATETIME NULL,
    score_total DOUBLE NULL,
    st_up_max_return_pct DOUBLE NULL,
    st_start_estimated_return_pct DOUBLE NULL,
    early3_estimated_return_pct DOUBLE NULL,
    early3_high_return_pct DOUBLE NULL,
    post_early3_extension_pct DOUBLE NULL,
    early3_lost_move_pct DOUBLE NULL,
    st_start_success_flag TINYINT NOT NULL DEFAULT 0,
    early3_success_flag TINYINT NOT NULL DEFAULT 0,
    st_start_weak_flag TINYINT NOT NULL DEFAULT 0,
    early3_fail_flag TINYINT NOT NULL DEFAULT 0,
    start_wins_early3_fails_flag TINYINT NOT NULL DEFAULT 0,
    early3_missed_big_move_flag TINYINT NOT NULL DEFAULT 0,
    post_peak_exhausted_flag TINYINT NOT NULL DEFAULT 0,
    open_overheated_flag TINYINT NOT NULL DEFAULT 0,
    low_overextended_flag TINYINT NOT NULL DEFAULT 0,
    amount_heavy_flag TINYINT NOT NULL DEFAULT 0,
    late_entry_flag TINYINT NOT NULL DEFAULT 0,
    live_filter_label_v1_2 VARCHAR(255) NULL,
    post_diagnostic_label_v1_2 VARCHAR(255) NULL,
    failure_reason_v1_5 VARCHAR(255) NOT NULL,
    action_hint_v1_5 VARCHAR(255) NOT NULL,
    start_from_day_open_pct DOUBLE NULL,
    start_from_day_low_pct DOUBLE NULL,
    start_cum_amount DOUBLE NULL,
    live_risk_score_v1_2 DOUBLE NULL,
    continuation_score_v1_3 DOUBLE NULL,
    continuation_label_v1_3 VARCHAR(64) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY ix_v15_key (trade_date, code, st_period, st_multiplier, segment_no),
    KEY ix_v15_reason (failure_reason_v1_5),
    KEY ix_v15_action (action_hint_v1_5),
    KEY ix_v15_score (score_total),
    KEY ix_v15_return (st_up_max_return_pct, early3_estimated_return_pct)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
""")

    execute(conn, f"""
CREATE TABLE {qident(SUMMARY_TABLE)} (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    source_mode VARCHAR(16) NOT NULL,
    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    failure_reason_v1_5 VARCHAR(255) NOT NULL,
    action_hint_v1_5 VARCHAR(255) NOT NULL,
    row_count INT NOT NULL,
    avg_score_total DOUBLE NULL,
    avg_st_up_max_return_pct DOUBLE NULL,
    avg_st_start_estimated_return_pct DOUBLE NULL,
    avg_early3_estimated_return_pct DOUBLE NULL,
    median_early3_estimated_return_pct DOUBLE NULL,
    avg_early3_lost_move_pct DOUBLE NULL,
    avg_early3_high_return_pct DOUBLE NULL,
    avg_post_early3_extension_pct DOUBLE NULL,
    st_start_success_rate DOUBLE NULL,
    early3_success_rate DOUBLE NULL,
    early3_fail_rate DOUBLE NULL,
    start_wins_early3_fails_rate DOUBLE NULL,
    early3_missed_big_move_rate DOUBLE NULL,
    post_peak_exhausted_rate DOUBLE NULL,
    avg_start_from_day_open_pct DOUBLE NULL,
    avg_start_from_day_low_pct DOUBLE NULL,
    avg_start_cum_amount DOUBLE NULL,
    avg_live_risk_score_v1_2 DOUBLE NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY ix_v15_sum_rank (st_period, st_multiplier, failure_reason_v1_5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
""")


def median(values: List[float]) -> Optional[float]:
    arr = sorted(v for v in values if v is not None)
    if not arr:
        return None
    n = len(arr)
    mid = n // 2
    if n % 2 == 1:
        return arr[mid]
    return (arr[mid - 1] + arr[mid]) / 2.0


def classify_reason(row: Dict[str, Any], success_return_pct: float, weak_return_pct: float, early_top_n: int) -> Tuple[str, str, Dict[str, int]]:
    st_ret = to_float(row.get("st_start_estimated_return_pct"))
    e_ret = to_float(row.get("early3_estimated_return_pct"))
    early3_high = to_float(row.get("early3_high_return_pct"))
    post_ext = to_float(row.get("post_early3_extension_pct"))
    start_open = to_float(row.get("start_from_day_open_pct"))
    start_low = to_float(row.get("start_from_day_low_pct"))
    risk = to_float(row.get("live_risk_score_v1_2"))
    live = str(row.get("live_filter_label_v1_2") or "")
    post = str(row.get("post_diagnostic_label_v1_2") or "")

    flags = {
        "st_start_success_flag": 1 if st_ret >= success_return_pct else 0,
        "early3_success_flag": 1 if e_ret >= success_return_pct else 0,
        "st_start_weak_flag": 1 if st_ret < weak_return_pct else 0,
        "early3_fail_flag": 1 if e_ret < weak_return_pct else 0,
        "start_wins_early3_fails_flag": 1 if (st_ret >= success_return_pct and e_ret < weak_return_pct) else 0,
        "early3_missed_big_move_flag": 1 if early3_high >= 6.0 and e_ret < weak_return_pct else 0,
        "post_peak_exhausted_flag": 1 if ("PEAK_EXHAUSTED" in post or post_ext <= 0.25) else 0,
        "open_overheated_flag": 1 if ("OPEN_OVERHEATED" in live or start_open >= 9.0) else 0,
        "low_overextended_flag": 1 if ("LOW_OVEREXTENDED" in live or start_low >= 10.0) else 0,
        "amount_heavy_flag": 1 if "AMOUNT_HEAVY" in live else 0,
        "late_entry_flag": 1 if "LATE" in live else 0,
    }

    if flags["start_wins_early3_fails_flag"] == 1:
        return "ST_START_WINS_EARLY3_FAILS", "ST_START 우선 진입 후보. EARLY3 대기는 수익구간 소실", flags
    if flags["post_peak_exhausted_flag"] == 1 and flags["early3_missed_big_move_flag"] == 1:
        return "EARLY3_ALREADY_EXHAUSTED", "EARLY3 진입 금지. 이미 1차 피크 소진", flags
    if flags["open_overheated_flag"] == 1 and flags["low_overextended_flag"] == 1:
        return "OPEN_AND_LOW_OVEREXTENDED", "시초 과열+저점대비 과확장. 눌림 재확인 필요", flags
    if flags["open_overheated_flag"] == 1:
        return "OPEN_OVERHEATED", "시가대비 과열. ST_START라도 비중 축소", flags
    if flags["low_overextended_flag"] == 1:
        return "LOW_OVEREXTENDED", "저점대비 과확장. 추격 진입 제한", flags
    if flags["late_entry_flag"] == 1:
        return "LATE_SEGMENT", "후반 ST 구간. 장초반 대장 검증과 분리", flags
    if flags["amount_heavy_flag"] == 1 and post_ext <= 1.0:
        return "AMOUNT_HEAVY_NO_EXTENSION", "거래대금 과다 대비 후속 확장 부족", flags
    if st_ret >= success_return_pct and e_ret >= success_return_pct:
        return "BOTH_START_AND_EARLY3_OK", "ST_START/확인진입 모두 가능. 체결강도/틱강도로 선택", flags
    if st_ret < weak_return_pct and e_ret < weak_return_pct:
        return "BOTH_WEAK", "ST 구간 자체 약함. 후보군 제외", flags
    if e_ret >= success_return_pct and st_ret < success_return_pct:
        return "EARLY3_BETTER_THAN_START", "확인 후 진입형. ST_START 성급진입 제한", flags
    if risk >= 50.0:
        return "LIVE_RISK_HIGH", "실시간 위험점수 높음. 자동매매 제외 후보", flags
    return "NEUTRAL", "추가 필터 필요. 테마/틱강도/호가흡수로 재분류", flags


def load_v13_join_rows(conn: Any, source_table: str, limit: int) -> List[Dict[str, Any]]:
    lim = "" if limit <= 0 else f" LIMIT {int(limit)}"
    sql = f"""
SELECT
    s.trade_date,
    s.code,
    s.name,
    s.st_period,
    s.st_multiplier,
    s.segment_no,
    s.st_up_start_time,
    s.score_total,
    s.st_up_max_return_pct,
    s.estimated_max_return_after_entry_pct AS st_start_estimated_return_pct,
    e.estimated_max_return_after_entry_pct AS early3_estimated_return_pct,
    e.early3_high_return_pct,
    e.post_early3_extension_pct,
    e.estimated_lost_move_before_entry_pct AS early3_lost_move_pct,
    e.live_filter_label_v1_2,
    e.post_diagnostic_label_v1_2,
    e.start_from_day_open_pct,
    e.start_from_day_low_pct,
    e.start_cum_amount,
    NULL AS live_risk_score_v1_2,
    e.continuation_score_v1_3,
    e.continuation_label_v1_3
FROM {qident(source_table)} s
JOIN {qident(source_table)} e
  ON s.trade_date = e.trade_date
 AND s.code = e.code
 AND s.st_period = e.st_period
 AND s.st_multiplier = e.st_multiplier
 AND s.segment_no = e.segment_no
WHERE s.entry_type = 'ST_START_ENTRY'
  AND e.entry_type = 'EARLY3_COMPOSITE_ENTRY'
ORDER BY s.trade_date, s.code, s.st_period, s.st_multiplier, s.segment_no
{lim}
"""
    return fetch_all(conn, sql)


def load_v12_rows(conn: Any, source_table: str, limit: int) -> List[Dict[str, Any]]:
    lim = "" if limit <= 0 else f" LIMIT {int(limit)}"
    sql = f"""
SELECT
    trade_date,
    code,
    name,
    st_period,
    st_multiplier,
    segment_no,
    st_up_start_time,
    score_total,
    st_up_max_return_pct,
    st_up_max_return_pct AS st_start_estimated_return_pct,
    post_early3_extension_pct AS early3_estimated_return_pct,
    early3_high_return_pct,
    post_early3_extension_pct,
    early3_high_return_pct AS early3_lost_move_pct,
    live_filter_label_v1_2,
    post_diagnostic_label_v1_2,
    start_from_day_open_pct,
    start_from_day_low_pct,
    start_cum_amount,
    live_risk_score_v1_2,
    NULL AS continuation_score_v1_3,
    NULL AS continuation_label_v1_3
FROM {qident(source_table)}
WHERE rank_return_in_stock_param = 1 OR rank_return_in_stock_param IS NULL
ORDER BY trade_date, code, st_period, st_multiplier, segment_no
{lim}
"""
    return fetch_all(conn, sql)


def insert_detail_rows(conn: Any, source_mode: str, source_table: str, rows: List[Dict[str, Any]], success_return_pct: float, weak_return_pct: float, early_top_n: int) -> int:
    sql = f"""
INSERT INTO {qident(DETAIL_TABLE)} (
    source_mode, source_table, trade_date, code, name, st_period, st_multiplier, segment_no, st_up_start_time,
    score_total, st_up_max_return_pct, st_start_estimated_return_pct, early3_estimated_return_pct,
    early3_high_return_pct, post_early3_extension_pct, early3_lost_move_pct,
    st_start_success_flag, early3_success_flag, st_start_weak_flag, early3_fail_flag,
    start_wins_early3_fails_flag, early3_missed_big_move_flag, post_peak_exhausted_flag,
    open_overheated_flag, low_overextended_flag, amount_heavy_flag, late_entry_flag,
    live_filter_label_v1_2, post_diagnostic_label_v1_2, failure_reason_v1_5, action_hint_v1_5,
    start_from_day_open_pct, start_from_day_low_pct, start_cum_amount, live_risk_score_v1_2,
    continuation_score_v1_3, continuation_label_v1_3
) VALUES (
    %s,%s,%s,%s,%s,%s,%s,%s,%s,
    %s,%s,%s,%s,
    %s,%s,%s,
    %s,%s,%s,%s,
    %s,%s,%s,
    %s,%s,%s,%s,
    %s,%s,%s,%s,
    %s,%s,%s,%s,
    %s,%s
)
"""
    values: List[Tuple[Any, ...]] = []
    for r in rows:
        rr = dict(r)
        reason, action, flags = classify_reason(rr, success_return_pct, weak_return_pct, early_top_n)
        values.append((
            source_mode, source_table,
            rr.get("trade_date"), rr.get("code"), rr.get("name"), to_int(rr.get("st_period")), to_float(rr.get("st_multiplier")),
            to_int(rr.get("segment_no")), rr.get("st_up_start_time"),
            to_float(rr.get("score_total")), to_float(rr.get("st_up_max_return_pct")),
            to_float(rr.get("st_start_estimated_return_pct")), to_float(rr.get("early3_estimated_return_pct")),
            to_float(rr.get("early3_high_return_pct")), to_float(rr.get("post_early3_extension_pct")),
            to_float(rr.get("early3_lost_move_pct")),
            flags["st_start_success_flag"], flags["early3_success_flag"], flags["st_start_weak_flag"], flags["early3_fail_flag"],
            flags["start_wins_early3_fails_flag"], flags["early3_missed_big_move_flag"], flags["post_peak_exhausted_flag"],
            flags["open_overheated_flag"], flags["low_overextended_flag"], flags["amount_heavy_flag"], flags["late_entry_flag"],
            rr.get("live_filter_label_v1_2"), rr.get("post_diagnostic_label_v1_2"), reason, action,
            to_float(rr.get("start_from_day_open_pct")), to_float(rr.get("start_from_day_low_pct")),
            to_float(rr.get("start_cum_amount")), to_float(rr.get("live_risk_score_v1_2")),
            None if rr.get("continuation_score_v1_3") is None else to_float(rr.get("continuation_score_v1_3")),
            rr.get("continuation_label_v1_3"),
        ))

    if not values:
        return 0
    with conn.cursor() as cur:
        cur.executemany(sql, values)
        return int(cur.rowcount)


def build_summary(conn: Any) -> int:
    rows = fetch_all(conn, f"SELECT * FROM {qident(DETAIL_TABLE)}")
    grouped: Dict[Tuple[str, int, float, str, str], List[Dict[str, Any]]] = {}
    for r in rows:
        key = (
            str(r["source_mode"]),
            to_int(r["st_period"]),
            to_float(r["st_multiplier"]),
            str(r["failure_reason_v1_5"]),
            str(r["action_hint_v1_5"]),
        )
        grouped.setdefault(key, []).append(r)

    insert_sql = f"""
INSERT INTO {qident(SUMMARY_TABLE)} (
    source_mode, st_period, st_multiplier, failure_reason_v1_5, action_hint_v1_5, row_count,
    avg_score_total, avg_st_up_max_return_pct, avg_st_start_estimated_return_pct,
    avg_early3_estimated_return_pct, median_early3_estimated_return_pct,
    avg_early3_lost_move_pct, avg_early3_high_return_pct, avg_post_early3_extension_pct,
    st_start_success_rate, early3_success_rate, early3_fail_rate,
    start_wins_early3_fails_rate, early3_missed_big_move_rate, post_peak_exhausted_rate,
    avg_start_from_day_open_pct, avg_start_from_day_low_pct, avg_start_cum_amount, avg_live_risk_score_v1_2
) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
"""

    def avg(items: List[Dict[str, Any]], key: str) -> Optional[float]:
        vals = [to_float(x.get(key)) for x in items if x.get(key) is not None]
        if not vals:
            return None
        return sum(vals) / float(len(vals))

    vals: List[Tuple[Any, ...]] = []
    for key, items in grouped.items():
        source_mode, st_period, st_multiplier, reason, action = key
        n = len(items)
        early_vals = [to_float(x.get("early3_estimated_return_pct")) for x in items if x.get("early3_estimated_return_pct") is not None]
        vals.append((
            source_mode, st_period, st_multiplier, reason, action, n,
            avg(items, "score_total"),
            avg(items, "st_up_max_return_pct"),
            avg(items, "st_start_estimated_return_pct"),
            avg(items, "early3_estimated_return_pct"),
            median(early_vals),
            avg(items, "early3_lost_move_pct"),
            avg(items, "early3_high_return_pct"),
            avg(items, "post_early3_extension_pct"),
            avg(items, "st_start_success_flag"),
            avg(items, "early3_success_flag"),
            avg(items, "early3_fail_flag"),
            avg(items, "start_wins_early3_fails_flag"),
            avg(items, "early3_missed_big_move_flag"),
            avg(items, "post_peak_exhausted_flag"),
            avg(items, "start_from_day_open_pct"),
            avg(items, "start_from_day_low_pct"),
            avg(items, "start_cum_amount"),
            avg(items, "live_risk_score_v1_2"),
        ))

    if not vals:
        return 0
    with conn.cursor() as cur:
        cur.executemany(insert_sql, vals)
        return int(cur.rowcount)


def print_rows(title: str, rows: List[Dict[str, Any]], max_rows: int = 30) -> None:
    print(f"\n=== {title} ===")
    for r in rows[:max_rows]:
        print(dict(r))
    if len(rows) > max_rows:
        print(f"... {len(rows) - max_rows} more rows")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build MySQL-only ST_START vs EARLY3 failure diagnostics v1.5")
    p.add_argument("--mysql-conn", default="", help="Optional MySQL connection string")
    p.add_argument("--host", default="")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--database", default="")
    p.add_argument("--user", default="")
    p.add_argument("--password", default="")
    p.add_argument("--charset", default="utf8mb4")
    p.add_argument("--source-table", default="", help="Explicit v1.3 detail table or v1.2 fallback table")
    p.add_argument("--prefer", choices=["v13", "v12"], default="v13")
    p.add_argument("--limit", type=int, default=0, help="0 means all rows")
    p.add_argument("--early-top-n", type=int, default=3)
    p.add_argument("--weak-return-pct", type=float, default=2.0)
    p.add_argument("--success-return-pct", type=float, default=5.0)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = build_mysql_config(args)
    safe_cfg = dict(cfg)
    safe_cfg["password"] = "***" if safe_cfg.get("password") else ""
    print("=== BUILD v1.5 ST_START vs EARLY3 Failure Diagnostics ===")
    print(f"mysql={safe_cfg['host']}:{safe_cfg['port']} db={safe_cfg['database']} user={safe_cfg['user']}")

    conn = pymysql.connect(**cfg)
    try:
        explicit = args.source_table.strip()
        source_mode = ""
        source_table: Optional[str] = None

        if explicit:
            ok13, _ = has_required_columns(conn, explicit, V13_REQUIRED)
            ok12, _ = has_required_columns(conn, explicit, V12_REQUIRED)
            if ok13:
                source_mode = "v1.3"
                source_table = explicit
            elif ok12:
                source_mode = "v1.2"
                source_table = explicit
            else:
                raise RuntimeError(f"지정 source_table={explicit} 는 v1.3/v1.2 필수 컬럼 조건을 만족하지 않습니다.")
        else:
            if args.prefer == "v13":
                source_table = auto_find_table(conn, "", V13_TABLE_HINTS, V13_REQUIRED, "v1.3")
                if source_table:
                    source_mode = "v1.3"
                else:
                    source_table = auto_find_table(conn, "", V12_TABLE_HINTS, V12_REQUIRED, "v1.2")
                    source_mode = "v1.2" if source_table else ""
            else:
                source_table = auto_find_table(conn, "", V12_TABLE_HINTS, V12_REQUIRED, "v1.2")
                if source_table:
                    source_mode = "v1.2"
                else:
                    source_table = auto_find_table(conn, "", V13_TABLE_HINTS, V13_REQUIRED, "v1.3")
                    source_mode = "v1.3" if source_table else ""

        if not source_table:
            tables = list_tables(conn)
            raise RuntimeError("v1.3/v1.2 SuperTrend source table을 찾지 못했습니다. --source-table을 지정하세요. tables=" + ", ".join(tables[:50]))

        print(f"source_mode={source_mode}")
        print(f"source_table={source_table}")

        create_tables(conn)

        if source_mode == "v1.3":
            rows = load_v13_join_rows(conn, source_table, args.limit)
        else:
            rows = load_v12_rows(conn, source_table, args.limit)

        print(f"source_rows={len(rows)}")
        inserted = insert_detail_rows(conn, source_mode, source_table, rows, args.success_return_pct, args.weak_return_pct, args.early_top_n)
        summary_inserted = build_summary(conn)
        conn.commit()

        print(f"detail_inserted={inserted}")
        print(f"summary_inserted={summary_inserted}")

        summary_rows = fetch_all(conn, f"""
SELECT
    source_mode, st_period, st_multiplier, failure_reason_v1_5, action_hint_v1_5, row_count,
    avg_st_start_estimated_return_pct, avg_early3_estimated_return_pct, median_early3_estimated_return_pct,
    avg_early3_lost_move_pct, st_start_success_rate, early3_success_rate, early3_fail_rate,
    start_wins_early3_fails_rate, early3_missed_big_move_rate, post_peak_exhausted_rate
FROM {qident(SUMMARY_TABLE)}
ORDER BY row_count DESC, start_wins_early3_fails_rate DESC, early3_fail_rate DESC
""")
        print_rows("v1.5 Failure Summary", summary_rows, 40)

        bad_rows = fetch_all(conn, f"""
SELECT
    trade_date, code, name, st_period, st_multiplier, segment_no, st_up_start_time,
    score_total, st_start_estimated_return_pct, early3_estimated_return_pct,
    early3_high_return_pct, post_early3_extension_pct, early3_lost_move_pct,
    failure_reason_v1_5, action_hint_v1_5, live_filter_label_v1_2, post_diagnostic_label_v1_2,
    start_from_day_open_pct, start_from_day_low_pct, start_cum_amount
FROM {qident(DETAIL_TABLE)}
WHERE start_wins_early3_fails_flag = 1 OR early3_missed_big_move_flag = 1 OR post_peak_exhausted_flag = 1
ORDER BY score_total DESC, st_start_estimated_return_pct DESC
LIMIT 50
""")
        print_rows("v1.5 Key Failure Examples", bad_rows, 50)

        print("\n=== DONE scripts/build_supertrend_start_vs_early3_failure_v1_5.ps1 ===")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
