# -*- coding: utf-8 -*-
"""Build SuperTrend Regime Discovery.

This script extracts SuperTrend uptrend segments from the current condition-search universe.
It does not create a buy/sell strategy. It creates reusable regime labels:
Good ST, Great ST, Bad ST, false/noisy ST.

Run:
    python -m src.analysis.build_supertrend_regime_discovery --env .env --rebuild
"""

from __future__ import annotations

import argparse
import math
import os
import statistics
import sys
from datetime import date, datetime, time, timedelta
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
    ddl = Path("sql/create_supertrend_regime_discovery.sql").read_text(encoding="utf-8-sig")
    with conn.cursor() as cur:
        if rebuild:
            cur.execute("DROP TABLE IF EXISTS supertrend_regime_feature_summary")
            cur.execute("DROP TABLE IF EXISTS supertrend_regime_summary")
            cur.execute("DROP TABLE IF EXISTS supertrend_regime_segment")
        for statement in ddl.split(";"):
            sql = statement.strip()
            if sql:
                cur.execute(sql)
    conn.commit()


def normalize_time_value(value: Any) -> time:
    """Normalize MySQL TIME values.

    PyMySQL often returns MySQL TIME columns as datetime.timedelta, not datetime.time.
    datetime.combine requires datetime.time, so every search_time must pass through this helper.
    """
    if isinstance(value, time):
        return value
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds())
        if total_seconds < 0:
            total_seconds = 0
        total_seconds = total_seconds % (24 * 60 * 60)
        hour = total_seconds // 3600
        minute = (total_seconds % 3600) // 60
        second = total_seconds % 60
        return time(hour, minute, second)
    if isinstance(value, str):
        parts = value.strip().split(":")
        if len(parts) >= 2:
            hour = int(parts[0])
            minute = int(parts[1])
            second = int(parts[2]) if len(parts) >= 3 else 0
            return time(hour, minute, second)
    raise TypeError("Unsupported time value: " + repr(value))


def combine_date_time(date_value: Any, time_value: Any) -> datetime:
    if isinstance(date_value, datetime):
        d = date_value.date()
    elif isinstance(date_value, date):
        d = date_value
    elif isinstance(date_value, str):
        d = datetime.fromisoformat(date_value).date()
    else:
        raise TypeError("Unsupported date value: " + repr(date_value))
    return datetime.combine(d, normalize_time_value(time_value))


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


def avg(values: List[Optional[float]]) -> Optional[float]:
    items = [v for v in values if v is not None]
    if not items:
        return None
    return sum(items) / float(len(items))


def median(values: List[Optional[float]]) -> Optional[float]:
    items = [v for v in values if v is not None]
    if not items:
        return None
    return float(statistics.median(items))


def rate_int(values: List[int], target: int = 1) -> Optional[float]:
    if not values:
        return None
    return sum(1 for v in values if v == target) / float(len(values))


def amount_from_row(row: Dict[str, Any]) -> Optional[float]:
    o = to_float(row.get("open_price"))
    h = to_float(row.get("high_price"))
    l = to_float(row.get("low_price"))
    c = to_float(row.get("close_price"))
    v = to_float(row.get("volume"))
    if o is None or h is None or l is None or c is None or v is None:
        return None
    return ((o + h + l + c) / 4.0) * v


