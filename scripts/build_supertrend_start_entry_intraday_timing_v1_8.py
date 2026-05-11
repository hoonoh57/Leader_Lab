#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Leader_Lab v1.8
ST_START Fast Leader Intraday Timing Builder

MySQL 전용.

목표:
- v1.6 A등급 FAST_LEADER 후보를 실제 1분봉/분봉 테이블과 조인한다.
- ST_START 즉시/다음봉시가/눌림/고가재돌파 타이밍을 같은 표본에서 비교한다.
- v1.7에서 REQUIRES_INTRADAY_JOIN 으로 남긴 타이밍들을 실제 가격 기준으로 측정한다.

기본 입력:
- source table: supertrend_start_entry_filter_detail_v1_6
- candle table: 자동 탐색 또는 --candle-table 직접 지정

출력:
- supertrend_start_entry_intraday_timing_detail_v1_8
- supertrend_start_entry_intraday_timing_summary_v1_8
- supertrend_start_entry_intraday_timing_examples_v1_8
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date, datetime, time
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import pymysql
    from pymysql.cursors import DictCursor
except Exception:
    print("[FATAL] pymysql import failed. Install with: py -3 -m pip install pymysql", file=sys.stderr)
    raise

SOURCE_TABLE_DEFAULT = "supertrend_start_entry_filter_detail_v1_6"
DETAIL_TABLE = "supertrend_start_entry_intraday_timing_detail_v1_8"
SUMMARY_TABLE = "supertrend_start_entry_intraday_timing_summary_v1_8"
EXAMPLE_TABLE = "supertrend_start_entry_intraday_timing_examples_v1_8"

TIMING_ST_START_CLOSE = "ST_START_CLOSE"
TIMING_NEXT_BAR_OPEN = "NEXT_BAR_OPEN"
TIMING_FIRST_PULLBACK = "FIRST_PULLBACK"
TIMING_HIGH_REBREAK = "HIGH_REBREAK"

SOURCE_REQUIRED_COLS = [
    "trade_date", "code", "name", "st_period", "st_multiplier", "segment_no", "st_up_start_time",
    "score_total", "st_start_estimated_return_pct", "early3_estimated_return_pct", "early3_high_return_pct",
    "post_early3_extension_pct", "start_from_day_open_pct", "start_from_day_low_pct", "start_cum_amount",
    "live_risk_score_v1_2", "filter_label_v1_6", "filter_grade_v1_6", "filter_score_v1_6",
    "entry_decision_v1_6", "auto_entry_candidate", "skip_candidate"
]

DETAIL_COLS = [
    "source_table", "candle_table", "trade_date", "code", "name", "st_period", "st_multiplier", "segment_no",
    "st_up_start_time", "entry_timing_v1_8", "entry_time", "entry_price", "entry_bar_index_from_start",
    "future_high_after_entry", "future_high_time", "future_low_after_entry", "future_low_time",
    "estimated_return_pct", "max_adverse_excursion_pct", "estimated_lost_move_pct", "delay_penalty_vs_st_start_pct",
    "timing_score_v1_8", "timing_label_v1_8", "timing_rank_v1_8", "validation_status_v1_8", "timing_reason_v1_8",
    "score_total", "filter_label_v1_6", "filter_grade_v1_6", "filter_score_v1_6", "entry_decision_v1_6",
    "st_start_estimated_return_pct", "early3_estimated_return_pct", "early3_high_return_pct", "post_early3_extension_pct",
    "start_from_day_open_pct", "start_from_day_low_pct", "start_cum_amount", "live_risk_score_v1_2"
]

CANDIDATE_CANDLE_TABLES = [
    "minute_candles", "minute_candle", "intraday_candles", "intraday_candle", "candles_minute", "candles_m1",
    "m1_candles", "candle_m1", "stock_minute_candles", "daily_intraday_candles", "price_candles_m1"
]

