# -*- coding: utf-8 -*-
"""Build VIX Entry Mode Benchmark v1.

Compare +X% breakout entry modes:

M0_MECHANICAL_TX
    Enter at the +X% threshold price on the TX breakout event.

M1_TX_CLOSE_CONFIRM
    Enter only if the TX candle closes above the +X% threshold.
    Entry price is the TX close.

M2_NEXT1_LOW_GUARD
    Enter only if the next candle after TX does not break below entry level by
    more than the allowed guard value. Entry price is next1 close.

M3_NEXT3_HOLD_CONFIRM
    Enter only if at least N of next 3 candles close above the +X% threshold.
    Entry price is the confirmation candle close.

Then sweep stop values for each mode.
"""

from __future__ import annotations

import argparse
import csv
import html
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src.review import build_vix_entry_continuation_benchmark_v1 as base


DEFAULT_THRESHOLDS = "10"
DEFAULT_STOPS = "-1,-2,-3,-4,-5,-6,-8"
DEFAULT_TARGET_PCT = 2.0
DEFAULT_NEXT1_GUARD_PCT = -2.0
DEFAULT_NEXT3_HOLD_MIN = 2


ENTRY_MODES = [
    "M0_MECHANICAL_TX",
    "M1_TX_CLOSE_CONFIRM",
    "M2_NEXT1_LOW_GUARD",
    "M3_NEXT3_HOLD_CONFIRM",
]


def parse_float_list(text: str) -> List[float]:
    arr: List[float] = []
    for raw in text.split(","):
        item = raw.strip()
        if item != "":
            arr.append(float(item))
    return arr


def avg(values: Iterable[Optional[float]]) -> Optional[float]:
    arr: List[float] = []
    for value in values:
        if value is not None:
            arr.append(value)
    if len(arr) == 0:
        return None
    return sum(arr) / len(arr)


def pct(price: Optional[float], base_price: Optional[float]) -> Optional[float]:
    if price is None or base_price is None or base_price <= 0:
        return None
    return (price / base_price - 1.0) * 100.0


def get_num(row: Optional[Dict[str, Any]], key: str) -> Optional[float]:
    if row is None:
        return None
    return base.safe_float(row.get(key))


def candle_dt(row: Optional[Dict[str, Any]]) -> Optional[Any]:
    if row is None:
        return None
    return base.candle_dt(row)


def tx_index(candles: Sequence[Dict[str, Any]], tx: Any) -> int:
    for i, row in enumerate(candles):
        if candle_dt(row) == tx:
            return i
    return -1


def mode_entry(mode: str, candles: Sequence[Dict[str, Any]], tx_idx: int, threshold_entry_price: float, next1_guard_pct: float, next3_hold_min: int) -> Optional[Dict[str, Any]]:
    if tx_idx < 0 or tx_idx >= len(candles):
        return None

    tx_row = candles[tx_idx]
    tx_close = get_num(tx_row, "close")

    if mode == "M0_MECHANICAL_TX":
        return {
            "entry_idx": tx_idx,
            "entry_time": candle_dt(tx_row),
            "entry_price": threshold_entry_price,
            "entry_confirm_reason": "TX_TOUCH",
        }

    if mode == "M1_TX_CLOSE_CONFIRM":
        if tx_close is not None and tx_close >= threshold_entry_price:
            return {
                "entry_idx": tx_idx,
                "entry_time": candle_dt(tx_row),
                "entry_price": tx_close,
                "entry_confirm_reason": "TX_CLOSE_ABOVE_ENTRY",
            }
        return None

    next1 = candles[tx_idx + 1] if tx_idx + 1 < len(candles) else None
    if mode == "M2_NEXT1_LOW_GUARD":
        if next1 is None:
            return None
        next1_low = get_num(next1, "low")
        next1_close = get_num(next1, "close")
        low_ret = pct(next1_low, threshold_entry_price)
        if low_ret is not None and low_ret >= next1_guard_pct and next1_close is not None:
            return {
                "entry_idx": tx_idx + 1,
                "entry_time": candle_dt(next1),
                "entry_price": next1_close,
                "entry_confirm_reason": "NEXT1_LOW_GUARD",
            }
        return None

    if mode == "M3_NEXT3_HOLD_CONFIRM":
        close_hold_count = 0
        confirm_idx = -1
        for offset in range(1, 4):
            idx = tx_idx + offset
            if idx >= len(candles):
                continue
            row = candles[idx]
            close_price = get_num(row, "close")
            if close_price is not None and close_price >= threshold_entry_price:
                close_hold_count += 1
            confirm_idx = idx
        if close_hold_count >= next3_hold_min and confirm_idx >= 0:
            confirm_row = candles[confirm_idx]
            confirm_close = get_num(confirm_row, "close")
            if confirm_close is not None:
                return {
                    "entry_idx": confirm_idx,
                    "entry_time": candle_dt(confirm_row),
                    "entry_price": confirm_close,
                    "entry_confirm_reason": "NEXT3_HOLD_CONFIRM",
                }
        return None

    return None


