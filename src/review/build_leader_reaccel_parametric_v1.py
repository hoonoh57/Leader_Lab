# -*- coding: utf-8 -*-
"""Leader Reaccel Parametric Backtest v1.

Purpose
-------
Run full-period or single-date backtests for the practical main candidate:

    Leader_Reaccel_Parametric_v1

The strategy is designed to avoid the structural live risk of raw +10% VIX chasing.
It looks for prior leader strength, RSI cooldown, then renewed reacceleration with
trend reclaim and participation.

Source universe
---------------
Default source is the existing Kiwoom 1516 SQLite condition-captured candidate universe.
This keeps the benchmark aligned with the project's actual condition-search workflow.

Entry signal
------------
On 5-minute candles after T_capture:
    1. close > SMA(trend_period)
    2. RSI(rsi_period) had cooled below cooldown_level inside lookback bars
    3. RSI crosses above reclaim_level
    4. single bar return >= bar_return_min_pct
    5. participation condition is satisfied
    6. prior leader/base context is satisfied

Execution
---------
Default entry is next bar open after the signal bar.

Exit
----
Uses current promoted exit style:
    VIX_JMA_PARTIAL_TRAIL_v1
    P1 + JMA down partial sell, remainder trailing or ST down.

Outputs
-------
reports/leader_reaccel_parametric_detail_v1.csv
reports/leader_reaccel_parametric_summary_v1.csv
reports/leader_reaccel_parametric_daily_v1.csv
reports/leader_reaccel_parametric_v1.html
"""

from __future__ import annotations

import argparse
import csv
import html
import sqlite3
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src.review import build_vix_entry_continuation_benchmark_v1 as base
from src.review import build_rsi70_ma20_amount_breakout_v1 as rsi_base


STRATEGY_NAME = "Leader_Reaccel_Parametric_v1"


def parse_float_list(text: str) -> List[float]:
    result: List[float] = []
    for raw in text.split(","):
        item = raw.strip()
        if item != "":
            result.append(float(item))
    return result


def parse_int_list(text: str) -> List[int]:
    return [int(v) for v in parse_float_list(text)]


def safe_avg(values: Iterable[Optional[float]]) -> Optional[float]:
    arr: List[float] = []
    for value in values:
        if value is not None:
            arr.append(value)
    if len(arr) == 0:
        return None
    return sum(arr) / float(len(arr))


def safe_min(values: Iterable[Optional[float]]) -> Optional[float]:
    arr: List[float] = [v for v in values if v is not None]
    return min(arr) if arr else None


def safe_max(values: Iterable[Optional[float]]) -> Optional[float]:
    arr: List[float] = [v for v in values if v is not None]
    return max(arr) if arr else None


def get_num(row: Dict[str, Any], key: str) -> Optional[float]:
    return base.safe_float(row.get(key))


def candle_dt(row: Dict[str, Any]) -> Optional[datetime]:
    return base.candle_dt(row)


def pct(price: Optional[float], base_price: Optional[float]) -> Optional[float]:
    if price is None or base_price is None or base_price <= 0:
        return None
    return (price / base_price - 1.0) * 100.0


def close_position(row: Dict[str, Any]) -> Optional[float]:
    high = get_num(row, "high")
    low = get_num(row, "low")
    close = get_num(row, "close")
    if high is None or low is None or close is None:
        return None
    rng = high - low
    if rng <= 0:
        return None
    return (close - low) / rng


def upper_tail_ratio(row: Dict[str, Any]) -> Optional[float]:
    op = get_num(row, "open")
    high = get_num(row, "high")
    low = get_num(row, "low")
    close = get_num(row, "close")
    if op is None or high is None or low is None or close is None:
        return None
    rng = high - low
    if rng <= 0:
        return None
    return (high - max(op, close)) / rng


def body_ratio(row: Dict[str, Any]) -> Optional[float]:
    op = get_num(row, "open")
    high = get_num(row, "high")
    low = get_num(row, "low")
    close = get_num(row, "close")
    if op is None or high is None or low is None or close is None:
        return None
    rng = high - low
    if rng <= 0:
        return None
    return abs(close - op) / rng