CODE_COLS = ["code", "ticker", "symbol", "stock_code"]
DATE_COLS = ["trade_date", "date", "ymd", "candle_date"]
TIME_COLS = ["dt", "datetime", "timestamp", "time", "candle_time", "bar_time", "start_time", "time_stamp"]
OPEN_COLS = ["open", "open_price", "o"]
HIGH_COLS = ["high", "high_price", "h"]
LOW_COLS = ["low", "low_price", "l"]
CLOSE_COLS = ["close", "close_price", "c"]
VOLUME_COLS = ["volume", "vol", "qty"]
AMOUNT_COLS = ["amount", "trade_amount", "cum_amount", "value"]


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
    cols: List[str] = []
    for r in rows:
        v = r.get("column_name")
        if v is not None:
            cols.append(str(v))
    return cols


def find_col(cols: Sequence[str], candidates: Sequence[str]) -> str:
    lower_map: Dict[str, str] = {}
    for c in cols:
        lower_map[c.lower()] = c
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    return ""


def assert_source_table(conn: Any, table_name: str) -> None:
    if not table_exists(conn, table_name):
        raise RuntimeError("source table not found: " + table_name)
    cols = set(c.lower() for c in get_columns(conn, table_name))
    missing = [c for c in SOURCE_REQUIRED_COLS if c.lower() not in cols]
    if missing:
        raise RuntimeError("source table required columns missing: " + ", ".join(missing))


def detect_candle_mapping(conn: Any, requested_table: str) -> Dict[str, str]:
    candidates: List[str] = []
    if requested_table:
        candidates.append(requested_table)
    candidates.extend(CANDIDATE_CANDLE_TABLES)
    rows = fetch_all(conn, "SELECT table_name AS table_name FROM information_schema.tables WHERE table_schema = DATABASE() ORDER BY table_name")
    for r in rows:
        t = str(r.get("table_name") or "")
        tl = t.lower()
        if ("candle" in tl or "minute" in tl or tl.endswith("_m1")) and t not in candidates:
            candidates.append(t)

    checked: List[str] = []
    for table_name in candidates:
        if not table_name or not table_exists(conn, table_name):
            continue
        cols = get_columns(conn, table_name)
        mapping = {
            "table": table_name,
            "code": find_col(cols, CODE_COLS),
            "date": find_col(cols, DATE_COLS),
            "time": find_col(cols, TIME_COLS),
            "open": find_col(cols, OPEN_COLS),
            "high": find_col(cols, HIGH_COLS),
            "low": find_col(cols, LOW_COLS),
            "close": find_col(cols, CLOSE_COLS),
            "volume": find_col(cols, VOLUME_COLS),
            "amount": find_col(cols, AMOUNT_COLS),
        }
        ok = bool(mapping["code"] and mapping["time"] and mapping["open"] and mapping["high"] and mapping["low"] and mapping["close"])
        # date 컬럼이 없어도 datetime 컬럼 하나로 날짜 필터가 가능하므로 허용한다.
        if ok:
            return mapping
        checked.append(table_name + "(" + ",".join(cols[:12]) + ")")
    raise RuntimeError("분봉 candle table 자동 탐색 실패. --candle-table을 지정하세요. checked=" + " | ".join(checked[:10]))


