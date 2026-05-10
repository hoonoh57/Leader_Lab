# -*- coding: utf-8 -*-
"""Build chart_review_case from strict/break-fill entry logic.

This creates the compact case list used by the WYSIWYG chart review dashboard.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pymysql

from src.analysis.build_exit_strategy_simulation import calculate_rsi14, find_singlebar, pct, to_float, to_int
from src.analysis.build_exit_strategy_simulation_strict import find_first_break


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
    ddl = Path("sql/create_chart_review_case.sql").read_text(encoding="utf-8-sig")
    with conn.cursor() as cur:
        if rebuild:
            cur.execute("DROP TABLE IF EXISTS chart_review_case")
        for statement in ddl.split(";"):
            sql = statement.strip()
            if sql:
                cur.execute(sql)
    conn.commit()


def load_targets(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT search_date, search_time, code, name,
                   max_after_return_pct AS actual_max_after_return_pct,
                   history_grade
            FROM analysis_5m_result
            WHERE valid_analysis_flag = 1
              AND history_grade IN ('normal_intraday', 'partial_intraday', 'weak_intraday')
            ORDER BY search_date, search_time, code
            """
        )
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


def after_entry_metrics(rows: List[Dict[str, Any]], entry_idx: int, entry_price: Optional[float]) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "day_high_after_entry": None,
        "max_return_after_entry_pct": None,
        "close_return_from_entry_pct": None,
        "max_drawdown_after_entry_pct": None,
    }
    if entry_idx < 0 or entry_price is None:
        return result
    max_price: Optional[float] = None
    min_price: Optional[float] = None
    last_close: Optional[float] = None
    for idx in range(entry_idx, len(rows)):
        high_value = to_float(rows[idx].get("high_price"))
        low_value = to_float(rows[idx].get("low_price"))
        close_value = to_float(rows[idx].get("close_price"))
        if high_value is not None and (max_price is None or high_value > max_price):
            max_price = high_value
        if low_value is not None and (min_price is None or low_value < min_price):
            min_price = low_value
        last_close = close_value
    result["day_high_after_entry"] = max_price
    result["max_return_after_entry_pct"] = pct(max_price, entry_price)
    result["close_return_from_entry_pct"] = pct(last_close, entry_price)
    result["max_drawdown_after_entry_pct"] = pct(min_price, entry_price)
    return result


def make_case(conn: Any, target: Dict[str, Any], ranks: Dict[Tuple[Any, str], int], threshold_pct: float) -> Optional[Dict[str, Any]]:
    search_date = target.get("search_date")
    code = str(target.get("code"))
    rows = load_day_candles(conn, search_date, code)
    if not rows:
        return None

    day_open = to_float(rows[0].get("open_price"))
    day_high = max([to_float(r.get("high_price")) or -999999999.0 for r in rows])
    day_low = min([to_float(r.get("low_price")) or 999999999.0 for r in rows])
    day_close = to_float(rows[-1].get("close_price"))

    rsi14 = calculate_rsi14(rows)
    base_idx = find_singlebar(rows, threshold_pct)
    if base_idx < 0:
        return None

    base = rows[base_idx]
    base_high = to_float(base.get("high_price"))
    break_idx, break_type, break_price = find_first_break(rows, base_idx, base_high)
    if break_idx < 0 or break_price is None:
        return None

    break_rsi = rsi14[break_idx] if break_idx < len(rsi14) else None
    if break_rsi is None or break_rsi <= 60.0:
        return None

    break_row = rows[break_idx]
    actual_rank = ranks.get((search_date, code))
    entry_idx = break_idx + 1
    # Review is based on break-fill entry price, but outcome metrics start from next bar to match breakfill simulation.
    metrics = after_entry_metrics(rows, entry_idx, break_price)

    singlebar_close = to_float(base.get("close_price"))
    return {
        "search_date": search_date,
        "search_time": target.get("search_time"),
        "code": code,
        "name": target.get("name"),
        "threshold_pct": threshold_pct,
        "entry_filter_name": "T_BREAK_RSI_GT60_FIRSTBREAK_BREAKFILL",
        "actual_rank": actual_rank,
        "actual_max_after_return_pct": to_float(target.get("actual_max_after_return_pct")),
        "day_open": day_open,
        "day_high": day_high,
        "day_low": day_low,
        "day_close": day_close,
        "singlebar_time": base.get("candle_time"),
        "singlebar_open": to_float(base.get("open_price")),
        "singlebar_high": base_high,
        "singlebar_low": to_float(base.get("low_price")),
        "singlebar_close": singlebar_close,
        "singlebar_volume": to_int(base.get("volume")),
        "singlebar_close_return_pct": pct(singlebar_close, to_float(base.get("open_price"))),
        "singlebar_from_day_open_pct": pct(singlebar_close, day_open),
        "break_time": break_row.get("candle_time"),
        "break_price": break_price,
        "break_rsi14": break_rsi,
        "break_from_day_open_pct": pct(break_price, day_open),
        "entry_time": break_row.get("candle_time"),
        "entry_price": break_price,
        "entry_from_day_open_pct": pct(break_price, day_open),
        "day_high_after_entry": metrics["day_high_after_entry"],
        "max_return_after_entry_pct": metrics["max_return_after_entry_pct"],
        "close_return_from_entry_pct": metrics["close_return_from_entry_pct"],
        "max_drawdown_after_entry_pct": metrics["max_drawdown_after_entry_pct"],
        "review_tag": None,
        "review_memo": None,
    }