def first_day_bar(candles: Sequence[Dict[str, Any]], trade_date_text: str) -> Optional[Dict[str, Any]]:
    d = base.parse_date(trade_date_text)
    if d is None:
        return None
    for row in candles:
        ts = candle_dt(row)
        if ts is not None and ts.date() == d:
            return row
    return None


def first_bar_extension_bucket(first_open_return: Optional[float]) -> str:
    if first_open_return is None:
        return "UNKNOWN"
    if first_open_return < 10.0:
        return "LT_10"
    if first_open_return < 13.0:
        return "GTE_10_LT_13"
    if first_open_return < 15.0:
        return "GTE_13_LT_15"
    if first_open_return < 18.0:
        return "GTE_15_LT_18"
    return "GTE_18"


def rsi_cooldown_exists(rsi: Sequence[Optional[float]], idx: int, cooldown_level: float, lookback_bars: int) -> Tuple[bool, Optional[float], Optional[int]]:
    start = max(0, idx - lookback_bars)
    low_value: Optional[float] = None
    bars_since: Optional[int] = None
    found = False
    for j in range(start, idx):
        value = rsi[j]
        if value is None:
            continue
        if low_value is None or value < low_value:
            low_value = value
        if value <= cooldown_level:
            found = True
            bars_since = idx - j
    return found, low_value, bars_since


def recent_base_context(candles: Sequence[Dict[str, Any]], signal_idx: int, trade_date_text: str, args: argparse.Namespace) -> Dict[str, Any]:
    high_rise = rsi_base.last5d_high_rise_until(candles, signal_idx, trade_date_text)
    basebar_flag = 0
    basebar_high_break_flag = 0
    basebar_amount_ratio: Optional[float] = None

    signal_close = get_num(candles[signal_idx], "close") if 0 <= signal_idx < len(candles) else None
    signal_cum_amount = 0.0
    signal_day = base.parse_date(trade_date_text)
    for k in range(0, signal_idx + 1):
        ts = candle_dt(candles[k])
        if ts is not None and signal_day is not None and ts.date() == signal_day:
            signal_cum_amount += base.amount_from_candle(candles[k])

    lookback_start = max(1, signal_idx - args.basebar_lookback_bars)
    best_base_high: Optional[float] = None
    best_base_amount: Optional[float] = None
    for i in range(lookback_start, signal_idx + 1):
        prev_close = get_num(candles[i - 1], "close")
        close = get_num(candles[i], "close")
        high = get_num(candles[i], "high")
        amount = base.amount_from_candle(candles[i])
        ret = pct(close, prev_close)
        if ret is not None and ret >= args.basebar_min_return_pct and amount >= args.basebar_min_amount:
            basebar_flag = 1
            if best_base_high is None or (high is not None and high > best_base_high):
                best_base_high = high
                best_base_amount = amount

    if best_base_high is not None and signal_close is not None and signal_close >= best_base_high:
        basebar_high_break_flag = 1
    if best_base_amount is not None and best_base_amount > 0:
        basebar_amount_ratio = signal_cum_amount / best_base_amount

    return {
        "last5d_high_rise_pct": high_rise,
        "basebar_flag": basebar_flag,
        "basebar_high_break_flag": basebar_high_break_flag,
        "basebar_amount_ratio": basebar_amount_ratio,
    }


