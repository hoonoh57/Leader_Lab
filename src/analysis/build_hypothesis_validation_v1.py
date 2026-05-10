# -*- coding: utf-8 -*-
"""Build hypothesis_validation_v1_result from the locked validation plan.

Validated hypotheses:
- H5M-1: single 5m open->close +5% base bar, later base-high breakout, breakout volume > base volume
- H5M-2: H5M base breakout with RSI(14)>60 or RSI(14)>RSI(14)[1]
- H5M-3: H5M base breakout with breakout close crossing above MA10
- D-1/D-2: optional daily structure checks when daily_candles exists with expected columns

Run:
    python -m src.analysis.build_hypothesis_validation_v1 --env .env --rebuild
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import datetime, timedelta, time
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
    ddl = Path("sql/create_hypothesis_validation_v1.sql").read_text(encoding="utf-8-sig")
    with conn.cursor() as cur:
        if rebuild:
            cur.execute("DROP TABLE IF EXISTS hypothesis_validation_v1_summary")
            cur.execute("DROP TABLE IF EXISTS hypothesis_validation_v1_result")
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


def quote_name(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


def table_exists(conn: Any, table_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
            """,
            (table_name,),
        )
        row = cur.fetchone()
    return to_int(row.get("cnt")) > 0


def columns(conn: Any, table_name: str) -> List[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """,
            (table_name,),
        )
        rows = cur.fetchall()
    return [str(row["COLUMN_NAME"]) for row in rows]


def pick(cols: List[str], candidates: Sequence[str], required: bool = True) -> Optional[str]:
    lower = {c.lower(): c for c in cols}
    for candidate in candidates:
        found = lower.get(candidate.lower())
        if found is not None:
            return found
    if required:
        raise RuntimeError("필수 컬럼 탐지 실패: 후보=" + ",".join(candidates) + " 실제=" + ",".join(cols))
    return None


def build_daily_meta(conn: Any) -> Optional[Dict[str, str]]:
    if not table_exists(conn, "daily_candles"):
        return None
    cols = columns(conn, "daily_candles")
    try:
        return {
            "code": str(pick(cols, ["code", "stock_code", "ticker", "종목코드"])),
            "date": str(pick(cols, ["candle_date", "trade_date", "date", "일자"])),
            "open": str(pick(cols, ["open", "open_price", "시가"])),
            "high": str(pick(cols, ["high", "high_price", "고가"])),
            "low": str(pick(cols, ["low", "low_price", "저가"])),
            "close": str(pick(cols, ["close", "close_price", "종가"])),
            "volume": str(pick(cols, ["volume", "vol", "거래량"])),
        }
    except Exception:
        return None


def amount_from_row(row: Dict[str, Any]) -> Optional[float]:
    o = to_float(row.get("open_price"))
    h = to_float(row.get("high_price"))
    l = to_float(row.get("low_price"))
    c = to_float(row.get("close_price"))
    v = to_float(row.get("volume"))
    if o is None or h is None or l is None or c is None or v is None:
        return None
    return ((o + h + l + c) / 4.0) * v


def load_targets(conn: Any, limit: int) -> List[Dict[str, Any]]:
    sql = """
        SELECT search_date, search_time, code, name,
               capture_time, capture_price,
               max_after_return_pct AS actual_max_after_return_pct,
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


def build_actual_ranks(targets: List[Dict[str, Any]]) -> Dict[Tuple[Any, str], int]:
    grouped: Dict[Any, List[Tuple[str, float]]] = {}
    for row in targets:
        d = row.get("search_date")
        code = str(row.get("code"))
        value = to_float(row.get("actual_max_after_return_pct"))
        if value is None:
            continue
        if d not in grouped:
            grouped[d] = []
        grouped[d].append((code, value))
    ranks: Dict[Tuple[Any, str], int] = {}
    for d, values in grouped.items():
        values.sort(key=lambda item: (-item[1], item[0]))
        for idx, item in enumerate(values, start=1):
            ranks[(d, item[0])] = idx
    return ranks


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


def calculate_rsi14(rows: List[Dict[str, Any]]) -> List[Optional[float]]:
    closes = [to_float(row.get("close_price")) for row in rows]
    result: List[Optional[float]] = [None] * len(rows)
    if len(rows) < 15:
        return result

    gains: List[float] = []
    losses: List[float] = []
    for i in range(1, len(closes)):
        if closes[i] is None or closes[i - 1] is None:
            gains.append(0.0)
            losses.append(0.0)
        else:
            change = float(closes[i]) - float(closes[i - 1])
            gains.append(max(change, 0.0))
            losses.append(max(-change, 0.0))

    period = 14
    avg_gain = sum(gains[0:period]) / float(period)
    avg_loss = sum(losses[0:period]) / float(period)
    if avg_loss == 0:
        result[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100.0 - (100.0 / (1.0 + rs))

    for i in range(period + 1, len(rows)):
        gain = gains[i - 1]
        loss = losses[i - 1]
        avg_gain = ((avg_gain * (period - 1)) + gain) / float(period)
        avg_loss = ((avg_loss * (period - 1)) + loss) / float(period)
        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100.0 - (100.0 / (1.0 + rs))
    return result


def calculate_ma10(rows: List[Dict[str, Any]]) -> List[Optional[float]]:
    closes = [to_float(row.get("close_price")) for row in rows]
    result: List[Optional[float]] = [None] * len(rows)
    window: List[float] = []
    running_sum = 0.0
    for idx, close_value in enumerate(closes):
        if close_value is None:
            window.append(0.0)
            running_sum += 0.0
        else:
            window.append(close_value)
            running_sum += close_value
        if len(window) > 10:
            running_sum -= window.pop(0)
        if len(window) == 10:
            result[idx] = running_sum / 10.0
    return result


def find_singlebar5(rows: List[Dict[str, Any]], threshold_pct: float) -> Tuple[int, Optional[Dict[str, Any]]]:
    for idx, row in enumerate(rows):
        ret = pct(to_float(row.get("close_price")), to_float(row.get("open_price")))
        if ret is not None and ret >= threshold_pct:
            return idx, row
    return -1, None


def find_singlebar3(rows: List[Dict[str, Any]]) -> bool:
    for row in rows:
        ret = pct(to_float(row.get("close_price")), to_float(row.get("open_price")))
        if ret is not None and ret >= 3.0:
            return True
    return False


def find_break_after_base(rows: List[Dict[str, Any]], base_idx: int, base_high: Optional[float]) -> Tuple[int, Optional[str], Optional[float]]:
    if base_idx < 0 or base_high is None:
        return -1, None, None
    for idx in range(base_idx + 1, len(rows)):
        row = rows[idx]
        close_value = to_float(row.get("close_price"))
        high_value = to_float(row.get("high_price"))
        if close_value is not None and close_value > base_high:
            return idx, "close_break_base_high", close_value
        if high_value is not None and high_value > base_high:
            return idx, "high_touch_base_high", base_high
    return -1, None, None


def calc_after_break(rows: List[Dict[str, Any]], break_idx: int, break_price: Optional[float]) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "break_after_max_time": None,
        "break_after_max_price": None,
        "break_after_max_return_pct": None,
        "break_after_close_return_pct": None,
        "break_after_max_drawdown_pct": None,
    }
    if break_idx < 0 or break_price is None:
        return result
    max_price: Optional[float] = None
    max_time: Optional[datetime] = None
    min_price: Optional[float] = None
    close_final: Optional[float] = None
    for idx in range(break_idx, len(rows)):
        row = rows[idx]
        high_value = to_float(row.get("high_price"))
        low_value = to_float(row.get("low_price"))
        close_value = to_float(row.get("close_price"))
        if high_value is not None and (max_price is None or high_value > max_price):
            max_price = high_value
            max_time = row.get("candle_time")
        if low_value is not None and (min_price is None or low_value < min_price):
            min_price = low_value
        close_final = close_value
    result.update({
        "break_after_max_time": max_time,
        "break_after_max_price": max_price,
        "break_after_max_return_pct": pct(max_price, break_price),
        "break_after_close_return_pct": pct(close_final, break_price),
        "break_after_max_drawdown_pct": pct(min_price, break_price),
    })
    return result


def load_daily_rows(conn: Any, meta: Dict[str, str], code: str, search_date: Any, lookback: int) -> List[Dict[str, Any]]:
    sql = (
        "SELECT "
        + quote_name(meta["date"]) + " AS trade_date, "
        + quote_name(meta["open"]) + " AS open_price, "
        + quote_name(meta["high"]) + " AS high_price, "
        + quote_name(meta["low"]) + " AS low_price, "
        + quote_name(meta["close"]) + " AS close_price, "
        + quote_name(meta["volume"]) + " AS volume "
        + "FROM daily_candles WHERE " + quote_name(meta["code"]) + "=%s AND " + quote_name(meta["date"]) + "<%s "
        + "ORDER BY " + quote_name(meta["date"]) + " DESC LIMIT %s"
    )
    with conn.cursor() as cur:
        cur.execute(sql, (code, search_date, lookback))
        rows = list(cur.fetchall())
    rows.reverse()
    return rows


def daily_checks(conn: Any, daily_meta: Optional[Dict[str, str]], target: Dict[str, Any], rows5: List[Dict[str, Any]]) -> Dict[str, Any]:
    result = {
        "has_daily_context": 0,
        "d1_prev5_up10_high_break_5m3": 0,
        "d2_prev10_high20_closeup_5d_highvol": 0,
        "daily_reason": None,
    }
    if daily_meta is None:
        result["daily_reason"] = "daily_candles_unavailable"
        return result

    code = str(target.get("code"))
    search_date = target.get("search_date")
    daily10 = load_daily_rows(conn, daily_meta, code, search_date, 10)
    if len(daily10) < 5:
        result["daily_reason"] = "insufficient_daily_rows"
        return result
    result["has_daily_context"] = 1

    day_high = max([to_float(r.get("high_price")) or -999999999.0 for r in rows5]) if rows5 else None
    has_5m3 = find_singlebar3(rows5)

    # D-1: within previous 5 daily candles, close return >=10, current intraday high breaks that daily high, and 5m singlebar >=3
    prev5 = daily10[-5:]
    for i in range(1, len(prev5)):
        prev_close = to_float(prev5[i - 1].get("close_price"))
        close_value = to_float(prev5[i].get("close_price"))
        high_value = to_float(prev5[i].get("high_price"))
        close_ret = pct(close_value, prev_close)
        if close_ret is not None and close_ret >= 10.0 and day_high is not None and high_value is not None and day_high > high_value and has_5m3:
            result["d1_prev5_up10_high_break_5m3"] = 1
            break

    # D-2: within previous 10 daily candles, high return >=20, previous close rising, 5-day high, 5-day volume high
    for idx in range(1, len(daily10)):
        prev_close = to_float(daily10[idx - 1].get("close_price"))
        open_value = to_float(daily10[idx].get("open_price"))
        high_value = to_float(daily10[idx].get("high_price"))
        close_value = to_float(daily10[idx].get("close_price"))
        volume_value = to_float(daily10[idx].get("volume"))
        high_ret = pct(high_value, open_value)
        close_up = close_value is not None and prev_close is not None and close_value > prev_close
        start = max(0, idx - 4)
        window = daily10[start:idx + 1]
        max_high = max([to_float(r.get("high_price")) or -999999999.0 for r in window])
        max_volume = max([to_float(r.get("volume")) or -1.0 for r in window])
        is_5d_high = high_value is not None and high_value >= max_high
        is_5d_vol = volume_value is not None and volume_value >= max_volume
        if high_ret is not None and high_ret >= 20.0 and close_up and is_5d_high and is_5d_vol:
            result["d2_prev10_high20_closeup_5d_highvol"] = 1
            break

    if result["d1_prev5_up10_high_break_5m3"] == 0 and result["d2_prev10_high20_closeup_5d_highvol"] == 0:
        result["daily_reason"] = "daily_context_no_match"
    else:
        result["daily_reason"] = "daily_context_match"
    return result


def analyze_target(conn: Any, target: Dict[str, Any], actual_ranks: Dict[Tuple[Any, str], int], daily_meta: Optional[Dict[str, str]], threshold_pct: float) -> Dict[str, Any]:
    d = target.get("search_date")
    code = str(target.get("code"))
    actual_rank = actual_ranks.get((d, code))
    rows = load_day_candles(conn, d, code)

    result: Dict[str, Any] = {
        "search_date": d,
        "search_time": target.get("search_time"),
        "code": code,
        "name": target.get("name"),
        "actual_rank": actual_rank,
        "in_actual_top10": 1 if actual_rank is not None and actual_rank <= 10 else 0,
        "actual_max_after_return_pct": to_float(target.get("actual_max_after_return_pct")),
        "has_singlebar_close5": 0,
        "singlebar_time": None,
        "singlebar_open": None,
        "singlebar_high": None,
        "singlebar_low": None,
        "singlebar_close": None,
        "singlebar_volume": None,
        "singlebar_amount": None,
        "singlebar_close_return_pct": None,
        "singlebar_high_return_pct": None,
        "break_time": None,
        "break_type": None,
        "break_price": None,
        "break_open": None,
        "break_high": None,
        "break_low": None,
        "break_close": None,
        "break_volume": None,
        "break_amount": None,
        "bars_to_break": None,
        "break_volume_gt_base": 0,
        "break_rsi14": None,
        "break_rsi14_prev": None,
        "break_rsi_gt_60": 0,
        "break_rsi_rising": 0,
        "break_ma10": None,
        "break_ma10_prev": None,
        "break_close_gt_ma10": 0,
        "break_close_cross_ma10": 0,
        "h5m1_singlebar5_break_volume": 0,
        "h5m2_singlebar5_break_rsi": 0,
        "h5m3_singlebar5_break_ma10": 0,
        "valid_flag": 0,
        "invalid_reason": "no_day_candles",
        "history_grade": target.get("history_grade"),
    }
    result.update(calc_after_break([], -1, None))
    result.update({"has_daily_context": 0, "d1_prev5_up10_high_break_5m3": 0, "d2_prev10_high20_closeup_5d_highvol": 0, "daily_reason": None})

    if not rows:
        return result
    result["valid_flag"] = 1
    result["invalid_reason"] = None

    rsi14 = calculate_rsi14(rows)
    ma10 = calculate_ma10(rows)
    base_idx, base_row = find_singlebar5(rows, threshold_pct)
    if base_idx >= 0 and base_row is not None:
        base_open = to_float(base_row.get("open_price"))
        base_high = to_float(base_row.get("high_price"))
        base_low = to_float(base_row.get("low_price"))
        base_close = to_float(base_row.get("close_price"))
        base_volume = to_int(base_row.get("volume"))
        result.update({
            "has_singlebar_close5": 1,
            "singlebar_time": base_row.get("candle_time"),
            "singlebar_open": base_open,
            "singlebar_high": base_high,
            "singlebar_low": base_low,
            "singlebar_close": base_close,
            "singlebar_volume": base_volume,
            "singlebar_amount": amount_from_row(base_row),
            "singlebar_close_return_pct": pct(base_close, base_open),
            "singlebar_high_return_pct": pct(base_high, base_open),
        })
        break_idx, break_type, break_price = find_break_after_base(rows, base_idx, base_high)
        if break_idx >= 0:
            break_row = rows[break_idx]
            break_close = to_float(break_row.get("close_price"))
            break_volume = to_int(break_row.get("volume"))
            rsi_value = rsi14[break_idx] if break_idx < len(rsi14) else None
            rsi_prev = rsi14[break_idx - 1] if break_idx > 0 and break_idx - 1 < len(rsi14) else None
            ma_value = ma10[break_idx] if break_idx < len(ma10) else None
            ma_prev = ma10[break_idx - 1] if break_idx > 0 and break_idx - 1 < len(ma10) else None
            prev_close = to_float(rows[break_idx - 1].get("close_price")) if break_idx > 0 else None
            break_close_gt_ma = 1 if break_close is not None and ma_value is not None and break_close > ma_value else 0
            break_cross_ma = 1 if break_close_gt_ma == 1 and prev_close is not None and ma_prev is not None and prev_close <= ma_prev else 0
            rsi_gt_60 = 1 if rsi_value is not None and rsi_value > 60.0 else 0
            rsi_rising = 1 if rsi_value is not None and rsi_prev is not None and rsi_value > rsi_prev else 0
            vol_gt_base = 1 if break_volume > base_volume else 0
            result.update({
                "break_time": break_row.get("candle_time"),
                "break_type": break_type,
                "break_price": break_price,
                "break_open": to_float(break_row.get("open_price")),
                "break_high": to_float(break_row.get("high_price")),
                "break_low": to_float(break_row.get("low_price")),
                "break_close": break_close,
                "break_volume": break_volume,
                "break_amount": amount_from_row(break_row),
                "bars_to_break": break_idx - base_idx,
                "break_volume_gt_base": vol_gt_base,
                "break_rsi14": rsi_value,
                "break_rsi14_prev": rsi_prev,
                "break_rsi_gt_60": rsi_gt_60,
                "break_rsi_rising": rsi_rising,
                "break_ma10": ma_value,
                "break_ma10_prev": ma_prev,
                "break_close_gt_ma10": break_close_gt_ma,
                "break_close_cross_ma10": break_cross_ma,
                "h5m1_singlebar5_break_volume": 1 if vol_gt_base == 1 else 0,
                "h5m2_singlebar5_break_rsi": 1 if (rsi_gt_60 == 1 or rsi_rising == 1) else 0,
                "h5m3_singlebar5_break_ma10": 1 if break_cross_ma == 1 else 0,
            })
            result.update(calc_after_break(rows, break_idx, break_price))

    result.update(daily_checks(conn, daily_meta, target, rows))
    return result


def upsert_result(conn: Any, row: Dict[str, Any]) -> None:
    sql = """
        INSERT INTO hypothesis_validation_v1_result (
            search_date, search_time, code, name,
            actual_rank, in_actual_top10, actual_max_after_return_pct,
            has_singlebar_close5, singlebar_time, singlebar_open, singlebar_high, singlebar_low, singlebar_close, singlebar_volume, singlebar_amount,
            singlebar_close_return_pct, singlebar_high_return_pct,
            break_time, break_type, break_price, break_open, break_high, break_low, break_close, break_volume, break_amount, bars_to_break,
            break_volume_gt_base, break_rsi14, break_rsi14_prev, break_rsi_gt_60, break_rsi_rising,
            break_ma10, break_ma10_prev, break_close_gt_ma10, break_close_cross_ma10,
            h5m1_singlebar5_break_volume, h5m2_singlebar5_break_rsi, h5m3_singlebar5_break_ma10,
            break_after_max_time, break_after_max_price, break_after_max_return_pct, break_after_close_return_pct, break_after_max_drawdown_pct,
            has_daily_context, d1_prev5_up10_high_break_5m3, d2_prev10_high20_closeup_5d_highvol, daily_reason,
            valid_flag, invalid_reason, history_grade
        ) VALUES (
            %(search_date)s, %(search_time)s, %(code)s, %(name)s,
            %(actual_rank)s, %(in_actual_top10)s, %(actual_max_after_return_pct)s,
            %(has_singlebar_close5)s, %(singlebar_time)s, %(singlebar_open)s, %(singlebar_high)s, %(singlebar_low)s, %(singlebar_close)s, %(singlebar_volume)s, %(singlebar_amount)s,
            %(singlebar_close_return_pct)s, %(singlebar_high_return_pct)s,
            %(break_time)s, %(break_type)s, %(break_price)s, %(break_open)s, %(break_high)s, %(break_low)s, %(break_close)s, %(break_volume)s, %(break_amount)s, %(bars_to_break)s,
            %(break_volume_gt_base)s, %(break_rsi14)s, %(break_rsi14_prev)s, %(break_rsi_gt_60)s, %(break_rsi_rising)s,
            %(break_ma10)s, %(break_ma10_prev)s, %(break_close_gt_ma10)s, %(break_close_cross_ma10)s,
            %(h5m1_singlebar5_break_volume)s, %(h5m2_singlebar5_break_rsi)s, %(h5m3_singlebar5_break_ma10)s,
            %(break_after_max_time)s, %(break_after_max_price)s, %(break_after_max_return_pct)s, %(break_after_close_return_pct)s, %(break_after_max_drawdown_pct)s,
            %(has_daily_context)s, %(d1_prev5_up10_high_break_5m3)s, %(d2_prev10_high20_closeup_5d_highvol)s, %(daily_reason)s,
            %(valid_flag)s, %(invalid_reason)s, %(history_grade)s
        )
        ON DUPLICATE KEY UPDATE
            name=VALUES(name), actual_rank=VALUES(actual_rank), in_actual_top10=VALUES(in_actual_top10), actual_max_after_return_pct=VALUES(actual_max_after_return_pct),
            has_singlebar_close5=VALUES(has_singlebar_close5), singlebar_time=VALUES(singlebar_time), singlebar_open=VALUES(singlebar_open), singlebar_high=VALUES(singlebar_high),
            singlebar_low=VALUES(singlebar_low), singlebar_close=VALUES(singlebar_close), singlebar_volume=VALUES(singlebar_volume), singlebar_amount=VALUES(singlebar_amount),
            singlebar_close_return_pct=VALUES(singlebar_close_return_pct), singlebar_high_return_pct=VALUES(singlebar_high_return_pct),
            break_time=VALUES(break_time), break_type=VALUES(break_type), break_price=VALUES(break_price), break_open=VALUES(break_open), break_high=VALUES(break_high),
            break_low=VALUES(break_low), break_close=VALUES(break_close), break_volume=VALUES(break_volume), break_amount=VALUES(break_amount), bars_to_break=VALUES(bars_to_break),
            break_volume_gt_base=VALUES(break_volume_gt_base), break_rsi14=VALUES(break_rsi14), break_rsi14_prev=VALUES(break_rsi14_prev),
            break_rsi_gt_60=VALUES(break_rsi_gt_60), break_rsi_rising=VALUES(break_rsi_rising), break_ma10=VALUES(break_ma10), break_ma10_prev=VALUES(break_ma10_prev),
            break_close_gt_ma10=VALUES(break_close_gt_ma10), break_close_cross_ma10=VALUES(break_close_cross_ma10),
            h5m1_singlebar5_break_volume=VALUES(h5m1_singlebar5_break_volume), h5m2_singlebar5_break_rsi=VALUES(h5m2_singlebar5_break_rsi), h5m3_singlebar5_break_ma10=VALUES(h5m3_singlebar5_break_ma10),
            break_after_max_time=VALUES(break_after_max_time), break_after_max_price=VALUES(break_after_max_price), break_after_max_return_pct=VALUES(break_after_max_return_pct),
            break_after_close_return_pct=VALUES(break_after_close_return_pct), break_after_max_drawdown_pct=VALUES(break_after_max_drawdown_pct),
            has_daily_context=VALUES(has_daily_context), d1_prev5_up10_high_break_5m3=VALUES(d1_prev5_up10_high_break_5m3),
            d2_prev10_high20_closeup_5d_highvol=VALUES(d2_prev10_high20_closeup_5d_highvol), daily_reason=VALUES(daily_reason),
            valid_flag=VALUES(valid_flag), invalid_reason=VALUES(invalid_reason), history_grade=VALUES(history_grade), updated_at=CURRENT_TIMESTAMP
    """
    with conn.cursor() as cur:
        cur.execute(sql, row)


def avg(values: List[Optional[float]]) -> Optional[float]:
    filtered = [v for v in values if v is not None]
    if not filtered:
        return None
    return sum(filtered) / float(len(filtered))


def win_rate(values: List[Optional[float]], threshold: float) -> Optional[float]:
    filtered = [v for v in values if v is not None]
    if not filtered:
        return None
    count = 0
    for value in filtered:
        if value >= threshold:
            count += 1
    return count / float(len(filtered))


def refresh_summary(conn: Any) -> None:
    definitions = [
        ("H0_has_singlebar_close5", "has_singlebar_close5=1"),
        ("H5M1_singlebar5_break_volume", "h5m1_singlebar5_break_volume=1"),
        ("H5M2_singlebar5_break_rsi", "h5m2_singlebar5_break_rsi=1"),
        ("H5M3_singlebar5_break_ma10", "h5m3_singlebar5_break_ma10=1"),
        ("D1_prev5_up10_high_break_5m3", "d1_prev5_up10_high_break_5m3=1"),
        ("D2_prev10_high20_closeup_5d_highvol", "d2_prev10_high20_closeup_5d_highvol=1"),
    ]
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE hypothesis_validation_v1_summary")
        for name, where_sql in definitions:
            cur.execute(
                """
                SELECT in_actual_top10, actual_max_after_return_pct,
                       break_after_max_return_pct, break_after_close_return_pct, break_after_max_drawdown_pct
                FROM hypothesis_validation_v1_result
                WHERE valid_flag=1 AND """ + where_sql
            )
            rows = list(cur.fetchall())
            returns = [to_float(r.get("break_after_max_return_pct")) for r in rows]
            sample_count = len(rows)
            top10_count = sum(1 for r in rows if to_int(r.get("in_actual_top10")) == 1)
            summary = {
                "hypothesis_name": name,
                "sample_count": sample_count,
                "actual_top10_count": top10_count,
                "hit_rate_to_actual_top10": top10_count / float(sample_count) if sample_count > 0 else None,
                "avg_actual_max_after_return_pct": avg([to_float(r.get("actual_max_after_return_pct")) for r in rows]),
                "avg_break_after_max_return_pct": avg(returns),
                "avg_break_after_close_return_pct": avg([to_float(r.get("break_after_close_return_pct")) for r in rows]),
                "avg_break_after_max_drawdown_pct": avg([to_float(r.get("break_after_max_drawdown_pct")) for r in rows]),
                "win_rate_after_3pct": win_rate(returns, 3.0),
                "win_rate_after_5pct": win_rate(returns, 5.0),
                "win_rate_after_10pct": win_rate(returns, 10.0),
                "win_rate_after_20pct": win_rate(returns, 20.0),
            }
            cur.execute(
                """
                INSERT INTO hypothesis_validation_v1_summary (
                    hypothesis_name, sample_count, actual_top10_count, hit_rate_to_actual_top10,
                    avg_actual_max_after_return_pct, avg_break_after_max_return_pct,
                    avg_break_after_close_return_pct, avg_break_after_max_drawdown_pct,
                    win_rate_after_3pct, win_rate_after_5pct, win_rate_after_10pct, win_rate_after_20pct
                ) VALUES (
                    %(hypothesis_name)s, %(sample_count)s, %(actual_top10_count)s, %(hit_rate_to_actual_top10)s,
                    %(avg_actual_max_after_return_pct)s, %(avg_break_after_max_return_pct)s,
                    %(avg_break_after_close_return_pct)s, %(avg_break_after_max_drawdown_pct)s,
                    %(win_rate_after_3pct)s, %(win_rate_after_5pct)s, %(win_rate_after_10pct)s, %(win_rate_after_20pct)s
                )
                """,
                summary,
            )


def print_summary(conn: Any) -> None:
    queries = [
        ("hypothesis summary", """
            SELECT hypothesis_name, sample_count, actual_top10_count, hit_rate_to_actual_top10,
                   avg_actual_max_after_return_pct, avg_break_after_max_return_pct,
                   avg_break_after_close_return_pct, avg_break_after_max_drawdown_pct,
                   win_rate_after_3pct, win_rate_after_5pct, win_rate_after_10pct, win_rate_after_20pct
            FROM hypothesis_validation_v1_summary
            ORDER BY sample_count DESC
        """),
        ("top H5M1 samples", """
            SELECT search_date, search_time, code, name, actual_rank, actual_max_after_return_pct,
                   singlebar_time, singlebar_close_return_pct,
                   break_time, break_type, break_volume_gt_base,
                   break_after_max_return_pct, break_after_close_return_pct, break_after_max_drawdown_pct
            FROM hypothesis_validation_v1_result
            WHERE h5m1_singlebar5_break_volume=1
            ORDER BY actual_rank ASC, actual_max_after_return_pct DESC
            LIMIT 30
        """),
        ("actual top10 missed by H5M1", """
            SELECT search_date, search_time, code, name, actual_rank, actual_max_after_return_pct,
                   has_singlebar_close5, break_time, break_volume_gt_base, h5m1_singlebar5_break_volume
            FROM hypothesis_validation_v1_result
            WHERE in_actual_top10=1
              AND h5m1_singlebar5_break_volume=0
            ORDER BY search_date, actual_rank
            LIMIT 50
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
        actual_ranks = build_actual_ranks(targets)
        daily_meta = build_daily_meta(conn)
        print("=== build_hypothesis_validation_v1 ===")
        print("targets=" + str(len(targets)))
        print("threshold_pct=" + str(args.threshold_pct))
        print("daily_meta=" + str(daily_meta))

        ok_count = 0
        fail_count = 0
        for idx, target in enumerate(targets, start=1):
            try:
                row = analyze_target(conn, target, actual_ranks, daily_meta, args.threshold_pct)
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
        print("\n=== DONE build_hypothesis_validation_v1 ===")
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