def create_output_tables(conn: Any) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(EXAMPLE_TABLE))
    execute(conn, "DROP TABLE IF EXISTS " + qident(SUMMARY_TABLE))
    execute(conn, "DROP TABLE IF EXISTS " + qident(DETAIL_TABLE))
    execute(conn, f"""
CREATE TABLE {qident(DETAIL_TABLE)} (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    source_table VARCHAR(128) NOT NULL,
    candle_table VARCHAR(128) NOT NULL,
    trade_date DATE NOT NULL,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(128) NULL,
    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    segment_no INT NOT NULL,
    st_up_start_time DATETIME NULL,
    entry_timing_v1_8 VARCHAR(64) NOT NULL,
    entry_time DATETIME NULL,
    entry_price DOUBLE NULL,
    entry_bar_index_from_start INT NULL,
    future_high_after_entry DOUBLE NULL,
    future_high_time DATETIME NULL,
    future_low_after_entry DOUBLE NULL,
    future_low_time DATETIME NULL,
    estimated_return_pct DOUBLE NULL,
    max_adverse_excursion_pct DOUBLE NULL,
    estimated_lost_move_pct DOUBLE NULL,
    delay_penalty_vs_st_start_pct DOUBLE NULL,
    timing_score_v1_8 DOUBLE NOT NULL,
    timing_label_v1_8 VARCHAR(64) NOT NULL,
    timing_rank_v1_8 INT NOT NULL,
    validation_status_v1_8 VARCHAR(64) NOT NULL,
    timing_reason_v1_8 VARCHAR(255) NOT NULL,
    score_total DOUBLE NULL,
    filter_label_v1_6 VARCHAR(64) NULL,
    filter_grade_v1_6 VARCHAR(8) NULL,
    filter_score_v1_6 DOUBLE NULL,
    entry_decision_v1_6 VARCHAR(255) NULL,
    st_start_estimated_return_pct DOUBLE NULL,
    early3_estimated_return_pct DOUBLE NULL,
    early3_high_return_pct DOUBLE NULL,
    post_early3_extension_pct DOUBLE NULL,
    start_from_day_open_pct DOUBLE NULL,
    start_from_day_low_pct DOUBLE NULL,
    start_cum_amount DOUBLE NULL,
    live_risk_score_v1_2 DOUBLE NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY ix_v18_key (trade_date, code, st_period, st_multiplier, segment_no),
    KEY ix_v18_timing (entry_timing_v1_8, timing_label_v1_8),
    KEY ix_v18_score (timing_score_v1_8),
    KEY ix_v18_entry_time (entry_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
""")
    execute(conn, f"""
CREATE TABLE {qident(SUMMARY_TABLE)} (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    filter_grade_v1_6 VARCHAR(8) NOT NULL,
    filter_label_v1_6 VARCHAR(64) NOT NULL,
    entry_timing_v1_8 VARCHAR(64) NOT NULL,
    timing_label_v1_8 VARCHAR(64) NOT NULL,
    row_count INT NOT NULL,
    avg_timing_score_v1_8 DOUBLE NULL,
    avg_estimated_return_pct DOUBLE NULL,
    median_estimated_return_pct DOUBLE NULL,
    avg_max_adverse_excursion_pct DOUBLE NULL,
    avg_estimated_lost_move_pct DOUBLE NULL,
    avg_delay_penalty_vs_st_start_pct DOUBLE NULL,
    avg_score_total DOUBLE NULL,
    avg_filter_score_v1_6 DOUBLE NULL,
    avg_start_from_day_open_pct DOUBLE NULL,
    avg_start_from_day_low_pct DOUBLE NULL,
    avg_start_cum_amount DOUBLE NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY ix_v18_sum (st_period, st_multiplier, filter_grade_v1_6, entry_timing_v1_8),
    KEY ix_v18_sum_score (avg_timing_score_v1_8)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
""")
    execute(conn, f"CREATE TABLE {qident(EXAMPLE_TABLE)} LIKE {qident(DETAIL_TABLE)}")