def participation_ok(row: Dict[str, Any], cum_amount: float, prev_volume_avg: Optional[float], args: argparse.Namespace) -> Tuple[bool, str, Dict[str, Any]]:
    amount = base.amount_from_candle(row)
    volume = get_num(row, "volume") or 0.0
    volume_ratio = volume / prev_volume_avg if prev_volume_avg is not None and prev_volume_avg > 0 else None

    amount_ok = amount >= args.bar_amount_min or cum_amount >= args.cum_amount_min
    volume_ok = volume_ratio is not None and volume_ratio >= args.volume_ratio_min

    # Tick intensity is a placeholder until true tick/trade-count source is joined.
    tick_ok = False

    ptype = args.participation_type.lower()
    if ptype == "amount":
        ok = amount_ok
    elif ptype == "volume":
        ok = volume_ok
    elif ptype == "amount_or_volume":
        ok = amount_ok or volume_ok
    elif ptype == "amount_and_volume":
        ok = amount_ok and volume_ok
    elif ptype == "tick_intensity_placeholder":
        ok = amount_ok
    else:
        ok = amount_ok

    return ok, ptype, {
        "bar_amount": amount,
        "cum_amount": cum_amount,
        "bar_volume": volume,
        "volume_ratio": volume_ratio,
        "participation_amount_ok": 1 if amount_ok else 0,
        "participation_volume_ok": 1 if volume_ok else 0,
        "participation_tick_ok": 1 if tick_ok else 0,
    }


def find_signal_for_params(candles: Sequence[Dict[str, Any]], candidate: Dict[str, Any], params: Dict[str, Any], args: argparse.Namespace) -> Optional[Dict[str, Any]]:
    if len(candles) == 0:
        return None

    closes: List[float] = []
    volumes: List[float] = []
    for row in candles:
        closes.append(get_num(row, "close") or 0.0)
        volumes.append(get_num(row, "volume") or 0.0)

    sma = rsi_base.calc_sma(closes, int(params["trend_period"]))
    rsi = rsi_base.calc_rsi_wilder(closes, int(params["rsi_period"]))
    d = base.parse_date(candidate["trade_date"])
    if d is None:
        return None

    first_bar = first_day_bar(candles, candidate["trade_date"])
    prev_close_for_first = base.previous_close_from_candles if False else None
    first_open_return = None
    # Use first intraday row's open against previous close from the prior row if available.
    if first_bar is not None:
        first_idx = candles.index(first_bar)
        if first_idx > 0:
            first_open_return = pct(get_num(first_bar, "open"), get_num(candles[first_idx - 1], "close"))
    extension_bucket = first_bar_extension_bucket(first_open_return)

    cum_amount = 0.0
    for i, row in enumerate(candles):
        ts = candle_dt(row)
        if ts is None or ts.date() != d:
            continue
        amount = base.amount_from_candle(row)
        cum_amount += amount
        if ts < candidate["T_capture"]:
            continue
        if i <= 0 or i + 1 >= len(candles):
            continue

        close = get_num(row, "close")
        prev_close = get_num(candles[i - 1], "close")
        if close is None or prev_close is None or prev_close <= 0:
            continue
        ma_value = sma[i]
        rsi_prev = rsi[i - 1]
        rsi_now = rsi[i]
        if ma_value is None or rsi_prev is None or rsi_now is None:
            continue

        cooldown_ok, cooldown_low, bars_since = rsi_cooldown_exists(
            rsi,
            i,
            float(params["rsi_cooldown_level"]),
            int(params["rsi_cooldown_lookback_bars"]),
        )
        reclaim = rsi_prev <= float(params["rsi_reclaim_level"]) and rsi_now > float(params["rsi_reclaim_level"])
        bar_ret = (close / prev_close - 1.0) * 100.0
        cp = close_position(row)
        utr = upper_tail_ratio(row)
        br = body_ratio(row)

        prev_vol_window = volumes[max(0, i - args.volume_ratio_lookback_bars) : i]
        prev_vol_avg = safe_avg(prev_vol_window)
        participation, participation_type, part_cols = participation_ok(row, cum_amount, prev_vol_avg, args)
        context = recent_base_context(candles, i, candidate["trade_date"], args)

        trend_ok = close > ma_value * (1.0 + float(params["trend_buffer_pct"]) / 100.0)
        candle_ok = bar_ret >= float(params["bar_return_min_pct"])
        if args.use_candle_quality:
            if cp is None or cp < args.close_position_min:
                candle_ok = False
            if utr is None or utr > args.upper_tail_max:
                candle_ok = False
            if br is None or br < args.body_ratio_min:
                candle_ok = False

        context_ok = False
        high_rise = context.get("last5d_high_rise_pct")
        if high_rise is not None and high_rise >= float(params["high_rise_min_pct"]):
            context_ok = True
        if int(context.get("basebar_flag") or 0) == 1:
            context_ok = True

        extension_penalty = 0.0
        if first_open_return is not None:
            extension_penalty = max(0.0, first_open_return - 10.0)
        if args.exclude_first_open_return_gte > 0 and first_open_return is not None and first_open_return >= args.exclude_first_open_return_gte:
            continue

        if trend_ok and cooldown_ok and reclaim and candle_ok and participation and context_ok:
            entry_row = candles[i + 1]
            entry_time = candle_dt(entry_row)
            entry_price = get_num(entry_row, "open")
            if entry_time is None or entry_price is None or entry_price <= 0:
                continue
            return {
                "signal_idx": i,
                "signal_time": ts,
                "signal_close": close,
                "entry_idx": i + 1,
                "entry_time": entry_time,
                "entry_price": entry_price,
                "trend_ma": ma_value,
                "rsi_prev": rsi_prev,
                "rsi_now": rsi_now,
                "rsi_cooldown_low": cooldown_low,
                "bars_since_rsi_cooldown": bars_since,
                "bar_return_pct": bar_ret,
                "close_position": cp,
                "upper_tail_ratio": utr,
                "body_ratio": br,
                "participation_type": participation_type,
                "first_bar_open_return_pct": first_open_return,
                "first_bar_extension_bucket": extension_bucket,
                "extension_risk_penalty": extension_penalty,
                **part_cols,
                **context,
            }
    return None


