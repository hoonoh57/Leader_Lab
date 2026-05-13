# -*- coding: utf-8 -*-
"""Build VIX Entry Continuation Benchmark v1.

Purpose:
    Use the last available Kiwoom 1516 condition-capture rows as source universe.
    Treat +X% breakout itself as the entry filter.
    Measure whether post-breakout +2% continuation succeeds.

This script is intentionally schema-tolerant because the 1516 SQLite table names
and Korean/English column names can differ between rebuild versions.

Outputs:
    reports/vix_entry_continuation_benchmark_v1.csv
    reports/vix_entry_threshold_comparison_v1.csv
    reports/vix_entry_daily_summary_v1.csv
    reports/vix_entry_continuation_benchmark_v1.html
"""

from __future__ import annotations

import argparse
import csv
import html
import math
import os
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pymysql


DEFAULT_THRESHOLDS = [10.0, 11.0, 12.0, 13.0]
DEFAULT_TARGET_PCT = 2.0
DEFAULT_STOP_PCT = -2.0
DEFAULT_CAPTURE_TIME = "09:05"


# ----------------------------- env / connection -----------------------------


def load_env(env_path: str) -> None:
    path = Path(env_path)
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def env_value(names: Sequence[str], default: Optional[str] = None) -> Optional[str]:
    for name in names:
        value = os.environ.get(name)
        if value is not None and value.strip() != "":
            return value.strip()
    return default