def upsert_case(conn: Any, row: Dict[str, Any]) -> None:
    sql = """
        INSERT INTO chart_review_case (
            search_date, search_time, code, name,
            threshold_pct, entry_filter_name,
            actual_rank, actual_max_after_return_pct,
            day_open, day_high, day_low, day_close,
            singlebar_time, singlebar_open, singlebar_high, singlebar_low, singlebar_close, singlebar_volume,
            singlebar_close_return_pct, singlebar_from_day_open_pct,
            break_time, break_price, break_rsi14, break_from_day_open_pct,
            entry_time, entry_price, entry_from_day_open_pct,
            day_high_after_entry, max_return_after_entry_pct, close_return_from_entry_pct, max_drawdown_after_entry_pct,
            review_tag, review_memo
        ) VALUES (
            %(search_date)s, %(search_time)s, %(code)s, %(name)s,
            %(threshold_pct)s, %(entry_filter_name)s,
            %(actual_rank)s, %(actual_max_after_return_pct)s,
            %(day_open)s, %(day_high)s, %(day_low)s, %(day_close)s,
            %(singlebar_time)s, %(singlebar_open)s, %(singlebar_high)s, %(singlebar_low)s, %(singlebar_close)s, %(singlebar_volume)s,
            %(singlebar_close_return_pct)s, %(singlebar_from_day_open_pct)s,
            %(break_time)s, %(break_price)s, %(break_rsi14)s, %(break_from_day_open_pct)s,
            %(entry_time)s, %(entry_price)s, %(entry_from_day_open_pct)s,
            %(day_high_after_entry)s, %(max_return_after_entry_pct)s, %(close_return_from_entry_pct)s, %(max_drawdown_after_entry_pct)s,
            %(review_tag)s, %(review_memo)s
        )
        ON DUPLICATE KEY UPDATE
            name=VALUES(name), actual_rank=VALUES(actual_rank), actual_max_after_return_pct=VALUES(actual_max_after_return_pct),
            day_open=VALUES(day_open), day_high=VALUES(day_high), day_low=VALUES(day_low), day_close=VALUES(day_close),
            singlebar_time=VALUES(singlebar_time), singlebar_open=VALUES(singlebar_open), singlebar_high=VALUES(singlebar_high),
            singlebar_low=VALUES(singlebar_low), singlebar_close=VALUES(singlebar_close), singlebar_volume=VALUES(singlebar_volume),
            singlebar_close_return_pct=VALUES(singlebar_close_return_pct), singlebar_from_day_open_pct=VALUES(singlebar_from_day_open_pct),
            break_time=VALUES(break_time), break_price=VALUES(break_price), break_rsi14=VALUES(break_rsi14), break_from_day_open_pct=VALUES(break_from_day_open_pct),
            entry_time=VALUES(entry_time), entry_price=VALUES(entry_price), entry_from_day_open_pct=VALUES(entry_from_day_open_pct),
            day_high_after_entry=VALUES(day_high_after_entry), max_return_after_entry_pct=VALUES(max_return_after_entry_pct),
            close_return_from_entry_pct=VALUES(close_return_from_entry_pct), max_drawdown_after_entry_pct=VALUES(max_drawdown_after_entry_pct),
            updated_at=CURRENT_TIMESTAMP
    """
    with conn.cursor() as cur:
        cur.execute(sql, row)


def print_summary(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT threshold_pct, COUNT(*) AS case_count,
                   COUNT(DISTINCT search_date) AS active_days,
                   AVG(entry_from_day_open_pct) AS avg_entry_from_open,
                   AVG(max_return_after_entry_pct) AS avg_max_after_entry,
                   AVG(close_return_from_entry_pct) AS avg_close_from_entry,
                   AVG(max_drawdown_after_entry_pct) AS avg_drawdown_after_entry
            FROM chart_review_case
            GROUP BY threshold_pct
            ORDER BY threshold_pct DESC
            """
        )
        print("\n=== chart_review_case summary ===")
        for row in cur.fetchall():
            print(row)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--thresholds", default="6.0,5.5")
    args = parser.parse_args()

    load_env(args.env)
    thresholds = [float(x.strip()) for x in args.thresholds.split(",") if x.strip()]
    conn = open_conn()
    try:
        ensure_schema(conn, args.rebuild)
        targets = load_targets(conn)
        ranks = build_actual_ranks(targets)
        total = 0
        for threshold in thresholds:
            count = 0
            for target in targets:
                row = make_case(conn, target, ranks, threshold)
                if row is None:
                    continue
                upsert_case(conn, row)
                count += 1
                total += 1
            conn.commit()
            print("[threshold] " + str(threshold) + " cases=" + str(count))
        print("=== DONE build_chart_review_case ===")
        print("total_cases=" + str(total))
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