def load_source_rows(conn: Any, source_table: str, args: argparse.Namespace) -> List[Dict[str, Any]]:
    where_parts = ["filter_grade_v1_6 = %s", "skip_candidate = 0"]
    params: List[Any] = [args.filter_grade]
    if args.filter_label:
        where_parts.append("filter_label_v1_6 = %s")
        params.append(args.filter_label)
    lim = "" if args.limit <= 0 else " LIMIT " + str(int(args.limit))
    sql = f"""
SELECT
    trade_date, code, name, st_period, st_multiplier, segment_no, st_up_start_time,
    score_total, st_start_estimated_return_pct, early3_estimated_return_pct, early3_high_return_pct,
    post_early3_extension_pct, start_from_day_open_pct, start_from_day_low_pct, start_cum_amount,
    live_risk_score_v1_2, filter_label_v1_6, filter_grade_v1_6, filter_score_v1_6,
    entry_decision_v1_6, auto_entry_candidate, skip_candidate
FROM {qident(source_table)}
WHERE {' AND '.join(where_parts)}
ORDER BY trade_date, code, st_period, st_multiplier, segment_no
{lim}
"""
    return fetch_all(conn, sql, params)


def normalize_datetime(value: Any, fallback_date: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time(0, 0))
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y%m%d%H%M%S", "%Y%m%d%H%M"):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            pass
    if re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", text):
        d = fallback_date
        if isinstance(d, datetime):
            dd = d.date()
        elif isinstance(d, date):
            dd = d
        else:
            dd = datetime.strptime(str(d), "%Y-%m-%d").date()
        fmt = "%H:%M:%S" if text.count(":") == 2 else "%H:%M"
        tt = datetime.strptime(text, fmt).time()
        return datetime.combine(dd, tt)
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def candle_time_expr(mapping: Dict[str, str]) -> str:
    return qident(mapping["time"])


def load_candles_for_event(conn: Any, mapping: Dict[str, str], row: Dict[str, Any], args: argparse.Namespace) -> List[Dict[str, Any]]:
    table_name = mapping["table"]
    time_col = mapping["time"]
    code_col = mapping["code"]
    start_dt = normalize_datetime(row.get("st_up_start_time"), row.get("trade_date"))
    if start_dt is None:
        return []
    end_dt = datetime.combine(start_dt.date(), time(args.session_end_hour, args.session_end_minute))
    select_cols = [
        f"{qident(time_col)} AS candle_time",
        f"{qident(mapping['open'])} AS open_price",
        f"{qident(mapping['high'])} AS high_price",
        f"{qident(mapping['low'])} AS low_price",
        f"{qident(mapping['close'])} AS close_price",
    ]
    if mapping.get("volume"):
        select_cols.append(f"{qident(mapping['volume'])} AS volume")
    else:
        select_cols.append("NULL AS volume")
    if mapping.get("amount"):
        select_cols.append(f"{qident(mapping['amount'])} AS amount")
    else:
        select_cols.append("NULL AS amount")

    where = [f"{qident(code_col)} = %s"]
    params: List[Any] = [row.get("code")]
    if mapping.get("date"):
        date_col = mapping["date"]
        where.append(f"{qident(date_col)} = %s")
        params.append(row.get("trade_date"))
    where.append(f"{qident(time_col)} >= %s")
    where.append(f"{qident(time_col)} <= %s")
    params.extend([start_dt, end_dt])
    sql = f"""
SELECT {', '.join(select_cols)}
FROM {qident(table_name)}
WHERE {' AND '.join(where)}
ORDER BY {qident(time_col)}
LIMIT {int(args.max_bars_after_start)}
"""
    candles = fetch_all(conn, sql, params)
    if candles:
        return candles

    # 일부 DB는 time 컬럼이 TIME 문자열이고 date 컬럼과 조합해야 한다.
    if mapping.get("date"):
        t0 = start_dt.strftime("%H:%M:%S")
        t1 = end_dt.strftime("%H:%M:%S")
        sql2 = f"""
SELECT {', '.join(select_cols)}
FROM {qident(table_name)}
WHERE {qident(code_col)} = %s AND {qident(mapping['date'])} = %s
  AND {qident(time_col)} >= %s AND {qident(time_col)} <= %s
ORDER BY {qident(time_col)}
LIMIT {int(args.max_bars_after_start)}
"""
        return fetch_all(conn, sql2, [row.get("code"), row.get("trade_date"), t0, t1])
    return []