def open_mysql_conn() -> Any:
    db_name = env_value(["DB_NAME", "MYSQL_DATABASE", "MYSQL_DB", "MYSQL_DB_STOCK_INFO"], "stock_info")
    return pymysql.connect(
        host=env_value(["DB_HOST", "MYSQL_HOST"], "127.0.0.1"),
        port=int(env_value(["DB_PORT", "MYSQL_PORT"], "3306") or "3306"),
        user=env_value(["DB_USER", "MYSQL_USER"], "root"),
        password=env_value(["DB_PASS", "DB_PASSWORD", "MYSQL_PASSWORD", "MYSQL_PASS"], ""),
        database=db_name,
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


# -------------------------------- utilities ---------------------------------


def safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        x = float(value)
    except Exception:
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return x


def safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def normalize_code(value: Any) -> str:
    text = str(value or "").strip()
    if text.startswith("A") and len(text) >= 7:
        text = text[1:]
    if text.isdigit() and len(text) < 6:
        text = text.zfill(6)
    return text


def parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip().replace("/", "-").replace(".", "-")
    if not text:
        return None
    if " " in text:
        text = text.split(" ", 1)[0]
    if len(text) == 8 and text.isdigit():
        text = f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    try:
        return datetime.fromisoformat(text).date()
    except Exception:
        return None


def parse_time_text(value: Any, fallback: str = DEFAULT_CAPTURE_TIME) -> str:
    if value is None or str(value).strip() == "":
        return fallback + ":00" if len(fallback) == 5 else fallback
    text = str(value).strip()
    if " " in text:
        text = text.split(" ")[-1]
    if "T" in text:
        text = text.split("T")[-1]
    text = text.replace(".", ":")
    if len(text) == 4 and text.isdigit():
        text = text[:2] + ":" + text[2:] + ":00"
    elif len(text) == 5 and text[2] == ":":
        text = text + ":00"
    return text


def combine_dt(day_value: Any, time_value: Any, fallback_time: str = DEFAULT_CAPTURE_TIME) -> Optional[datetime]:
    d = parse_date(day_value)
    if d is None:
        return None
    t = parse_time_text(time_value, fallback_time)
    try:
        return datetime.fromisoformat(d.isoformat() + " " + t)
    except Exception:
        return None


def amount_from_candle(row: Dict[str, Any]) -> float:
    o = safe_float(row.get("open")) or safe_float(row.get("open_price")) or 0.0
    h = safe_float(row.get("high")) or safe_float(row.get("high_price")) or 0.0
    l = safe_float(row.get("low")) or safe_float(row.get("low_price")) or 0.0
    c = safe_float(row.get("close")) or safe_float(row.get("close_price")) or 0.0
    v = safe_float(row.get("volume")) or 0.0
    if o <= 0 or h <= 0 or l <= 0 or c <= 0 or v <= 0:
        return 0.0
    return ((o + h + l + c) / 4.0) * v


def pct_from_base(price: float, base: float) -> float:
    if base <= 0:
        return 0.0
    return (price / base - 1.0) * 100.0


# ------------------------------- schema scan --------------------------------


def sqlite_tables(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    return [str(r[0]) for r in rows]


def sqlite_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    rows = conn.execute(f"PRAGMA table_info({quote_ident_sqlite(table)})").fetchall()
    return [str(r[1]) for r in rows]


def quote_ident_sqlite(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def pick_col(cols: Sequence[str], candidates: Sequence[str]) -> Optional[str]:
    by_lower = {c.lower(): c for c in cols}
    for cand in candidates:
        if cand.lower() in by_lower:
            return by_lower[cand.lower()]
    # loose Korean/semantic contains match
    for cand in candidates:
        lc = cand.lower()
        for c in cols:
            if lc in c.lower():
                return c
    return None


@dataclass
class CandidateSchema:
    table: str
    code_col: str
    name_col: Optional[str]
    date_col: str
    time_col: Optional[str]
    condition_col: Optional[str]
    max_return_col: Optional[str]


def find_candidate_schema(conn: sqlite3.Connection, preferred_table: Optional[str] = None) -> CandidateSchema:
    tables = [preferred_table] if preferred_table else sqlite_tables(conn)
    code_candidates = ["code", "stock_code", "ticker", "종목코드", "단축코드"]
    name_candidates = ["name", "stock_name", "종목명"]
    date_candidates = ["trade_date", "search_date", "date", "일자", "검색일자"]
    time_candidates = ["search_time", "capture_time", "time", "검색시각", "시각", "시간"]
    cond_candidates = ["condition_name", "condition", "조건식", "조건명", "cond_name"]
    ret_candidates = ["max_profit", "max_return", "max_return_pct", "최고수익률", "기간내최고수익률", "period_max_return_pct"]

    best: Optional[Tuple[int, CandidateSchema]] = None
    for table in tables:
        if table is None:
            continue
        cols = sqlite_columns(conn, table)
        code_col = pick_col(cols, code_candidates)
        date_col = pick_col(cols, date_candidates)
        if not code_col or not date_col:
            continue
        schema = CandidateSchema(
            table=table,
            code_col=code_col,
            name_col=pick_col(cols, name_candidates),
            date_col=date_col,
            time_col=pick_col(cols, time_candidates),
            condition_col=pick_col(cols, cond_candidates),
            max_return_col=pick_col(cols, ret_candidates),
        )
        score = 0
        score += 10 if code_col else 0
        score += 10 if date_col else 0
        score += 3 if schema.time_col else 0
        score += 2 if schema.name_col else 0
        score += 2 if schema.max_return_col else 0
        if best is None or score > best[0]:
            best = (score, schema)
    if best is None:
        raise RuntimeError("1516 SQLite에서 후보 테이블을 찾지 못했습니다. --candidate-table 로 테이블명을 지정하세요.")
    return best[1]


def mysql_table_exists(conn: Any, table: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name=%s", (table,))
        row = cur.fetchone()
    return int(row.get("n", 0)) > 0


def mysql_columns(conn: Any, table: str) -> List[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT column_name AS column_name FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=%s ORDER BY ordinal_position", (table,))
        rows = cur.fetchall()
    result: List[str] = []
    for r in rows:
        result.append(str(r.get("column_name") or r.get("COLUMN_NAME") or list(r.values())[0]))
    return result


def pick_candle_table(conn: Any, preferred: Optional[str] = None) -> str:
    candidates = [preferred] if preferred else ["minute1_candles", "minute3_candles", "minute5_candles"]
    for table in candidates:
        if table and mysql_table_exists(conn, table):
            return table
    raise RuntimeError("분봉 테이블을 찾지 못했습니다. --candle-table minute5_candles 등으로 지정하세요.")


def pick_daily_table(conn: Any) -> Optional[str]:
    for table in ["daily_candles", "daily_candle"]:
        if mysql_table_exists(conn, table):
            return table
    return None


# ------------------------------- data loading --------------------------------


def load_candidates(sqlite_conn: sqlite3.Connection, schema: CandidateSchema, start_date: Optional[str], end_date: Optional[str], condition_name: Optional[str], capture_time: str) -> List[Dict[str, Any]]:
    cols = [schema.code_col, schema.date_col]
    if schema.name_col:
        cols.append(schema.name_col)
    if schema.time_col:
        cols.append(schema.time_col)
    if schema.condition_col:
        cols.append(schema.condition_col)
    if schema.max_return_col:
        cols.append(schema.max_return_col)
    cols_unique = []
    for c in cols:
        if c not in cols_unique:
            cols_unique.append(c)
    where = []
    params: List[Any] = []
    if start_date:
        where.append(f"{quote_ident_sqlite(schema.date_col)} >= ?")
        params.append(start_date)
    if end_date:
        where.append(f"{quote_ident_sqlite(schema.date_col)} <= ?")
        params.append(end_date)
    if condition_name and schema.condition_col:
        where.append(f"{quote_ident_sqlite(schema.condition_col)} = ?")
        params.append(condition_name)
    sql = "SELECT " + ", ".join(quote_ident_sqlite(c) for c in cols_unique) + " FROM " + quote_ident_sqlite(schema.table)
    if where:
        sql += " WHERE " + " AND ".join(where)
    rows = [dict(r) for r in sqlite_conn.execute(sql, params).fetchall()]
    result: List[Dict[str, Any]] = []
    seen = set()
    for r in rows:
        d = parse_date(r.get(schema.date_col))
        if d is None:
            continue
        code = normalize_code(r.get(schema.code_col))
        if not code:
            continue
        cap_dt = combine_dt(d, r.get(schema.time_col) if schema.time_col else capture_time, capture_time)
        if cap_dt is None:
            continue
        key = (d.isoformat(), code, cap_dt.strftime("%H:%M:%S"))
        if key in seen:
            continue
        seen.add(key)
        result.append({
            "trade_date": d.isoformat(),
            "code": code,
            "name": r.get(schema.name_col) if schema.name_col else "",
            "condition_name": r.get(schema.condition_col) if schema.condition_col else (condition_name or schema.table),
            "T_capture": cap_dt,
            "source_max_return_pct": safe_float(r.get(schema.max_return_col)) if schema.max_return_col else None,
        })
    return result


def load_day_candles(conn: Any, candle_table: str, code: str, trade_date: str) -> List[Dict[str, Any]]:
    day = parse_date(trade_date)
    if day is None:
        return []
    start = datetime.combine(day, time(9, 0, 0))
    end = datetime.combine(day, time(15, 30, 0))
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT candle_time, open, high, low, close, volume
            FROM `{candle_table}`
            WHERE code=%s AND candle_time >= %s AND candle_time <= %s
            ORDER BY candle_time
            """,
            (code, start, end),
        )
        rows = list(cur.fetchall())
    return rows


def previous_close_from_candles(conn: Any, candle_table: str, code: str, trade_date: str) -> Optional[float]:
    day = parse_date(trade_date)
    if day is None:
        return None
    start = datetime.combine(day, time(9, 0, 0))
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT close
            FROM `{candle_table}`
            WHERE code=%s AND candle_time < %s
            ORDER BY candle_time DESC
            LIMIT 1
            """,
            (code, start),
        )
        row = cur.fetchone()
    return safe_float(row.get("close")) if row else None


def candle_dt(row: Dict[str, Any]) -> Optional[datetime]:
    value = row.get("candle_time")
    if isinstance(value, datetime):
        return value
    if value is None:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


# ------------------------------- evaluation ---------------------------------


def first_breakout(candles: Sequence[Dict[str, Any]], prev_close: float, threshold_pct: float, after_dt: datetime) -> Optional[Dict[str, Any]]:
    for row in candles:
        ts = candle_dt(row)
        if ts is None or ts < after_dt:
            continue
        high = safe_float(row.get("high")) or 0.0
        if pct_from_base(high, prev_close) >= threshold_pct:
            entry_price = prev_close * (1.0 + threshold_pct / 100.0)
            item = dict(row)
            item["TX"] = ts
            item["entry_price"] = entry_price
            return item
    return None


def pre_window_stats(candles: Sequence[Dict[str, Any]], capture_dt: datetime, tx: datetime, prev_close: float) -> Dict[str, Any]:
    rows = [r for r in candles if (candle_dt(r) is not None and capture_dt <= candle_dt(r) <= tx)]
    if not rows:
        return {
            "minutes_capture_to_TX": None,
            "amount_capture_to_TX": 0.0,
            "amount_velocity_per_min": None,
            "pullback_depth_before_TX_pct": None,
            "high_hold_ratio_before_TX": None,
            "return_capture_to_TX_pct": None,
        }
    amount = sum(amount_from_candle(r) for r in rows)
    minutes = max((tx - capture_dt).total_seconds() / 60.0, 1.0)
    highs = [safe_float(r.get("high")) or 0.0 for r in rows]
    lows = [safe_float(r.get("low")) or 0.0 for r in rows]
    closes = [safe_float(r.get("close")) or 0.0 for r in rows]
    max_high = max(highs) if highs else 0.0
    min_low_after_max = 0.0
    if highs and lows:
        idx_max = highs.index(max_high)
        min_low_after_max = min(lows[idx_max:]) if idx_max < len(lows) else min(lows)
    pullback = pct_from_base(min_low_after_max, max_high) if max_high > 0 and min_low_after_max > 0 else None
    entry_level = prev_close * 1.10
    hold_count = sum(1 for c in closes if c >= entry_level * 0.98) if entry_level > 0 else 0
    high_hold_ratio = hold_count / len(closes) if closes else None
    capture_price = safe_float(rows[0].get("open")) or safe_float(rows[0].get("close")) or prev_close
    return {
        "minutes_capture_to_TX": minutes,
        "amount_capture_to_TX": amount,
        "amount_velocity_per_min": amount / minutes if minutes > 0 else None,
        "pullback_depth_before_TX_pct": pullback,
        "high_hold_ratio_before_TX": high_hold_ratio,
        "return_capture_to_TX_pct": pct_from_base(max_high, capture_price) if capture_price and max_high else None,
    }


def post_window_result(candles: Sequence[Dict[str, Any]], tx: datetime, entry_price: float, target_pct: float, stop_pct: float) -> Dict[str, Any]:
    rows = [r for r in candles if (candle_dt(r) is not None and candle_dt(r) >= tx)]
    if not rows:
        return {
            "post_TX_max_return_pct": None,
            "post_TX_mae_pct": None,
            "post_TX_plus2_success": 0,
            "post_TX_stop_hit": 0,
            "post_TX_outcome_label": "NO_POST_DATA",
        }
    max_ret = -999999.0
    min_ret = 999999.0
    target_hit = False
    stop_hit = False
    first_event = "STALL"
    for r in rows:
        h = safe_float(r.get("high")) or 0.0
        l = safe_float(r.get("low")) or 0.0
        hret = pct_from_base(h, entry_price)
        lret = pct_from_base(l, entry_price)
        max_ret = max(max_ret, hret)
        min_ret = min(min_ret, lret)
        if not target_hit and not stop_hit:
            # conservative ordering for same candle: stop first if both occur.
            if lret <= stop_pct:
                stop_hit = True
                first_event = "STOP_FIRST"
            elif hret >= target_pct:
                target_hit = True
                first_event = "TARGET_FIRST"
    if target_hit:
        label = "VIX_CONTINUATION_WIN"
    elif stop_hit:
        label = "VIX_WEAK_REJECT"
    else:
        label = "VIX_STALL"
    return {
        "post_TX_max_return_pct": max_ret,
        "post_TX_mae_pct": min_ret,
        "post_TX_plus2_success": 1 if target_hit else 0,
        "post_TX_stop_hit": 1 if stop_hit else 0,
        "post_TX_first_event": first_event,
        "post_TX_outcome_label": label,
    }


def evaluate_candidate(candidate: Dict[str, Any], candles: Sequence[Dict[str, Any]], prev_close: Optional[float], thresholds: Sequence[float], target_pct: float, stop_pct: float) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if prev_close is None or prev_close <= 0 or not candles:
        for x in thresholds:
            rows.append(make_no_entry(candidate, x, "NO_PREV_CLOSE_OR_CANDLES"))
        return rows
    cap_dt = candidate["T_capture"]
    for x in thresholds:
        tx_row = first_breakout(candles, prev_close, x, cap_dt)
        if tx_row is None:
            rows.append(make_no_entry(candidate, x, "NO_VIX_ENTRY"))
            continue
        tx = tx_row["TX"]
        entry_price = tx_row["entry_price"]
        pre = pre_window_stats(candles, cap_dt, tx, prev_close)
        post = post_window_result(candles, tx, entry_price, target_pct, stop_pct)
        out = {
            "trade_date": candidate["trade_date"],
            "condition_name": candidate.get("condition_name") or "",
            "T_capture": cap_dt.isoformat(sep=" "),
            "breakout_threshold_pct": x,
            "code": candidate["code"],
            "name": candidate.get("name") or "",
            "TX": tx.isoformat(sep=" "),
            "entry_price": entry_price,
            "prev_close": prev_close,
            "source_max_return_pct": candidate.get("source_max_return_pct"),
        }
        out.update(pre)
        out.update(post)
        rows.append(out)
    return rows


def make_no_entry(candidate: Dict[str, Any], threshold: float, label: str) -> Dict[str, Any]:
    return {
        "trade_date": candidate["trade_date"],
        "condition_name": candidate.get("condition_name") or "",
        "T_capture": candidate["T_capture"].isoformat(sep=" "),
        "breakout_threshold_pct": threshold,
        "code": candidate["code"],
        "name": candidate.get("name") or "",
        "TX": None,
        "entry_price": None,
        "prev_close": None,
        "source_max_return_pct": candidate.get("source_max_return_pct"),
        "minutes_capture_to_TX": None,
        "amount_capture_to_TX": None,
        "amount_velocity_per_min": None,
        "pullback_depth_before_TX_pct": None,
        "high_hold_ratio_before_TX": None,
        "return_capture_to_TX_pct": None,
        "post_TX_max_return_pct": None,
        "post_TX_mae_pct": None,
        "post_TX_plus2_success": 0,
        "post_TX_stop_hit": 0,
        "post_TX_first_event": None,
        "post_TX_outcome_label": label,
    }


# ------------------------------- summaries ----------------------------------


def summarize_threshold(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[float, List[Dict[str, Any]]] = {}
    for r in rows:
        groups.setdefault(float(r["breakout_threshold_pct"]), []).append(r)
    result: List[Dict[str, Any]] = []
    for x, rs in sorted(groups.items()):
        entries = [r for r in rs if r.get("TX")]
        wins = [r for r in entries if int(r.get("post_TX_plus2_success") or 0) == 1]
        rejects = [r for r in entries if r.get("post_TX_outcome_label") == "VIX_WEAK_REJECT"]
        avg_mae = avg([safe_float(r.get("post_TX_mae_pct")) for r in entries])
        avg_max = avg([safe_float(r.get("post_TX_max_return_pct")) for r in entries])
        result.append({
            "breakout_threshold_pct": x,
            "candidate_rows": len(rs),
            "entry_count": len(entries),
            "entry_rate": len(entries) / len(rs) if rs else 0.0,
            "plus2_success_count": len(wins),
            "plus2_success_rate": len(wins) / len(entries) if entries else 0.0,
            "reject_count": len(rejects),
            "reject_rate": len(rejects) / len(entries) if entries else 0.0,
            "avg_post_TX_max_return_pct": avg_max,
            "avg_post_TX_mae_pct": avg_mae,
        })
    return result


def summarize_daily(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[str, float], List[Dict[str, Any]]] = {}
    for r in rows:
        groups.setdefault((str(r["trade_date"]), float(r["breakout_threshold_pct"])), []).append(r)
    result: List[Dict[str, Any]] = []
    for (d, x), rs in sorted(groups.items()):
        entries = [r for r in rs if r.get("TX")]
        wins = [r for r in entries if int(r.get("post_TX_plus2_success") or 0) == 1]
        result.append({
            "trade_date": d,
            "breakout_threshold_pct": x,
            "candidate_count": len(rs),
            "entry_count": len(entries),
            "plus2_success_count": len(wins),
            "plus2_success_rate": len(wins) / len(entries) if entries else 0.0,
        })
    return result


def avg(values: Iterable[Optional[float]]) -> Optional[float]:
    arr = [v for v in values if v is not None]
    if not arr:
        return None
    return sum(arr) / len(arr)


# -------------------------------- output -------------------------------------


def write_csv(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fields: List[str] = []
    for r in rows:
        for k in r.keys():
            if k not in fields:
                fields.append(k)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def fmt_pct(v: Any) -> str:
    x = safe_float(v)
    if x is None:
        return "-"
    return f"{x:.2%}" if abs(x) <= 1.0 else f"{x:.2f}%"


def fmt_num(v: Any, d: int = 2) -> str:
    x = safe_float(v)
    if x is None:
        return "-"
    return f"{x:.{d}f}"


def build_html_report(rows: Sequence[Dict[str, Any]], threshold_summary: Sequence[Dict[str, Any]], daily_summary: Sequence[Dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    best_rows = sorted([r for r in rows if r.get("TX")], key=lambda r: (float(r.get("breakout_threshold_pct") or 0), -(safe_float(r.get("post_TX_max_return_pct")) or -999)))[:500]
    html_parts: List[str] = []
    html_parts.append("<!doctype html><html lang='ko'><head><meta charset='utf-8'><title>VIX Entry Continuation Benchmark v1</title>")
    html_parts.append("<style>body{font-family:Segoe UI,Malgun Gothic,Arial;background:#111827;color:#e5e7eb;margin:0;padding:18px}h1,h2{color:#fbbf24}table{border-collapse:collapse;width:100%;font-size:12px;margin:12px 0;background:#0f172a}th,td{border:1px solid #334155;padding:5px;text-align:right}th{background:#1e293b}.left{text-align:left}.win{color:#86efac}.reject{color:#fca5a5}.stall{color:#fde68a}.box{border:1px solid #334155;border-radius:10px;padding:12px;background:#0f172a;margin-bottom:12px}</style></head><body>")
    html_parts.append("<h1>VIX Entry Continuation Benchmark v1</h1>")
    html_parts.append("<div class='box'>진입 기준 X%를 10/11/12/13 등 변수로 두고, 조건식 포착 종목이 X% 돌파 후 +2%를 주는지 측정합니다. 10% 전후 유동성 함정 회피를 위해 12% 돌파 진입도 동일 기준으로 비교합니다.</div>")
    html_parts.append("<h2>Threshold Comparison</h2>")
    html_parts.append(table_html(threshold_summary, ["breakout_threshold_pct", "candidate_rows", "entry_count", "entry_rate", "plus2_success_count", "plus2_success_rate", "reject_count", "reject_rate", "avg_post_TX_max_return_pct", "avg_post_TX_mae_pct"]))
    html_parts.append("<h2>Daily Summary</h2>")
    html_parts.append(table_html(daily_summary[:300], ["trade_date", "breakout_threshold_pct", "candidate_count", "entry_count", "plus2_success_count", "plus2_success_rate"]))
    html_parts.append("<h2>Entry Rows Top Sample</h2>")
    html_parts.append(table_html(best_rows, ["trade_date", "breakout_threshold_pct", "code", "name", "T_capture", "TX", "minutes_capture_to_TX", "amount_capture_to_TX", "amount_velocity_per_min", "post_TX_max_return_pct", "post_TX_mae_pct", "post_TX_outcome_label"]))
    html_parts.append("</body></html>")
    output.write_text("\n".join(html_parts), encoding="utf-8")


def table_html(rows: Sequence[Dict[str, Any]], fields: Sequence[str]) -> str:
    h = ["<table><thead><tr>"]
    for f in fields:
        h.append(f"<th>{html.escape(f)}</th>")
    h.append("</tr></thead><tbody>")
    for r in rows:
        label = str(r.get("post_TX_outcome_label") or "")
        cls = "win" if "WIN" in label else ("reject" if "REJECT" in label else ("stall" if "STALL" in label else ""))
        h.append("<tr>")
        for f in fields:
            v = r.get(f)
            text = "-" if v is None else str(v)
            if f.endswith("rate"):
                text = fmt_pct(v)
            elif f.endswith("pct") or "return" in f or "mae" in f:
                text = fmt_num(v)
            elif "amount" in f and safe_float(v) is not None:
                text = fmt_num((safe_float(v) or 0.0) / 100000000.0) + "억"
            align = "left" if f in ("name", "post_TX_outcome_label") else ""
            h.append(f"<td class='{align} {cls}'>{html.escape(text)}</td>")
        h.append("</tr>")
    h.append("</tbody></table>")
    return "".join(h)


# ---------------------------------- main -------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--sqlite-db", default=None)
    parser.add_argument("--candidate-table", default=None)
    parser.add_argument("--condition-name", default=None)
    parser.add_argument("--capture-time", default=DEFAULT_CAPTURE_TIME)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--candle-table", default=None)
    parser.add_argument("--thresholds", default="10,11,12,13")
    parser.add_argument("--target-pct", type=float, default=DEFAULT_TARGET_PCT)
    parser.add_argument("--stop-pct", type=float, default=DEFAULT_STOP_PCT)
    parser.add_argument("--output-dir", default="reports")
    args = parser.parse_args()

    load_env(args.env)
    sqlite_path = args.sqlite_db or env_value(["SQLITE_1516_DB"])
    if not sqlite_path:
        raise RuntimeError("SQLITE_1516_DB 또는 --sqlite-db가 필요합니다.")
    thresholds = [float(x.strip()) for x in args.thresholds.split(",") if x.strip()]

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    mysql_conn = open_mysql_conn()
    try:
        schema = find_candidate_schema(sqlite_conn, args.candidate_table)
        candle_table = pick_candle_table(mysql_conn, args.candle_table)
        candidates = load_candidates(sqlite_conn, schema, args.start_date, args.end_date, args.condition_name, args.capture_time)
        print("=== VIX Entry Continuation Benchmark v1 ===")
        print("sqlite_db=" + str(sqlite_path))
        print("candidate_table=" + schema.table)
        print("candidate_columns=code:%s date:%s time:%s name:%s condition:%s max_return:%s" % (schema.code_col, schema.date_col, schema.time_col, schema.name_col, schema.condition_col, schema.max_return_col))
        print("candle_table=" + candle_table)
        print("candidate_count=" + str(len(candidates)))

        candle_cache: Dict[Tuple[str, str], Tuple[List[Dict[str, Any]], Optional[float]]] = {}
        all_rows: List[Dict[str, Any]] = []
        for i, cand in enumerate(candidates, 1):
            key = (cand["trade_date"], cand["code"])
            if key not in candle_cache:
                candles = load_day_candles(mysql_conn, candle_table, cand["code"], cand["trade_date"])
                prev_close = previous_close_from_candles(mysql_conn, candle_table, cand["code"], cand["trade_date"])
                candle_cache[key] = (candles, prev_close)
            candles, prev_close = candle_cache[key]
            all_rows.extend(evaluate_candidate(cand, candles, prev_close, thresholds, args.target_pct, args.stop_pct))
            if i % 200 == 0:
                print("processed_candidates=" + str(i))

        threshold_summary = summarize_threshold(all_rows)
        daily_summary = summarize_daily(all_rows)

        outdir = Path(args.output_dir)
        write_csv(outdir / "vix_entry_continuation_benchmark_v1.csv", all_rows)
        write_csv(outdir / "vix_entry_threshold_comparison_v1.csv", threshold_summary)
        write_csv(outdir / "vix_entry_daily_summary_v1.csv", daily_summary)
        build_html_report(all_rows, threshold_summary, daily_summary, outdir / "vix_entry_continuation_benchmark_v1.html")

        print("=== Threshold Summary ===")
        for r in threshold_summary:
            print(r)
        print("output_csv=" + str((outdir / "vix_entry_continuation_benchmark_v1.csv").resolve()))
        print("output_threshold=" + str((outdir / "vix_entry_threshold_comparison_v1.csv").resolve()))
        print("output_daily=" + str((outdir / "vix_entry_daily_summary_v1.csv").resolve()))
        print("output_html=" + str((outdir / "vix_entry_continuation_benchmark_v1.html").resolve()))
        return 0
    finally:
        sqlite_conn.close()
        mysql_conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
