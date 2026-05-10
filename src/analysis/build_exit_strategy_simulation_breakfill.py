# -*- coding: utf-8 -*-
"""Break-fill / next-bar evaluation exit simulation.

Purpose:
- Strict simulation reproduced the correct candidate count but over-counted same-candle stop losses.
- Next-open simulation avoided same-candle OHLC ambiguity but entered too late.

This version uses a practical stop-entry assumption:

    first singlebar open->close return >= threshold
    first later base-high breakout
    RSI14 > 60 at that first breakout candle
    entry_price = break_price
    entry_time = break_time
    exit evaluation starts from the next 5m candle

This means we assume the breakout stop order is filled at break_price, but we do not use
pre-fill low/high inside the same 5m candle for TP/SL/trailing decisions.

Run:
    python -m src.analysis.build_exit_strategy_simulation_breakfill --env .env --rebuild
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Dict, List, Optional, Tuple

from src.analysis.build_exit_strategy_simulation import (
    calculate_rsi14,
    ensure_schema,
    find_singlebar,
    load_day_candles,
    load_env,
    load_targets,
    open_conn,
    pct,
    price_at_return,
    refresh_summary,
    strategy_defs,
    to_float,
    upsert_result,
    build_actual_ranks,
    print_summary,
)
from src.analysis.build_exit_strategy_simulation_strict import find_first_break


def detect_entry_strict_breakfill(
    conn: Any,
    target: Dict[str, Any],
    actual_ranks: Dict[Tuple[Any, str], int],
    threshold_pct: float,
    entry_filter_name: str,
) -> Optional[Dict[str, Any]]:
    if entry_filter_name != "T_BREAK_RSI_GT60_FIRSTBREAK_BREAKFILL":
        raise RuntimeError("Unsupported entry_filter_name: " + entry_filter_name)

    search_date = target.get("search_date")
    code = str(target.get("code"))
    rows = load_day_candles(conn, search_date, code)
    if not rows:
        return None

    rsi14 = calculate_rsi14(rows)
    base_idx = find_singlebar(rows, threshold_pct)
    if base_idx < 0:
        return None

    base_row = rows[base_idx]
    base_high = to_float(base_row.get("high_price"))
    break_idx, break_type, break_price = find_first_break(rows, base_idx, base_high)
    if break_idx < 0 or break_price is None:
        return None

    break_rsi = rsi14[break_idx] if break_idx < len(rsi14) else None
    if break_rsi is None or break_rsi <= 60.0:
        return None

    eval_start_idx = break_idx + 1
    if eval_start_idx >= len(rows):
        return None

    break_row = rows[break_idx]
    return {
        "rows": rows,
        "base_idx": base_idx,
        "break_idx": eval_start_idx,
        "original_break_idx": break_idx,
        "break_type": break_type,
        "search_date": search_date,
        "search_time": target.get("search_time"),
        "code": code,
        "name": target.get("name"),
        "actual_rank": actual_ranks.get((search_date, code)),
        "actual_max_after_return_pct": to_float(target.get("actual_max_after_return_pct")),
        "singlebar_time": base_row.get("candle_time"),
        "singlebar_close_return_pct": pct(to_float(base_row.get("close_price")), to_float(base_row.get("open_price"))),
        "break_time": break_row.get("candle_time"),
        "break_price": break_price,
        "break_rsi14": break_rsi,
        "entry_time": break_row.get("candle_time"),
        "entry_price": break_price,
    }


def simulate_exit_from_next_bar(entry: Dict[str, Any], strategy: Dict[str, Any]) -> Dict[str, Any]:
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
    holding_bars = max(0, len(rows) - start_idx)

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

        # Conservative priority within bars after entry: stop before target.
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
        entry_filters = [("T_BREAK_RSI_GT60_FIRSTBREAK_BREAKFILL", 6.0), ("T_BREAK_RSI_GT60_FIRSTBREAK_BREAKFILL", 5.5)]
        strategies = strategy_defs()
        print("=== build_exit_strategy_simulation_breakfill ===")
        print("targets=" + str(len(targets)))
        print("entry_filters=" + str(entry_filters))
        print("strategies=" + str(len(strategies)))

        entry_count = 0
        row_count = 0
        per_filter_count: Dict[str, int] = {}

        for entry_filter_name, threshold_pct in entry_filters:
            filter_key = entry_filter_name + "_" + str(threshold_pct)
            per_filter_count[filter_key] = 0
            for target in targets:
                entry = detect_entry_strict_breakfill(conn, target, ranks, threshold_pct, entry_filter_name)
                if entry is None:
                    continue
                entry_count += 1
                per_filter_count[filter_key] += 1

                for strategy in strategies:
                    exit_result = simulate_exit_from_next_bar(entry, strategy)
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
            print("[entry_filter] " + filter_key + " entries=" + str(per_filter_count[filter_key]) + " committed")

        refresh_summary(conn)
        conn.commit()
        print("\n=== DONE build_exit_strategy_simulation_breakfill ===")
        print("entries=" + str(entry_count) + " sim_rows=" + str(row_count))
        print("per_filter_count=" + str(per_filter_count))
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