def get_candle_dt(candle: Dict[str, Any], fallback_date: Any) -> Optional[datetime]:
    return normalize_datetime(candle.get("candle_time"), fallback_date)


def pct(numer: float, denom: float) -> float:
    if denom <= 0:
        return 0.0
    return (numer - denom) / denom * 100.0


def future_stats(candles: List[Dict[str, Any]], entry_index: int, entry_price: float, fallback_date: Any) -> Tuple[float, Optional[datetime], float, Optional[datetime]]:
    high_price = entry_price
    low_price = entry_price
    high_dt: Optional[datetime] = None
    low_dt: Optional[datetime] = None
    for i in range(entry_index, len(candles)):
        h = to_float(candles[i].get("high_price"))
        l = to_float(candles[i].get("low_price"))
        dt = get_candle_dt(candles[i], fallback_date)
        if h > high_price:
            high_price = h
            high_dt = dt
        if l < low_price:
            low_price = l
            low_dt = dt
    return high_price, high_dt, low_price, low_dt


def timing_label(score: float, ret_pct: float, mae_pct: float) -> str:
    if ret_pct >= 7.0 and mae_pct >= -3.0 and score >= 85.0:
        return "TIMING_STRONG"
    if ret_pct >= 5.0 and mae_pct >= -4.5:
        return "TIMING_GOOD"
    if ret_pct >= 2.0:
        return "TIMING_WATCH"
    return "TIMING_WEAK"


def make_detail_for_timing(
    row: Dict[str, Any], candles: List[Dict[str, Any]], timing_name: str, entry_index: int, entry_price: float,
    source_table: str, candle_table: str, reason: str
) -> Tuple[Any, ...]:
    fallback_date = row.get("trade_date")
    entry_candle = candles[entry_index]
    entry_dt = get_candle_dt(entry_candle, fallback_date)
    future_high, future_high_dt, future_low, future_low_dt = future_stats(candles, entry_index, entry_price, fallback_date)
    ret_pct = pct(future_high, entry_price)
    mae_pct = pct(future_low, entry_price)
    st_ref = to_float(row.get("st_start_estimated_return_pct"))
    lost = max(0.0, st_ref - ret_pct)
    delay = lost
    score = 100.0
    score -= min(45.0, max(0.0, delay) * 4.0)
    score -= min(25.0, max(0.0, -mae_pct) * 3.0)
    score += min(20.0, max(0.0, ret_pct) * 1.5)
    score = max(0.0, min(100.0, score))
    label = timing_label(score, ret_pct, mae_pct)
    return (
        source_table, candle_table, row.get("trade_date"), row.get("code"), row.get("name"), to_int(row.get("st_period")),
        to_float(row.get("st_multiplier")), to_int(row.get("segment_no")), row.get("st_up_start_time"), timing_name,
        entry_dt, entry_price, entry_index, future_high, future_high_dt, future_low, future_low_dt,
        ret_pct, mae_pct, lost, delay, score, label, 0, "MEASURED_INTRADAY", reason,
        to_float(row.get("score_total")), row.get("filter_label_v1_6"), row.get("filter_grade_v1_6"), to_float(row.get("filter_score_v1_6")),
        row.get("entry_decision_v1_6"), to_float(row.get("st_start_estimated_return_pct")), to_float(row.get("early3_estimated_return_pct")),
        to_float(row.get("early3_high_return_pct")), to_float(row.get("post_early3_extension_pct")),
        to_float(row.get("start_from_day_open_pct")), to_float(row.get("start_from_day_low_pct")),
        to_float(row.get("start_cum_amount")), to_float(row.get("live_risk_score_v1_2"))
    )