def evaluate_post_from_entry(candles: Sequence[Dict[str, Any]], entry_idx: int, entry_price: float, target_pct: float, stop_pct: float) -> Dict[str, Any]:
    rows = candles[entry_idx:] if entry_idx >= 0 else []
    if len(rows) == 0:
        return {
            "post_entry_max_return_pct": None,
            "post_entry_mae_pct": None,
            "target_success": 0,
            "stop_hit": 0,
            "first_event": "NO_POST_DATA",
            "outcome_label": "NO_POST_DATA",
            "realized_pnl_pct": 0.0,
        }

    max_ret: Optional[float] = None
    min_ret: Optional[float] = None
    target_hit = False
    stop_hit = False
    first_event = "STALL"

    for row in rows:
        high_ret = pct(get_num(row, "high"), entry_price)
        low_ret = pct(get_num(row, "low"), entry_price)
        if high_ret is not None:
            max_ret = high_ret if max_ret is None else max(max_ret, high_ret)
        if low_ret is not None:
            min_ret = low_ret if min_ret is None else min(min_ret, low_ret)
        if not target_hit and not stop_hit:
            if low_ret is not None and low_ret <= stop_pct:
                stop_hit = True
                first_event = "STOP_FIRST"
            elif high_ret is not None and high_ret >= target_pct:
                target_hit = True
                first_event = "TARGET_FIRST"

    if target_hit:
        label = "WIN"
        pnl = target_pct
    elif stop_hit:
        label = "LOSS"
        pnl = stop_pct
    else:
        label = "STALL"
        pnl = 0.0

    return {
        "post_entry_max_return_pct": max_ret,
        "post_entry_mae_pct": min_ret,
        "target_success": 1 if target_hit else 0,
        "stop_hit": 1 if stop_hit else 0,
        "first_event": first_event,
        "outcome_label": label,
        "realized_pnl_pct": pnl,
    }


def evaluate_candidate(candidate: Dict[str, Any], candles: Sequence[Dict[str, Any]], prev_close: Optional[float], thresholds: Sequence[float], stops: Sequence[float], target_pct: float, next1_guard_pct: float, next3_hold_min: int) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    if prev_close is None or prev_close <= 0 or len(candles) == 0:
        return result

    cap_dt = candidate["T_capture"]
    for threshold_pct in thresholds:
        tx_row = base.first_breakout(candles, prev_close, threshold_pct, cap_dt)
        if tx_row is None:
            continue
        tx = tx_row["TX"]
        tx_idx = tx_index(candles, tx)
        if tx_idx < 0:
            continue
        threshold_entry_price = float(tx_row["entry_price"])
        pre = base.pre_window_stats(candles, cap_dt, tx, prev_close)
        for mode in ENTRY_MODES:
            entry = mode_entry(mode, candles, tx_idx, threshold_entry_price, next1_guard_pct, next3_hold_min)
            if entry is None:
                continue
            for stop_pct in stops:
                post = evaluate_post_from_entry(candles, int(entry["entry_idx"]), float(entry["entry_price"]), target_pct, stop_pct)
                row: Dict[str, Any] = {
                    "trade_date": candidate.get("trade_date"),
                    "condition_name": candidate.get("condition_name") or "",
                    "code": candidate.get("code"),
                    "name": candidate.get("name") or "",
                    "T_capture": cap_dt.isoformat(sep=" "),
                    "breakout_threshold_pct": threshold_pct,
                    "TX": tx.isoformat(sep=" "),
                    "threshold_entry_price": threshold_entry_price,
                    "entry_mode": mode,
                    "entry_time": entry["entry_time"].isoformat(sep=" ") if hasattr(entry["entry_time"], "isoformat") else str(entry["entry_time"]),
                    "entry_price": entry["entry_price"],
                    "entry_confirm_reason": entry["entry_confirm_reason"],
                    "target_pct": target_pct,
                    "stop_loss_pct": stop_pct,
                    "prev_close": prev_close,
                    "source_max_return_pct": candidate.get("source_max_return_pct"),
                }
                row.update(pre)
                row.update(post)
                result.append(row)
    return result


