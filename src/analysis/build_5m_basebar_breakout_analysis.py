# -*- coding: utf-8 -*-
"""Build 5-minute basebar breakout analysis.

This script restores the original planned validation:
- Find 5-minute base bars whose single-bar or day-open based rise is >= 5%.
- Check whether later candles break above the base bar high.
- Measure return after breakout, close return, drawdown, and pattern summaries.

Run:
    python -m src.analysis.build_5m_basebar_breakout_analysis --env .env --rebuild
"""

from __future__ import annotations

import argparse
import math
import os
import statistics
import sys
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pymysql


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


def open_conn() -> Any:
    db_name = env_value(["DB_NAME", "MYSQL_DATABASE", "MYSQL_DB"])
    if db_name is None:
        raise RuntimeError(".env에 DB_NAME 또는 MYSQL_DATABASE가 필요합니다.")
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


def ensure_schema(conn: Any, rebuild: bool) -> None:
    ddl = Path("sql/create_analysis_5m_basebar_result.sql").read_text(encoding="utf-8-sig")
    with conn.cursor() as cur:
        if rebuild:
            cur.execute("DROP TABLE IF EXISTS analysis_5m_basebar_pattern_summary")
            cur.execute("DROP TABLE IF EXISTS analysis_5m_basebar_result")
        for statement in ddl.split(";"):
            sql = statement.strip()
            if sql:
                cur.execute(sql)
    conn.commit()


def to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        value = float(value)
    try:
        result = float(value)
    except Exception:
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def to_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, Decimal):
        return int(value)
    try:
        return int(float(value))
    except Exception:
        return 0


def pct(new_value: Optional[float], base_value: Optional[float]) -> Optional[float]:
    if new_value is None or base_value is None or base_value == 0:
        return None
    return (new_value - base_value) / base_value * 100.0


def amount_from_ohlcv(row: Dict[str, Any]) -> Optional[float]:
    open_value = to_float(row.get("open_price"))
    high_value = to_float(row.get("high_price"))
    low_value = to_float(row.get("low_price"))
    close_value = to_float(row.get("close_price"))
    volume_value = to_float(row.get("volume"))
    if open_value is None or high_value is None or low_value is None or close_value is None or volume_value is None:
        return None
    return ((open_value + high_value + low_value + close_value) / 4.0) * volume_value


