# -*- coding: utf-8 -*-
"""Simulate exit strategies for high-precision singlebar entry gates.

Entry filters:
- A+: threshold=6.0, T_BREAK_RSI_GT60
- A : threshold=5.5, T_BREAK_RSI_GT60

Entry:
- first 5m candle whose open->close return >= threshold
- later base-high breakout
- RSI14 > 60 at breakout candle
- entry_price = break_price

Run:
    python -m src.analysis.build_exit_strategy_simulation --env .env --rebuild
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
    ddl = Path("sql/create_exit_strategy_simulation.sql").read_text(encoding="utf-8-sig")
    with conn.cursor() as cur:
        if rebuild:
            cur.execute("DROP TABLE IF EXISTS exit_strategy_sim_summary")
            cur.execute("DROP TABLE IF EXISTS exit_strategy_sim_result")
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


def price_at_return(entry_price: float, return_pct: float) -> float:
    return entry_price * (1.0 + (return_pct / 100.0))


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


def find_singlebar(rows: List[Dict[str, Any]], threshold_pct: float) -> int:
    for idx, row in enumerate(rows):
        ret = pct(to_float(row.get("close_price")), to_float(row.get("open_price")))
        if ret is not None and ret >= threshold_pct:
            return idx
    return -1


def find_break_rsi_gt60(rows: List[Dict[str, Any]], rsi14: List[Optional[float]], base_idx: int, base_high: Optional[float]) -> Tuple[int, Optional[str], Optional[float]]:
    if base_idx < 0 or base_high is None:
        return -1, None, None
    for idx in range(base_idx + 1, len(rows)):
        rsi_value = rsi14[idx] if idx < len(rsi14) else None
        if rsi_value is None or rsi_value <= 60.0:
            continue
        close_value = to_float(rows[idx].get("close_price"))
        high_value = to_float(rows[idx].get("high_price"))
        if close_value is not None and close_value > base_high:
            return idx, "close_break_base_high", close_value
        if high_value is not None and high_value > base_high:
            return idx, "high_touch_base_high", base_high
    return -1, None, None


def detect_entry(conn: Any, target: Dict[str, Any], actual_ranks: Dict[Tuple[Any, str], int], threshold_pct: float, entry_filter_name: str) -> Optional[Dict[str, Any]]:
    if entry_filter_name != "T_BREAK_RSI_GT60":
        raise RuntimeError("Unsupported entry_filter_name: " + entry_filter_name)

    d = target.get("search_date")
    code = str(target.get("code"))
    rows = load_day_candles(conn, d, code)
    if not rows:
        return None
    rsi14 = calculate_rsi14(rows)
    base_idx = find_singlebar(rows, threshold_pct)
    if base_idx < 0:
        return None
    base = rows[base_idx]
    base_high = to_float(base.get("high_price"))
    break_idx, break_type, break_price = find_break_rsi_gt60(rows, rsi14, base_idx, base_high)
    if break_idx < 0 or break_price is None:
        return None
    break_row = rows[break_idx]
    return {
        "rows": rows,
        "base_idx": base_idx,
        "break_idx": break_idx,
        "search_date": d,
        "search_time": target.get("search_time"),
        "code": code,
        "name": target.get("name"),
        "actual_rank": actual_ranks.get((d, code)),
        "actual_max_after_return_pct": to_float(target.get("actual_max_after_return_pct")),
        "singlebar_time": base.get("candle_time"),
        "singlebar_close_return_pct": pct(to_float(base.get("close_price")), to_float(base.get("open_price"))),
        "break_time": break_row.get("candle_time"),
        "break_price": break_price,
        "break_rsi14": rsi14[break_idx] if break_idx < len(rsi14) else None,
        "entry_time": break_row.get("candle_time"),
        "entry_price": break_price,
    }


def strategy_defs() -> List[Dict[str, Any]]:
    return [
        {"name": "TP3_SL2", "tp": 3.0, "sl": -2.0, "trail": None, "time_bars": None},
        {"name": "TP4_SL2", "tp": 4.0, "sl": -2.0, "trail": None, "time_bars": None},
        {"name": "TP5_SL2", "tp": 5.0, "sl": -2.0, "trail": None, "time_bars": None},
        {"name": "TP5_SL25", "tp": 5.0, "sl": -2.5, "trail": None, "time_bars": None},
        {"name": "TP7_SL25", "tp": 7.0, "sl": -2.5, "trail": None, "time_bars": None},
        {"name": "TP7_SL25_TR3", "tp": 7.0, "sl": -2.5, "trail": 3.0, "time_bars": None},
        {"name": "TP10_SL3", "tp": 10.0, "sl": -3.0, "trail": None, "time_bars": None},
        {"name": "TP10_SL3_TR5", "tp": 10.0, "sl": -3.0, "trail": 5.0, "time_bars": None},
        {"name": "TP12_SL4_TR5", "tp": 12.0, "sl": -4.0, "trail": 5.0, "time_bars": None},
        {"name": "TP15_SL5_TR7", "tp": 15.0, "sl": -5.0, "trail": 7.0, "time_bars": None},
        {"name": "TRAIL3_ONLY_SL2", "tp": None, "sl": -2.0, "trail": 3.0, "time_bars": None},
        {"name": "TRAIL5_ONLY_SL3", "tp": None, "sl": -3.0, "trail": 5.0, "time_bars": None},
        {"name": "TP3_SL15_TIME6", "tp": 3.0, "sl": -1.5, "trail": None, "time_bars": 6},
        {"name": "TP5_SL2_TIME6", "tp": 5.0, "sl": -2.0, "trail": None, "time_bars": 6},
        {"name": "TIME6_CLOSE", "tp": None, "sl": None, "trail": None, "time_bars": 6},
        {"name": "DAY_CLOSE", "tp": None, "sl": None, "trail": None, "time_bars": None},
    ]


def simulate_exit(entry: Dict[str, Any], strategy: Dict[str, Any]) -> Dict[str, Any]:
    rows = entry["rows"]
    start_idx = int(entry["break_idx"])
    entry_price = float(entry["entry_price"])
    tp = strategy.get("tp")
    sl = strategy.get("sl")
    trail = strategy.get("trail")
    time_bars = strategy.get("time_bars")

    highest = entry_price
    lowest = entry_price
    max_profit = 0.0
    max_drawdown = 0.0
    exit_time = rows[-1].get("candle_time")
    exit_price = to_float(rows[-1].get("close_price")) or entry_price
    exit_reason = "close_exit"
    holding_bars = len(rows) - start_idx

    for offset, idx in enumerate(range(start_idx, len(rows)), start=1):
        row = rows[idx]
        high_value = to_float(row.get("high_price")) or entry_price
        low_value = to_float(row.get("low_price")) or entry_price
        close_value = to_float(row.get("close_price")) or entry_price

        if high_value > highest:
            highest = high_value
        if low_value < lowest:
            lowest = low_value
        max_profit = max(max_profit, pct(highest, entry_price) or 0.0)
        max_drawdown = min(max_drawdown, pct(lowest, entry_price) or 0.0)

        # Conservative intrabar priority: stop-loss before take-profit if both are possible in same bar.
        if sl is not None:
            sl_price = price_at_return(entry_price, float(sl))
            if low_value <= sl_price:
                exit_time = row.get("candle_time")
                exit_price = sl_price
                exit_reason = "sl_exit"
                holding_bars = offset
                break

        if trail is not None and highest > entry_price:
            trail_price = highest * (1.0 - (float(trail) / 100.0))
            if low_value <= trail_price:
                exit_time = row.get("candle_time")
                exit_price = trail_price
                exit_reason = "trailing_exit"
                holding_bars = offset
                break

        if tp is not None:
            tp_price = price_at_return(entry_price, float(tp))
            if high_value >= tp_price:
                exit_time = row.get("candle_time")
                exit_price = tp_price
                exit_reason = "tp_exit"
                holding_bars = offset
                break

        if time_bars is not None and offset >= int(time_bars):
            exit_time = row.get("candle_time")
            exit_price = close_value
            exit_reason = "time_exit"
            holding_bars = offset
            break

    realized = pct(exit_price, entry_price)
    return {
        "exit_time": exit_time,
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "realized_return_pct": realized,
        "max_profit_before_exit_pct": max_profit,
        "max_drawdown_before_exit_pct": max_drawdown,
        "holding_bars": holding_bars,
        "win_flag": 1 if realized is not None and realized > 0 else 0,
        "loss_flag": 1 if realized is not None and realized < 0 else 0,
    }


def upsert_result(conn: Any, row: Dict[str, Any]) -> None:
    sql = """
        INSERT INTO exit_strategy_sim_result (
            entry_filter_name, threshold_pct, exit_strategy_name,
            search_date, search_time, code, name,
            actual_rank, actual_max_after_return_pct,
            singlebar_time, singlebar_close_return_pct,
            break_time, break_price, break_rsi14,
            entry_time, entry_price,
            exit_time, exit_price, exit_reason, realized_return_pct,
            max_profit_before_exit_pct, max_drawdown_before_exit_pct, holding_bars,
            win_flag, loss_flag
        ) VALUES (
            %(entry_filter_name)s, %(threshold_pct)s, %(exit_strategy_name)s,
            %(search_date)s, %(search_time)s, %(code)s, %(name)s,
            %(actual_rank)s, %(actual_max_after_return_pct)s,
            %(singlebar_time)s, %(singlebar_close_return_pct)s,
            %(break_time)s, %(break_price)s, %(break_rsi14)s,
            %(entry_time)s, %(entry_price)s,
            %(exit_time)s, %(exit_price)s, %(exit_reason)s, %(realized_return_pct)s,
            %(max_profit_before_exit_pct)s, %(max_drawdown_before_exit_pct)s, %(holding_bars)s,
            %(win_flag)s, %(loss_flag)s
        )
        ON DUPLICATE KEY UPDATE
            name=VALUES(name), actual_rank=VALUES(actual_rank), actual_max_after_return_pct=VALUES(actual_max_after_return_pct),
            singlebar_time=VALUES(singlebar_time), singlebar_close_return_pct=VALUES(singlebar_close_return_pct),
            break_time=VALUES(break_time), break_price=VALUES(break_price), break_rsi14=VALUES(break_rsi14),
            entry_time=VALUES(entry_time), entry_price=VALUES(entry_price),
            exit_time=VALUES(exit_time), exit_price=VALUES(exit_price), exit_reason=VALUES(exit_reason), realized_return_pct=VALUES(realized_return_pct),
            max_profit_before_exit_pct=VALUES(max_profit_before_exit_pct), max_drawdown_before_exit_pct=VALUES(max_drawdown_before_exit_pct), holding_bars=VALUES(holding_bars),
            win_flag=VALUES(win_flag), loss_flag=VALUES(loss_flag), updated_at=CURRENT_TIMESTAMP
    """
    with conn.cursor() as cur:
        cur.execute(sql, row)


def refresh_summary(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE exit_strategy_sim_summary")
        cur.execute(
            """
            SELECT entry_filter_name, threshold_pct, exit_strategy_name,
                   search_date, realized_return_pct, max_profit_before_exit_pct,
                   max_drawdown_before_exit_pct, holding_bars, exit_reason
            FROM exit_strategy_sim_result
            """
        )
        rows = list(cur.fetchall())

    grouped: Dict[Tuple[str, float, str], List[Dict[str, Any]]] = {}
    for row in rows:
        key = (str(row.get("entry_filter_name")), float(row.get("threshold_pct")), str(row.get("exit_strategy_name")))
        grouped.setdefault(key, []).append(row)

    insert_sql = """
        INSERT INTO exit_strategy_sim_summary (
            entry_filter_name, threshold_pct, exit_strategy_name,
            sample_count, active_days, avg_trade_per_day,
            avg_return_pct, median_return_pct, win_rate, loss_rate, profit_factor,
            avg_win_pct, avg_loss_pct, max_loss_pct,
            avg_max_profit_before_exit_pct, avg_max_drawdown_before_exit_pct, avg_holding_bars,
            tp_exit_count, sl_exit_count, trailing_exit_count, time_exit_count, close_exit_count
        ) VALUES (
            %(entry_filter_name)s, %(threshold_pct)s, %(exit_strategy_name)s,
            %(sample_count)s, %(active_days)s, %(avg_trade_per_day)s,
            %(avg_return_pct)s, %(median_return_pct)s, %(win_rate)s, %(loss_rate)s, %(profit_factor)s,
            %(avg_win_pct)s, %(avg_loss_pct)s, %(max_loss_pct)s,
            %(avg_max_profit_before_exit_pct)s, %(avg_max_drawdown_before_exit_pct)s, %(avg_holding_bars)s,
            %(tp_exit_count)s, %(sl_exit_count)s, %(trailing_exit_count)s, %(time_exit_count)s, %(close_exit_count)s
        )
    """
    with conn.cursor() as cur:
        for key, vals in grouped.items():
            returns = [to_float(v.get("realized_return_pct")) for v in vals]
            wins = [v for v in returns if v is not None and v > 0]
            losses = [v for v in returns if v is not None and v < 0]
            gross_profit = sum(wins)
            gross_loss_abs = abs(sum(losses))
            summary = {
                "entry_filter_name": key[0],
                "threshold_pct": key[1],
                "exit_strategy_name": key[2],
                "sample_count": len(vals),
                "active_days": len({v.get("search_date") for v in vals}),
                "avg_trade_per_day": len(vals) / 82.0,
                "avg_return_pct": avg(returns),
                "median_return_pct": median(returns),
                "win_rate": len(wins) / float(len(vals)) if vals else None,
                "loss_rate": len(losses) / float(len(vals)) if vals else None,
                "profit_factor": gross_profit / gross_loss_abs if gross_loss_abs > 0 else None,
                "avg_win_pct": avg(wins),
                "avg_loss_pct": avg(losses),
                "max_loss_pct": min([v for v in returns if v is not None]) if returns else None,
                "avg_max_profit_before_exit_pct": avg([to_float(v.get("max_profit_before_exit_pct")) for v in vals]),
                "avg_max_drawdown_before_exit_pct": avg([to_float(v.get("max_drawdown_before_exit_pct")) for v in vals]),
                "avg_holding_bars": avg([to_float(v.get("holding_bars")) for v in vals]),
                "tp_exit_count": sum(1 for v in vals if v.get("exit_reason") == "tp_exit"),
                "sl_exit_count": sum(1 for v in vals if v.get("exit_reason") == "sl_exit"),
                "trailing_exit_count": sum(1 for v in vals if v.get("exit_reason") == "trailing_exit"),
                "time_exit_count": sum(1 for v in vals if v.get("exit_reason") == "time_exit"),
                "close_exit_count": sum(1 for v in vals if v.get("exit_reason") == "close_exit"),
            }
            cur.execute(insert_sql, summary)


def print_summary(conn: Any) -> None:
    queries = [
        ("best avg return", """
            SELECT entry_filter_name, threshold_pct, exit_strategy_name, sample_count, active_days, avg_trade_per_day,
                   avg_return_pct, median_return_pct, win_rate, loss_rate, profit_factor,
                   avg_win_pct, avg_loss_pct, max_loss_pct, avg_holding_bars,
                   tp_exit_count, sl_exit_count, trailing_exit_count, time_exit_count, close_exit_count
            FROM exit_strategy_sim_summary
            ORDER BY avg_return_pct DESC, profit_factor DESC
            LIMIT 30
        """),
        ("best profit factor", """
            SELECT entry_filter_name, threshold_pct, exit_strategy_name, sample_count, active_days, avg_trade_per_day,
                   avg_return_pct, median_return_pct, win_rate, loss_rate, profit_factor,
                   avg_win_pct, avg_loss_pct, max_loss_pct, avg_holding_bars,
                   tp_exit_count, sl_exit_count, trailing_exit_count, time_exit_count, close_exit_count
            FROM exit_strategy_sim_summary
            WHERE sample_count >= 30
            ORDER BY profit_factor DESC, avg_return_pct DESC
            LIMIT 30
        """),
        ("stable high win", """
            SELECT entry_filter_name, threshold_pct, exit_strategy_name, sample_count, active_days, avg_trade_per_day,
                   avg_return_pct, median_return_pct, win_rate, loss_rate, profit_factor,
                   avg_win_pct, avg_loss_pct, max_loss_pct, avg_holding_bars,
                   tp_exit_count, sl_exit_count, trailing_exit_count, time_exit_count, close_exit_count
            FROM exit_strategy_sim_summary
            WHERE sample_count >= 30
            ORDER BY win_rate DESC, avg_return_pct DESC, max_loss_pct DESC
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
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    load_env(args.env)
    conn = open_conn()
    try:
        ensure_schema(conn, args.rebuild)
        targets = load_targets(conn, args.limit)
        ranks = build_actual_ranks(targets)
        entry_filters = [("T_BREAK_RSI_GT60", 6.0), ("T_BREAK_RSI_GT60", 5.5)]
        strategies = strategy_defs()
        print("=== build_exit_strategy_simulation ===")
        print("targets=" + str(len(targets)))
        print("entry_filters=" + str(entry_filters))
        print("strategies=" + str(len(strategies)))

        entry_count = 0
        row_count = 0
        for entry_filter_name, threshold_pct in entry_filters:
            for target in targets:
                entry = detect_entry(conn, target, ranks, threshold_pct, entry_filter_name)
                if entry is None:
                    continue
                entry_count += 1
                for strategy in strategies:
                    exit_result = simulate_exit(entry, strategy)
                    row = {
                        "entry_filter_name": entry_filter_name,
                        "threshold_pct": threshold_pct,
                        "exit_strategy_name": strategy["name"],
                        "search_date": entry["search_date"],
                        "search_time": entry["search_time"],
                        "code": entry["code"],
                        "name": entry["name"],
                        "actual_rank": entry["actual_rank"],
                        "actual_max_after_return_pct": entry["actual_max_after_return_pct"],
                        "singlebar_time": entry["singlebar_time"],
                        "singlebar_close_return_pct": entry["singlebar_close_return_pct"],
                        "break_time": entry["break_time"],
                        "break_price": entry["break_price"],
                        "break_rsi14": entry["break_rsi14"],
                        "entry_time": entry["entry_time"],
                        "entry_price": entry["entry_price"],
                    }
                    row.update(exit_result)
                    upsert_result(conn, row)
                    row_count += 1
            conn.commit()
            print("[entry_filter] " + entry_filter_name + " threshold=" + str(threshold_pct) + " committed")

        refresh_summary(conn)
        conn.commit()
        print("\n=== DONE build_exit_strategy_simulation ===")
        print("entries=" + str(entry_count) + " sim_rows=" + str(row_count))
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