def summarize(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[str, float, float], List[Dict[str, Any]]] = {}
    for row in rows:
        key = (str(row.get("entry_mode")), float(row.get("breakout_threshold_pct") or 0.0), float(row.get("stop_loss_pct") or 0.0))
        if key not in groups:
            groups[key] = []
        groups[key].append(row)

    result: List[Dict[str, Any]] = []
    for key in sorted(groups.keys()):
        mode, threshold_pct, stop_pct = key
        rs = groups[key]
        wins = [r for r in rs if int(r.get("target_success") or 0) == 1]
        losses = [r for r in rs if int(r.get("stop_hit") or 0) == 1]
        stalls = [r for r in rs if str(r.get("outcome_label") or "") == "STALL"]
        gross_win = sum([base.safe_float(r.get("realized_pnl_pct")) or 0.0 for r in wins])
        gross_loss = abs(sum([base.safe_float(r.get("realized_pnl_pct")) or 0.0 for r in losses]))
        result.append({
            "entry_mode": mode,
            "breakout_threshold_pct": threshold_pct,
            "stop_loss_pct": stop_pct,
            "entry_count": len(rs),
            "win_count": len(wins),
            "win_rate": len(wins) / len(rs) if len(rs) > 0 else 0.0,
            "loss_count": len(losses),
            "loss_rate": len(losses) / len(rs) if len(rs) > 0 else 0.0,
            "stall_count": len(stalls),
            "stall_rate": len(stalls) / len(rs) if len(rs) > 0 else 0.0,
            "expected_pct_per_entry": avg([base.safe_float(r.get("realized_pnl_pct")) for r in rs]),
            "profit_factor_simple": gross_win / gross_loss if gross_loss > 0 else None,
            "avg_post_entry_mfe_pct": avg([base.safe_float(r.get("post_entry_max_return_pct")) for r in rs]),
            "avg_post_entry_mae_pct": avg([base.safe_float(r.get("post_entry_mae_pct")) for r in rs]),
        })
    result.sort(key=lambda r: base.safe_float(r.get("expected_pct_per_entry")) or -999999.0, reverse=True)
    return result


def summarize_daily(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[str, str, float, float], List[Dict[str, Any]]] = {}
    for row in rows:
        key = (str(row.get("trade_date")), str(row.get("entry_mode")), float(row.get("breakout_threshold_pct") or 0.0), float(row.get("stop_loss_pct") or 0.0))
        if key not in groups:
            groups[key] = []
        groups[key].append(row)
    result: List[Dict[str, Any]] = []
    for key in sorted(groups.keys()):
        trade_date, mode, threshold_pct, stop_pct = key
        rs = groups[key]
        wins = [r for r in rs if int(r.get("target_success") or 0) == 1]
        losses = [r for r in rs if int(r.get("stop_hit") or 0) == 1]
        result.append({
            "trade_date": trade_date,
            "entry_mode": mode,
            "breakout_threshold_pct": threshold_pct,
            "stop_loss_pct": stop_pct,
            "entry_count": len(rs),
            "win_count": len(wins),
            "win_rate": len(wins) / len(rs) if len(rs) > 0 else 0.0,
            "loss_count": len(losses),
            "loss_rate": len(losses) / len(rs) if len(rs) > 0 else 0.0,
            "expected_pct_per_entry": avg([base.safe_float(r.get("realized_pnl_pct")) for r in rs]),
        })
    return result


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


def fmt_num(value: Any, digits: int = 2) -> str:
    num = base.safe_float(value)
    if num is None:
        return "-"
    return f"{num:.{digits}f}"