def load_targets(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT search_date, search_time, code, name
            FROM analysis_5m_result
            WHERE valid_analysis_flag = 1
              AND history_grade IN ('normal_intraday', 'partial_intraday', 'weak_intraday')
            GROUP BY search_date, search_time, code, name
            ORDER BY search_date, search_time, code
        """)
        return list(cur.fetchall())


def load_day_candles(conn: Any, trade_date: Any, code: str) -> List[Dict[str, Any]]:
    start_dt = datetime.combine(trade_date, time(9, 0, 0))
    end_dt = datetime.combine(trade_date, time(15, 30, 0))
    with conn.cursor() as cur:
        cur.execute("""
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
        """, (code, start_dt, end_dt))
        return list(cur.fetchall())


def true_range(row: Dict[str, Any], prev_close: Optional[float]) -> Optional[float]:
    high = to_float(row.get("high_price"))
    low = to_float(row.get("low_price"))
    if high is None or low is None:
        return None
    if prev_close is None:
        return high - low
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def calculate_atr(rows: List[Dict[str, Any]], period: int) -> List[Optional[float]]:
    atr: List[Optional[float]] = [None] * len(rows)
    trs: List[float] = []
    prev_close: Optional[float] = None
    for row in rows:
        tr = true_range(row, prev_close)
        trs.append(0.0 if tr is None else tr)
        prev_close = to_float(row.get("close_price"))
    if len(rows) < period:
        return atr
    initial = sum(trs[0:period]) / float(period)
    atr[period - 1] = initial
    for i in range(period, len(rows)):
        prev_atr = atr[i - 1]
        if prev_atr is None:
            prev_atr = initial
        atr[i] = ((prev_atr * (period - 1)) + trs[i]) / float(period)
    return atr


def calculate_supertrend(rows: List[Dict[str, Any]], period: int, multiplier: float) -> Tuple[List[Optional[float]], List[int]]:
    n = len(rows)
    atr = calculate_atr(rows, period)
    final_upper: List[Optional[float]] = [None] * n
    final_lower: List[Optional[float]] = [None] * n
    st_line: List[Optional[float]] = [None] * n
    direction: List[int] = [0] * n

    for i in range(n):
        high = to_float(rows[i].get("high_price"))
        low = to_float(rows[i].get("low_price"))
        close = to_float(rows[i].get("close_price"))
        if high is None or low is None or close is None or atr[i] is None:
            continue
        hl2 = (high + low) / 2.0
        basic_upper = hl2 + multiplier * atr[i]
        basic_lower = hl2 - multiplier * atr[i]

        if i == 0 or final_upper[i - 1] is None or final_lower[i - 1] is None:
            final_upper[i] = basic_upper
            final_lower[i] = basic_lower
            direction[i] = 1
            st_line[i] = final_lower[i]
            continue

        prev_close = to_float(rows[i - 1].get("close_price"))
        prev_upper = final_upper[i - 1]
        prev_lower = final_lower[i - 1]
        if prev_upper is None or prev_lower is None:
            final_upper[i] = basic_upper
            final_lower[i] = basic_lower
        else:
            final_upper[i] = basic_upper if basic_upper < prev_upper or (prev_close is not None and prev_close > prev_upper) else prev_upper
            final_lower[i] = basic_lower if basic_lower > prev_lower or (prev_close is not None and prev_close < prev_lower) else prev_lower

        prev_dir = direction[i - 1]
        if prev_dir == 0:
            prev_dir = 1
        if prev_dir == -1 and close > (final_upper[i] or basic_upper):
            direction[i] = 1
        elif prev_dir == 1 and close < (final_lower[i] or basic_lower):
            direction[i] = -1
        else:
            direction[i] = prev_dir
        st_line[i] = final_lower[i] if direction[i] == 1 else final_upper[i]
    return st_line, direction


def build_start_features(rows: List[Dict[str, Any]], start_idx: int) -> Dict[str, Any]:
    day_open = to_float(rows[0].get("open_price")) if rows else None
    before = rows[0:start_idx + 1]
    lows = [to_float(r.get("low_price")) for r in before]
    highs = [to_float(r.get("high_price")) for r in before]
    day_low_so_far = min([v for v in lows if v is not None]) if any(v is not None for v in lows) else None
    high_so_far = max([v for v in highs if v is not None]) if any(v is not None for v in highs) else None
    start_price = to_float(rows[start_idx].get("close_price"))

    cum_amount = 0.0
    cum_volume = 0
    max_singlebar: Optional[float] = None
    for row in before:
        amount = amount_from_row(row)
        if amount is not None:
            cum_amount += amount
        cum_volume += to_int(row.get("volume"))
        sb = pct(to_float(row.get("close_price")), to_float(row.get("open_price")))
        if sb is not None and (max_singlebar is None or sb > max_singlebar):
            max_singlebar = sb
    return {
        "start_from_day_open_pct": pct(start_price, day_open),
        "start_from_day_low_pct": pct(start_price, day_low_so_far),
        "start_cum_amount": cum_amount,
        "start_cum_volume": cum_volume,
        "start_range_so_far_pct": pct(high_so_far, day_low_so_far),
        "start_high_so_far_from_open_pct": pct(high_so_far, day_open),
        "max_singlebar_return_before_start": max_singlebar,
        "singlebar_3pct_exists_before_start": 1 if max_singlebar is not None and max_singlebar >= 3.0 else 0,
        "singlebar_5pct_exists_before_start": 1 if max_singlebar is not None and max_singlebar >= 5.0 else 0,
    }


def build_segment_features(rows: List[Dict[str, Any]], start_idx: int, end_idx: int) -> Dict[str, Any]:
    segment = rows[start_idx:end_idx + 1]
    amount_sum = 0.0
    volume_sum = 0
    green_count = 0
    red_count = 0
    max_singlebar: Optional[float] = None
    for row in segment:
        amount = amount_from_row(row)
        if amount is not None:
            amount_sum += amount
        volume_sum += to_int(row.get("volume"))
        o = to_float(row.get("open_price"))
        c = to_float(row.get("close_price"))
        if o is not None and c is not None:
            if c >= o:
                green_count += 1
            else:
                red_count += 1
        sb = pct(c, o)
        if sb is not None and (max_singlebar is None or sb > max_singlebar):
            max_singlebar = sb
    return {
        "segment_amount": amount_sum,
        "segment_volume": volume_sum,
        "segment_avg_amount_per_bar": amount_sum / float(len(segment)) if segment else None,
        "segment_max_singlebar_return_pct": max_singlebar,
        "segment_green_bar_count": green_count,
        "segment_red_bar_count": red_count,
    }


def extract_segments(target: Dict[str, Any], rows: List[Dict[str, Any]], period: int, multiplier: float) -> List[Dict[str, Any]]:
    if len(rows) < period + 3:
        return []
    _st_line, direction = calculate_supertrend(rows, period, multiplier)
    capture_dt = combine_date_time(target.get("search_date"), target.get("search_time"))
    search_time_value = normalize_time_value(target.get("search_time"))
    segments: List[Dict[str, Any]] = []
    i = 0
    seg_no = 1
    while i < len(rows):
        if direction[i] != 1:
            i += 1
            continue
        start_idx = i
        j = i
        while j + 1 < len(rows) and direction[j + 1] == 1:
            j += 1
        end_idx = j

        start_time = rows[start_idx].get("candle_time")
        end_time = rows[end_idx].get("candle_time")
        if start_time is None:
            i = end_idx + 1
            continue
        if end_time is not None and end_time < capture_dt:
            i = end_idx + 1
            continue

        already_up_at_capture = 1 if start_time <= capture_dt <= (end_time or start_time) else 0
        start_price = to_float(rows[start_idx].get("close_price"))
        end_price = to_float(rows[end_idx].get("close_price"))
        highs = [to_float(r.get("high_price")) for r in rows[start_idx:end_idx + 1]]
        lows = [to_float(r.get("low_price")) for r in rows[start_idx:end_idx + 1]]
        max_price = max([v for v in highs if v is not None]) if any(v is not None for v in highs) else None
        min_price = min([v for v in lows if v is not None]) if any(v is not None for v in lows) else None
        max_ret = pct(max_price, start_price)
        end_ret = pct(end_price, start_price)
        drawdown = pct(min_price, start_price)
        start_features = build_start_features(rows, start_idx)
        segment_features = build_segment_features(rows, start_idx, end_idx)
        row: Dict[str, Any] = {
            "trade_date": target.get("search_date"),
            "search_time": search_time_value,
            "code": str(target.get("code")),
            "name": target.get("name"),
            "timeframe": "m5",
            "st_period": period,
            "st_multiplier": multiplier,
            "segment_no": seg_no,
            "capture_time": capture_dt,
            "already_up_at_capture": already_up_at_capture,
            "st_up_start_time": start_time,
            "st_up_end_time": end_time,
            "st_up_bars": end_idx - start_idx + 1,
            "st_up_start_price": start_price,
            "st_up_max_price": max_price,
            "st_up_end_price": end_price,
            "st_up_min_price": min_price,
            "st_up_max_return_pct": max_ret,
            "st_up_end_return_pct": end_ret,
            "st_up_max_drawdown_pct": drawdown,
            **start_features,
            **segment_features,
            "label_st_gain_3pct": 1 if max_ret is not None and max_ret >= 3.0 else 0,
            "label_st_gain_5pct": 1 if max_ret is not None and max_ret >= 5.0 else 0,
            "label_st_gain_10pct": 1 if max_ret is not None and max_ret >= 10.0 else 0,
            "label_st_fail_1pct": 1 if max_ret is not None and max_ret < 1.0 else 0,
            "label_st_end_negative": 1 if end_ret is not None and end_ret < 0.0 else 0,
        }
        segments.append(row)
        seg_no += 1
        i = end_idx + 1
    return segments


def upsert_segment(conn: Any, row: Dict[str, Any]) -> None:
    cols = list(row.keys())
    placeholders = ["%s"] * len(cols)
    updates = [c + "=VALUES(" + c + ")" for c in cols if c not in ("trade_date", "code", "timeframe", "st_period", "st_multiplier", "segment_no")]
    sql = "INSERT INTO supertrend_regime_segment (" + ",".join(cols) + ") VALUES (" + ",".join(placeholders) + ") ON DUPLICATE KEY UPDATE " + ",".join(updates) + ", updated_at=CURRENT_TIMESTAMP"
    with conn.cursor() as cur:
        cur.execute(sql, [row.get(c) for c in cols])


def load_segments(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM supertrend_regime_segment")
        return list(cur.fetchall())


def refresh_summary(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE supertrend_regime_summary")
        cur.execute("TRUNCATE TABLE supertrend_regime_feature_summary")
    rows = load_segments(conn)
    grouped: Dict[Tuple[int, float, str], List[Dict[str, Any]]] = {}
    for row in rows:
        groups = ["ALL"]
        if to_int(row.get("label_st_gain_5pct")) == 1:
            groups.append("GOOD_GAIN5")
        if to_int(row.get("label_st_gain_10pct")) == 1:
            groups.append("GREAT_GAIN10")
        if to_int(row.get("label_st_fail_1pct")) == 1 or to_int(row.get("label_st_end_negative")) == 1:
            groups.append("BAD_FAIL_OR_NEG")
        if to_int(row.get("already_up_at_capture")) == 1:
            groups.append("ALREADY_UP_AT_CAPTURE")
        for g in groups:
            grouped.setdefault((to_int(row.get("st_period")), float(row.get("st_multiplier")), g), []).append(row)

    sql_summary = """
        INSERT INTO supertrend_regime_summary (
            st_period, st_multiplier, segment_group, segment_count, active_days, avg_segments_per_day,
            avg_st_up_bars, avg_st_up_max_return_pct, median_st_up_max_return_pct,
            avg_st_up_end_return_pct, avg_st_up_max_drawdown_pct,
            gain3_rate, gain5_rate, gain10_rate, fail1_rate, end_negative_rate,
            avg_start_from_day_open_pct, avg_start_from_day_low_pct, avg_start_cum_amount,
            avg_start_range_so_far_pct, avg_segment_amount, avg_segment_max_singlebar_return_pct
        ) VALUES (
            %(st_period)s, %(st_multiplier)s, %(segment_group)s, %(segment_count)s, %(active_days)s, %(avg_segments_per_day)s,
            %(avg_st_up_bars)s, %(avg_st_up_max_return_pct)s, %(median_st_up_max_return_pct)s,
            %(avg_st_up_end_return_pct)s, %(avg_st_up_max_drawdown_pct)s,
            %(gain3_rate)s, %(gain5_rate)s, %(gain10_rate)s, %(fail1_rate)s, %(end_negative_rate)s,
            %(avg_start_from_day_open_pct)s, %(avg_start_from_day_low_pct)s, %(avg_start_cum_amount)s,
            %(avg_start_range_so_far_pct)s, %(avg_segment_amount)s, %(avg_segment_max_singlebar_return_pct)s
        )
    """
    with conn.cursor() as cur:
        for key, vals in grouped.items():
            row = {
                "st_period": key[0],
                "st_multiplier": key[1],
                "segment_group": key[2],
                "segment_count": len(vals),
                "active_days": len({v.get("trade_date") for v in vals}),
                "avg_segments_per_day": len(vals) / 82.0,
                "avg_st_up_bars": avg([to_float(v.get("st_up_bars")) for v in vals]),
                "avg_st_up_max_return_pct": avg([to_float(v.get("st_up_max_return_pct")) for v in vals]),
                "median_st_up_max_return_pct": median([to_float(v.get("st_up_max_return_pct")) for v in vals]),
                "avg_st_up_end_return_pct": avg([to_float(v.get("st_up_end_return_pct")) for v in vals]),
                "avg_st_up_max_drawdown_pct": avg([to_float(v.get("st_up_max_drawdown_pct")) for v in vals]),
                "gain3_rate": rate_int([to_int(v.get("label_st_gain_3pct")) for v in vals]),
                "gain5_rate": rate_int([to_int(v.get("label_st_gain_5pct")) for v in vals]),
                "gain10_rate": rate_int([to_int(v.get("label_st_gain_10pct")) for v in vals]),
                "fail1_rate": rate_int([to_int(v.get("label_st_fail_1pct")) for v in vals]),
                "end_negative_rate": rate_int([to_int(v.get("label_st_end_negative")) for v in vals]),
                "avg_start_from_day_open_pct": avg([to_float(v.get("start_from_day_open_pct")) for v in vals]),
                "avg_start_from_day_low_pct": avg([to_float(v.get("start_from_day_low_pct")) for v in vals]),
                "avg_start_cum_amount": avg([to_float(v.get("start_cum_amount")) for v in vals]),
                "avg_start_range_so_far_pct": avg([to_float(v.get("start_range_so_far_pct")) for v in vals]),
                "avg_segment_amount": avg([to_float(v.get("segment_amount")) for v in vals]),
                "avg_segment_max_singlebar_return_pct": avg([to_float(v.get("segment_max_singlebar_return_pct")) for v in vals]),
            }
            cur.execute(sql_summary, row)

    feature_names = [
        "start_from_day_open_pct", "start_from_day_low_pct", "start_cum_amount",
        "start_range_so_far_pct", "start_high_so_far_from_open_pct",
        "max_singlebar_return_before_start", "segment_amount", "segment_avg_amount_per_bar",
        "segment_max_singlebar_return_pct", "st_up_bars",
    ]
    sql_feature = """
        INSERT INTO supertrend_regime_feature_summary (
            st_period, st_multiplier, feature_name, good_group, bad_group,
            good_count, bad_count, good_avg_value, bad_avg_value, diff_avg_value
        ) VALUES (
            %(st_period)s, %(st_multiplier)s, %(feature_name)s, %(good_group)s, %(bad_group)s,
            %(good_count)s, %(bad_count)s, %(good_avg_value)s, %(bad_avg_value)s, %(diff_avg_value)s
        )
    """
    params = sorted({(to_int(r.get("st_period")), float(r.get("st_multiplier"))) for r in rows})
    with conn.cursor() as cur:
        for period, mult in params:
            p_rows = [r for r in rows if to_int(r.get("st_period")) == period and float(r.get("st_multiplier")) == mult]
            good = [r for r in p_rows if to_int(r.get("label_st_gain_5pct")) == 1]
            bad = [r for r in p_rows if to_int(r.get("label_st_fail_1pct")) == 1 or to_int(r.get("label_st_end_negative")) == 1]
            for feature in feature_names:
                good_avg = avg([to_float(r.get(feature)) for r in good])
                bad_avg = avg([to_float(r.get(feature)) for r in bad])
                row = {
                    "st_period": period,
                    "st_multiplier": mult,
                    "feature_name": feature,
                    "good_group": "GOOD_GAIN5",
                    "bad_group": "BAD_FAIL_OR_NEG",
                    "good_count": len(good),
                    "bad_count": len(bad),
                    "good_avg_value": good_avg,
                    "bad_avg_value": bad_avg,
                    "diff_avg_value": good_avg - bad_avg if good_avg is not None and bad_avg is not None else None,
                }
                cur.execute(sql_feature, row)
    conn.commit()


def print_summary(conn: Any) -> None:
    with conn.cursor() as cur:
        print("\n=== supertrend_regime_summary ===")
        cur.execute("""
            SELECT st_period, st_multiplier, segment_group, segment_count, active_days,
                   avg_segments_per_day, avg_st_up_bars, avg_st_up_max_return_pct,
                   median_st_up_max_return_pct, avg_st_up_end_return_pct,
                   gain3_rate, gain5_rate, gain10_rate, fail1_rate, end_negative_rate,
                   avg_start_from_day_open_pct, avg_start_cum_amount
            FROM supertrend_regime_summary
            ORDER BY st_period, st_multiplier,
                     FIELD(segment_group, 'ALL','GOOD_GAIN5','GREAT_GAIN10','BAD_FAIL_OR_NEG','ALREADY_UP_AT_CAPTURE')
        """)
        for row in cur.fetchall():
            print(row)
        print("\n=== supertrend_regime_feature_summary top diffs ===")
        cur.execute("""
            SELECT st_period, st_multiplier, feature_name, good_count, bad_count,
                   good_avg_value, bad_avg_value, diff_avg_value
            FROM supertrend_regime_feature_summary
            ORDER BY ABS(COALESCE(diff_avg_value, 0)) DESC
            LIMIT 80
        """)
        for row in cur.fetchall():
            print(row)


def parse_params(text: str) -> List[Tuple[int, float]]:
    result: List[Tuple[int, float]] = []
    for item in text.split(","):
        t = item.strip()
        if not t:
            continue
        p, m = t.split(":")
        result.append((int(p), float(m)))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--params", default="7:1.5,7:2.0,10:2.0,14:2.0")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    load_env(args.env)
    conn = open_conn()
    try:
        ensure_schema(conn, args.rebuild)
        targets = load_targets(conn)
        if args.limit > 0:
            targets = targets[:args.limit]
        params = parse_params(args.params)
        print("=== build_supertrend_regime_discovery ===")
        print("targets=" + str(len(targets)))
        print("params=" + str(params))
        total = 0
        candle_cache: Dict[Tuple[Any, str], List[Dict[str, Any]]] = {}
        for target in targets:
            key = (target.get("search_date"), str(target.get("code")))
            if key not in candle_cache:
                candle_cache[key] = load_day_candles(conn, target.get("search_date"), str(target.get("code")))
            rows = candle_cache[key]
            if not rows:
                continue
            for period, multiplier in params:
                segments = extract_segments(target, rows, period, multiplier)
                for seg in segments:
                    upsert_segment(conn, seg)
                    total += 1
            if total > 0 and total % 500 == 0:
                conn.commit()
                print("segments_so_far=" + str(total))
        conn.commit()
        refresh_summary(conn)
        print("\n=== DONE build_supertrend_regime_discovery ===")
        print("segments=" + str(total))
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