def find_first_pullback(candles: List[Dict[str, Any]], args: argparse.Namespace) -> Tuple[int, float]:
    start_close = to_float(candles[0].get("close_price"))
    start_low = to_float(candles[0].get("low_price"))
    if start_close <= 0:
        return -1, 0.0
    best_idx = -1
    best_price = 0.0
    max_i = min(len(candles) - 1, int(args.pullback_lookahead_bars))
    threshold = start_close * (1.0 - args.pullback_min_pct / 100.0)
    for i in range(1, max_i + 1):
        low_price = to_float(candles[i].get("low_price"))
        if low_price <= 0:
            continue
        if low_price <= threshold and low_price >= start_low * (1.0 - args.pullback_max_break_pct / 100.0):
            if best_idx < 0 or low_price < best_price:
                best_idx = i
                best_price = low_price
    return best_idx, best_price


def find_high_rebreak(candles: List[Dict[str, Any]], args: argparse.Namespace) -> Tuple[int, float]:
    start_high = to_float(candles[0].get("high_price"))
    if start_high <= 0:
        return -1, 0.0
    max_i = min(len(candles) - 1, int(args.rebreak_lookahead_bars))
    trigger = start_high * (1.0 + args.rebreak_buffer_pct / 100.0)
    for i in range(1, max_i + 1):
        high_price = to_float(candles[i].get("high_price"))
        if high_price >= trigger:
            return i, trigger
    return -1, 0.0


def build_detail_rows(conn: Any, source_rows: List[Dict[str, Any]], mapping: Dict[str, str], source_table: str, args: argparse.Namespace) -> int:
    col_csv = ", ".join(qident(c) for c in DETAIL_COLS)
    placeholders = ",".join(["%s"] * len(DETAIL_COLS))
    sql = f"INSERT INTO {qident(DETAIL_TABLE)} ({col_csv}) VALUES ({placeholders})"
    batch: List[Tuple[Any, ...]] = []
    candle_table = mapping["table"]
    missing_candles = 0
    for row in source_rows:
        candles = load_candles_for_event(conn, mapping, row, args)
        if not candles:
            missing_candles += 1
            continue
        # 첫 번째 캔들은 st_up_start_time 이상 첫 캔들이다.
        start_close = to_float(candles[0].get("close_price"))
        if start_close > 0:
            batch.append(make_detail_for_timing(row, candles, TIMING_ST_START_CLOSE, 0, start_close, source_table, candle_table, "ST_START 캔들 종가 기준 실제 잔여 최고수익률 측정"))
        if len(candles) >= 2:
            next_open = to_float(candles[1].get("open_price"))
            if next_open > 0:
                batch.append(make_detail_for_timing(row, candles, TIMING_NEXT_BAR_OPEN, 1, next_open, source_table, candle_table, "ST_START 다음 봉 시가 기준 실제 진입 가능성 측정"))
        pb_idx, pb_price = find_first_pullback(candles, args)
        if pb_idx >= 0 and pb_price > 0:
            batch.append(make_detail_for_timing(row, candles, TIMING_FIRST_PULLBACK, pb_idx, pb_price, source_table, candle_table, "ST_START 이후 제한된 눌림 가격 기준 측정"))
        rb_idx, rb_price = find_high_rebreak(candles, args)
        if rb_idx >= 0 and rb_price > 0:
            batch.append(make_detail_for_timing(row, candles, TIMING_HIGH_REBREAK, rb_idx, rb_price, source_table, candle_table, "ST_START 고가 재돌파 가격 기준 측정"))

    if batch:
        with conn.cursor() as cur:
            cur.executemany(sql, batch)
            inserted = int(cur.rowcount)
    else:
        inserted = 0
    print("source_rows=", len(source_rows))
    print("missing_candle_events=", missing_candles)
    return inserted


