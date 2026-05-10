# -*- coding: utf-8 -*-
"""Next-open exit simulation for strict first-break entries.

Why this version exists:
- Strict first-break simulation reproduced the correct candidate counts.
- However, it entered at break_price and evaluated stop-loss on the same 5m candle.
- For a high-touch breakout, the candle low may have happened before the breakout fill.
- That makes immediate stop-loss overcounted and produces unrealistically negative results.

This version uses a more executable assumption:

    first singlebar open->close return >= threshold
    first later base-high breakout
    RSI14 > 60 at the first breakout candle
    entry_time = next candle time
    entry_price = next candle open

Then TP/SL/trailing/time exits are evaluated from the entry candle onward.

Run:
    python -m src.analysis.build_exit_strategy_simulation_nextopen --env .env --rebuild
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
    refresh_summary,
    simulate_exit,
    strategy_defs,
    to_float,
    upsert_result,
    build_actual_ranks,
    print_summary,
)
from src.analysis.build_exit_strategy_simulation_strict import find_first_break


def detect_entry_strict_next_open(
    conn: Any,
    target: Dict[str, Any],
    actual_ranks: Dict[Tuple[Any, str], int],
    threshold_pct: float,
    entry_filter_name: str,
) -> Optional[Dict[str, Any]]:
    if entry_filter_name != "T_BREAK_RSI_GT60_FIRSTBREAK_NEXTOPEN":
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

    next_idx = break_idx + 1
    if next_idx >= len(rows):
        return None

    break_row = rows[break_idx]
    entry_row = rows[next_idx]
    entry_price = to_float(entry_row.get("open_price"))
    if entry_price is None or entry_price <= 0:
        return None

    return {
        "rows": rows,
        "base_idx": base_idx,
        "break_idx": next_idx,
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
        "entry_time": entry_row.get("candle_time"),
        "entry_price": entry_price,
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
        entry_filters = [("T_BREAK_RSI_GT60_FIRSTBREAK_NEXTOPEN", 6.0), ("T_BREAK_RSI_GT60_FIRSTBREAK_NEXTOPEN", 5.5)]
        strategies = strategy_defs()
        print("=== build_exit_strategy_simulation_nextopen ===")
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
                entry = detect_entry_strict_next_open(conn, target, ranks, threshold_pct, entry_filter_name)
                if entry is None:
                    continue
                entry_count += 1
                per_filter_count[filter_key] += 1

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
            print("[entry_filter] " + filter_key + " entries=" + str(per_filter_count[filter_key]) + " committed")

        refresh_summary(conn)
        conn.commit()
        print("\n=== DONE build_exit_strategy_simulation_nextopen ===")
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
