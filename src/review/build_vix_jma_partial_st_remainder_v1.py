# -*- coding: utf-8 -*-
"""Build VIX JMA Partial Profit + ST Remainder Benchmark v1.

Baseline:
    PP0_FULL_JMA_PROFIT
        +X% entry. After P1 profit is reached, exit 100% on first JMA down.
        If SuperTrend turns down before that, exit 100% at ST-down close.

Partial policies:
    PP1_PARTIAL_ST_REMAINDER
        At P1 + JMA down, sell Q%. Remainder exits on ST down or day end.

    PP2_PARTIAL_P2_REMAINDER
        At P1 + JMA down, sell Q%. Remainder exits at P2 target, ST down, or day end.

    PP3_PARTIAL_TRAIL_REMAINDER
        At P1 + JMA down, sell Q%. Remainder held while ST up and trailed from
        post-partial high by T%. Remainder exits on trailing stop, ST down, or day end.

Outputs:
    reports/vix_jma_partial_st_remainder_detail_v1.csv
    reports/vix_jma_partial_st_remainder_summary_v1.csv
    reports/vix_jma_partial_st_remainder_daily_v1.csv
    reports/vix_jma_partial_st_remainder_v1.html
"""

from __future__ import annotations

import argparse
import csv
import html
import math
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src.review import build_vix_entry_continuation_benchmark_v1 as base
from src.review import build_vix_entry_jma_st_hold_overlay_v1 as core


DEFAULT_THRESHOLDS = "10"
DEFAULT_JMA_PERIODS = "7"
DEFAULT_JMA_PHASE = 50
DEFAULT_JMA_POWER = 2
DEFAULT_ST_PERIODS = "14"
DEFAULT_ST_MULTIPLIERS = "3"
DEFAULT_P1 = "3"
DEFAULT_P2 = "4,5,6,8"
DEFAULT_Q = "0.3,0.5,0.7"
DEFAULT_TRAIL = "1,1.5,2,3"

POLICIES = [
    "PP0_FULL_JMA_PROFIT",
    "PP1_PARTIAL_ST_REMAINDER",
    "PP2_PARTIAL_P2_REMAINDER",
    "PP3_PARTIAL_TRAIL_REMAINDER",
]


def parse_float_list(text: str) -> List[float]:
    values: List[float] = []
    for raw in text.split(","):
        item = raw.strip()
        if item != "":
            values.append(float(item))
    return values


def parse_int_list(text: str) -> List[int]:
    return [int(float(v)) for v in parse_float_list(text)]


def safe_avg(values: Iterable[Optional[float]]) -> Optional[float]:
    arr: List[float] = []
    for v in values:
        if v is not None and not math.isnan(v) and not math.isinf(v):
            arr.append(v)
    if len(arr) == 0:
        return None
    return sum(arr) / len(arr)


def pct(price: Optional[float], base_price: Optional[float]) -> Optional[float]:
    if price is None or base_price is None or base_price <= 0:
        return None
    return (price / base_price - 1.0) * 100.0


def get_num(row: Dict[str, Any], key: str) -> Optional[float]:
    return base.safe_float(row.get(key))


def candle_dt(row: Dict[str, Any]) -> Optional[Any]:
    return base.candle_dt(row)


def tx_index(candles: Sequence[Dict[str, Any]], tx: Any) -> int:
    for i, row in enumerate(candles):
        if candle_dt(row) == tx:
            return i
    return -1


def st_down_turn(st_state: Sequence[str], idx: int) -> bool:
    if idx <= 0 or idx >= len(st_state):
        return False
    return st_state[idx] == "DOWN" and st_state[idx - 1] == "UP"


def jma_down_turn(jma_state: Sequence[str], idx: int) -> bool:
    if idx <= 0 or idx >= len(jma_state):
        return False
    return jma_state[idx] == "DOWN" and jma_state[idx - 1] != "DOWN"


def close_price(candles: Sequence[Dict[str, Any]], idx: int, fallback: float) -> float:
    if idx < 0 or idx >= len(candles):
        return fallback
    c = get_num(candles[idx], "close")
    return c if c is not None else fallback


