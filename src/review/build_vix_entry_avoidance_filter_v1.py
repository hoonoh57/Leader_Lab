# -*- coding: utf-8 -*-
"""Build VIX Entry Avoidance Filter Benchmark v1.

Goal:
    Mechanical +X% breakout entry produced a positive result only with a very wide
    stop in the stop-sweep benchmark. This script investigates avoidable collapse
    patterns around TX so that bad +X% entries can be filtered before JMA/ST exit
    logic is applied.

Outputs:
    reports/vix_entry_avoidance_detail_v1.csv
    reports/vix_entry_avoidance_feature_summary_v1.csv
    reports/vix_entry_avoidance_rule_lift_v1.csv
    reports/vix_entry_avoidance_benchmark_v1.html
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
DEFAULT_TARGET_PCT = 2.0
DEFAULT_COLLAPSE_MAE_PCT = -6.0
DEFAULT_REJECT_MAE_PCT = -2.0


def parse_float_list(text: str) -> List[float]:
    result: List[float] = []
    for raw in text.split(","):
        value = raw.strip()
        if value != "":
            result.append(float(value))
    return result


def avg(values: Iterable[Optional[float]]) -> Optional[float]:
    arr: List[float] = []
    for v in values:
        if v is not None and not math.isnan(v) and not math.isinf(v):
            arr.append(v)
    if len(arr) == 0:
        return None
    return sum(arr) / len(arr)


def median(values: Iterable[Optional[float]]) -> Optional[float]:
    arr: List[float] = []
    for v in values:
        if v is not None and not math.isnan(v) and not math.isinf(v):
            arr.append(v)
    if len(arr) == 0:
        return None
    arr.sort()
    mid = len(arr) // 2
    if len(arr) % 2 == 1:
        return arr[mid]
    return (arr[mid - 1] + arr[mid]) / 2.0


def pct(price: Optional[float], base_price: Optional[float]) -> Optional[float]:
    if price is None or base_price is None or base_price <= 0:
        return None
    return (price / base_price - 1.0) * 100.0


def candle_time(row: Dict[str, Any]) -> Optional[Any]:
    return base.candle_dt(row)


def get_num(row: Optional[Dict[str, Any]], key: str) -> Optional[float]:
    if row is None:
        return None
    return base.safe_float(row.get(key))


def row_amount(row: Optional[Dict[str, Any]]) -> Optional[float]:
    if row is None:
        return None
    return base.amount_from_candle(row)


def tx_index(candles: Sequence[Dict[str, Any]], tx: Any) -> int:
    for i, row in enumerate(candles):
        ts = candle_time(row)
        if ts == tx:
            return i
    return -1


def range_position(close_price: Optional[float], low_price: Optional[float], high_price: Optional[float]) -> Optional[float]:
    if close_price is None or low_price is None or high_price is None:
        return None
    rng = high_price - low_price
    if rng <= 0:
        return None
    return (close_price - low_price) / rng


def body_ratio(open_price: Optional[float], close_price: Optional[float], low_price: Optional[float], high_price: Optional[float]) -> Optional[float]:
    if open_price is None or close_price is None or low_price is None or high_price is None:
        return None
    rng = high_price - low_price
    if rng <= 0:
        return None
    return abs(close_price - open_price) / rng


def upper_tail_ratio(open_price: Optional[float], close_price: Optional[float], low_price: Optional[float], high_price: Optional[float]) -> Optional[float]:
    if open_price is None or close_price is None or low_price is None or high_price is None:
        return None
    rng = high_price - low_price
    if rng <= 0:
        return None
    body_top = max(open_price, close_price)
    return (high_price - body_top) / rng


def lower_tail_ratio(open_price: Optional[float], close_price: Optional[float], low_price: Optional[float], high_price: Optional[float]) -> Optional[float]:
    if open_price is None or close_price is None or low_price is None or high_price is None:
        return None
    rng = high_price - low_price
    if rng <= 0:
        return None
    body_bottom = min(open_price, close_price)
    return (body_bottom - low_price) / rng


def evaluate_post_path(candles: Sequence[Dict[str, Any]], idx: int, entry_price: float, target_pct: float, collapse_mae_pct: float, reject_mae_pct: float) -> Dict[str, Any]:
    rows = candles[idx:] if idx >= 0 else []
    if len(rows) == 0:
        return {
            "post_TX_max_return_pct": None,
            "post_TX_mae_pct": None,
            "plus_target_success": 0,
            "collapse_after_TX_flag": 0,
            "reject_near_TX_flag": 0,
            "outcome_label": "NO_POST_DATA",
        }
    max_ret: Optional[float] = None
    min_ret: Optional[float] = None
    for row in rows:
        high_price = get_num(row, "high")
        low_price = get_num(row, "low")
        high_ret = pct(high_price, entry_price)
        low_ret = pct(low_price, entry_price)
        if high_ret is not None:
            max_ret = high_ret if max_ret is None else max(max_ret, high_ret)
        if low_ret is not None:
            min_ret = low_ret if min_ret is None else min(min_ret, low_ret)
    success = 1 if max_ret is not None and max_ret >= target_pct else 0
    collapse = 1 if min_ret is not None and min_ret <= collapse_mae_pct else 0
    reject = 1 if min_ret is not None and min_ret <= reject_mae_pct and success == 0 else 0
    if success == 1 and collapse == 0:
        label = "CONTINUATION"
    elif collapse == 1:
        label = "COLLAPSE_AFTER_TX"
    elif reject == 1:
        label = "REJECT_NEAR_TX"
    else:
        label = "STALL"
    return {
        "post_TX_max_return_pct": max_ret,
        "post_TX_mae_pct": min_ret,
        "plus_target_success": success,
        "collapse_after_TX_flag": collapse,
        "reject_near_TX_flag": reject,
        "outcome_label": label,
    }


def next_bar_features(candles: Sequence[Dict[str, Any]], idx: int, entry_price: float) -> Dict[str, Any]:
    n1 = candles[idx + 1] if idx + 1 < len(candles) else None
    n2 = candles[idx + 2] if idx + 2 < len(candles) else None
    n3 = candles[idx + 3] if idx + 3 < len(candles) else None
    next_rows: List[Optional[Dict[str, Any]]] = [n1, n2, n3]
    close_hold_count = 0
    valid_close_count = 0
    low_vals: List[float] = []
    for row in next_rows:
        if row is None:
            continue
        close_price = get_num(row, "close")
        low_price = get_num(row, "low")
        if close_price is not None:
            valid_close_count += 1
            if close_price >= entry_price:
                close_hold_count += 1
        if low_price is not None:
            low_ret = pct(low_price, entry_price)
            if low_ret is not None:
                low_vals.append(low_ret)
    return {
        "next1_low_vs_entry_pct": pct(get_num(n1, "low"), entry_price),
        "next1_close_vs_entry_pct": pct(get_num(n1, "close"), entry_price),
        "next2_low_vs_entry_pct": pct(get_num(n2, "low"), entry_price),
        "next2_close_vs_entry_pct": pct(get_num(n2, "close"), entry_price),
        "next3_low_vs_entry_pct": pct(get_num(n3, "low"), entry_price),
        "next3_close_vs_entry_pct": pct(get_num(n3, "close"), entry_price),
        "next3_min_low_vs_entry_pct": min(low_vals) if len(low_vals) > 0 else None,
        "next3_close_hold_count": close_hold_count,
        "next3_close_hold_ratio": close_hold_count / valid_close_count if valid_close_count > 0 else None,
    }


def tx_candle_features(tx_row: Dict[str, Any], prev_close: float, entry_price: float, threshold_pct: float) -> Dict[str, Any]:
    op = get_num(tx_row, "open")
    hi = get_num(tx_row, "high")
    lo = get_num(tx_row, "low")
    cl = get_num(tx_row, "close")
    close_from_entry = pct(cl, entry_price)
    return {
        "tx_open_return_from_prev_close_pct": pct(op, prev_close),
        "tx_high_return_from_prev_close_pct": pct(hi, prev_close),
        "tx_low_return_from_prev_close_pct": pct(lo, prev_close),
        "tx_close_return_from_prev_close_pct": pct(cl, prev_close),
        "tx_close_vs_entry_pct": close_from_entry,
        "tx_close_above_entry_flag": 1 if close_from_entry is not None and close_from_entry >= 0 else 0,
        "tx_close_position_in_range": range_position(cl, lo, hi),
        "tx_body_ratio": body_ratio(op, cl, lo, hi),
        "tx_upper_tail_ratio": upper_tail_ratio(op, cl, lo, hi),
        "tx_lower_tail_ratio": lower_tail_ratio(op, cl, lo, hi),
        "tx_wick_only_breakout_flag": 1 if hi is not None and hi >= entry_price and (cl is None or cl < entry_price) else 0,
        "tx_amount": row_amount(tx_row),
        "tx_is_red_flag": 1 if op is not None and cl is not None and cl < op else 0,
        "tx_singlebar_range_pct": pct(hi, lo) if hi is not None and lo is not None and lo > 0 else None,
    }


def evaluate_candidate(candidate: Dict[str, Any], candles: Sequence[Dict[str, Any]], prev_close: Optional[float], thresholds: Sequence[float], target_pct: float, collapse_mae_pct: float, reject_mae_pct: float) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if prev_close is None or prev_close <= 0 or len(candles) == 0:
        return rows
    cap_dt = candidate["T_capture"]
    for threshold_pct in thresholds:
        tx_row = base.first_breakout(candles, prev_close, threshold_pct, cap_dt)
        if tx_row is None:
            continue
        tx = tx_row["TX"]
        entry_price = tx_row["entry_price"]
        idx = tx_index(candles, tx)
        if idx < 0:
            continue
        pre = base.pre_window_stats(candles, cap_dt, tx, prev_close)
        txf = tx_candle_features(candles[idx], prev_close, entry_price, threshold_pct)
        nxf = next_bar_features(candles, idx, entry_price)
        post = evaluate_post_path(candles, idx, entry_price, target_pct, collapse_mae_pct, reject_mae_pct)
        out: Dict[str, Any] = {
            "trade_date": candidate.get("trade_date"),
            "condition_name": candidate.get("condition_name") or "",
            "T_capture": cap_dt.isoformat(sep=" "),
            "breakout_threshold_pct": threshold_pct,
            "target_pct": target_pct,
            "collapse_mae_pct": collapse_mae_pct,
            "reject_mae_pct": reject_mae_pct,
            "code": candidate.get("code"),
            "name": candidate.get("name") or "",
            "TX": tx.isoformat(sep=" "),
            "entry_price": entry_price,
            "prev_close": prev_close,
            "source_max_return_pct": candidate.get("source_max_return_pct"),
        }
        out.update(pre)
        out.update(txf)
        out.update(nxf)
        out.update(post)
        rows.append(out)
    return rows


def feature_summary(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    feature_names = [
        "minutes_capture_to_TX",
        "amount_capture_to_TX",
        "amount_velocity_per_min",
        "pullback_depth_before_TX_pct",
        "high_hold_ratio_before_TX",
        "return_capture_to_TX_pct",
        "tx_close_vs_entry_pct",
        "tx_close_position_in_range",
        "tx_body_ratio",
        "tx_upper_tail_ratio",
        "tx_lower_tail_ratio",
        "tx_wick_only_breakout_flag",
        "tx_amount",
        "tx_is_red_flag",
        "tx_singlebar_range_pct",
        "next1_low_vs_entry_pct",
        "next1_close_vs_entry_pct",
        "next2_low_vs_entry_pct",
        "next2_close_vs_entry_pct",
        "next3_min_low_vs_entry_pct",
        "next3_close_hold_ratio",
    ]
    groups = {
        "CONTINUATION": [r for r in rows if r.get("outcome_label") == "CONTINUATION"],
        "COLLAPSE_OR_REJECT": [r for r in rows if r.get("outcome_label") in ("COLLAPSE_AFTER_TX", "REJECT_NEAR_TX")],
        "ALL": list(rows),
    }
    result: List[Dict[str, Any]] = []
    for feature in feature_names:
        cont_vals = [base.safe_float(r.get(feature)) for r in groups["CONTINUATION"]]
        bad_vals = [base.safe_float(r.get(feature)) for r in groups["COLLAPSE_OR_REJECT"]]
        result.append({
            "feature_name": feature,
            "continuation_count": len(groups["CONTINUATION"]),
            "bad_count": len(groups["COLLAPSE_OR_REJECT"]),
            "continuation_avg": avg(cont_vals),
            "bad_avg": avg(bad_vals),
            "diff_avg_cont_minus_bad": (avg(cont_vals) - avg(bad_vals)) if avg(cont_vals) is not None and avg(bad_vals) is not None else None,
            "continuation_median": median(cont_vals),
            "bad_median": median(bad_vals),
        })
    result.sort(key=lambda r: abs(base.safe_float(r.get("diff_avg_cont_minus_bad")) or 0.0), reverse=True)
    return result


def add_rule_result(result: List[Dict[str, Any]], rows: Sequence[Dict[str, Any]], rule_name: str, selected: Sequence[Dict[str, Any]]) -> None:
    base_entries = list(rows)
    selected_entries = list(selected)
    avoided_entries = [r for r in base_entries if r not in selected_entries]
    base_bad = [r for r in base_entries if r.get("outcome_label") in ("COLLAPSE_AFTER_TX", "REJECT_NEAR_TX")]
    selected_bad = [r for r in selected_entries if r.get("outcome_label") in ("COLLAPSE_AFTER_TX", "REJECT_NEAR_TX")]
    avoided_bad = [r for r in avoided_entries if r.get("outcome_label") in ("COLLAPSE_AFTER_TX", "REJECT_NEAR_TX")]
    base_good = [r for r in base_entries if r.get("outcome_label") == "CONTINUATION"]
    selected_good = [r for r in selected_entries if r.get("outcome_label") == "CONTINUATION"]
    avoided_good = [r for r in avoided_entries if r.get("outcome_label") == "CONTINUATION"]
    result.append({
        "rule_name": rule_name,
        "base_entry_count": len(base_entries),
        "selected_entry_count": len(selected_entries),
        "avoided_entry_count": len(avoided_entries),
        "base_bad_count": len(base_bad),
        "selected_bad_count": len(selected_bad),
        "avoided_bad_count": len(avoided_bad),
        "base_good_count": len(base_good),
        "selected_good_count": len(selected_good),
        "missed_good_count": len(avoided_good),
        "selected_good_rate": len(selected_good) / len(selected_entries) if len(selected_entries) > 0 else 0.0,
        "selected_bad_rate": len(selected_bad) / len(selected_entries) if len(selected_entries) > 0 else 0.0,
        "collapse_avoid_rate": len(avoided_bad) / len(base_bad) if len(base_bad) > 0 else 0.0,
        "false_avoid_rate": len(avoided_good) / len(base_good) if len(base_good) > 0 else 0.0,
        "selected_avg_mae": avg([base.safe_float(r.get("post_TX_mae_pct")) for r in selected_entries]),
        "base_avg_mae": avg([base.safe_float(r.get("post_TX_mae_pct")) for r in base_entries]),
        "selected_avg_mfe": avg([base.safe_float(r.get("post_TX_max_return_pct")) for r in selected_entries]),
        "base_avg_mfe": avg([base.safe_float(r.get("post_TX_max_return_pct")) for r in base_entries]),
    })


def rule_lift(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    base_rows = list(rows)
    add_rule_result(result, base_rows, "BASE_ALL", base_rows)
    add_rule_result(result, base_rows, "TX_CLOSE_ABOVE_ENTRY", [r for r in base_rows if int(r.get("tx_close_above_entry_flag") or 0) == 1])
    add_rule_result(result, base_rows, "NO_WICK_ONLY_BREAKOUT", [r for r in base_rows if int(r.get("tx_wick_only_breakout_flag") or 0) == 0])
    add_rule_result(result, base_rows, "TX_CLOSE_POS_GE_0_55", [r for r in base_rows if (base.safe_float(r.get("tx_close_position_in_range")) or -999) >= 0.55])
    add_rule_result(result, base_rows, "TX_UPPER_TAIL_LE_0_35", [r for r in base_rows if (base.safe_float(r.get("tx_upper_tail_ratio")) or 999) <= 0.35])
    add_rule_result(result, base_rows, "NEXT1_CLOSE_GE_ENTRY", [r for r in base_rows if (base.safe_float(r.get("next1_close_vs_entry_pct")) or -999) >= 0])
    add_rule_result(result, base_rows, "NEXT1_LOW_GE_MINUS_2", [r for r in base_rows if (base.safe_float(r.get("next1_low_vs_entry_pct")) or -999) >= -2])
    add_rule_result(result, base_rows, "NEXT3_HOLD_RATIO_GE_0_67", [r for r in base_rows if (base.safe_float(r.get("next3_close_hold_ratio")) or -999) >= 0.67])
    add_rule_result(result, base_rows, "TX_CLOSE_ABOVE_AND_NO_WICK", [r for r in base_rows if int(r.get("tx_close_above_entry_flag") or 0) == 1 and int(r.get("tx_wick_only_breakout_flag") or 0) == 0])
    add_rule_result(result, base_rows, "CLOSE_POS_AND_NEXT1_HOLD", [r for r in base_rows if (base.safe_float(r.get("tx_close_position_in_range")) or -999) >= 0.55 and (base.safe_float(r.get("next1_close_vs_entry_pct")) or -999) >= 0])
    result.sort(key=lambda r: ((base.safe_float(r.get("selected_good_rate")) or 0.0) - (base.safe_float(r.get("selected_bad_rate")) or 0.0), base.safe_float(r.get("collapse_avoid_rate")) or 0.0), reverse=True)
    return result


def write_csv(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fields: List[str] = []
    for r in rows:
        for k in r.keys():
            if k not in fields:
                fields.append(k)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def fmt(v: Any, digits: int = 2) -> str:
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
    for r in rows:
        parts.append("<tr>")
        for f in fields:
            val = r.get(f)
            if f.endswith("rate"):
                text = fmt_rate(val)
            elif "amount" in f and base.safe_float(val) is not None:
                text = fmt((base.safe_float(val) or 0.0) / 100000000.0) + "억"
            elif isinstance(val, float):
                text = fmt(val)
            else:
                text = "-" if val is None else str(val)
            align = "left" if f in ("rule_name", "feature_name", "name", "outcome_label") else ""
            parts.append("<td class='" + align + "'>" + html.escape(text) + "</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def build_html(detail: Sequence[Dict[str, Any]], features: Sequence[Dict[str, Any]], rules: Sequence[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rule_fields = ["rule_name", "base_entry_count", "selected_entry_count", "avoided_entry_count", "selected_good_count", "selected_good_rate", "selected_bad_count", "selected_bad_rate", "collapse_avoid_rate", "false_avoid_rate", "selected_avg_mae", "base_avg_mae", "selected_avg_mfe", "base_avg_mfe"]
    feature_fields = ["feature_name", "continuation_count", "bad_count", "continuation_avg", "bad_avg", "diff_avg_cont_minus_bad", "continuation_median", "bad_median"]
    detail_fields = ["trade_date", "breakout_threshold_pct", "code", "name", "TX", "outcome_label", "tx_close_vs_entry_pct", "tx_close_position_in_range", "tx_upper_tail_ratio", "tx_wick_only_breakout_flag", "next1_close_vs_entry_pct", "next1_low_vs_entry_pct", "next3_close_hold_ratio", "post_TX_max_return_pct", "post_TX_mae_pct"]
    html_text = "\n".join([
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'><title>VIX Entry Avoidance Filter v1</title>",
        "<style>body{font-family:Segoe UI,Malgun Gothic,Arial;background:#111827;color:#e5e7eb;margin:0;padding:18px}h1,h2{color:#fbbf24}.box{border:1px solid #334155;border-radius:10px;padding:12px;background:#0f172a;margin-bottom:12px}table{border-collapse:collapse;width:100%;font-size:12px;margin:12px 0;background:#0f172a}th,td{border:1px solid #334155;padding:5px;text-align:right}th{background:#1e293b}.left{text-align:left}</style></head><body>",
        "<h1>VIX Entry Avoidance Filter v1</h1>",
        "<div class='box'>+X% 기계적 진입 전에 회피해야 할 급락/유동성 함정 패턴을 돌파봉 품질, 직후 1~3봉 유지력, TX 전 거래대금 경로로 분석합니다.</div>",
        "<h2>Rule Lift</h2>",
        table_html(rules, rule_fields),
        "<h2>Feature Summary: CONTINUATION vs COLLAPSE/REJECT</h2>",
        table_html(features, feature_fields),
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
    parser.add_argument("--target-pct", type=float, default=DEFAULT_TARGET_PCT)
    parser.add_argument("--collapse-mae-pct", type=float, default=DEFAULT_COLLAPSE_MAE_PCT)
    parser.add_argument("--reject-mae-pct", type=float, default=DEFAULT_REJECT_MAE_PCT)
    parser.add_argument("--output-dir", default="reports")
    args = parser.parse_args()

    base.load_env(args.env)
    sqlite_path = args.sqlite_db or base.env_value(["SQLITE_1516_DB"])
    if not sqlite_path:
        raise RuntimeError("SQLITE_1516_DB 또는 --sqlite-db가 필요합니다.")

    thresholds = parse_float_list(args.thresholds)
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    mysql_conn = base.open_mysql_conn()
    try:
        schema = base.find_candidate_schema(sqlite_conn, args.candidate_table)
        candle_table = base.pick_candle_table(mysql_conn, args.candle_table)
        candidates = base.load_candidates(sqlite_conn, schema, args.start_date, args.end_date, args.condition_name, args.capture_time)

        print("=== VIX Entry Avoidance Filter v1 ===")
        print("candidate_table=" + schema.table)
        print("candle_table=" + candle_table)
        print("candidate_count=" + str(len(candidates)))
        print("thresholds=" + str(thresholds))

        candle_cache: Dict[Tuple[str, str], Tuple[List[Dict[str, Any]], Optional[float]]] = {}
        detail_rows: List[Dict[str, Any]] = []
        for i, cand in enumerate(candidates, 1):
            key = (cand["trade_date"], cand["code"])
            if key not in candle_cache:
                candles = base.load_day_candles(mysql_conn, candle_table, cand["code"], cand["trade_date"])
                prev_close = base.previous_close_from_candles(mysql_conn, candle_table, cand["code"], cand["trade_date"])
                candle_cache[key] = (candles, prev_close)
            candles, prev_close = candle_cache[key]
            detail_rows.extend(evaluate_candidate(cand, candles, prev_close, thresholds, args.target_pct, args.collapse_mae_pct, args.reject_mae_pct))
            if i % 200 == 0:
                print("processed_candidates=" + str(i))

        features = feature_summary(detail_rows)
        rules = rule_lift(detail_rows)
        outdir = Path(args.output_dir)
        write_csv(outdir / "vix_entry_avoidance_detail_v1.csv", detail_rows)
        write_csv(outdir / "vix_entry_avoidance_feature_summary_v1.csv", features)
        write_csv(outdir / "vix_entry_avoidance_rule_lift_v1.csv", rules)
        build_html(detail_rows, features, rules, outdir / "vix_entry_avoidance_benchmark_v1.html")

        print("=== Top Rule Lift ===")
        for r in rules[:20]:
            print(r)
        print("output_detail=" + str((outdir / "vix_entry_avoidance_detail_v1.csv").resolve()))
        print("output_feature=" + str((outdir / "vix_entry_avoidance_feature_summary_v1.csv").resolve()))
        print("output_rule=" + str((outdir / "vix_entry_avoidance_rule_lift_v1.csv").resolve()))
        print("output_html=" + str((outdir / "vix_entry_avoidance_benchmark_v1.html").resolve()))
        return 0
    finally:
        sqlite_conn.close()
        mysql_conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