def load_targets(conn: Any, limit: int) -> List[Dict[str, Any]]:
    sql = """
        SELECT search_date, search_time, code, name,
               capture_time, capture_price,
               max_after_price, max_after_return_pct,
               close_1530, close_return_pct,
               history_grade
        FROM analysis_5m_result
        WHERE valid_analysis_flag = 1
          AND history_grade IN ('normal_intraday', 'partial_intraday', 'weak_intraday')
        ORDER BY search_date, search_time, code
    """
    params: Tuple[Any, ...] = ()
    if limit > 0:
        sql += " LIMIT %s"
        params = (limit,)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def load_day_candles(conn: Any, search_date: Any, code: str) -> List[Dict[str, Any]]:
    start_dt = datetime.combine(search_date, time(9, 0, 0))
    end_dt = datetime.combine(search_date, time(15, 30, 0))
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT candle_time AS candle_time,
                   open AS open_price,
                   high AS high_price,
                   low AS low_price,
                   close AS close_price,
                   volume AS volume
            FROM minute5_candles
            WHERE code = %s
              AND candle_time >= %s
              AND candle_time <= %s
            ORDER BY candle_time
            """,
            (code, start_dt, end_dt),
        )
        return list(cur.fetchall())


def is_true(value: Optional[float], threshold: float) -> int:
    if value is None:
        return 0
    return 1 if value >= threshold else 0


def close_position_pct(low_value: Optional[float], high_value: Optional[float], close_value: Optional[float]) -> Optional[float]:
    if low_value is None or high_value is None or close_value is None:
        return None
    spread = high_value - low_value
    if spread <= 0:
        return None
    return (close_value - low_value) / spread * 100.0


def choose_basebar(rows: List[Dict[str, Any]], threshold_pct: float) -> Tuple[int, Optional[Dict[str, Any]], Dict[str, Any]]:
    day_open = to_float(rows[0].get("open_price")) if rows else None
    best_idx = -1
    best_row: Optional[Dict[str, Any]] = None
    best_score = -999999.0
    best_metrics: Dict[str, Any] = {}

    for idx, row in enumerate(rows):
        open_value = to_float(row.get("open_price"))
        high_value = to_float(row.get("high_price"))
        low_value = to_float(row.get("low_price"))
        close_value = to_float(row.get("close_price"))
        volume_value = to_int(row.get("volume"))
        amount_value = amount_from_ohlcv(row)

        bar_ret = pct(close_value, open_value)
        day_close_ret = pct(close_value, day_open)
        day_high_ret = pct(high_value, day_open)
        close_pos = close_position_pct(low_value, high_value, close_value)

        cond_bar = is_true(bar_ret, threshold_pct)
        cond_day_close = is_true(day_close_ret, threshold_pct)
        cond_day_high = is_true(day_high_ret, threshold_pct)

        if cond_bar == 0 and cond_day_close == 0 and cond_day_high == 0:
            continue

        # Pick the earliest strong bar; if same time domain, prefer stronger day close return.
        score = max(bar_ret or -999999.0, day_close_ret or -999999.0, day_high_ret or -999999.0)
        if best_idx < 0 or idx < best_idx or (idx == best_idx and score > best_score):
            best_idx = idx
            best_row = row
            best_score = score
            best_metrics = {
                "base_open": open_value,
                "base_high": high_value,
                "base_low": low_value,
                "base_close": close_value,
                "base_volume": volume_value,
                "base_amount": amount_value,
                "bar_return_pct": bar_ret,
                "from_day_open_close_pct": day_close_ret,
                "from_day_open_high_pct": day_high_ret,
                "close_position_pct": close_pos,
                "is_bar_return_5": cond_bar,
                "is_from_day_open_close_5": cond_day_close,
                "is_from_day_open_high_5": cond_day_high,
            }
            # Since earliest bar has priority, break immediately.
            break

    return best_idx, best_row, best_metrics


def find_breakout(rows: List[Dict[str, Any]], base_idx: int, base_high: Optional[float], base_low: Optional[float]) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "base_low_broken_before_break": 0,
        "max_pullback_before_break_pct": None,
        "break_time": None,
        "break_price": None,
        "break_type": None,
        "bars_to_break": None,
        "bars_after_break": None,
        "break_after_max_time": None,
        "break_after_max_price": None,
        "break_after_max_return_pct": None,
        "break_after_close_return_pct": None,
        "break_after_max_drawdown_pct": None,
    }
    if base_idx < 0 or base_high is None or base_low is None:
        return result

    min_low_before_break: Optional[float] = None
    break_idx = -1
    break_price: Optional[float] = None
    break_type: Optional[str] = None

    for idx in range(base_idx + 1, len(rows)):
        row = rows[idx]
        high_value = to_float(row.get("high_price"))
        close_value = to_float(row.get("close_price"))
        low_value = to_float(row.get("low_price"))

        if low_value is not None:
            if min_low_before_break is None or low_value < min_low_before_break:
                min_low_before_break = low_value
            if low_value < base_low:
                result["base_low_broken_before_break"] = 1

        if close_value is not None and close_value > base_high:
            break_idx = idx
            break_price = close_value
            break_type = "close_break_base_high"
            break
        if high_value is not None and high_value > base_high:
            break_idx = idx
            break_price = base_high
            break_type = "high_touch_base_high"
            break

    result["max_pullback_before_break_pct"] = pct(min_low_before_break, base_high)

    if break_idx < 0 or break_price is None:
        return result

    break_row = rows[break_idx]
    max_price: Optional[float] = None
    max_time: Optional[datetime] = None
    min_price: Optional[float] = None
    close_final: Optional[float] = None

    for idx in range(break_idx, len(rows)):
        row = rows[idx]
        row_time = row.get("candle_time")
        high_value = to_float(row.get("high_price"))
        low_value = to_float(row.get("low_price"))
        close_value = to_float(row.get("close_price"))
        if high_value is not None and (max_price is None or high_value > max_price):
            max_price = high_value
            max_time = row_time
        if low_value is not None and (min_price is None or low_value < min_price):
            min_price = low_value
        close_final = close_value

    result.update({
        "break_time": break_row.get("candle_time"),
        "break_price": break_price,
        "break_type": break_type,
        "bars_to_break": break_idx - base_idx,
        "bars_after_break": len(rows) - break_idx,
        "break_after_max_time": max_time,
        "break_after_max_price": max_price,
        "break_after_max_return_pct": pct(max_price, break_price),
        "break_after_close_return_pct": pct(close_final, break_price),
        "break_after_max_drawdown_pct": pct(min_price, break_price),
    })
    return result


def pattern_type(metrics: Dict[str, Any], breakout: Dict[str, Any]) -> str:
    parts: List[str] = []
    if metrics.get("is_bar_return_5") == 1:
        parts.append("bar5")
    if metrics.get("is_from_day_open_close_5") == 1:
        parts.append("dayclose5")
    if metrics.get("is_from_day_open_high_5") == 1:
        parts.append("dayhigh5")
    if not parts:
        return "none"
    if breakout.get("break_time") is not None:
        parts.append("break")
        if breakout.get("base_low_broken_before_break") == 0:
            parts.append("no_low_break")
    else:
        parts.append("no_break")
    return "_".join(parts)


def analyze_target(conn: Any, target: Dict[str, Any], threshold_pct: float) -> Dict[str, Any]:
    search_date = target.get("search_date")
    search_time = target.get("search_time")
    code = str(target.get("code"))
    name = target.get("name")

    rows = load_day_candles(conn, search_date, code)
    base_result: Dict[str, Any] = {
        "search_date": search_date,
        "search_time": search_time,
        "code": code,
        "name": name,
        "day_open": None,
        "day_high": None,
        "day_low": None,
        "day_close": None,
        "capture_time": target.get("capture_time"),
        "capture_price": to_float(target.get("capture_price")),
        "capture_to_day_high_return_pct": pct(to_float(target.get("max_after_price")), to_float(target.get("capture_price"))),
        "capture_to_close_return_pct": to_float(target.get("close_return_pct")),
        "base_candle_time": None,
        "base_open": None,
        "base_high": None,
        "base_low": None,
        "base_close": None,
        "base_volume": None,
        "base_amount": None,
        "bar_return_pct": None,
        "from_day_open_close_pct": None,
        "from_day_open_high_pct": None,
        "close_position_pct": None,
        "is_bar_return_5": 0,
        "is_from_day_open_close_5": 0,
        "is_from_day_open_high_5": 0,
        "base_low_broken_before_break": 0,
        "max_pullback_before_break_pct": None,
        "break_time": None,
        "break_price": None,
        "break_type": None,
        "bars_to_break": None,
        "bars_after_break": None,
        "break_after_max_time": None,
        "break_after_max_price": None,
        "break_after_max_return_pct": None,
        "break_after_close_return_pct": None,
        "break_after_max_drawdown_pct": None,
        "pattern_type": "none",
        "valid_flag": 0,
        "invalid_reason": "no_day_candles",
        "history_grade": target.get("history_grade"),
    }

    if not rows:
        return base_result

    day_open = to_float(rows[0].get("open_price"))
    day_high = max([to_float(row.get("high_price")) or -999999.0 for row in rows])
    day_low = min([to_float(row.get("low_price")) or 999999999.0 for row in rows])
    day_close = to_float(rows[-1].get("close_price"))
    base_result.update({
        "day_open": day_open,
        "day_high": day_high,
        "day_low": day_low,
        "day_close": day_close,
    })

    base_idx, base_row, metrics = choose_basebar(rows, threshold_pct)
    if base_idx < 0 or base_row is None:
        base_result.update({
            "valid_flag": 1,
            "invalid_reason": None,
            "pattern_type": "no_5pct_basebar",
        })
        return base_result

    breakout = find_breakout(rows, base_idx, metrics.get("base_high"), metrics.get("base_low"))
    ptype = pattern_type(metrics, breakout)

    base_result.update(metrics)
    base_result.update(breakout)
    base_result.update({
        "base_candle_time": base_row.get("candle_time"),
        "pattern_type": ptype,
        "valid_flag": 1,
        "invalid_reason": None,
    })
    return base_result


def upsert_result(conn: Any, row: Dict[str, Any]) -> None:
    sql = """
        INSERT INTO analysis_5m_basebar_result (
            search_date, search_time, code, name,
            day_open, day_high, day_low, day_close,
            capture_time, capture_price, capture_to_day_high_return_pct, capture_to_close_return_pct,
            base_candle_time, base_open, base_high, base_low, base_close, base_volume, base_amount,
            bar_return_pct, from_day_open_close_pct, from_day_open_high_pct, close_position_pct,
            is_bar_return_5, is_from_day_open_close_5, is_from_day_open_high_5,
            base_low_broken_before_break, max_pullback_before_break_pct,
            break_time, break_price, break_type, bars_to_break, bars_after_break,
            break_after_max_time, break_after_max_price, break_after_max_return_pct,
            break_after_close_return_pct, break_after_max_drawdown_pct,
            pattern_type, valid_flag, invalid_reason, history_grade
        ) VALUES (
            %(search_date)s, %(search_time)s, %(code)s, %(name)s,
            %(day_open)s, %(day_high)s, %(day_low)s, %(day_close)s,
            %(capture_time)s, %(capture_price)s, %(capture_to_day_high_return_pct)s, %(capture_to_close_return_pct)s,
            %(base_candle_time)s, %(base_open)s, %(base_high)s, %(base_low)s, %(base_close)s, %(base_volume)s, %(base_amount)s,
            %(bar_return_pct)s, %(from_day_open_close_pct)s, %(from_day_open_high_pct)s, %(close_position_pct)s,
            %(is_bar_return_5)s, %(is_from_day_open_close_5)s, %(is_from_day_open_high_5)s,
            %(base_low_broken_before_break)s, %(max_pullback_before_break_pct)s,
            %(break_time)s, %(break_price)s, %(break_type)s, %(bars_to_break)s, %(bars_after_break)s,
            %(break_after_max_time)s, %(break_after_max_price)s, %(break_after_max_return_pct)s,
            %(break_after_close_return_pct)s, %(break_after_max_drawdown_pct)s,
            %(pattern_type)s, %(valid_flag)s, %(invalid_reason)s, %(history_grade)s
        )
        ON DUPLICATE KEY UPDATE
            name=VALUES(name), day_open=VALUES(day_open), day_high=VALUES(day_high), day_low=VALUES(day_low), day_close=VALUES(day_close),
            capture_time=VALUES(capture_time), capture_price=VALUES(capture_price),
            capture_to_day_high_return_pct=VALUES(capture_to_day_high_return_pct), capture_to_close_return_pct=VALUES(capture_to_close_return_pct),
            base_candle_time=VALUES(base_candle_time), base_open=VALUES(base_open), base_high=VALUES(base_high), base_low=VALUES(base_low),
            base_close=VALUES(base_close), base_volume=VALUES(base_volume), base_amount=VALUES(base_amount),
            bar_return_pct=VALUES(bar_return_pct), from_day_open_close_pct=VALUES(from_day_open_close_pct),
            from_day_open_high_pct=VALUES(from_day_open_high_pct), close_position_pct=VALUES(close_position_pct),
            is_bar_return_5=VALUES(is_bar_return_5), is_from_day_open_close_5=VALUES(is_from_day_open_close_5),
            is_from_day_open_high_5=VALUES(is_from_day_open_high_5),
            base_low_broken_before_break=VALUES(base_low_broken_before_break), max_pullback_before_break_pct=VALUES(max_pullback_before_break_pct),
            break_time=VALUES(break_time), break_price=VALUES(break_price), break_type=VALUES(break_type),
            bars_to_break=VALUES(bars_to_break), bars_after_break=VALUES(bars_after_break),
            break_after_max_time=VALUES(break_after_max_time), break_after_max_price=VALUES(break_after_max_price),
            break_after_max_return_pct=VALUES(break_after_max_return_pct), break_after_close_return_pct=VALUES(break_after_close_return_pct),
            break_after_max_drawdown_pct=VALUES(break_after_max_drawdown_pct),
            pattern_type=VALUES(pattern_type), valid_flag=VALUES(valid_flag), invalid_reason=VALUES(invalid_reason),
            history_grade=VALUES(history_grade), updated_at=CURRENT_TIMESTAMP
    """
    with conn.cursor() as cur:
        cur.execute(sql, row)


def calc_avg(values: List[Optional[float]]) -> Optional[float]:
    filtered = [v for v in values if v is not None]
    if not filtered:
        return None
    return sum(filtered) / float(len(filtered))


def calc_median(values: List[Optional[float]]) -> Optional[float]:
    filtered = [v for v in values if v is not None]
    if not filtered:
        return None
    return float(statistics.median(filtered))


def win_rate(values: List[Optional[float]], threshold: float) -> Optional[float]:
    filtered = [v for v in values if v is not None]
    if not filtered:
        return None
    win_count = 0
    for value in filtered:
        if value >= threshold:
            win_count += 1
    return win_count / float(len(filtered))


def refresh_summary(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE analysis_5m_basebar_pattern_summary")
        cur.execute(
            """
            SELECT pattern_type,
                   capture_to_day_high_return_pct,
                   capture_to_close_return_pct,
                   break_time,
                   break_after_max_return_pct,
                   break_after_close_return_pct,
                   break_after_max_drawdown_pct,
                   bars_to_break,
                   bars_after_break
            FROM analysis_5m_basebar_result
            WHERE valid_flag = 1
            """
        )
        rows = list(cur.fetchall())

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        name = str(row.get("pattern_type"))
        if name not in grouped:
            grouped[name] = []
        grouped[name].append(row)

    insert_sql = """
        INSERT INTO analysis_5m_basebar_pattern_summary (
            pattern_name, sample_count, break_count, break_rate,
            avg_capture_to_day_high_return_pct, avg_capture_to_close_return_pct,
            avg_break_after_max_return_pct, median_break_after_max_return_pct,
            avg_break_after_close_return_pct, avg_break_after_max_drawdown_pct,
            win_rate_3pct, win_rate_5pct, win_rate_10pct, win_rate_20pct,
            avg_bars_to_break, avg_bars_after_break
        ) VALUES (
            %(pattern_name)s, %(sample_count)s, %(break_count)s, %(break_rate)s,
            %(avg_capture_to_day_high_return_pct)s, %(avg_capture_to_close_return_pct)s,
            %(avg_break_after_max_return_pct)s, %(median_break_after_max_return_pct)s,
            %(avg_break_after_close_return_pct)s, %(avg_break_after_max_drawdown_pct)s,
            %(win_rate_3pct)s, %(win_rate_5pct)s, %(win_rate_10pct)s, %(win_rate_20pct)s,
            %(avg_bars_to_break)s, %(avg_bars_after_break)s
        )
        ON DUPLICATE KEY UPDATE
            sample_count=VALUES(sample_count), break_count=VALUES(break_count), break_rate=VALUES(break_rate),
            avg_capture_to_day_high_return_pct=VALUES(avg_capture_to_day_high_return_pct),
            avg_capture_to_close_return_pct=VALUES(avg_capture_to_close_return_pct),
            avg_break_after_max_return_pct=VALUES(avg_break_after_max_return_pct),
            median_break_after_max_return_pct=VALUES(median_break_after_max_return_pct),
            avg_break_after_close_return_pct=VALUES(avg_break_after_close_return_pct),
            avg_break_after_max_drawdown_pct=VALUES(avg_break_after_max_drawdown_pct),
            win_rate_3pct=VALUES(win_rate_3pct), win_rate_5pct=VALUES(win_rate_5pct),
            win_rate_10pct=VALUES(win_rate_10pct), win_rate_20pct=VALUES(win_rate_20pct),
            avg_bars_to_break=VALUES(avg_bars_to_break), avg_bars_after_break=VALUES(avg_bars_after_break),
            updated_at=CURRENT_TIMESTAMP
    """

    with conn.cursor() as cur:
        for pattern_name, pattern_rows in grouped.items():
            sample_count = len(pattern_rows)
            break_rows = [row for row in pattern_rows if row.get("break_time") is not None]
            break_count = len(break_rows)
            max_returns = [to_float(row.get("break_after_max_return_pct")) for row in break_rows]
            close_returns = [to_float(row.get("break_after_close_return_pct")) for row in break_rows]
            drawdowns = [to_float(row.get("break_after_max_drawdown_pct")) for row in break_rows]
            bars_to_break = [to_float(row.get("bars_to_break")) for row in break_rows]
            bars_after_break = [to_float(row.get("bars_after_break")) for row in break_rows]
            summary = {
                "pattern_name": pattern_name,
                "sample_count": sample_count,
                "break_count": break_count,
                "break_rate": break_count / float(sample_count) if sample_count > 0 else None,
                "avg_capture_to_day_high_return_pct": calc_avg([to_float(row.get("capture_to_day_high_return_pct")) for row in pattern_rows]),
                "avg_capture_to_close_return_pct": calc_avg([to_float(row.get("capture_to_close_return_pct")) for row in pattern_rows]),
                "avg_break_after_max_return_pct": calc_avg(max_returns),
                "median_break_after_max_return_pct": calc_median(max_returns),
                "avg_break_after_close_return_pct": calc_avg(close_returns),
                "avg_break_after_max_drawdown_pct": calc_avg(drawdowns),
                "win_rate_3pct": win_rate(max_returns, 3.0),
                "win_rate_5pct": win_rate(max_returns, 5.0),
                "win_rate_10pct": win_rate(max_returns, 10.0),
                "win_rate_20pct": win_rate(max_returns, 20.0),
                "avg_bars_to_break": calc_avg(bars_to_break),
                "avg_bars_after_break": calc_avg(bars_after_break),
            }
            cur.execute(insert_sql, summary)


def print_summary(conn: Any) -> None:
    queries = [
        ("basebar overall", """
            SELECT COUNT(*) AS rows_count,
                   SUM(CASE WHEN valid_flag=1 THEN 1 ELSE 0 END) AS valid_rows,
                   SUM(CASE WHEN pattern_type='no_5pct_basebar' THEN 1 ELSE 0 END) AS no_basebar_rows,
                   SUM(CASE WHEN pattern_type<>'no_5pct_basebar' AND pattern_type<>'none' THEN 1 ELSE 0 END) AS basebar_rows,
                   SUM(CASE WHEN break_time IS NOT NULL THEN 1 ELSE 0 END) AS break_rows
            FROM analysis_5m_basebar_result
        """),
        ("pattern summary", """
            SELECT pattern_name, sample_count, break_count, break_rate,
                   avg_capture_to_day_high_return_pct,
                   avg_capture_to_close_return_pct,
                   avg_break_after_max_return_pct,
                   median_break_after_max_return_pct,
                   avg_break_after_close_return_pct,
                   avg_break_after_max_drawdown_pct,
                   win_rate_3pct, win_rate_5pct, win_rate_10pct, win_rate_20pct,
                   avg_bars_to_break
            FROM analysis_5m_basebar_pattern_summary
            ORDER BY sample_count DESC, avg_break_after_max_return_pct DESC
        """),
        ("top basebar breakout returns", """
            SELECT search_date, search_time, code, name, pattern_type,
                   base_candle_time, bar_return_pct, from_day_open_close_pct, from_day_open_high_pct,
                   break_time, break_type, break_after_max_return_pct,
                   break_after_close_return_pct, break_after_max_drawdown_pct,
                   base_volume, base_amount
            FROM analysis_5m_basebar_result
            WHERE valid_flag=1 AND break_time IS NOT NULL
            ORDER BY break_after_max_return_pct DESC
            LIMIT 30
        """),
        ("basebar no breakout sample", """
            SELECT search_date, search_time, code, name, pattern_type,
                   base_candle_time, bar_return_pct, from_day_open_close_pct, from_day_open_high_pct,
                   capture_to_day_high_return_pct, capture_to_close_return_pct,
                   base_volume, base_amount
            FROM analysis_5m_basebar_result
            WHERE valid_flag=1
              AND pattern_type <> 'no_5pct_basebar'
              AND break_time IS NULL
            ORDER BY capture_to_day_high_return_pct DESC
            LIMIT 30
        """),
    ]
    with conn.cursor() as cur:
        for title, sql in queries:
            print("\n=== " + title + " ===")
            cur.execute(sql)
            for row in cur.fetchall():
                print(row)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--threshold-pct", type=float, default=5.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--commit-every", type=int, default=200)
    args = parser.parse_args()

    load_env(args.env)
    conn = open_conn()
    try:
        ensure_schema(conn, args.rebuild)
        targets = load_targets(conn, args.limit)
        print("=== build_5m_basebar_breakout_analysis ===")
        print("targets=" + str(len(targets)))
        print("threshold_pct=" + str(args.threshold_pct))

        ok_count = 0
        fail_count = 0
        for idx, target in enumerate(targets, start=1):
            try:
                row = analyze_target(conn, target, args.threshold_pct)
                upsert_result(conn, row)
                ok_count += 1
            except Exception as ex:
                fail_count += 1
                print("[ERROR] idx=" + str(idx) + " target=" + str(target) + " ex=" + str(ex))
            if idx % args.commit_every == 0:
                conn.commit()
                print("[" + str(idx) + "/" + str(len(targets)) + "] committed ok=" + str(ok_count) + " fail=" + str(fail_count))

        refresh_summary(conn)
        conn.commit()
        print("\n=== DONE build_5m_basebar_breakout_analysis ===")
        print("total=" + str(len(targets)) + " ok=" + str(ok_count) + " fail=" + str(fail_count))
        print_summary(conn)
        return 0
    except Exception as ex:
        conn.rollback()
        print("[FATAL] " + str(ex), file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
