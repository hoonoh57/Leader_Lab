# -*- coding: utf-8 -*-
"""Build VIX Entry + JMA Profit Taking + SuperTrend Hold Overlay v1.

Entry:
    +X% breakout threshold, currently M0-style early entry at threshold price.

Exit policies:
    P0_FIXED_TARGET_STDOWN
        Exit at +P1 target if hit before SuperTrend down. If SuperTrend down first,
        exit at ST-down candle close.

    P1_JMA_PROFIT
        After unrealized profit reaches P1, exit on first JMA down-turn.
        If SuperTrend turns down before that, exit on ST down.

    P2_JMA_SUPPRESS_ST_UP
        After profit reaches P1, when JMA turns down:
          - if SuperTrend is UP, suppress sell and keep holding.
          - if SuperTrend is DOWN, exit.
        Exit on SuperTrend down.

    P3_SECOND_WAVE_ST_HOLD
        After a suppressed JMA down while ST remains UP, seek P2 target.
        Exit at P2 if hit, otherwise exit on SuperTrend down.

Outputs:
    reports/vix_entry_jma_st_hold_overlay_detail_v1.csv
    reports/vix_entry_jma_st_hold_overlay_summary_v1.csv
    reports/vix_entry_jma_st_hold_overlay_daily_v1.csv
    reports/vix_entry_jma_st_hold_overlay_v1.html
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


DEFAULT_THRESHOLDS = "10"
DEFAULT_JMA_PERIODS = "7"
DEFAULT_JMA_PHASE = 50
DEFAULT_JMA_POWER = 2
DEFAULT_ST_PERIODS = "10,14"
DEFAULT_ST_MULTIPLIERS = "2,3"
DEFAULT_P1 = "1.5,2,2.5,3"
DEFAULT_P2 = "4,5,6"

POLICIES = [
    "P0_FIXED_TARGET_STDOWN",
    "P1_JMA_PROFIT",
    "P2_JMA_SUPPRESS_ST_UP",
    "P3_SECOND_WAVE_ST_HOLD",
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


# ------------------------------ indicators ----------------------------------


def calc_jma_states(closes: Sequence[float], period: int, phase: int, power: int) -> Dict[str, List[Any]]:
    n = len(closes)
    jma: List[Optional[float]] = [None] * n
    slope: List[Optional[float]] = [None] * n
    state: List[str] = ["NA"] * n

    if n == 0:
        return {"jma": jma, "slope": slope, "state": state}

    if phase < -100:
        phase_ratio = 0.5
    elif phase > 100:
        phase_ratio = 2.5
    else:
        phase_ratio = phase / 100.0 + 1.5

    beta = 0.45 * (period - 1) / (0.45 * (period - 1) + 2.0)
    alpha = math.pow(beta, power)

    e0: Optional[float] = None
    e1 = 0.0
    e2 = 0.0
    last_jma: Optional[float] = None
    last_state = "NA"

    for i, src in enumerate(closes):
        if e0 is None or last_jma is None:
            e0 = src
            e1 = 0.0
            e2 = 0.0
            last_jma = src

        e0 = (1.0 - alpha) * src + alpha * e0
        e1 = (src - e0) * (1.0 - beta) + beta * e1
        e2 = (e0 + phase_ratio * e1 - last_jma) * math.pow(1.0 - alpha, 2.0) + math.pow(alpha, 2.0) * e2

        if i < period:
            current = sum(closes[: i + 1]) / float(i + 1)
        else:
            current = round(e2 + last_jma, 1)

        jma[i] = current
        if i > 0 and jma[i - 1] is not None and jma[i - 1] != 0:
            slope[i] = round((current / float(jma[i - 1]) - 1.0) * 100.0, 1)
        else:
            slope[i] = 0.0

        if current > last_jma:
            state[i] = "UP"
            last_state = "UP"
        elif current < last_jma:
            state[i] = "DOWN"
            last_state = "DOWN"
        else:
            state[i] = last_state

        last_jma = current

    return {"jma": jma, "slope": slope, "state": state}


def calc_supertrend_states(candles: Sequence[Dict[str, Any]], period: int, multiplier: float) -> Dict[str, List[Any]]:
    n = len(candles)
    atr: List[Optional[float]] = [None] * n
    st_line: List[Optional[float]] = [None] * n
    state: List[str] = ["NA"] * n

    trs: List[float] = []
    prev_close: Optional[float] = None
    for row in candles:
        high = get_num(row, "high") or 0.0
        low = get_num(row, "low") or 0.0
        close = get_num(row, "close") or 0.0
        if prev_close is None:
            tr = high - low
        else:
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
        prev_close = close

    for i, tr in enumerate(trs):
        if i == 0:
            atr[i] = tr
        elif i < period:
            atr[i] = sum(trs[: i + 1]) / float(i + 1)
        else:
            prev_atr = atr[i - 1] if atr[i - 1] is not None else tr
            atr[i] = ((prev_atr * (period - 1)) + tr) / float(period)

    final_upper: List[Optional[float]] = [None] * n
    final_lower: List[Optional[float]] = [None] * n

    for i, row in enumerate(candles):
        high = get_num(row, "high") or 0.0
        low = get_num(row, "low") or 0.0
        close = get_num(row, "close") or 0.0
        prev_c = get_num(candles[i - 1], "close") if i > 0 else close
        hl2 = (high + low) / 2.0
        a = atr[i] if atr[i] is not None else 0.0
        basic_upper = hl2 + multiplier * a
        basic_lower = hl2 - multiplier * a

        if i == 0:
            final_upper[i] = basic_upper
            final_lower[i] = basic_lower
            state[i] = "DOWN"
            st_line[i] = final_upper[i]
            continue

        pu = final_upper[i - 1] if final_upper[i - 1] is not None else basic_upper
        pl = final_lower[i - 1] if final_lower[i - 1] is not None else basic_lower
        final_upper[i] = basic_upper if (basic_upper < pu or (prev_c is not None and prev_c > pu)) else pu
        final_lower[i] = basic_lower if (basic_lower > pl or (prev_c is not None and prev_c < pl)) else pl

        prev_state = state[i - 1]
        if prev_state == "UP":
            if close < (final_lower[i] if final_lower[i] is not None else close):
                state[i] = "DOWN"
            else:
                state[i] = "UP"
        else:
            if close > (final_upper[i] if final_upper[i] is not None else close):
                state[i] = "UP"
            else:
                state[i] = "DOWN"

        st_line[i] = final_lower[i] if state[i] == "UP" else final_upper[i]

    return {"atr": atr, "st_line": st_line, "state": state}


def is_jma_down_turn(jma_state: Sequence[str], idx: int) -> bool:
    if idx <= 0 or idx >= len(jma_state):
        return False
    return jma_state[idx] == "DOWN" and jma_state[idx - 1] != "DOWN"


def is_jma_up_turn(jma_state: Sequence[str], idx: int) -> bool:
    if idx <= 0 or idx >= len(jma_state):
        return False
    return jma_state[idx] == "UP" and jma_state[idx - 1] != "UP"


def is_st_down_turn(st_state: Sequence[str], idx: int) -> bool:
    if idx <= 0 or idx >= len(st_state):
        return False
    return st_state[idx] == "DOWN" and st_state[idx - 1] == "UP"


# ------------------------------ policy engine --------------------------------


def evaluate_policy(
    candles: Sequence[Dict[str, Any]],
    entry_idx: int,
    entry_price: float,
    policy: str,
    p1: float,
    p2: float,
    jma_state: Sequence[str],
    st_state: Sequence[str],
) -> Dict[str, Any]:
    max_ret: Optional[float] = None
    min_ret: Optional[float] = None
    profit_triggered = False
    jma_suppressed = False
    next_jma_up_after_suppression = False
    first_profit_time = None
    first_jma_down_after_profit_time = None
    st_state_at_first_jma_down = None
    next_jma_up_time = None

    exit_idx: Optional[int] = None
    exit_reason = "DAY_END"
    exit_price: Optional[float] = None

    for i in range(entry_idx, len(candles)):
        row = candles[i]
        high = get_num(row, "high") or 0.0
        low = get_num(row, "low") or 0.0
        close = get_num(row, "close") or 0.0
        ts = candle_dt(row)
        high_ret = pct(high, entry_price)
        low_ret = pct(low, entry_price)
        close_ret = pct(close, entry_price)
        if high_ret is not None:
            max_ret = high_ret if max_ret is None else max(max_ret, high_ret)
        if low_ret is not None:
            min_ret = low_ret if min_ret is None else min(min_ret, low_ret)

        if not profit_triggered and high_ret is not None and high_ret >= p1:
            profit_triggered = True
            first_profit_time = ts

        if policy == "P0_FIXED_TARGET_STDOWN":
            if high_ret is not None and high_ret >= p1:
                exit_idx = i
                exit_reason = "FIXED_TARGET_P1"
                exit_price = entry_price * (1.0 + p1 / 100.0)
                break
            if is_st_down_turn(st_state, i):
                exit_idx = i
                exit_reason = "ST_DOWN_BEFORE_TARGET"
                exit_price = close
                break
            continue

        if policy == "P1_JMA_PROFIT":
            if profit_triggered and is_jma_down_turn(jma_state, i):
                exit_idx = i
                exit_reason = "JMA_DOWN_AFTER_P1"
                exit_price = close
                first_jma_down_after_profit_time = ts
                st_state_at_first_jma_down = st_state[i]
                break
            if is_st_down_turn(st_state, i):
                exit_idx = i
                exit_reason = "ST_DOWN_EXIT"
                exit_price = close
                break
            continue

        if policy == "P2_JMA_SUPPRESS_ST_UP":
            if profit_triggered and is_jma_down_turn(jma_state, i):
                if first_jma_down_after_profit_time is None:
                    first_jma_down_after_profit_time = ts
                    st_state_at_first_jma_down = st_state[i]
                if st_state[i] == "UP":
                    jma_suppressed = True
                else:
                    exit_idx = i
                    exit_reason = "JMA_DOWN_ST_NOT_UP"
                    exit_price = close
                    break
            if is_st_down_turn(st_state, i):
                exit_idx = i
                exit_reason = "ST_DOWN_EXIT"
                exit_price = close
                break
            continue

        if policy == "P3_SECOND_WAVE_ST_HOLD":
            if profit_triggered and is_jma_down_turn(jma_state, i):
                if first_jma_down_after_profit_time is None:
                    first_jma_down_after_profit_time = ts
                    st_state_at_first_jma_down = st_state[i]
                if st_state[i] == "UP":
                    jma_suppressed = True
                else:
                    exit_idx = i
                    exit_reason = "JMA_DOWN_ST_NOT_UP"
                    exit_price = close
                    break
            if jma_suppressed and not next_jma_up_after_suppression and is_jma_up_turn(jma_state, i):
                next_jma_up_after_suppression = True
                next_jma_up_time = ts
            if jma_suppressed and next_jma_up_after_suppression and high_ret is not None and high_ret >= p2:
                exit_idx = i
                exit_reason = "SECOND_WAVE_TARGET_P2"
                exit_price = entry_price * (1.0 + p2 / 100.0)
                break
            if is_st_down_turn(st_state, i):
                exit_idx = i
                exit_reason = "ST_DOWN_EXIT"
                exit_price = close
                break
            continue

    if exit_idx is None:
        exit_idx = len(candles) - 1
        exit_price = get_num(candles[exit_idx], "close") or entry_price
        exit_reason = "DAY_END"

    exit_time = candle_dt(candles[exit_idx])
    pnl = pct(exit_price, entry_price) or 0.0
    hold_minutes = None
    start_time = candle_dt(candles[entry_idx])
    if start_time is not None and exit_time is not None:
        hold_minutes = (exit_time - start_time).total_seconds() / 60.0

    return {
        "exit_time": exit_time.isoformat(sep=" ") if hasattr(exit_time, "isoformat") else str(exit_time),
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "realized_pnl_pct": pnl,
        "max_favorable_excursion_pct": max_ret,
        "max_adverse_excursion_pct": min_ret,
        "holding_minutes": hold_minutes,
        "first_profit_trigger_time": first_profit_time.isoformat(sep=" ") if hasattr(first_profit_time, "isoformat") else None,
        "first_jma_down_after_profit_time": first_jma_down_after_profit_time.isoformat(sep=" ") if hasattr(first_jma_down_after_profit_time, "isoformat") else None,
        "st_state_at_first_jma_down": st_state_at_first_jma_down,
        "jma_sell_suppressed_flag": 1 if jma_suppressed else 0,
        "next_jma_up_after_suppression_time": next_jma_up_time.isoformat(sep=" ") if hasattr(next_jma_up_time, "isoformat") else None,
        "second_wave_success_flag": 1 if exit_reason == "SECOND_WAVE_TARGET_P2" else 0,
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
    jma_phase: int,
    jma_power: int,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if prev_close is None or prev_close <= 0 or len(candles) == 0:
        return rows

    closes: List[float] = []
    for row in candles:
        close = get_num(row, "close")
        closes.append(close if close is not None else 0.0)

    jma_cache: Dict[int, Dict[str, List[Any]]] = {}
    for jp in jma_periods:
        jma_cache[jp] = calc_jma_states(closes, jp, jma_phase, jma_power)

    st_cache: Dict[Tuple[int, float], Dict[str, List[Any]]] = {}
    for sp in st_periods:
        for sm in st_multipliers:
            st_cache[(sp, sm)] = calc_supertrend_states(candles, sp, sm)

    cap_dt = candidate["T_capture"]
    for threshold_pct in thresholds:
        tx_row = base.first_breakout(candles, prev_close, threshold_pct, cap_dt)
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
            jma_values = jma_cache[jp]["jma"]
            jma_slope = jma_cache[jp]["slope"]
            for sp in st_periods:
                for sm in st_multipliers:
                    st_state = st_cache[(sp, sm)]["state"]
                    st_line = st_cache[(sp, sm)]["st_line"]
                    for p1 in p1_values:
                        for p2 in p2_values:
                            if p2 <= p1:
                                continue
                            for policy in POLICIES:
                                result = evaluate_policy(candles, entry_idx, entry_price, policy, p1, p2, jma_state, st_state)
                                row: Dict[str, Any] = {
                                    "trade_date": candidate.get("trade_date"),
                                    "condition_name": candidate.get("condition_name") or "",
                                    "code": candidate.get("code"),
                                    "name": candidate.get("name") or "",
                                    "T_capture": cap_dt.isoformat(sep=" "),
                                    "breakout_threshold_pct": threshold_pct,
                                    "TX": tx.isoformat(sep=" "),
                                    "entry_time": tx.isoformat(sep=" "),
                                    "entry_price": entry_price,
                                    "exit_policy": policy,
                                    "jma_period": jp,
                                    "jma_phase": jma_phase,
                                    "jma_power": jma_power,
                                    "st_period": sp,
                                    "st_multiplier": sm,
                                    "profit_trigger_p1": p1,
                                    "profit_target_p2": p2,
                                    "jma_state_at_TX": jma_state[entry_idx],
                                    "jma_value_at_TX": jma_values[entry_idx],
                                    "jma_slope_at_TX": jma_slope[entry_idx],
                                    "st_state_at_TX": st_state[entry_idx],
                                    "st_line_at_TX": st_line[entry_idx],
                                    "source_max_return_pct": candidate.get("source_max_return_pct"),
                                }
                                row.update(pre)
                                row.update(result)
                                rows.append(row)
    return rows


# ------------------------------ summaries/output -----------------------------


def summarize(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[str, float, int, int, float, float, float], List[Dict[str, Any]]] = {}
    for row in rows:
        key = (
            str(row.get("exit_policy")),
            float(row.get("breakout_threshold_pct") or 0.0),
            int(row.get("jma_period") or 0),
            int(row.get("st_period") or 0),
            float(row.get("st_multiplier") or 0.0),
            float(row.get("profit_trigger_p1") or 0.0),
            float(row.get("profit_target_p2") or 0.0),
        )
        if key not in groups:
            groups[key] = []
        groups[key].append(row)

    output: List[Dict[str, Any]] = []
    for key in sorted(groups.keys()):
        policy, x, jp, sp, sm, p1, p2 = key
        rs = groups[key]
        wins = [r for r in rs if (base.safe_float(r.get("realized_pnl_pct")) or 0.0) > 0]
        losses = [r for r in rs if (base.safe_float(r.get("realized_pnl_pct")) or 0.0) < 0]
        gross_win = sum([(base.safe_float(r.get("realized_pnl_pct")) or 0.0) for r in wins])
        gross_loss = abs(sum([(base.safe_float(r.get("realized_pnl_pct")) or 0.0) for r in losses]))
        output.append({
            "exit_policy": policy,
            "breakout_threshold_pct": x,
            "jma_period": jp,
            "st_period": sp,
            "st_multiplier": sm,
            "profit_trigger_p1": p1,
            "profit_target_p2": p2,
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
            "jma_suppressed_count": sum([int(r.get("jma_sell_suppressed_flag") or 0) for r in rs]),
            "second_wave_success_count": sum([int(r.get("second_wave_success_flag") or 0) for r in rs]),
        })
    output.sort(key=lambda r: base.safe_float(r.get("avg_realized_pnl_pct")) or -999999.0, reverse=True)
    return output


def summarize_daily(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[str, str, float, int, int, float, float, float], List[Dict[str, Any]]] = {}
    for row in rows:
        key = (
            str(row.get("trade_date")),
            str(row.get("exit_policy")),
            float(row.get("breakout_threshold_pct") or 0.0),
            int(row.get("jma_period") or 0),
            int(row.get("st_period") or 0),
            float(row.get("st_multiplier") or 0.0),
            float(row.get("profit_trigger_p1") or 0.0),
            float(row.get("profit_target_p2") or 0.0),
        )
        if key not in groups:
            groups[key] = []
        groups[key].append(row)
    output: List[Dict[str, Any]] = []
    for key in sorted(groups.keys()):
        trade_date, policy, x, jp, sp, sm, p1, p2 = key
        rs = groups[key]
        output.append({
            "trade_date": trade_date,
            "exit_policy": policy,
            "breakout_threshold_pct": x,
            "jma_period": jp,
            "st_period": sp,
            "st_multiplier": sm,
            "profit_trigger_p1": p1,
            "profit_target_p2": p2,
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


def fmt_num(value: Any, digits: int = 2) -> str:
    v = base.safe_float(value)
    if v is None:
        return "-"
    return f"{v:.{digits}f}"


def fmt_rate(value: Any) -> str:
    v = base.safe_float(value)
    if v is None:
        return "-"
    return f"{v:.2%}"


def table_html(rows: Sequence[Dict[str, Any]], fields: Sequence[str]) -> str:
    parts: List[str] = ["<table><thead><tr>"]
    for field in fields:
        parts.append("<th>" + html.escape(field) + "</th>")
    parts.append("</tr></thead><tbody>")
    for row in rows:
        parts.append("<tr>")
        for field in fields:
            value = row.get(field)
            if field.endswith("rate"):
                text = fmt_rate(value)
            elif field.endswith("pct") or field in ("profit_factor", "avg_holding_minutes"):
                text = fmt_num(value)
            elif "amount" in field and base.safe_float(value) is not None:
                text = fmt_num((base.safe_float(value) or 0.0) / 100000000.0) + "억"
            else:
                text = "-" if value is None else str(value)
            align = "left" if field in ("exit_policy", "name", "exit_reason") else ""
            parts.append("<td class='" + align + "'>" + html.escape(text) + "</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def build_html(detail: Sequence[Dict[str, Any]], summary: Sequence[Dict[str, Any]], daily: Sequence[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary_fields = ["exit_policy", "breakout_threshold_pct", "jma_period", "st_period", "st_multiplier", "profit_trigger_p1", "profit_target_p2", "entry_count", "win_rate", "loss_rate", "avg_realized_pnl_pct", "total_realized_pnl_pct", "profit_factor", "avg_mfe_pct", "avg_mae_pct", "avg_holding_minutes", "jma_suppressed_count", "second_wave_success_count"]
    daily_fields = ["trade_date", "exit_policy", "breakout_threshold_pct", "jma_period", "st_period", "st_multiplier", "profit_trigger_p1", "profit_target_p2", "entry_count", "avg_realized_pnl_pct", "total_realized_pnl_pct"]
    detail_fields = ["trade_date", "code", "name", "exit_policy", "breakout_threshold_pct", "TX", "entry_price", "exit_time", "exit_price", "exit_reason", "realized_pnl_pct", "max_favorable_excursion_pct", "max_adverse_excursion_pct", "jma_sell_suppressed_flag", "second_wave_success_flag"]
    html_text = "\n".join([
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'><title>VIX JMA ST Hold Overlay v1</title>",
        "<style>body{font-family:Segoe UI,Malgun Gothic,Arial;background:#111827;color:#e5e7eb;margin:0;padding:18px}h1,h2{color:#fbbf24}.box{border:1px solid #334155;border-radius:10px;padding:12px;background:#0f172a;margin-bottom:12px}table{border-collapse:collapse;width:100%;font-size:12px;margin:12px 0;background:#0f172a}th,td{border:1px solid #334155;padding:5px;text-align:right}th{background:#1e293b}.left{text-align:left}</style></head><body>",
        "<h1>VIX Entry + JMA Profit Taking + SuperTrend Hold Overlay v1</h1>",
        "<div class='box'>+X% 조기진입의 장점을 유지한 상태에서 JMA 익절, ST 상승구간 매도억제, ST 하락전환 청산을 비교합니다.</div>",
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

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    mysql_conn = base.open_mysql_conn()
    try:
        schema = base.find_candidate_schema(sqlite_conn, args.candidate_table)
        candle_table = base.pick_candle_table(mysql_conn, args.candle_table)
        candidates = base.load_candidates(sqlite_conn, schema, args.start_date, args.end_date, args.condition_name, args.capture_time)

        print("=== VIX JMA ST Hold Overlay v1 ===")
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
            detail_rows.extend(evaluate_candidate(cand, candles, prev_close, thresholds, jma_periods, st_periods, st_multipliers, p1_values, p2_values, args.jma_phase, args.jma_power))
            if i % 200 == 0:
                print("processed_candidates=" + str(i))

        summary_rows = summarize(detail_rows)
        daily_rows = summarize_daily(detail_rows)
        outdir = Path(args.output_dir)
        write_csv(outdir / "vix_entry_jma_st_hold_overlay_detail_v1.csv", detail_rows)
        write_csv(outdir / "vix_entry_jma_st_hold_overlay_summary_v1.csv", summary_rows)
        write_csv(outdir / "vix_entry_jma_st_hold_overlay_daily_v1.csv", daily_rows)
        build_html(detail_rows, summary_rows, daily_rows, outdir / "vix_entry_jma_st_hold_overlay_v1.html")

        print("=== Top JMA/ST Hold Overlay Summary ===")
        for row in summary_rows[:20]:
            print(row)
        print("output_detail=" + str((outdir / "vix_entry_jma_st_hold_overlay_detail_v1.csv").resolve()))
        print("output_summary=" + str((outdir / "vix_entry_jma_st_hold_overlay_summary_v1.csv").resolve()))
        print("output_daily=" + str((outdir / "vix_entry_jma_st_hold_overlay_daily_v1.csv").resolve()))
        print("output_html=" + str((outdir / "vix_entry_jma_st_hold_overlay_v1.html").resolve()))
        return 0
    finally:
        sqlite_conn.close()
        mysql_conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