def find_full_jma_profit_exit(
    candles: Sequence[Dict[str, Any]],
    entry_idx: int,
    entry_price: float,
    p1: float,
    jma_state: Sequence[str],
    st_state: Sequence[str],
) -> Dict[str, Any]:
    profit_triggered = False
    first_profit_idx: Optional[int] = None
    first_jma_down_idx: Optional[int] = None
    exit_idx: Optional[int] = None
    exit_reason = "DAY_END"
    exit_price = close_price(candles, len(candles) - 1, entry_price)
    max_ret: Optional[float] = None
    min_ret: Optional[float] = None

    for i in range(entry_idx, len(candles)):
        high_ret = pct(get_num(candles[i], "high"), entry_price)
        low_ret = pct(get_num(candles[i], "low"), entry_price)
        if high_ret is not None:
            max_ret = high_ret if max_ret is None else max(max_ret, high_ret)
        if low_ret is not None:
            min_ret = low_ret if min_ret is None else min(min_ret, low_ret)
        if not profit_triggered and high_ret is not None and high_ret >= p1:
            profit_triggered = True
            first_profit_idx = i
        if profit_triggered and jma_down_turn(jma_state, i):
            first_jma_down_idx = i
            exit_idx = i
            exit_reason = "FULL_JMA_DOWN_AFTER_P1"
            exit_price = close_price(candles, i, entry_price)
            break
        if st_down_turn(st_state, i):
            exit_idx = i
            exit_reason = "ST_DOWN_BEFORE_JMA_PROFIT"
            exit_price = close_price(candles, i, entry_price)
            break

    if exit_idx is None:
        exit_idx = len(candles) - 1
    exit_time = candle_dt(candles[exit_idx])
    entry_time = candle_dt(candles[entry_idx])
    holding_minutes = None
    if entry_time is not None and exit_time is not None:
        holding_minutes = (exit_time - entry_time).total_seconds() / 60.0
    return {
        "first_profit_idx": first_profit_idx,
        "first_jma_down_idx": first_jma_down_idx,
        "exit_idx": exit_idx,
        "exit_reason": exit_reason,
        "exit_price": exit_price,
        "realized_pnl_pct": pct(exit_price, entry_price) or 0.0,
        "max_favorable_excursion_pct": max_ret,
        "max_adverse_excursion_pct": min_ret,
        "holding_minutes": holding_minutes,
    }