def score_row(row: Dict[str, Any]) -> Dict[str, Any]:
    technical = 0.0
    participation = 0.0
    context = 0.0
    penalty = base.safe_float(row.get("extension_risk_penalty")) or 0.0

    rsi_now = base.safe_float(row.get("rsi_now")) or 0.0
    bar_ret = base.safe_float(row.get("bar_return_pct")) or 0.0
    cp = base.safe_float(row.get("close_position")) or 0.0
    amount = base.safe_float(row.get("bar_amount")) or 0.0
    cum_amount = base.safe_float(row.get("cum_amount")) or 0.0
    high_rise = base.safe_float(row.get("last5d_high_rise_pct")) or 0.0

    technical += min(30.0, max(0.0, rsi_now - 60.0))
    technical += min(20.0, bar_ret * 4.0)
    technical += min(10.0, cp * 10.0)
    participation += min(20.0, amount / 1000000000.0 * 5.0)
    participation += min(20.0, cum_amount / 5000000000.0 * 5.0)
    context += min(20.0, high_rise)
    if int(row.get("basebar_flag") or 0) == 1:
        context += 10.0
    if int(row.get("basebar_high_break_flag") or 0) == 1:
        context += 10.0

    final_score = technical + participation + context - penalty
    return {
        "technical_reaccel_score": technical,
        "participation_score": participation,
        "basebar_context_score": context,
        "extension_risk_penalty_score": penalty,
        "final_confidence_score": final_score,
    }


def evaluate_candidate(cand: Dict[str, Any], candles: Sequence[Dict[str, Any]], param_set: Dict[str, Any], args: argparse.Namespace) -> Optional[Dict[str, Any]]:
    sig = find_signal_for_params(candles, cand, param_set, args)
    if sig is None:
        return None
    exit_result = rsi_base.evaluate_exit(
        candles=candles,
        entry_idx=int(sig["entry_idx"]),
        entry_price=float(sig["entry_price"]),
        p1=args.p1,
        p2=args.p2,
        q=args.q,
        trail=args.trail,
        jma_period=args.jma_period,
        jma_phase=args.jma_phase,
        jma_power=args.jma_power,
        st_period=args.st_period,
        st_multiplier=args.st_multiplier,
    )
    row: Dict[str, Any] = {
        "strategy_name": STRATEGY_NAME,
        "param_id": param_set["param_id"],
        "trade_date": cand.get("trade_date"),
        "condition_name": cand.get("condition_name") or "",
        "code": cand.get("code"),
        "name": cand.get("name") or "",
        "T_capture": cand["T_capture"].isoformat(sep=" "),
        "signal_time": sig["signal_time"].isoformat(sep=" "),
        "entry_time": sig["entry_time"].isoformat(sep=" "),
        "entry_price": sig["entry_price"],
        **param_set,
        **sig,
    }
    row.update(score_row(row))
    row.update(exit_result)
    return row


