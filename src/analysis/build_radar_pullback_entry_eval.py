# -*- coding: utf-8 -*-
"""Evaluate 5m Radar -> Pullback -> Re-expansion entries.

This bundle changes the strong singlebar condition from a buy trigger into a leader radar.
It then tests whether waiting for pullback/compression and re-expansion produces better entries.

Run:
    python -m src.analysis.build_radar_pullback_entry_eval --env .env --rebuild
"""

from __future__ import annotations

import argparse
import math
import os
import statistics
import sys
from datetime import datetime, time
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
    ddl = Path("sql/create_radar_pullback_entry_eval.sql").read_text(encoding="utf-8-sig")
    with conn.cursor() as cur:
        if rebuild:
            cur.execute("DROP TABLE IF EXISTS radar_pullback_entry_summary")
            cur.execute("DROP TABLE IF EXISTS radar_pullback_entry_result")
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


def amount_from_row(row: Dict[str, Any]) -> Optional[float]:
    o = to_float(row.get("open_price"))
    h = to_float(row.get("high_price"))
    l = to_float(row.get("low_price"))
    c = to_float(row.get("close_price"))
    v = to_float(row.get("volume"))
    if o is None or h is None or l is None or c is None or v is None:
        return None
    return ((o + h + l + c) / 4.0) * v


def avg(values: List[Optional[float]]) -> Optional[float]:
    filtered = [v for v in values if v is not None]
    if not filtered:
        return None
    return sum(filtered) / float(len(filtered))


def median(values: List[Optional[float]]) -> Optional[float]:
    filtered = [v for v in values if v is not None]
    if not filtered:
        return None
    return float(statistics.median(filtered))


def rate(values: List[Optional[float]], threshold: float, above: bool) -> Optional[float]:
    filtered = [v for v in values if v is not None]
    if not filtered:
        return None
    count = 0
    for value in filtered:
        if above:
            if value >= threshold:
                count += 1
        else:
            if value <= threshold:
                count += 1
    return count / float(len(filtered))