def evaluate_partial_policy(
    candles: Sequence[Dict[str, Any]],
    entry_idx: int,
    entry_price: float,
    policy: str,
    p1: float,
    p2: float,
    q: float,
    trail_pct: float,
    jma_state: Sequence[str],
    st_state: Sequence[str],
) -> Dict[str, Any]:
    base_exit = find_full_jma_profit_exit(candles, entry_idx, entry_price, p1, jma_state, st_state)
    max_ret = base_exit.get("max_favorable_excursion_pct")
    min_ret = base_exit.get("max_adverse_excursion_pct")

    if policy == "PP0_FULL_JMA_PROFIT":
        return {
            "partial_exit_time": None,
            "partial_exit_price": None,
            "partial_exit_ratio": 1.0,
            "remainder_exit_time": candle_dt(candles[int(base_exit["exit_idx"])]).isoformat(sep=" ") if hasattr(candle_dt(candles[int(base_exit["exit_idx"])]), "isoformat") else None,
            "remainder_exit_price": base_exit["exit_price"],
            "remainder_exit_reason": base_exit["exit_reason"],
            "realized_pnl_pct": base_exit["realized_pnl_pct"],
            "max_favorable_excursion_pct": max_ret,
            "max_adverse_excursion_pct": min_ret,
            "holding_minutes": base_exit["holding_minutes"],
            "partial_exit_count": 0,
            "remainder_p2_exit_count": 0,
            "remainder_st_down_exit_count": 1 if str(base_exit["exit_reason"]).startswith("ST_DOWN") else 0,
            "remainder_trailing_exit_count": 0,
        }

    partial_idx = base_exit.get("first_jma_down_idx")
    if partial_idx is None:
        # If no JMA profit event occurred, partial policies are same as baseline final exit.
        return {
            "partial_exit_time": None,
            "partial_exit_price": None,
            "partial_exit_ratio": q,
            "remainder_exit_time": candle_dt(candles[int(base_exit["exit_idx"])]).isoformat(sep=" ") if hasattr(candle_dt(candles[int(base_exit["exit_idx"])]), "isoformat") else None,
            "remainder_exit_price": base_exit["exit_price"],
            "remainder_exit_reason": base_exit["exit_reason"],
            "realized_pnl_pct": base_exit["realized_pnl_pct"],
            "max_favorable_excursion_pct": max_ret,
            "max_adverse_excursion_pct": min_ret,
            "holding_minutes": base_exit["holding_minutes"],
            "partial_exit_count": 0,
            "remainder_p2_exit_count": 0,
            "remainder_st_down_exit_count": 1 if str(base_exit["exit_reason"]).startswith("ST_DOWN") else 0,
            "remainder_trailing_exit_count": 0,
        }

    partial_idx = int(partial_idx)
    partial_price = close_price(candles, partial_idx, entry_price)
    partial_pnl = pct(partial_price, entry_price) or 0.0
    remainder_ratio = max(0.0, 1.0 - q)
    remainder_exit_idx = len(candles) - 1
    remainder_exit_price = close_price(candles, remainder_exit_idx, entry_price)
    remainder_reason = "DAY_END"
    post_partial_high = partial_price

    for i in range(partial_idx + 1, len(candles)):
        high = get_num(candles[i], "high") or 0.0
        low = get_num(candles[i], "low") or 0.0
        close = close_price(candles, i, entry_price)
        high_ret = pct(high, entry_price)
        if high > post_partial_high:
            post_partial_high = high
        if max_ret is None and high_ret is not None:
            max_ret = high_ret
        elif high_ret is not None:
            max_ret = max(max_ret, high_ret)
        low_ret = pct(low, entry_price)
        if min_ret is None and low_ret is not None:
            min_ret = low_ret
        elif low_ret is not None:
            min_ret = min(min_ret, low_ret)

        if policy == "PP2_PARTIAL_P2_REMAINDER" and high_ret is not None and high_ret >= p2:
            remainder_exit_idx = i
            remainder_exit_price = entry_price * (1.0 + p2 / 100.0)
            remainder_reason = "REMAINDER_P2_TARGET"
            break

        if policy == "PP3_PARTIAL_TRAIL_REMAINDER":
            trail_stop_price = post_partial_high * (1.0 - trail_pct / 100.0)
            if low <= trail_stop_price:
                remainder_exit_idx = i
                remainder_exit_price = trail_stop_price
                remainder_reason = "REMAINDER_TRAILING_STOP"
                break

        if st_down_turn(st_state, i):
            remainder_exit_idx = i
            remainder_exit_price = close
            remainder_reason = "REMAINDER_ST_DOWN"
            break

    remainder_pnl = pct(remainder_exit_price, entry_price) or 0.0
    realized = q * partial_pnl + remainder_ratio * remainder_pnl
    entry_time = candle_dt(candles[entry_idx])
    remainder_time = candle_dt(candles[remainder_exit_idx])
    holding_minutes = None
    if entry_time is not None and remainder_time is not None:
        holding_minutes = (remainder_time - entry_time).total_seconds() / 60.0

    return {
        "partial_exit_time": candle_dt(candles[partial_idx]).isoformat(sep=" ") if hasattr(candle_dt(candles[partial_idx]), "isoformat") else None,
        "partial_exit_price": partial_price,
        "partial_exit_ratio": q,
        "remainder_exit_time": remainder_time.isoformat(sep=" ") if hasattr(remainder_time, "isoformat") else None,
        "remainder_exit_price": remainder_exit_price,
        "remainder_exit_reason": remainder_reason,
        "realized_pnl_pct": realized,
        "max_favorable_excursion_pct": max_ret,
        "max_adverse_excursion_pct": min_ret,
        "holding_minutes": holding_minutes,
        "partial_exit_count": 1,
        "remainder_p2_exit_count": 1 if remainder_reason == "REMAINDER_P2_TARGET" else 0,
        "remainder_st_down_exit_count": 1 if remainder_reason == "REMAINDER_ST_DOWN" else 0,
        "remainder_trailing_exit_count": 1 if remainder_reason == "REMAINDER_TRAILING_STOP" else 0,
    }