def update_timing_ranks(conn: Any) -> None:
    rows = fetch_all(conn, f"""
SELECT id, trade_date, code, st_period, st_multiplier, segment_no, timing_score_v1_8, estimated_return_pct, max_adverse_excursion_pct
FROM {qident(DETAIL_TABLE)}
ORDER BY trade_date, code, st_period, st_multiplier, segment_no,
         timing_score_v1_8 DESC, estimated_return_pct DESC, max_adverse_excursion_pct DESC
""")
    current_key = None
    rank = 0
    updates: List[Tuple[int, int]] = []
    for r in rows:
        key = (r.get("trade_date"), r.get("code"), r.get("st_period"), r.get("st_multiplier"), r.get("segment_no"))
        if key != current_key:
            current_key = key
            rank = 1
        else:
            rank += 1
        updates.append((rank, to_int(r.get("id"))))
    with conn.cursor() as cur:
        cur.executemany(f"UPDATE {qident(DETAIL_TABLE)} SET timing_rank_v1_8 = %s WHERE id = %s", updates)


def build_summary(conn: Any) -> None:
    execute(conn, f"""
INSERT INTO {qident(SUMMARY_TABLE)} (
    st_period, st_multiplier, filter_grade_v1_6, filter_label_v1_6, entry_timing_v1_8, timing_label_v1_8,
    row_count, avg_timing_score_v1_8, avg_estimated_return_pct, median_estimated_return_pct,
    avg_max_adverse_excursion_pct, avg_estimated_lost_move_pct, avg_delay_penalty_vs_st_start_pct,
    avg_score_total, avg_filter_score_v1_6, avg_start_from_day_open_pct, avg_start_from_day_low_pct, avg_start_cum_amount
)
SELECT
    d.st_period, d.st_multiplier, d.filter_grade_v1_6, d.filter_label_v1_6, d.entry_timing_v1_8, d.timing_label_v1_8,
    COUNT(*) AS row_count,
    AVG(d.timing_score_v1_8),
    AVG(d.estimated_return_pct),
    AVG(d.estimated_return_pct),
    AVG(d.max_adverse_excursion_pct),
    AVG(d.estimated_lost_move_pct),
    AVG(d.delay_penalty_vs_st_start_pct),
    AVG(d.score_total),
    AVG(d.filter_score_v1_6),
    AVG(d.start_from_day_open_pct),
    AVG(d.start_from_day_low_pct),
    AVG(d.start_cum_amount)
FROM {qident(DETAIL_TABLE)} d
GROUP BY d.st_period, d.st_multiplier, d.filter_grade_v1_6, d.filter_label_v1_6, d.entry_timing_v1_8, d.timing_label_v1_8
""")


def build_examples(conn: Any, top_n: int) -> None:
    execute(conn, f"TRUNCATE TABLE {qident(EXAMPLE_TABLE)}")
    cols = get_columns(conn, DETAIL_TABLE)
    col_csv = ", ".join(qident(c) for c in cols)
    execute(conn, f"""
INSERT INTO {qident(EXAMPLE_TABLE)} ({col_csv})
SELECT {col_csv} FROM (
    SELECT d.*, ROW_NUMBER() OVER (
        PARTITION BY d.entry_timing_v1_8
        ORDER BY d.timing_score_v1_8 DESC, d.estimated_return_pct DESC, d.max_adverse_excursion_pct DESC
    ) AS rn
    FROM {qident(DETAIL_TABLE)} d
) x
WHERE x.rn <= %s
""", [top_n])