def fmt_rate(value: Any) -> str:
    num = base.safe_float(value)
    if num is None:
        return "-"
    return f"{num:.2%}"


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
            elif field.endswith("pct") or field == "profit_factor_simple":
                text = fmt_num(value)
            elif "amount" in field and base.safe_float(value) is not None:
                text = fmt_num((base.safe_float(value) or 0.0) / 100000000.0) + "억"
            else:
                text = "-" if value is None else str(value)
            align = "left" if field in ("entry_mode", "name", "outcome_label", "entry_confirm_reason") else ""
            parts.append("<td class='" + align + "'>" + html.escape(text) + "</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def build_html(detail: Sequence[Dict[str, Any]], summary: Sequence[Dict[str, Any]], daily: Sequence[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary_fields = ["entry_mode", "breakout_threshold_pct", "stop_loss_pct", "entry_count", "win_count", "win_rate", "loss_count", "loss_rate", "stall_count", "stall_rate", "expected_pct_per_entry", "profit_factor_simple", "avg_post_entry_mfe_pct", "avg_post_entry_mae_pct"]
    daily_fields = ["trade_date", "entry_mode", "breakout_threshold_pct", "stop_loss_pct", "entry_count", "win_count", "win_rate", "loss_count", "loss_rate", "expected_pct_per_entry"]
    detail_fields = ["trade_date", "entry_mode", "breakout_threshold_pct", "stop_loss_pct", "code", "name", "TX", "entry_time", "entry_price", "entry_confirm_reason", "target_success", "stop_hit", "realized_pnl_pct", "post_entry_max_return_pct", "post_entry_mae_pct"]
    html_text = "\n".join([
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'><title>VIX Entry Mode Benchmark v1</title>",
        "<style>body{font-family:Segoe UI,Malgun Gothic,Arial;background:#111827;color:#e5e7eb;margin:0;padding:18px}h1,h2{color:#fbbf24}.box{border:1px solid #334155;border-radius:10px;padding:12px;background:#0f172a;margin-bottom:12px}table{border-collapse:collapse;width:100%;font-size:12px;margin:12px 0;background:#0f172a}th,td{border:1px solid #334155;padding:5px;text-align:right}th{background:#1e293b}.left{text-align:left}</style></head><body>",
        "<h1>VIX Entry Mode Benchmark v1</h1>",
        "<div class='box'>M0 기계적 TX 진입, M1 TX 종가확인, M2 다음봉 방어, M3 다음 3봉 유지확인을 같은 +X% 돌파 기준에서 비교합니다.</div>",
        "<h2>Entry Mode Summary</h2>",
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
    parser.add_argument("--stops", default=DEFAULT_STOPS)
    parser.add_argument("--target-pct", type=float, default=DEFAULT_TARGET_PCT)
    parser.add_argument("--next1-guard-pct", type=float, default=DEFAULT_NEXT1_GUARD_PCT)
    parser.add_argument("--next3-hold-min", type=int, default=DEFAULT_NEXT3_HOLD_MIN)
    parser.add_argument("--output-dir", default="reports")
    args = parser.parse_args()

    base.load_env(args.env)
    sqlite_path = args.sqlite_db or base.env_value(["SQLITE_1516_DB"])
    if not sqlite_path:
        raise RuntimeError("SQLITE_1516_DB 또는 --sqlite-db가 필요합니다.")

    thresholds = parse_float_list(args.thresholds)
    stops = parse_float_list(args.stops)
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    mysql_conn = base.open_mysql_conn()
    try:
        schema = base.find_candidate_schema(sqlite_conn, args.candidate_table)
        candle_table = base.pick_candle_table(mysql_conn, args.candle_table)
        candidates = base.load_candidates(sqlite_conn, schema, args.start_date, args.end_date, args.condition_name, args.capture_time)

        print("=== VIX Entry Mode Benchmark v1 ===")
        print("candidate_table=" + schema.table)
        print("candle_table=" + candle_table)
        print("candidate_count=" + str(len(candidates)))
        print("thresholds=" + str(thresholds))
        print("stops=" + str(stops))

        candle_cache: Dict[Tuple[str, str], Tuple[List[Dict[str, Any]], Optional[float]]] = {}
        detail_rows: List[Dict[str, Any]] = []
        for i, cand in enumerate(candidates, 1):
            key = (cand["trade_date"], cand["code"])
            if key not in candle_cache:
                candles = base.load_day_candles(mysql_conn, candle_table, cand["code"], cand["trade_date"])
                prev_close = base.previous_close_from_candles(mysql_conn, candle_table, cand["code"], cand["trade_date"])
                candle_cache[key] = (candles, prev_close)
            candles, prev_close = candle_cache[key]
            detail_rows.extend(evaluate_candidate(cand, candles, prev_close, thresholds, stops, args.target_pct, args.next1_guard_pct, args.next3_hold_min))
            if i % 200 == 0:
                print("processed_candidates=" + str(i))

        summary_rows = summarize(detail_rows)
        daily_rows = summarize_daily(detail_rows)
        outdir = Path(args.output_dir)
        write_csv(outdir / "vix_entry_mode_detail_v1.csv", detail_rows)
        write_csv(outdir / "vix_entry_mode_summary_v1.csv", summary_rows)
        write_csv(outdir / "vix_entry_mode_daily_v1.csv", daily_rows)
        build_html(detail_rows, summary_rows, daily_rows, outdir / "vix_entry_mode_benchmark_v1.html")

        print("=== Top Entry Mode Summary ===")
        for row in summary_rows[:20]:
            print(row)
        print("output_detail=" + str((outdir / "vix_entry_mode_detail_v1.csv").resolve()))
        print("output_summary=" + str((outdir / "vix_entry_mode_summary_v1.csv").resolve()))
        print("output_daily=" + str((outdir / "vix_entry_mode_daily_v1.csv").resolve()))
        print("output_html=" + str((outdir / "vix_entry_mode_benchmark_v1.html").resolve()))
        return 0
    finally:
        sqlite_conn.close()
        mysql_conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