def evaluate_candidate(
    candidate: Dict[str, Any],
    candles: Sequence[Dict[str, Any]],
    prev_close: Optional[float],
    thresholds: Sequence[float],
    jma_periods: Sequence[int],
    st_periods: Sequence[int],
    st_multipliers: Sequence[float],
    p1_values: Sequence[float],
    p2_values: Sequence[float],
    q_values: Sequence[float],
    trail_values: Sequence[float],
    jma_phase: int,
    jma_power: int,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if prev_close is None or prev_close <= 0 or len(candles) == 0:
        return rows

    closes: List[float] = []
    for row in candles:
        c = get_num(row, "close")
        closes.append(c if c is not None else 0.0)

    jma_cache: Dict[int, Dict[str, List[Any]]] = {}
    for jp in jma_periods:
        jma_cache[jp] = core.calc_jma_states(closes, jp, jma_phase, jma_power)

    st_cache: Dict[Tuple[int, float], Dict[str, List[Any]]] = {}
    for sp in st_periods:
        for sm in st_multipliers:
            st_cache[(sp, sm)] = core.calc_supertrend_states(candles, sp, sm)

    cap_dt = candidate["T_capture"]
    for x in thresholds:
        tx_row = base.first_breakout(candles, prev_close, x, cap_dt)
        if tx_row is None:
            continue
        tx = tx_row["TX"]
        entry_idx = tx_index(candles, tx)
        if entry_idx < 0:
            continue
        entry_price = float(tx_row["entry_price"])
        pre = base.pre_window_stats(candles, cap_dt, tx, prev_close)
        for jp in jma_periods:
            jma_state = jma_cache[jp]["state"]
            for sp in st_periods:
                for sm in st_multipliers:
                    st_state = st_cache[(sp, sm)]["state"]
                    for p1 in p1_values:
                        for p2 in p2_values:
                            if p2 <= p1:
                                continue
                            for q in q_values:
                                for trail in trail_values:
                                    for policy in POLICIES:
                                        if policy == "PP0_FULL_JMA_PROFIT" and (q != q_values[0] or trail != trail_values[0]):
                                            continue
                                        result = evaluate_partial_policy(candles, entry_idx, entry_price, policy, p1, p2, q, trail, jma_state, st_state)
                                        row: Dict[str, Any] = {
                                            "trade_date": candidate.get("trade_date"),
                                            "condition_name": candidate.get("condition_name") or "",
                                            "code": candidate.get("code"),
                                            "name": candidate.get("name") or "",
                                            "T_capture": cap_dt.isoformat(sep=" "),
                                            "breakout_threshold_pct": x,
                                            "TX": tx.isoformat(sep=" "),
                                            "entry_time": tx.isoformat(sep=" "),
                                            "entry_price": entry_price,
                                            "policy": policy,
                                            "jma_period": jp,
                                            "jma_phase": jma_phase,
                                            "jma_power": jma_power,
                                            "st_period": sp,
                                            "st_multiplier": sm,
                                            "profit_trigger_p1": p1,
                                            "profit_target_p2": p2,
                                            "partial_ratio_q": q,
                                            "trail_pct": trail,
                                            "source_max_return_pct": candidate.get("source_max_return_pct"),
                                        }
                                        row.update(pre)
                                        row.update(result)
                                        rows.append(row)
    return rows


def summarize(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[str, float, int, int, float, float, float, float, float], List[Dict[str, Any]]] = {}
    for row in rows:
        key = (
            str(row.get("policy")),
            float(row.get("breakout_threshold_pct") or 0.0),
            int(row.get("jma_period") or 0),
            int(row.get("st_period") or 0),
            float(row.get("st_multiplier") or 0.0),
            float(row.get("profit_trigger_p1") or 0.0),
            float(row.get("profit_target_p2") or 0.0),
            float(row.get("partial_ratio_q") or 0.0),
            float(row.get("trail_pct") or 0.0),
        )
        if key not in groups:
            groups[key] = []
        groups[key].append(row)

    output: List[Dict[str, Any]] = []
    for key in sorted(groups.keys()):
        policy, x, jp, sp, sm, p1, p2, q, trail = key
        rs = groups[key]
        wins = [r for r in rs if (base.safe_float(r.get("realized_pnl_pct")) or 0.0) > 0]
        losses = [r for r in rs if (base.safe_float(r.get("realized_pnl_pct")) or 0.0) < 0]
        gross_win = sum([(base.safe_float(r.get("realized_pnl_pct")) or 0.0) for r in wins])
        gross_loss = abs(sum([(base.safe_float(r.get("realized_pnl_pct")) or 0.0) for r in losses]))
        output.append({
            "policy": policy,
            "breakout_threshold_pct": x,
            "jma_period": jp,
            "st_period": sp,
            "st_multiplier": sm,
            "profit_trigger_p1": p1,
            "profit_target_p2": p2,
            "partial_ratio_q": q,
            "trail_pct": trail,
            "entry_count": len(rs),
            "win_count": len(wins),
            "win_rate": len(wins) / len(rs) if len(rs) > 0 else 0.0,
            "loss_count": len(losses),
            "loss_rate": len(losses) / len(rs) if len(rs) > 0 else 0.0,
            "avg_realized_pnl_pct": safe_avg([base.safe_float(r.get("realized_pnl_pct")) for r in rs]),
            "total_realized_pnl_pct": sum([(base.safe_float(r.get("realized_pnl_pct")) or 0.0) for r in rs]),
            "profit_factor": gross_win / gross_loss if gross_loss > 0 else None,
            "avg_mfe_pct": safe_avg([base.safe_float(r.get("max_favorable_excursion_pct")) for r in rs]),
            "avg_mae_pct": safe_avg([base.safe_float(r.get("max_adverse_excursion_pct")) for r in rs]),
            "avg_holding_minutes": safe_avg([base.safe_float(r.get("holding_minutes")) for r in rs]),
            "partial_exit_count": sum([int(r.get("partial_exit_count") or 0) for r in rs]),
            "remainder_p2_exit_count": sum([int(r.get("remainder_p2_exit_count") or 0) for r in rs]),
            "remainder_st_down_exit_count": sum([int(r.get("remainder_st_down_exit_count") or 0) for r in rs]),
            "remainder_trailing_exit_count": sum([int(r.get("remainder_trailing_exit_count") or 0) for r in rs]),
        })
    output.sort(key=lambda r: base.safe_float(r.get("avg_realized_pnl_pct")) or -999999.0, reverse=True)
    return output


def summarize_daily(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[str, str, float, float, float, float], List[Dict[str, Any]]] = {}
    for row in rows:
        key = (
            str(row.get("trade_date")),
            str(row.get("policy")),
            float(row.get("profit_trigger_p1") or 0.0),
            float(row.get("profit_target_p2") or 0.0),
            float(row.get("partial_ratio_q") or 0.0),
            float(row.get("trail_pct") or 0.0),
        )
        if key not in groups:
            groups[key] = []
        groups[key].append(row)
    output: List[Dict[str, Any]] = []
    for key in sorted(groups.keys()):
        d, policy, p1, p2, q, trail = key
        rs = groups[key]
        output.append({
            "trade_date": d,
            "policy": policy,
            "profit_trigger_p1": p1,
            "profit_target_p2": p2,
            "partial_ratio_q": q,
            "trail_pct": trail,
            "entry_count": len(rs),
            "avg_realized_pnl_pct": safe_avg([base.safe_float(r.get("realized_pnl_pct")) for r in rs]),
            "total_realized_pnl_pct": sum([(base.safe_float(r.get("realized_pnl_pct")) or 0.0) for r in rs]),
        })
    return output


def write_csv(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fields: List[str] = []
    for row in rows:
        for k in row.keys():
            if k not in fields:
                fields.append(k)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def fmt_num(v: Any, digits: int = 2) -> str:
    x = base.safe_float(v)
    if x is None:
        return "-"
    return f"{x:.{digits}f}"


def fmt_rate(v: Any) -> str:
    x = base.safe_float(v)
    if x is None:
        return "-"
    return f"{x:.2%}"


def table_html(rows: Sequence[Dict[str, Any]], fields: Sequence[str]) -> str:
    parts: List[str] = ["<table><thead><tr>"]
    for f in fields:
        parts.append("<th>" + html.escape(f) + "</th>")
    parts.append("</tr></thead><tbody>")
    for row in rows:
        parts.append("<tr>")
        for f in fields:
            value = row.get(f)
            if f.endswith("rate"):
                text = fmt_rate(value)
            elif f.endswith("pct") or f in ("profit_factor", "avg_holding_minutes"):
                text = fmt_num(value)
            else:
                text = "-" if value is None else str(value)
            align = "left" if f in ("policy", "name", "remainder_exit_reason") else ""
            parts.append("<td class='" + align + "'>" + html.escape(text) + "</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def build_html(detail: Sequence[Dict[str, Any]], summary: Sequence[Dict[str, Any]], daily: Sequence[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary_fields = ["policy", "breakout_threshold_pct", "jma_period", "st_period", "st_multiplier", "profit_trigger_p1", "profit_target_p2", "partial_ratio_q", "trail_pct", "entry_count", "win_rate", "loss_rate", "avg_realized_pnl_pct", "total_realized_pnl_pct", "profit_factor", "avg_mfe_pct", "avg_mae_pct", "avg_holding_minutes", "partial_exit_count", "remainder_p2_exit_count", "remainder_st_down_exit_count", "remainder_trailing_exit_count"]
    daily_fields = ["trade_date", "policy", "profit_trigger_p1", "profit_target_p2", "partial_ratio_q", "trail_pct", "entry_count", "avg_realized_pnl_pct", "total_realized_pnl_pct"]
    detail_fields = ["trade_date", "code", "name", "policy", "entry_price", "partial_exit_price", "partial_exit_ratio", "remainder_exit_price", "remainder_exit_reason", "realized_pnl_pct", "max_favorable_excursion_pct", "max_adverse_excursion_pct", "holding_minutes"]
    html_text = "\n".join([
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'><title>VIX JMA Partial ST Remainder v1</title>",
        "<style>body{font-family:Segoe UI,Malgun Gothic,Arial;background:#111827;color:#e5e7eb;margin:0;padding:18px}h1,h2{color:#fbbf24}.box{border:1px solid #334155;border-radius:10px;padding:12px;background:#0f172a;margin-bottom:12px}table{border-collapse:collapse;width:100%;font-size:12px;margin:12px 0;background:#0f172a}th,td{border:1px solid #334155;padding:5px;text-align:right}th{background:#1e293b}.left{text-align:left}</style></head><body>",
        "<h1>VIX JMA Partial Profit + ST Remainder v1</h1>",
        "<div class='box'>P1 JMA 100% 익절 기준전략과, Q% 부분익절 후 ST/P2/trailing으로 잔량을 보유하는 정책을 비교합니다.</div>",
        "<h2>Summary</h2>",
        table_html(summary, summary_fields),
        "<h2>Daily Summary</h2>",
        table_html(daily[:500], daily_fields),
        "<h2>Detail Sample</h2>",
        table_html(detail[:500], detail_fields),
        "</body></html>",
    ])
    path.write_text(html_text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--sqlite-db", default=None)
    parser.add_argument("--candidate-table", default=None)
    parser.add_argument("--condition-name", default=None)
    parser.add_argument("--capture-time", default=base.DEFAULT_CAPTURE_TIME)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--candle-table", default=None)
    parser.add_argument("--thresholds", default=DEFAULT_THRESHOLDS)
    parser.add_argument("--jma-periods", default=DEFAULT_JMA_PERIODS)
    parser.add_argument("--jma-phase", type=int, default=DEFAULT_JMA_PHASE)
    parser.add_argument("--jma-power", type=int, default=DEFAULT_JMA_POWER)
    parser.add_argument("--st-periods", default=DEFAULT_ST_PERIODS)
    parser.add_argument("--st-multipliers", default=DEFAULT_ST_MULTIPLIERS)
    parser.add_argument("--p1-values", default=DEFAULT_P1)
    parser.add_argument("--p2-values", default=DEFAULT_P2)
    parser.add_argument("--q-values", default=DEFAULT_Q)
    parser.add_argument("--trail-values", default=DEFAULT_TRAIL)
    parser.add_argument("--output-dir", default="reports")
    args = parser.parse_args()

    base.load_env(args.env)
    sqlite_path = args.sqlite_db or base.env_value(["SQLITE_1516_DB"])
    if not sqlite_path:
        raise RuntimeError("SQLITE_1516_DB 또는 --sqlite-db가 필요합니다.")

    thresholds = parse_float_list(args.thresholds)
    jma_periods = parse_int_list(args.jma_periods)
    st_periods = parse_int_list(args.st_periods)
    st_multipliers = parse_float_list(args.st_multipliers)
    p1_values = parse_float_list(args.p1_values)
    p2_values = parse_float_list(args.p2_values)
    q_values = parse_float_list(args.q_values)
    trail_values = parse_float_list(args.trail_values)

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    mysql_conn = base.open_mysql_conn()
    try:
        schema = base.find_candidate_schema(sqlite_conn, args.candidate_table)
        candle_table = base.pick_candle_table(mysql_conn, args.candle_table)
        candidates = base.load_candidates(sqlite_conn, schema, args.start_date, args.end_date, args.condition_name, args.capture_time)
        print("=== VIX JMA Partial ST Remainder v1 ===")
        print("candidate_table=" + schema.table)
        print("candle_table=" + candle_table)
        print("candidate_count=" + str(len(candidates)))

        candle_cache: Dict[Tuple[str, str], Tuple[List[Dict[str, Any]], Optional[float]]] = {}
        detail_rows: List[Dict[str, Any]] = []
        for i, cand in enumerate(candidates, 1):
            key = (cand["trade_date"], cand["code"])
            if key not in candle_cache:
                candles = base.load_day_candles(mysql_conn, candle_table, cand["code"], cand["trade_date"])
                prev_close = base.previous_close_from_candles(mysql_conn, candle_table, cand["code"], cand["trade_date"])
                candle_cache[key] = (candles, prev_close)
            candles, prev_close = candle_cache[key]
            detail_rows.extend(evaluate_candidate(cand, candles, prev_close, thresholds, jma_periods, st_periods, st_multipliers, p1_values, p2_values, q_values, trail_values, args.jma_phase, args.jma_power))
            if i % 200 == 0:
                print("processed_candidates=" + str(i))

        summary_rows = summarize(detail_rows)
        daily_rows = summarize_daily(detail_rows)
        outdir = Path(args.output_dir)
        write_csv(outdir / "vix_jma_partial_st_remainder_detail_v1.csv", detail_rows)
        write_csv(outdir / "vix_jma_partial_st_remainder_summary_v1.csv", summary_rows)
        write_csv(outdir / "vix_jma_partial_st_remainder_daily_v1.csv", daily_rows)
        build_html(detail_rows, summary_rows, daily_rows, outdir / "vix_jma_partial_st_remainder_v1.html")

        print("=== Top Partial ST Remainder Summary ===")
        for row in summary_rows[:20]:
            print(row)
        print("output_detail=" + str((outdir / "vix_jma_partial_st_remainder_detail_v1.csv").resolve()))
        print("output_summary=" + str((outdir / "vix_jma_partial_st_remainder_summary_v1.csv").resolve()))
        print("output_daily=" + str((outdir / "vix_jma_partial_st_remainder_daily_v1.csv").resolve()))
        print("output_html=" + str((outdir / "vix_jma_partial_st_remainder_v1.html").resolve()))
        return 0
    finally:
        sqlite_conn.close()
        mysql_conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