def make_param_grid(args: argparse.Namespace) -> List[Dict[str, Any]]:
    grid: List[Dict[str, Any]] = []
    idx = 0
    for trend_period in parse_int_list(args.trend_periods):
        for rsi_period in parse_int_list(args.rsi_periods):
            for reclaim in parse_float_list(args.rsi_reclaim_levels):
                for cooldown in parse_float_list(args.rsi_cooldown_levels):
                    for lookback in parse_int_list(args.rsi_cooldown_lookbacks):
                        for bar_ret in parse_float_list(args.bar_return_min_pcts):
                            for high_rise in parse_float_list(args.high_rise_min_pcts):
                                idx += 1
                                grid.append({
                                    "param_id": "P%03d" % idx,
                                    "trend_type": "SMA",
                                    "trend_period": trend_period,
                                    "trend_buffer_pct": args.trend_buffer_pct,
                                    "rsi_period": rsi_period,
                                    "rsi_reclaim_level": reclaim,
                                    "rsi_cooldown_level": cooldown,
                                    "rsi_cooldown_lookback_bars": lookback,
                                    "bar_return_min_pct": bar_ret,
                                    "high_rise_min_pct": high_rise,
                                })
    return grid


def summarize(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        key = str(row.get("param_id"))
        if key not in groups:
            groups[key] = []
        groups[key].append(row)
    output: List[Dict[str, Any]] = []
    for key in sorted(groups.keys()):
        rs = groups[key]
        wins = [r for r in rs if (base.safe_float(r.get("realized_pnl_pct")) or 0.0) > 0]
        losses = [r for r in rs if (base.safe_float(r.get("realized_pnl_pct")) or 0.0) < 0]
        gross_win = sum([(base.safe_float(r.get("realized_pnl_pct")) or 0.0) for r in wins])
        gross_loss = abs(sum([(base.safe_float(r.get("realized_pnl_pct")) or 0.0) for r in losses]))
        first = rs[0]
        output.append({
            "param_id": key,
            "entry_count": len(rs),
            "win_count": len(wins),
            "win_rate": len(wins) / len(rs) if rs else 0.0,
            "loss_count": len(losses),
            "loss_rate": len(losses) / len(rs) if rs else 0.0,
            "avg_realized_pnl_pct": safe_avg([base.safe_float(r.get("realized_pnl_pct")) for r in rs]),
            "total_realized_pnl_pct": sum([(base.safe_float(r.get("realized_pnl_pct")) or 0.0) for r in rs]),
            "profit_factor": gross_win / gross_loss if gross_loss > 0 else None,
            "avg_mfe_pct": safe_avg([base.safe_float(r.get("max_favorable_excursion_pct")) for r in rs]),
            "avg_mae_pct": safe_avg([base.safe_float(r.get("max_adverse_excursion_pct")) for r in rs]),
            "avg_score": safe_avg([base.safe_float(r.get("final_confidence_score")) for r in rs]),
            "trend_period": first.get("trend_period"),
            "rsi_period": first.get("rsi_period"),
            "rsi_reclaim_level": first.get("rsi_reclaim_level"),
            "rsi_cooldown_level": first.get("rsi_cooldown_level"),
            "rsi_cooldown_lookback_bars": first.get("rsi_cooldown_lookback_bars"),
            "bar_return_min_pct": first.get("bar_return_min_pct"),
            "high_rise_min_pct": first.get("high_rise_min_pct"),
        })
    output.sort(key=lambda r: (base.safe_float(r.get("avg_realized_pnl_pct")) or -999999.0, base.safe_float(r.get("profit_factor")) or 0.0), reverse=True)
    return output


def summarize_daily(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for row in rows:
        key = (str(row.get("trade_date")), str(row.get("param_id")))
        if key not in groups:
            groups[key] = []
        groups[key].append(row)
    out: List[Dict[str, Any]] = []
    for key in sorted(groups.keys()):
        d, pid = key
        rs = groups[key]
        out.append({
            "trade_date": d,
            "param_id": pid,
            "entry_count": len(rs),
            "avg_realized_pnl_pct": safe_avg([base.safe_float(r.get("realized_pnl_pct")) for r in rs]),
            "total_realized_pnl_pct": sum([(base.safe_float(r.get("realized_pnl_pct")) or 0.0) for r in rs]),
            "avg_score": safe_avg([base.safe_float(r.get("final_confidence_score")) for r in rs]),
        })
    return out


def summarize_topn(rows: Sequence[Dict[str, Any]], topn_values: Sequence[int]) -> List[Dict[str, Any]]:
    by_date_param: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for row in rows:
        key = (str(row.get("trade_date")), str(row.get("param_id")))
        if key not in by_date_param:
            by_date_param[key] = []
        by_date_param[key].append(row)
    out: List[Dict[str, Any]] = []
    for topn in topn_values:
        by_param: Dict[str, List[Dict[str, Any]]] = {}
        for (d, pid), rs in by_date_param.items():
            sorted_rs = sorted(rs, key=lambda r: base.safe_float(r.get("final_confidence_score")) or -999999.0, reverse=True)
            selected = sorted_rs[:topn]
            if pid not in by_param:
                by_param[pid] = []
            by_param[pid].extend(selected)
        for pid, rs in by_param.items():
            wins = [r for r in rs if (base.safe_float(r.get("realized_pnl_pct")) or 0.0) > 0]
            losses = [r for r in rs if (base.safe_float(r.get("realized_pnl_pct")) or 0.0) < 0]
            gross_win = sum([(base.safe_float(r.get("realized_pnl_pct")) or 0.0) for r in wins])
            gross_loss = abs(sum([(base.safe_float(r.get("realized_pnl_pct")) or 0.0) for r in losses]))
            out.append({
                "topn": topn,
                "param_id": pid,
                "entry_count": len(rs),
                "win_rate": len(wins) / len(rs) if rs else 0.0,
                "avg_realized_pnl_pct": safe_avg([base.safe_float(r.get("realized_pnl_pct")) for r in rs]),
                "total_realized_pnl_pct": sum([(base.safe_float(r.get("realized_pnl_pct")) or 0.0) for r in rs]),
                "profit_factor": gross_win / gross_loss if gross_loss > 0 else None,
                "avg_score": safe_avg([base.safe_float(r.get("final_confidence_score")) for r in rs]),
            })
    out.sort(key=lambda r: (int(r.get("topn") or 0), base.safe_float(r.get("avg_realized_pnl_pct")) or -999999.0), reverse=False)
    return out


def write_csv(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fields: List[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fields:
                fields.append(key)
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
            elif f.endswith("pct") or f in ("profit_factor", "avg_score"):
                text = fmt_num(value)
            elif "amount" in f and base.safe_float(value) is not None:
                text = fmt_num((base.safe_float(value) or 0.0) / 100000000.0) + "억"
            else:
                text = "-" if value is None else str(value)
            align = "left" if f in ("strategy_name", "name", "param_id", "first_bar_extension_bucket") else ""
            parts.append("<td class='" + align + "'>" + html.escape(text) + "</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def build_html(detail: Sequence[Dict[str, Any]], summary: Sequence[Dict[str, Any]], daily: Sequence[Dict[str, Any]], topn: Sequence[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary_fields = ["param_id", "entry_count", "win_rate", "loss_rate", "avg_realized_pnl_pct", "total_realized_pnl_pct", "profit_factor", "avg_mfe_pct", "avg_mae_pct", "avg_score", "trend_period", "rsi_period", "rsi_reclaim_level", "rsi_cooldown_level", "rsi_cooldown_lookback_bars", "bar_return_min_pct", "high_rise_min_pct"]
    topn_fields = ["topn", "param_id", "entry_count", "win_rate", "avg_realized_pnl_pct", "total_realized_pnl_pct", "profit_factor", "avg_score"]
    detail_fields = ["trade_date", "param_id", "code", "name", "signal_time", "entry_time", "rsi_prev", "rsi_now", "bar_return_pct", "bar_amount", "cum_amount", "last5d_high_rise_pct", "first_bar_extension_bucket", "final_confidence_score", "realized_pnl_pct", "max_favorable_excursion_pct", "max_adverse_excursion_pct"]
    html_text = "\n".join([
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'><title>Leader Reaccel Parametric v1</title>",
        "<style>body{font-family:Segoe UI,Malgun Gothic,Arial;background:#111827;color:#e5e7eb;margin:0;padding:18px}h1,h2{color:#fbbf24}.box{border:1px solid #334155;border-radius:10px;padding:12px;background:#0f172a;margin-bottom:12px}table{border-collapse:collapse;width:100%;font-size:12px;margin:12px 0;background:#0f172a}th,td{border:1px solid #334155;padding:5px;text-align:right}th{background:#1e293b}.left{text-align:left}</style></head><body>",
        "<h1>Leader Reaccel Parametric v1</h1>",
        "<div class='box'>조건식 후보군 안에서 RSI 냉각 후 재돌파, MA 재안착, 재가속 봉, 참여강도, 기준봉/최근 상승 문맥을 파라미터화해 전체기간 또는 지정일 백테스트합니다.</div>",
        "<h2>Parameter Summary</h2>",
        table_html(summary, summary_fields),
        "<h2>TopN by Confidence Score</h2>",
        table_html(topn, topn_fields),
        "<h2>Detail Sample</h2>",
        table_html(detail[:1000], detail_fields),
        "</body></html>",
    ])
    path.write_text(html_text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--sqlite-db", default=None)
    parser.add_argument("--candidate-table", default=None)
    parser.add_argument("--condition-name", default=None)
    parser.add_argument("--trade-date", default=None)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--capture-time", default=base.DEFAULT_CAPTURE_TIME)
    parser.add_argument("--candle-table", default=None)
    parser.add_argument("--lookback-calendar-days", type=int, default=20)
    parser.add_argument("--trend-periods", default="20")
    parser.add_argument("--trend-buffer-pct", type=float, default=0.0)
    parser.add_argument("--rsi-periods", default="14")
    parser.add_argument("--rsi-reclaim-levels", default="70")
    parser.add_argument("--rsi-cooldown-levels", default="70")
    parser.add_argument("--rsi-cooldown-lookbacks", default="24")
    parser.add_argument("--bar-return-min-pcts", default="2,2.5,3")
    parser.add_argument("--participation-type", default="amount")
    parser.add_argument("--bar-amount-min", type=float, default=1000000000.0)
    parser.add_argument("--cum-amount-min", type=float, default=5000000000.0)
    parser.add_argument("--volume-ratio-min", type=float, default=3.0)
    parser.add_argument("--volume-ratio-lookback-bars", type=int, default=20)
    parser.add_argument("--high-rise-min-pcts", default="10")
    parser.add_argument("--basebar-lookback-bars", type=int, default=120)
    parser.add_argument("--basebar-min-return-pct", type=float, default=5.0)
    parser.add_argument("--basebar-min-amount", type=float, default=1000000000.0)
    parser.add_argument("--use-candle-quality", action="store_true")
    parser.add_argument("--close-position-min", type=float, default=0.55)
    parser.add_argument("--upper-tail-max", type=float, default=0.50)
    parser.add_argument("--body-ratio-min", type=float, default=0.30)
    parser.add_argument("--exclude-first-open-return-gte", type=float, default=0.0)
    parser.add_argument("--p1", type=float, default=3.0)
    parser.add_argument("--p2", type=float, default=6.0)
    parser.add_argument("--q", type=float, default=0.3)
    parser.add_argument("--trail", type=float, default=1.0)
    parser.add_argument("--jma-period", type=int, default=7)
    parser.add_argument("--jma-phase", type=int, default=50)
    parser.add_argument("--jma-power", type=int, default=2)
    parser.add_argument("--st-period", type=int, default=14)
    parser.add_argument("--st-multiplier", type=float, default=3.0)
    parser.add_argument("--topn", default="3,5,6")
    parser.add_argument("--output-dir", default="reports")
    args = parser.parse_args()

    if args.trade_date:
        args.start_date = args.trade_date
        args.end_date = args.trade_date

    base.load_env(args.env)
    sqlite_path = args.sqlite_db or base.env_value(["SQLITE_1516_DB"])
    if not sqlite_path:
        raise RuntimeError("SQLITE_1516_DB 또는 --sqlite-db가 필요합니다.")

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    mysql_conn = base.open_mysql_conn()
    try:
        schema = base.find_candidate_schema(sqlite_conn, args.candidate_table)
        candle_table = base.pick_candle_table(mysql_conn, args.candle_table)
        candidates = base.load_candidates(sqlite_conn, schema, args.start_date, args.end_date, args.condition_name, args.capture_time)
        grid = make_param_grid(args)

        print("=== Leader Reaccel Parametric v1 ===")
        print("candidate_table=" + schema.table)
        print("candle_table=" + candle_table)
        print("candidate_count=" + str(len(candidates)))
        print("param_grid_count=" + str(len(grid)))

        candle_cache: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        detail_rows: List[Dict[str, Any]] = []
        for i, cand in enumerate(candidates, 1):
            key = (cand["trade_date"], cand["code"])
            if key not in candle_cache:
                candle_cache[key] = rsi_base.load_recent_candles(mysql_conn, candle_table, cand["code"], cand["trade_date"], args.lookback_calendar_days)
            candles = candle_cache[key]
            for param_set in grid:
                row = evaluate_candidate(cand, candles, param_set, args)
                if row is not None:
                    detail_rows.append(row)
            if i % 200 == 0:
                print("processed_candidates=" + str(i) + " signals=" + str(len(detail_rows)))

        summary_rows = summarize(detail_rows)
        daily_rows = summarize_daily(detail_rows)
        topn_rows = summarize_topn(detail_rows, parse_int_list(args.topn))
        outdir = Path(args.output_dir)
        write_csv(outdir / "leader_reaccel_parametric_detail_v1.csv", detail_rows)
        write_csv(outdir / "leader_reaccel_parametric_summary_v1.csv", summary_rows)
        write_csv(outdir / "leader_reaccel_parametric_daily_v1.csv", daily_rows)
        write_csv(outdir / "leader_reaccel_parametric_topn_v1.csv", topn_rows)
        build_html(detail_rows, summary_rows, daily_rows, topn_rows, outdir / "leader_reaccel_parametric_v1.html")

        print("=== Top Summary ===")
        for row in summary_rows[:20]:
            print(row)
        print("signal_count=" + str(len(detail_rows)))
        print("output_detail=" + str((outdir / "leader_reaccel_parametric_detail_v1.csv").resolve()))
        print("output_summary=" + str((outdir / "leader_reaccel_parametric_summary_v1.csv").resolve()))
        print("output_daily=" + str((outdir / "leader_reaccel_parametric_daily_v1.csv").resolve()))
        print("output_topn=" + str((outdir / "leader_reaccel_parametric_topn_v1.csv").resolve()))
        print("output_html=" + str((outdir / "leader_reaccel_parametric_v1.html").resolve()))
        return 0
    finally:
        sqlite_conn.close()
        mysql_conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