def load_targets(conn: Any, limit: int) -> List[Dict[str, Any]]:
    sql = """
        SELECT search_date, search_time, code, name,
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
        value = to_float(row.get("actual_max_after_return_pct"))
        if value is None:
            continue
        d = row.get("search_date")
        code = str(row.get("code"))
        grouped.setdefault(d, []).append((code, value))
    ranks: Dict[Tuple[Any, str], int] = {}
    for d, items in grouped.items():
        items.sort(key=lambda item: (-item[1], item[0]))
        for idx, item in enumerate(items, start=1):
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
    for idx in range(1, len(closes)):
        if closes[idx] is None or closes[idx - 1] is None:
            gains.append(0.0)
            losses.append(0.0)
        else:
            change = float(closes[idx]) - float(closes[idx - 1])
            gains.append(max(change, 0.0))
            losses.append(max(-change, 0.0))
    period = 14
    avg_gain = sum(gains[0:period]) / float(period)
    avg_loss = sum(losses[0:period]) / float(period)
    result[period] = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + (avg_gain / avg_loss)))
    for idx in range(period + 1, len(rows)):
        avg_gain = ((avg_gain * (period - 1)) + gains[idx - 1]) / float(period)
        avg_loss = ((avg_loss * (period - 1)) + losses[idx - 1]) / float(period)
        result[idx] = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + (avg_gain / avg_loss)))
    return result


def find_radar_idx(rows: List[Dict[str, Any]], threshold_pct: float) -> int:
    for idx, row in enumerate(rows):
        ret = pct(to_float(row.get("close_price")), to_float(row.get("open_price")))
        if ret is not None and ret >= threshold_pct:
            return idx
    return -1


def after_entry_metrics(rows: List[Dict[str, Any]], entry_idx: int, entry_price: Optional[float]) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "entry_after_max_time": None,
        "entry_after_max_price": None,
        "max_return_after_entry_pct": None,
        "close_return_from_entry_pct": None,
        "max_drawdown_after_entry_pct": None,
    }
    if entry_idx < 0 or entry_price is None:
        return result
    max_price: Optional[float] = None
    max_time: Optional[Any] = None
    min_price: Optional[float] = None
    last_close: Optional[float] = None
    for idx in range(entry_idx, len(rows)):
        high_value = to_float(rows[idx].get("high_price"))
        low_value = to_float(rows[idx].get("low_price"))
        close_value = to_float(rows[idx].get("close_price"))
        if high_value is not None and (max_price is None or high_value > max_price):
            max_price = high_value
            max_time = rows[idx].get("candle_time")
        if low_value is not None and (min_price is None or low_value < min_price):
            min_price = low_value
        last_close = close_value
    result["entry_after_max_time"] = max_time
    result["entry_after_max_price"] = max_price
    result["max_return_after_entry_pct"] = pct(max_price, entry_price)
    result["close_return_from_entry_pct"] = pct(last_close, entry_price)
    result["max_drawdown_after_entry_pct"] = pct(min_price, entry_price)
    return result


def analyze_one(
    rows: List[Dict[str, Any]],
    rsi14: List[Optional[float]],
    radar_threshold_pct: float,
    pullback_depth_pct: float,
    max_pullback_bars: int,
    volume_shrink_ratio: float,
) -> Optional[Dict[str, Any]]:
    radar_idx = find_radar_idx(rows, radar_threshold_pct)
    if radar_idx < 0:
        return None
    radar = rows[radar_idx]
    radar_high = to_float(radar.get("high_price"))
    radar_low = to_float(radar.get("low_price"))
    radar_close = to_float(radar.get("close_price"))
    radar_open = to_float(radar.get("open_price"))
    radar_volume = to_float(radar.get("volume"))
    if radar_high is None or radar_low is None or radar_close is None or radar_open is None or radar_volume is None or radar_volume <= 0:
        return None

    pullback_idx = -1
    pullback_low: Optional[float] = None
    pullback_volume_sum = 0.0
    pullback_volume_count = 0
    reaction_high = radar_high
    reaction_high_idx = radar_idx

    end_idx = min(len(rows) - 1, radar_idx + max_pullback_bars)
    for idx in range(radar_idx + 1, end_idx + 1):
        row = rows[idx]
        high_value = to_float(row.get("high_price"))
        low_value = to_float(row.get("low_price"))
        volume_value = to_float(row.get("volume"))
        if volume_value is not None:
            pullback_volume_sum += volume_value
            pullback_volume_count += 1
        if high_value is not None and high_value > reaction_high:
            reaction_high = high_value
            reaction_high_idx = idx
        depth = pct(low_value, radar_high)
        if depth is not None and depth <= -abs(pullback_depth_pct):
            pullback_idx = idx
            pullback_low = low_value
            break

    if pullback_idx < 0 or pullback_low is None:
        return None

    if pullback_volume_count <= 0:
        return None
    pullback_avg_volume = pullback_volume_sum / float(pullback_volume_count)
    pullback_volume_ratio_to_radar = pullback_avg_volume / radar_volume
    if pullback_volume_ratio_to_radar > volume_shrink_ratio:
        return None

    # Reaction high is the highest high from radar to pullback. Entry requires close above it later.
    reaction_high = max([to_float(rows[i].get("high_price")) or -999999999.0 for i in range(radar_idx, pullback_idx + 1)])
    reaction_high_idx = radar_idx
    for i in range(radar_idx, pullback_idx + 1):
        if to_float(rows[i].get("high_price")) == reaction_high:
            reaction_high_idx = i
            break

    entry_idx = -1
    for idx in range(pullback_idx + 1, len(rows)):
        close_value = to_float(rows[idx].get("close_price"))
        rsi_value = rsi14[idx] if idx < len(rsi14) else None
        if close_value is not None and close_value > reaction_high and rsi_value is not None and rsi_value > 50.0:
            entry_idx = idx
            break
    if entry_idx < 0:
        return None

    entry = rows[entry_idx]
    entry_price = to_float(entry.get("close_price"))
    metrics = after_entry_metrics(rows, entry_idx, entry_price)
    return {
        "radar_idx": radar_idx,
        "pullback_idx": pullback_idx,
        "reaction_high_idx": reaction_high_idx,
        "entry_idx": entry_idx,
        "radar_time": radar.get("candle_time"),
        "radar_open": radar_open,
        "radar_high": radar_high,
        "radar_low": radar_low,
        "radar_close": radar_close,
        "radar_volume": int(radar_volume),
        "radar_amount": amount_from_row(radar),
        "radar_close_return_pct": pct(radar_close, radar_open),
        "pullback_low_time": rows[pullback_idx].get("candle_time"),
        "pullback_low_price": pullback_low,
        "pullback_depth_from_radar_high_pct": pct(pullback_low, radar_high),
        "pullback_bars": pullback_idx - radar_idx,
        "pullback_avg_volume": pullback_avg_volume,
        "pullback_volume_ratio_to_radar": pullback_volume_ratio_to_radar,
        "reaction_high_time": rows[reaction_high_idx].get("candle_time"),
        "reaction_high_price": reaction_high,
        "entry_time": entry.get("candle_time"),
        "entry_price": entry_price,
        "entry_volume": to_int(entry.get("volume")),
        "entry_amount": amount_from_row(entry),
        "entry_rsi14": rsi14[entry_idx] if entry_idx < len(rsi14) else None,
        **metrics,
    }


def make_result_row(
    target: Dict[str, Any],
    ranks: Dict[Tuple[Any, str], int],
    rows: List[Dict[str, Any]],
    analyzed: Dict[str, Any],
    radar_threshold_pct: float,
    pullback_depth_pct: float,
    max_pullback_bars: int,
    volume_shrink_ratio: float,
) -> Dict[str, Any]:
    search_date = target.get("search_date")
    code = str(target.get("code"))
    day_open = to_float(rows[0].get("open_price"))
    day_low = min([to_float(r.get("low_price")) or 999999999.0 for r in rows])
    day_high = max([to_float(r.get("high_price")) or -999999999.0 for r in rows])
    day_close = to_float(rows[-1].get("close_price"))
    return {
        "radar_threshold_pct": radar_threshold_pct,
        "pullback_depth_pct": pullback_depth_pct,
        "max_pullback_bars": max_pullback_bars,
        "volume_shrink_ratio": volume_shrink_ratio,
        "search_date": search_date,
        "search_time": target.get("search_time"),
        "code": code,
        "name": target.get("name"),
        "actual_rank": ranks.get((search_date, code)),
        "actual_max_after_return_pct": to_float(target.get("actual_max_after_return_pct")),
        "day_open": day_open,
        "day_low": day_low,
        "day_high": day_high,
        "day_close": day_close,
        "radar_time": analyzed["radar_time"],
        "radar_open": analyzed["radar_open"],
        "radar_high": analyzed["radar_high"],
        "radar_low": analyzed["radar_low"],
        "radar_close": analyzed["radar_close"],
        "radar_volume": analyzed["radar_volume"],
        "radar_amount": analyzed["radar_amount"],
        "radar_close_return_pct": analyzed["radar_close_return_pct"],
        "radar_from_day_open_pct": pct(analyzed["radar_close"], day_open),
        "radar_from_day_low_pct": pct(analyzed["radar_close"], day_low),
        "pullback_low_time": analyzed["pullback_low_time"],
        "pullback_low_price": analyzed["pullback_low_price"],
        "pullback_depth_from_radar_high_pct": analyzed["pullback_depth_from_radar_high_pct"],
        "pullback_bars": analyzed["pullback_bars"],
        "pullback_avg_volume": analyzed["pullback_avg_volume"],
        "pullback_volume_ratio_to_radar": analyzed["pullback_volume_ratio_to_radar"],
        "reaction_high_time": analyzed["reaction_high_time"],
        "reaction_high_price": analyzed["reaction_high_price"],
        "entry_time": analyzed["entry_time"],
        "entry_price": analyzed["entry_price"],
        "entry_from_day_open_pct": pct(analyzed["entry_price"], day_open),
        "entry_from_day_low_pct": pct(analyzed["entry_price"], day_low),
        "entry_volume": analyzed["entry_volume"],
        "entry_amount": analyzed["entry_amount"],
        "entry_rsi14": analyzed["entry_rsi14"],
        "entry_after_max_time": analyzed["entry_after_max_time"],
        "entry_after_max_price": analyzed["entry_after_max_price"],
        "max_return_after_entry_pct": analyzed["max_return_after_entry_pct"],
        "close_return_from_entry_pct": analyzed["close_return_from_entry_pct"],
        "max_drawdown_after_entry_pct": analyzed["max_drawdown_after_entry_pct"],
        "valid_flag": 1,
        "invalid_reason": None,
    }


def upsert_result(conn: Any, row: Dict[str, Any]) -> None:
    sql = """
        INSERT INTO radar_pullback_entry_result (
            radar_threshold_pct, pullback_depth_pct, max_pullback_bars, volume_shrink_ratio,
            search_date, search_time, code, name,
            actual_rank, actual_max_after_return_pct,
            day_open, day_low, day_high, day_close,
            radar_time, radar_open, radar_high, radar_low, radar_close, radar_volume, radar_amount,
            radar_close_return_pct, radar_from_day_open_pct, radar_from_day_low_pct,
            pullback_low_time, pullback_low_price, pullback_depth_from_radar_high_pct, pullback_bars,
            pullback_avg_volume, pullback_volume_ratio_to_radar,
            reaction_high_time, reaction_high_price,
            entry_time, entry_price, entry_from_day_open_pct, entry_from_day_low_pct,
            entry_volume, entry_amount, entry_rsi14,
            entry_after_max_time, entry_after_max_price, max_return_after_entry_pct,
            close_return_from_entry_pct, max_drawdown_after_entry_pct,
            valid_flag, invalid_reason
        ) VALUES (
            %(radar_threshold_pct)s, %(pullback_depth_pct)s, %(max_pullback_bars)s, %(volume_shrink_ratio)s,
            %(search_date)s, %(search_time)s, %(code)s, %(name)s,
            %(actual_rank)s, %(actual_max_after_return_pct)s,
            %(day_open)s, %(day_low)s, %(day_high)s, %(day_close)s,
            %(radar_time)s, %(radar_open)s, %(radar_high)s, %(radar_low)s, %(radar_close)s, %(radar_volume)s, %(radar_amount)s,
            %(radar_close_return_pct)s, %(radar_from_day_open_pct)s, %(radar_from_day_low_pct)s,
            %(pullback_low_time)s, %(pullback_low_price)s, %(pullback_depth_from_radar_high_pct)s, %(pullback_bars)s,
            %(pullback_avg_volume)s, %(pullback_volume_ratio_to_radar)s,
            %(reaction_high_time)s, %(reaction_high_price)s,
            %(entry_time)s, %(entry_price)s, %(entry_from_day_open_pct)s, %(entry_from_day_low_pct)s,
            %(entry_volume)s, %(entry_amount)s, %(entry_rsi14)s,
            %(entry_after_max_time)s, %(entry_after_max_price)s, %(max_return_after_entry_pct)s,
            %(close_return_from_entry_pct)s, %(max_drawdown_after_entry_pct)s,
            %(valid_flag)s, %(invalid_reason)s
        ) ON DUPLICATE KEY UPDATE
            name=VALUES(name), actual_rank=VALUES(actual_rank), actual_max_after_return_pct=VALUES(actual_max_after_return_pct),
            day_open=VALUES(day_open), day_low=VALUES(day_low), day_high=VALUES(day_high), day_close=VALUES(day_close),
            radar_time=VALUES(radar_time), radar_open=VALUES(radar_open), radar_high=VALUES(radar_high), radar_low=VALUES(radar_low),
            radar_close=VALUES(radar_close), radar_volume=VALUES(radar_volume), radar_amount=VALUES(radar_amount),
            radar_close_return_pct=VALUES(radar_close_return_pct), radar_from_day_open_pct=VALUES(radar_from_day_open_pct), radar_from_day_low_pct=VALUES(radar_from_day_low_pct),
            pullback_low_time=VALUES(pullback_low_time), pullback_low_price=VALUES(pullback_low_price), pullback_depth_from_radar_high_pct=VALUES(pullback_depth_from_radar_high_pct),
            pullback_bars=VALUES(pullback_bars), pullback_avg_volume=VALUES(pullback_avg_volume), pullback_volume_ratio_to_radar=VALUES(pullback_volume_ratio_to_radar),
            reaction_high_time=VALUES(reaction_high_time), reaction_high_price=VALUES(reaction_high_price),
            entry_time=VALUES(entry_time), entry_price=VALUES(entry_price), entry_from_day_open_pct=VALUES(entry_from_day_open_pct), entry_from_day_low_pct=VALUES(entry_from_day_low_pct),
            entry_volume=VALUES(entry_volume), entry_amount=VALUES(entry_amount), entry_rsi14=VALUES(entry_rsi14),
            entry_after_max_time=VALUES(entry_after_max_time), entry_after_max_price=VALUES(entry_after_max_price), max_return_after_entry_pct=VALUES(max_return_after_entry_pct),
            close_return_from_entry_pct=VALUES(close_return_from_entry_pct), max_drawdown_after_entry_pct=VALUES(max_drawdown_after_entry_pct),
            valid_flag=VALUES(valid_flag), invalid_reason=VALUES(invalid_reason), updated_at=CURRENT_TIMESTAMP
    """
    with conn.cursor() as cur:
        cur.execute(sql, row)


def refresh_summary(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE radar_pullback_entry_summary")
        cur.execute("SELECT * FROM radar_pullback_entry_result WHERE valid_flag=1")
        rows = list(cur.fetchall())
    grouped: Dict[Tuple[float, float, int, float], List[Dict[str, Any]]] = {}
    for row in rows:
        key = (float(row["radar_threshold_pct"]), float(row["pullback_depth_pct"]), int(row["max_pullback_bars"]), float(row["volume_shrink_ratio"]))
        grouped.setdefault(key, []).append(row)
    sql = """
        INSERT INTO radar_pullback_entry_summary (
            radar_threshold_pct, pullback_depth_pct, max_pullback_bars, volume_shrink_ratio,
            sample_count, active_days, avg_trade_per_day,
            actual_top1_count, actual_top3_count, actual_top5_count, actual_top10_count, actual_top10_rate,
            avg_entry_from_day_open_pct, avg_entry_from_day_low_pct,
            avg_max_return_after_entry_pct, median_max_return_after_entry_pct,
            avg_close_return_from_entry_pct, avg_max_drawdown_after_entry_pct,
            win_rate_after_3pct, win_rate_after_5pct, win_rate_after_10pct,
            loss_rate_close_minus3pct, loss_rate_close_minus5pct
        ) VALUES (
            %(radar_threshold_pct)s, %(pullback_depth_pct)s, %(max_pullback_bars)s, %(volume_shrink_ratio)s,
            %(sample_count)s, %(active_days)s, %(avg_trade_per_day)s,
            %(actual_top1_count)s, %(actual_top3_count)s, %(actual_top5_count)s, %(actual_top10_count)s, %(actual_top10_rate)s,
            %(avg_entry_from_day_open_pct)s, %(avg_entry_from_day_low_pct)s,
            %(avg_max_return_after_entry_pct)s, %(median_max_return_after_entry_pct)s,
            %(avg_close_return_from_entry_pct)s, %(avg_max_drawdown_after_entry_pct)s,
            %(win_rate_after_3pct)s, %(win_rate_after_5pct)s, %(win_rate_after_10pct)s,
            %(loss_rate_close_minus3pct)s, %(loss_rate_close_minus5pct)s
        )
    """
    total_days = 82.0
    with conn.cursor() as cur:
        for key, vals in grouped.items():
            max_returns = [to_float(v.get("max_return_after_entry_pct")) for v in vals]
            close_returns = [to_float(v.get("close_return_from_entry_pct")) for v in vals]
            top1 = sum(1 for v in vals if to_int(v.get("actual_rank")) == 1)
            top3 = sum(1 for v in vals if 1 <= to_int(v.get("actual_rank")) <= 3)
            top5 = sum(1 for v in vals if 1 <= to_int(v.get("actual_rank")) <= 5)
            top10 = sum(1 for v in vals if 1 <= to_int(v.get("actual_rank")) <= 10)
            row = {
                "radar_threshold_pct": key[0],
                "pullback_depth_pct": key[1],
                "max_pullback_bars": key[2],
                "volume_shrink_ratio": key[3],
                "sample_count": len(vals),
                "active_days": len({v.get("search_date") for v in vals}),
                "avg_trade_per_day": len(vals) / total_days,
                "actual_top1_count": top1,
                "actual_top3_count": top3,
                "actual_top5_count": top5,
                "actual_top10_count": top10,
                "actual_top10_rate": top10 / float(len(vals)) if vals else None,
                "avg_entry_from_day_open_pct": avg([to_float(v.get("entry_from_day_open_pct")) for v in vals]),
                "avg_entry_from_day_low_pct": avg([to_float(v.get("entry_from_day_low_pct")) for v in vals]),
                "avg_max_return_after_entry_pct": avg(max_returns),
                "median_max_return_after_entry_pct": median(max_returns),
                "avg_close_return_from_entry_pct": avg(close_returns),
                "avg_max_drawdown_after_entry_pct": avg([to_float(v.get("max_drawdown_after_entry_pct")) for v in vals]),
                "win_rate_after_3pct": rate(max_returns, 3.0, True),
                "win_rate_after_5pct": rate(max_returns, 5.0, True),
                "win_rate_after_10pct": rate(max_returns, 10.0, True),
                "loss_rate_close_minus3pct": rate(close_returns, -3.0, False),
                "loss_rate_close_minus5pct": rate(close_returns, -5.0, False),
            }
            cur.execute(sql, row)


def print_summary(conn: Any) -> None:
    queries = [
        ("best radar pullback avg return", """
            SELECT radar_threshold_pct, pullback_depth_pct, max_pullback_bars, volume_shrink_ratio,
                   sample_count, active_days, avg_trade_per_day,
                   actual_top10_count, actual_top10_rate,
                   avg_entry_from_day_open_pct, avg_entry_from_day_low_pct,
                   avg_max_return_after_entry_pct, median_max_return_after_entry_pct,
                   avg_close_return_from_entry_pct, avg_max_drawdown_after_entry_pct,
                   win_rate_after_3pct, win_rate_after_5pct, win_rate_after_10pct,
                   loss_rate_close_minus3pct, loss_rate_close_minus5pct
            FROM radar_pullback_entry_summary
            WHERE sample_count >= 20
            ORDER BY avg_max_return_after_entry_pct DESC, loss_rate_close_minus5pct ASC
            LIMIT 30
        """),
        ("balanced candidates 1~5 per day", """
            SELECT radar_threshold_pct, pullback_depth_pct, max_pullback_bars, volume_shrink_ratio,
                   sample_count, active_days, avg_trade_per_day,
                   actual_top10_rate,
                   avg_entry_from_day_open_pct, avg_entry_from_day_low_pct,
                   avg_max_return_after_entry_pct, avg_close_return_from_entry_pct,
                   win_rate_after_3pct, win_rate_after_5pct,
                   loss_rate_close_minus5pct
            FROM radar_pullback_entry_summary
            WHERE avg_trade_per_day BETWEEN 1.0 AND 5.0
            ORDER BY loss_rate_close_minus5pct ASC, avg_max_return_after_entry_pct DESC
            LIMIT 30
        """),
    ]
    with conn.cursor() as cur:
        for title, sql in queries:
            print("\n=== " + title + " ===")
            cur.execute(sql)
            for row in cur.fetchall():
                print(row)


def parse_float_list(text: str) -> List[float]:
    return [float(x.strip()) for x in text.split(",") if x.strip()]


def parse_int_list(text: str) -> List[int]:
    return [int(x.strip()) for x in text.split(",") if x.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--radar-thresholds", default="2.0,2.5,3.0,3.5,4.0")
    parser.add_argument("--pullback-depths", default="2.0,3.0,5.0")
    parser.add_argument("--max-pullback-bars", default="6,9,12")
    parser.add_argument("--volume-shrink-ratios", default="0.7,0.5")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    load_env(args.env)
    conn = open_conn()
    try:
        ensure_schema(conn, args.rebuild)
        targets = load_targets(conn, args.limit)
        ranks = build_actual_ranks(targets)
        radar_thresholds = parse_float_list(args.radar_thresholds)
        pullback_depths = parse_float_list(args.pullback_depths)
        max_bars_list = parse_int_list(args.max_pullback_bars)
        shrink_ratios = parse_float_list(args.volume_shrink_ratios)
        print("=== build_radar_pullback_entry_eval ===")
        print("targets=" + str(len(targets)))
        print("radar_thresholds=" + str(radar_thresholds))
        print("pullback_depths=" + str(pullback_depths))
        print("max_bars=" + str(max_bars_list))
        print("shrink_ratios=" + str(shrink_ratios))

        cache: Dict[Tuple[Any, str], Tuple[List[Dict[str, Any]], List[Optional[float]]]] = {}
        total_rows = 0
        for target in targets:
            search_date = target.get("search_date")
            code = str(target.get("code"))
            rows = load_day_candles(conn, search_date, code)
            if not rows:
                continue
            rsi14 = calculate_rsi14(rows)
            cache[(search_date, code)] = (rows, rsi14)

        for rt in radar_thresholds:
            for depth in pullback_depths:
                for bars in max_bars_list:
                    for shrink in shrink_ratios:
                        combo_count = 0
                        for target in targets:
                            key = (target.get("search_date"), str(target.get("code")))
                            if key not in cache:
                                continue
                            rows, rsi14 = cache[key]
                            analyzed = analyze_one(rows, rsi14, rt, depth, bars, shrink)
                            if analyzed is None:
                                continue
                            row = make_result_row(target, ranks, rows, analyzed, rt, depth, bars, shrink)
                            upsert_result(conn, row)
                            combo_count += 1
                            total_rows += 1
                        conn.commit()
                        print("[combo] rt=" + str(rt) + " depth=" + str(depth) + " bars=" + str(bars) + " shrink=" + str(shrink) + " count=" + str(combo_count))

        refresh_summary(conn)
        conn.commit()
        print("\n=== DONE build_radar_pullback_entry_eval ===")
        print("total_result_rows=" + str(total_rows))
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