def print_rows(title: str, rows: List[Dict[str, Any]], max_rows: int = 60) -> None:
    print("\n=== " + title + " ===")
    for r in rows[:max_rows]:
        print(dict(r))
    if len(rows) > max_rows:
        print("... " + str(len(rows) - max_rows) + " more rows")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build ST_START intraday timing v1.8 from MySQL v1.6 FAST_LEADER candidates")
    p.add_argument("--mysql-conn", default="")
    p.add_argument("--host", default="")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--database", default="")
    p.add_argument("--user", default="")
    p.add_argument("--password", default="")
    p.add_argument("--charset", default="utf8mb4")
    p.add_argument("--source-table", default=SOURCE_TABLE_DEFAULT)
    p.add_argument("--candle-table", default="")
    p.add_argument("--filter-grade", default="A")
    p.add_argument("--filter-label", default="ST_START_A_FAST_LEADER")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--example-top-n", type=int, default=30)
    p.add_argument("--session-end-hour", type=int, default=15)
    p.add_argument("--session-end-minute", type=int, default=30)
    p.add_argument("--max-bars-after-start", type=int, default=420)
    p.add_argument("--pullback-lookahead-bars", type=int, default=10)
    p.add_argument("--pullback-min-pct", type=float, default=0.8)
    p.add_argument("--pullback-max-break-pct", type=float, default=1.5)
    p.add_argument("--rebreak-lookahead-bars", type=int, default=10)
    p.add_argument("--rebreak-buffer-pct", type=float, default=0.05)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    print("=== BUILD v1.8 ST_START Intraday Timing ===")
    cfg = build_mysql_config(args)
    conn = pymysql.connect(**cfg)
    try:
        source_table = args.source_table.strip() or SOURCE_TABLE_DEFAULT
        assert_source_table(conn, source_table)
        mapping = detect_candle_mapping(conn, args.candle_table.strip())
        create_output_tables(conn)
        source_rows = load_source_rows(conn, source_table, args)
        inserted = build_detail_rows(conn, source_rows, mapping, source_table, args)
        if inserted <= 0:
            raise RuntimeError("detail table row_count=0 입니다. --candle-table/분봉 컬럼/시간 형식을 확인하세요.")
        update_timing_ranks(conn)
        build_summary(conn)
        build_examples(conn, args.example_top_n)
        conn.commit()

        print("source_table=", source_table)
        print("candle_table=", mapping["table"])
        print("candle_mapping=", mapping)
        print("detail_table=", DETAIL_TABLE)
        print("summary_table=", SUMMARY_TABLE)
        print("example_table=", EXAMPLE_TABLE)
        print("detail_rows=", inserted)

        summary = fetch_all(conn, f"""
SELECT st_period, st_multiplier, filter_grade_v1_6, filter_label_v1_6, entry_timing_v1_8, timing_label_v1_8,
       row_count, avg_timing_score_v1_8, avg_estimated_return_pct, avg_max_adverse_excursion_pct,
       avg_estimated_lost_move_pct, avg_delay_penalty_vs_st_start_pct, avg_score_total,
       avg_start_from_day_open_pct, avg_start_from_day_low_pct, avg_start_cum_amount
FROM {qident(SUMMARY_TABLE)}
ORDER BY entry_timing_v1_8, avg_timing_score_v1_8 DESC, row_count DESC
""")
        print_rows("v1.8 Intraday Timing Summary", summary, 120)

        examples = fetch_all(conn, f"""
SELECT trade_date, code, name, st_period, st_multiplier, segment_no, st_up_start_time,
       entry_timing_v1_8, entry_time, entry_price, timing_rank_v1_8, timing_label_v1_8, timing_score_v1_8,
       estimated_return_pct, max_adverse_excursion_pct, estimated_lost_move_pct, delay_penalty_vs_st_start_pct,
       future_high_after_entry, future_high_time, future_low_after_entry, future_low_time,
       score_total, filter_label_v1_6, st_start_estimated_return_pct, early3_estimated_return_pct,
       early3_high_return_pct, post_early3_extension_pct, start_from_day_open_pct, start_from_day_low_pct,
       start_cum_amount, timing_reason_v1_8
FROM {qident(EXAMPLE_TABLE)}
ORDER BY entry_timing_v1_8, timing_score_v1_8 DESC, estimated_return_pct DESC
LIMIT 120
""")
        print_rows("v1.8 Intraday Timing Examples", examples, 120)
        print("=== DONE scripts/build_supertrend_start_entry_intraday_timing_v1_8.py ===")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
