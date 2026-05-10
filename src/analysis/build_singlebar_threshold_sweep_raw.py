# -*- coding: utf-8 -*-
"""Raw 5-minute single-bar threshold sweep.

This fixes the first sweep implementation flaw:
- The old sweep reused hypothesis_validation_v1_result, which was already built with threshold=5.0.
- Therefore 3.0~4.5% thresholds could not discover additional lower-threshold candles.

This script recomputes every threshold directly from minute5_candles.

Run:
    python -m src.analysis.build_singlebar_threshold_sweep_raw --env .env --rebuild
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
    ddl = Path("sql/create_singlebar_threshold_sweep.sql").read_text(encoding="utf-8-sig")
    with conn.cursor() as cur:
        if rebuild:
            cur.execute("DROP TABLE IF EXISTS singlebar_threshold_sweep_summary")
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
               max_after_return_pct AS actual_max_after_return_pct,
               close_return_pct AS capture_to_close_return_pct,
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
    for d, items in grouped.items():
        items.sort(key=lambda item: (-item[1], item[0]))
        for idx, item in enumerate(items, start=1):
            ranks[(d, item[0])] = idx
    return ranks


def load_d1_flags(conn: Any) -> Dict[Tuple[Any, str], int]:
    result: Dict[Tuple[Any, str], int] = {}
    with conn.cursor() as cur:
        try:
            cur.execute(
                """
                SELECT search_date, code, d1_prev5_up10_high_break_5m3
                FROM hypothesis_validation_v1_result
                WHERE valid_flag = 1
                """
            )
            rows = cur.fetchall()
        except Exception:
            return result
    for row in rows:
        result[(row.get("search_date"), str(row.get("code")))] = to_int(row.get("d1_prev5_up10_high_break_5m3"))
    return result


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


def calculate_ma10(rows: List[Dict[str, Any]]) -> List[Optional[float]]:
    result: List[Optional[float]] = [None] * len(rows)
    window: List[float] = []
    running_sum = 0.0
    for idx, row in enumerate(rows):
        close_value = to_float(row.get("close_price"))
        use_value = close_value if close_value is not None else 0.0
        window.append(use_value)
        running_sum += use_value
        if len(window) > 10:
            running_sum -= window.pop(0)
        if len(window) == 10:
            result[idx] = running_sum / 10.0
    return result


def find_singlebar(rows: List[Dict[str, Any]], threshold_pct: float) -> int:
    for idx, row in enumerate(rows):
        ret = pct(to_float(row.get("close_price")), to_float(row.get("open_price")))
        if ret is not None and ret >= threshold_pct:
            return idx
    return -1


def find_break(rows: List[Dict[str, Any]], base_idx: int, base_high: Optional[float]) -> Tuple[int, Optional[str], Optional[float]]:
    if base_idx < 0 or base_high is None:
        return -1, None, None
    for idx in range(base_idx + 1, len(rows)):
        close_value = to_float(rows[idx].get("close_price"))
        high_value = to_float(rows[idx].get("high_price"))
        if close_value is not None and close_value > base_high:
            return idx, "close_break_base_high", close_value
        if high_value is not None and high_value > base_high:
            return idx, "high_touch_base_high", base_high
    return -1, None, None


def calc_after_break(rows: List[Dict[str, Any]], break_idx: int, break_price: Optional[float]) -> Dict[str, Optional[float]]:
    result: Dict[str, Optional[float]] = {
        "break_after_max_return_pct": None,
        "break_after_close_return_pct": None,
        "break_after_max_drawdown_pct": None,
    }
    if break_idx < 0 or break_price is None:
        return result
    max_price: Optional[float] = None
    min_price: Optional[float] = None
    last_close: Optional[float] = None
    for idx in range(break_idx, len(rows)):
        high_value = to_float(rows[idx].get("high_price"))
        low_value = to_float(rows[idx].get("low_price"))
        close_value = to_float(rows[idx].get("close_price"))
        if high_value is not None and (max_price is None or high_value > max_price):
            max_price = high_value
        if low_value is not None and (min_price is None or low_value < min_price):
            min_price = low_value
        last_close = close_value
    result["break_after_max_return_pct"] = pct(max_price, break_price)
    result["break_after_close_return_pct"] = pct(last_close, break_price)
    result["break_after_max_drawdown_pct"] = pct(min_price, break_price)
    return result


def analyze_target_for_threshold(conn: Any, target: Dict[str, Any], actual_ranks: Dict[Tuple[Any, str], int], d1_flags: Dict[Tuple[Any, str], int], threshold_pct: float) -> Dict[str, Any]:
    d = target.get("search_date")
    code = str(target.get("code"))
    rows = load_day_candles(conn, d, code)
    actual_rank = actual_ranks.get((d, code))
    result: Dict[str, Any] = {
        "search_date": d,
        "code": code,
        "actual_rank": actual_rank,
        "actual_max_after_return_pct": to_float(target.get("actual_max_after_return_pct")),
        "singlebar_close_return_pct": None,
        "break_exists": 0,
        "break_volume_ratio": None,
        "break_rsi_gt_60": 0,
        "break_rsi_rising": 0,
        "break_close_gt_ma10": 0,
        "break_close_cross_ma10": 0,
        "d1_flag": d1_flags.get((d, code), 0),
        "break_after_max_return_pct": None,
        "break_after_close_return_pct": None,
        "break_after_max_drawdown_pct": None,
    }
    if not rows:
        return result
    rsi14 = calculate_rsi14(rows)
    ma10 = calculate_ma10(rows)
    base_idx = find_singlebar(rows, threshold_pct)
    if base_idx < 0:
        return result
    base = rows[base_idx]
    base_open = to_float(base.get("open_price"))
    base_close = to_float(base.get("close_price"))
    base_high = to_float(base.get("high_price"))
    base_volume = to_float(base.get("volume"))
    result["singlebar_close_return_pct"] = pct(base_close, base_open)
    break_idx, _break_type, break_price = find_break(rows, base_idx, base_high)
    if break_idx < 0:
        return result
    result["break_exists"] = 1
    break_row = rows[break_idx]
    break_volume = to_float(break_row.get("volume"))
    if base_volume is not None and base_volume > 0 and break_volume is not None:
        result["break_volume_ratio"] = break_volume / base_volume
    rsi_value = rsi14[break_idx] if break_idx < len(rsi14) else None
    rsi_prev = rsi14[break_idx - 1] if break_idx > 0 and break_idx - 1 < len(rsi14) else None
    result["break_rsi_gt_60"] = 1 if rsi_value is not None and rsi_value > 60.0 else 0
    result["break_rsi_rising"] = 1 if rsi_value is not None and rsi_prev is not None and rsi_value > rsi_prev else 0
    break_close = to_float(break_row.get("close_price"))
    prev_close = to_float(rows[break_idx - 1].get("close_price")) if break_idx > 0 else None
    ma_value = ma10[break_idx] if break_idx < len(ma10) else None
    ma_prev = ma10[break_idx - 1] if break_idx > 0 and break_idx - 1 < len(ma10) else None
    result["break_close_gt_ma10"] = 1 if break_close is not None and ma_value is not None and break_close > ma_value else 0
    result["break_close_cross_ma10"] = 1 if result["break_close_gt_ma10"] == 1 and prev_close is not None and ma_prev is not None and prev_close <= ma_prev else 0
    result.update(calc_after_break(rows, break_idx, break_price))
    return result


def pass_filter(row: Dict[str, Any], filter_name: str) -> bool:
    if row.get("singlebar_close_return_pct") is None:
        return False
    if filter_name == "T_ONLY":
        return True
    if to_int(row.get("break_exists")) != 1:
        return False
    if filter_name == "T_BREAK":
        return True
    vr = to_float(row.get("break_volume_ratio"))
    if filter_name == "T_BREAK_VOL_03":
        return vr is not None and vr >= 0.3
    if filter_name == "T_BREAK_VOL_05":
        return vr is not None and vr >= 0.5
    if filter_name == "T_BREAK_VOL_07":
        return vr is not None and vr >= 0.7
    if filter_name == "T_BREAK_VOL_10":
        return vr is not None and vr >= 1.0
    if filter_name == "T_BREAK_RSI_ANY":
        return to_int(row.get("break_rsi_gt_60")) == 1 or to_int(row.get("break_rsi_rising")) == 1
    if filter_name == "T_BREAK_RSI_GT60":
        return to_int(row.get("break_rsi_gt_60")) == 1
    if filter_name == "T_BREAK_RSI_RISING":
        return to_int(row.get("break_rsi_rising")) == 1
    if filter_name == "T_BREAK_RSI_BOTH":
        return to_int(row.get("break_rsi_gt_60")) == 1 and to_int(row.get("break_rsi_rising")) == 1
    if filter_name == "T_BREAK_MA10_GT":
        return to_int(row.get("break_close_gt_ma10")) == 1
    if filter_name == "T_BREAK_MA10_CROSS":
        return to_int(row.get("break_close_cross_ma10")) == 1
    if filter_name == "T_BREAK_VOL05_RSI_ANY":
        return vr is not None and vr >= 0.5 and (to_int(row.get("break_rsi_gt_60")) == 1 or to_int(row.get("break_rsi_rising")) == 1)
    if filter_name == "T_BREAK_VOL05_D1":
        return vr is not None and vr >= 0.5 and to_int(row.get("d1_flag")) == 1
    if filter_name == "T_BREAK_RSI_D1":
        return (to_int(row.get("break_rsi_gt_60")) == 1 or to_int(row.get("break_rsi_rising")) == 1) and to_int(row.get("d1_flag")) == 1
    if filter_name == "T_BREAK_VOL05_RSI_D1":
        return vr is not None and vr >= 0.5 and (to_int(row.get("break_rsi_gt_60")) == 1 or to_int(row.get("break_rsi_rising")) == 1) and to_int(row.get("d1_flag")) == 1
    raise RuntimeError("Unknown filter_name: " + filter_name)


def summarize(threshold_pct: float, filter_name: str, rows: List[Dict[str, Any]], total_days: int) -> Dict[str, Any]:
    passed = [row for row in rows if pass_filter(row, filter_name)]
    sample_count = len(passed)
    active_days = len({row.get("search_date") for row in passed})
    actual_values = [to_float(row.get("actual_max_after_return_pct")) for row in passed]
    break_values = [to_float(row.get("break_after_max_return_pct")) for row in passed]
    close_values = [to_float(row.get("break_after_close_return_pct")) for row in passed]
    drawdown_values = [to_float(row.get("break_after_max_drawdown_pct")) for row in passed]
    actual_top1 = sum(1 for row in passed if to_int(row.get("actual_rank")) == 1)
    actual_top3 = sum(1 for row in passed if 1 <= to_int(row.get("actual_rank")) <= 3)
    actual_top5 = sum(1 for row in passed if 1 <= to_int(row.get("actual_rank")) <= 5)
    actual_top10 = sum(1 for row in passed if 1 <= to_int(row.get("actual_rank")) <= 10)
    return {
        "threshold_pct": threshold_pct,
        "filter_name": filter_name,
        "sample_count": sample_count,
        "active_days": active_days,
        "avg_pass_per_day": sample_count / float(total_days) if total_days > 0 else None,
        "actual_top1_count": actual_top1,
        "actual_top3_count": actual_top3,
        "actual_top5_count": actual_top5,
        "actual_top10_count": actual_top10,
        "hit_rate_to_actual_top10": actual_top10 / float(sample_count) if sample_count > 0 else None,
        "avg_actual_max_after_return_pct": avg(actual_values),
        "median_actual_max_after_return_pct": median(actual_values),
        "avg_break_after_max_return_pct": avg(break_values),
        "median_break_after_max_return_pct": median(break_values),
        "avg_break_after_close_return_pct": avg(close_values),
        "avg_break_after_max_drawdown_pct": avg(drawdown_values),
        "win_rate_after_3pct": rate(break_values, 3.0, True),
        "win_rate_after_5pct": rate(break_values, 5.0, True),
        "win_rate_after_10pct": rate(break_values, 10.0, True),
        "win_rate_after_20pct": rate(break_values, 20.0, True),
        "loss_rate_after_close_minus3pct": rate(close_values, -3.0, False),
        "loss_rate_after_close_minus5pct": rate(close_values, -5.0, False),
    }


def upsert_summary(conn: Any, row: Dict[str, Any]) -> None:
    sql = """
        INSERT INTO singlebar_threshold_sweep_summary (
            threshold_pct, filter_name,
            sample_count, active_days, avg_pass_per_day,
            actual_top1_count, actual_top3_count, actual_top5_count, actual_top10_count, hit_rate_to_actual_top10,
            avg_actual_max_after_return_pct, median_actual_max_after_return_pct,
            avg_break_after_max_return_pct, median_break_after_max_return_pct,
            avg_break_after_close_return_pct, avg_break_after_max_drawdown_pct,
            win_rate_after_3pct, win_rate_after_5pct, win_rate_after_10pct, win_rate_after_20pct,
            loss_rate_after_close_minus3pct, loss_rate_after_close_minus5pct
        ) VALUES (
            %(threshold_pct)s, %(filter_name)s,
            %(sample_count)s, %(active_days)s, %(avg_pass_per_day)s,
            %(actual_top1_count)s, %(actual_top3_count)s, %(actual_top5_count)s, %(actual_top10_count)s, %(hit_rate_to_actual_top10)s,
            %(avg_actual_max_after_return_pct)s, %(median_actual_max_after_return_pct)s,
            %(avg_break_after_max_return_pct)s, %(median_break_after_max_return_pct)s,
            %(avg_break_after_close_return_pct)s, %(avg_break_after_max_drawdown_pct)s,
            %(win_rate_after_3pct)s, %(win_rate_after_5pct)s, %(win_rate_after_10pct)s, %(win_rate_after_20pct)s,
            %(loss_rate_after_close_minus3pct)s, %(loss_rate_after_close_minus5pct)s
        )
        ON DUPLICATE KEY UPDATE
            sample_count=VALUES(sample_count), active_days=VALUES(active_days), avg_pass_per_day=VALUES(avg_pass_per_day),
            actual_top1_count=VALUES(actual_top1_count), actual_top3_count=VALUES(actual_top3_count), actual_top5_count=VALUES(actual_top5_count),
            actual_top10_count=VALUES(actual_top10_count), hit_rate_to_actual_top10=VALUES(hit_rate_to_actual_top10),
            avg_actual_max_after_return_pct=VALUES(avg_actual_max_after_return_pct), median_actual_max_after_return_pct=VALUES(median_actual_max_after_return_pct),
            avg_break_after_max_return_pct=VALUES(avg_break_after_max_return_pct), median_break_after_max_return_pct=VALUES(median_break_after_max_return_pct),
            avg_break_after_close_return_pct=VALUES(avg_break_after_close_return_pct), avg_break_after_max_drawdown_pct=VALUES(avg_break_after_max_drawdown_pct),
            win_rate_after_3pct=VALUES(win_rate_after_3pct), win_rate_after_5pct=VALUES(win_rate_after_5pct),
            win_rate_after_10pct=VALUES(win_rate_after_10pct), win_rate_after_20pct=VALUES(win_rate_after_20pct),
            loss_rate_after_close_minus3pct=VALUES(loss_rate_after_close_minus3pct), loss_rate_after_close_minus5pct=VALUES(loss_rate_after_close_minus5pct),
            updated_at=CURRENT_TIMESTAMP
    """
    with conn.cursor() as cur:
        cur.execute(sql, row)


def print_summary(conn: Any) -> None:
    queries = [
        ("high precision candidates avg 0.5~3 per day", """
            SELECT threshold_pct, filter_name, sample_count, active_days, avg_pass_per_day,
                   actual_top1_count, actual_top3_count, actual_top5_count, actual_top10_count,
                   hit_rate_to_actual_top10,
                   avg_actual_max_after_return_pct,
                   median_actual_max_after_return_pct,
                   avg_break_after_max_return_pct,
                   avg_break_after_close_return_pct,
                   win_rate_after_5pct, win_rate_after_10pct,
                   loss_rate_after_close_minus5pct
            FROM singlebar_threshold_sweep_summary
            WHERE avg_pass_per_day BETWEEN 0.5 AND 3.0
            ORDER BY hit_rate_to_actual_top10 DESC,
                     avg_actual_max_after_return_pct DESC,
                     loss_rate_after_close_minus5pct ASC
            LIMIT 40
        """),
        ("strict high win candidates", """
            SELECT threshold_pct, filter_name, sample_count, active_days, avg_pass_per_day,
                   actual_top5_count, actual_top10_count,
                   hit_rate_to_actual_top10,
                   avg_actual_max_after_return_pct,
                   win_rate_after_5pct, win_rate_after_10pct,
                   loss_rate_after_close_minus5pct
            FROM singlebar_threshold_sweep_summary
            WHERE sample_count >= 20
            ORDER BY hit_rate_to_actual_top10 DESC,
                     avg_actual_max_after_return_pct DESC,
                     win_rate_after_5pct DESC
            LIMIT 40
        """),
        ("threshold/filter matrix", """
            SELECT threshold_pct, filter_name, sample_count, avg_pass_per_day,
                   hit_rate_to_actual_top10, avg_actual_max_after_return_pct,
                   win_rate_after_5pct, loss_rate_after_close_minus5pct
            FROM singlebar_threshold_sweep_summary
            ORDER BY threshold_pct, filter_name
        """),
    ]
    with conn.cursor() as cur:
        for title, sql in queries:
            print("\n=== " + title + " ===")
            cur.execute(sql)
            for row in cur.fetchall():
                print(row)


def parse_thresholds(text: str) -> List[float]:
    values: List[float] = []
    for item in text.split(","):
        item = item.strip()
        if item:
            values.append(float(item))
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--thresholds", default="3.0,3.5,4.0,4.5,5.0,5.5,6.0")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    load_env(args.env)
    thresholds = parse_thresholds(args.thresholds)
    filters = [
        "T_ONLY",
        "T_BREAK",
        "T_BREAK_VOL_03",
        "T_BREAK_VOL_05",
        "T_BREAK_VOL_07",
        "T_BREAK_VOL_10",
        "T_BREAK_RSI_ANY",
        "T_BREAK_RSI_GT60",
        "T_BREAK_RSI_RISING",
        "T_BREAK_RSI_BOTH",
        "T_BREAK_MA10_GT",
        "T_BREAK_MA10_CROSS",
        "T_BREAK_VOL05_RSI_ANY",
        "T_BREAK_VOL05_D1",
        "T_BREAK_RSI_D1",
        "T_BREAK_VOL05_RSI_D1",
    ]

    conn = open_conn()
    try:
        ensure_schema(conn, args.rebuild)
        targets = load_targets(conn, args.limit)
        actual_ranks = build_actual_ranks(targets)
        d1_flags = load_d1_flags(conn)
        total_days = len({target.get("search_date") for target in targets})
        print("=== build_singlebar_threshold_sweep_raw ===")
        print("targets=" + str(len(targets)))
        print("days=" + str(total_days))
        print("thresholds=" + ", ".join([str(v) for v in thresholds]))

        for threshold in thresholds:
            print("[threshold] " + str(threshold))
            rows_for_threshold: List[Dict[str, Any]] = []
            for target in targets:
                rows_for_threshold.append(analyze_target_for_threshold(conn, target, actual_ranks, d1_flags, threshold))
            for filter_name in filters:
                upsert_summary(conn, summarize(threshold, filter_name, rows_for_threshold, total_days))
            conn.commit()
        print("\n=== DONE build_singlebar_threshold_sweep_raw ===")
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
