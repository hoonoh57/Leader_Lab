# -*- coding: utf-8 -*-
"""Build VIX Entry Stop-Sweep Benchmark v1.

Stop loss is not fixed. This benchmark sweeps stop-loss values for each
+X% breakout entry threshold and reports the simple expected return.
"""

from __future__ import annotations

import argparse
import csv
import html
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src.review import build_vix_entry_continuation_benchmark_v1 as base


DEFAULT_THRESHOLDS = "10,11,12,13"
DEFAULT_STOPS = "-0.5,-1,-1.5,-2,-2.5,-3,-4,-5,-6,-8"
DEFAULT_TARGET_PCT = 2.0


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
        if v is not None:
            arr.append(v)
    if len(arr) = 0:
        return None
    return sum(arr) / len(arr)


def outcome_pnl_pct(post: Dict[str, Any], target_pct: float, stop_pct: float) -> float:
    label = str(post.get("post_TX_outcome_label") or "")
    if label = "VIX_CONTINUATION_WIN":
        return target_pct
    if label = "VIX_WEAK_REJECT":
        return stop_pct
    return 0.0


def make_no_entry(candidate: Dict[str, Any], threshold_pct: float, stop_pct: float, target_pct: float, label: str) -> Dict[str, Any]:
    return {
        "trade_date": candidate.get("trade_date"),
        "condition_name": candidate.get("condition_name") or "",
        "T_capture": candidate.get("T_capture").isoformat(sep=" "),
        "breakout_threshold_pct": threshold_pct,
        "target_pct": target_pct,
        "stop_loss_pct": stop_pct,
        "code": candidate.get("code"),
        "name": candidate.get("name") or "",
        "TX": None,
        "entry_price": None,
        "prev_close": None,
        "source_max_return_pct": candidate.get("source_max_return_pct"),
        "minutes_capture_to_TX": None,
        "amount_capture_to_TX": None,
        "amount_velocity_per_min": None,
        "pullback_depth_before_TX_pct": None,
        "high_hold_ratio_before_TX": None,
        "return_capture_to_TX_pct": None,
        "post_TX_max_return_pct": None,
        "post_TX_mae_pct": None,
        "post_TX_plus2_success": 0,
        "post_TX_stop_hit": 0,
        "post_TX_first_event": None,
        "post_TX_outcome_label": label,
        "expected_trade_pnl_pct": 0.0,
    }


def evaluate_candidate_stop_sweep(candidate: Dict[str, Any], candles: Sequence[Dict[str, Any]], prev_close: Optional[float], thresholds: Sequence[float], stops: Sequence[float], target_pct: float) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if prev_close is None or prev_close <= 0 or len(candles) = 0:
        for threshold_pct in thresholds:
            for stop_pct in stops:
                rows.append(make_no_entry(candidate, threshold_pct, stop_pct, target_pct, "NO_PREV_CLOSE_OR_CANDLES"))
        return rows

    cap_dt = candidate["T_capture"]
    for threshold_pct in thresholds:
        tx_row = base.first_breakout(candles, prev_close, threshold_pct, cap_dt)
        if tx_row is None:
            for stop_pct in stops:
                rows.append(make_no_entry(candidate, threshold_pct, stop_pct, target_pct, "NO_VIX_ENTRY"))
            continue

        tx = tx_row["TX"]
        entry_price = tx_row["entry_price"]
        pre = base.pre_window_stats(candles, cap_dt, tx, prev_close)
        for stop_pct in stops:
            post = base.post_window_result(candles, tx, entry_price, target_pct, stop_pct)
            out: Dict[str, Any] = {
                "trade_date": candidate.get("trade_date"),
                "condition_name": candidate.get("condition_name") or "",
                "T_capture": cap_dt.isoformat(sep=" "),
                "breakout_threshold_pct": threshold_pct,
                "target_pct": target_pct,
                "stop_loss_pct": stop_pct,
                "code": candidate.get("code"),
                "name": candidate.get("name") or "",
                "TX": tx.isoformat(sep=" "),
                "entry_price": entry_price,
                "prev_close": prev_close,
                "source_max_return_pct": candidate.get("source_max_return_pct"),
                "expected_trade_pnl_pct": outcome_pnl_pct(post, target_pct, stop_pct),
            }
            out.update(pre)
            out.update(post)
            rows.append(out)
    return rows


def summarize_stop_sweep(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[float, float], List[Dict[str, Any]]] = {}
    for r in rows:
        key = (float(r.get("breakout_threshold_pct") or 0.0), float(r.get("stop_loss_pct") or 0.0))
        if key not in groups:
            groups[key] = []
        groups[key].append(r)

    result: List[Dict[str, Any]] = []
    for key in sorted(groups.keys()):
        threshold_pct, stop_pct = key
        rs = groups[key]
        entries: List[Dict[str, Any]] = []
        wins: List[Dict[str, Any]] = []
        rejects: List[Dict[str, Any]] = []
        stalls: List[Dict[str, Any]] = []
        for r in rs:
            if r.get("TX") is not None:
                entries.append(r)
                if int(r.get("post_TX_plus2_success") or 0) = 1:
                    wins.append(r)
                elif str(r.get("post_TX_outcome_label") or "") = "VIX_WEAK_REJECT":
                    rejects.append(r)
                elif str(r.get("post_TX_outcome_label") or "") = "VIX_STALL":
                    stalls.append(r)
        target_pct = float(rs[0].get("target_pct") or DEFAULT_TARGET_PCT)
        gross_win = len(wins) * target_pct
        gross_loss = len(rejects) * abs(stop_pct)
        expected_per_entry = avg([base.safe_float(r.get("expected_trade_pnl_pct")) for r in entries])
        expected_per_candidate = avg([base.safe_float(r.get("expected_trade_pnl_pct")) for r in rs])
        result.append({
            "breakout_threshold_pct": threshold_pct,
            "stop_loss_pct": stop_pct,
            "candidate_rows": len(rs),
            "entry_count": len(entries),
            "entry_rate": len(entries) / len(rs) if len(rs) > 0 else 0.0,
            "plus2_success_count": len(wins),
            "plus2_success_rate": len(wins) / len(entries) if len(entries) > 0 else 0.0,
            "reject_count": len(rejects),
            "reject_rate": len(rejects) / len(entries) if len(entries) > 0 else 0.0,
            "stall_count": len(stalls),
            "stall_rate": len(stalls) / len(entries) if len(entries) > 0 else 0.0,
            "expected_pct_per_entry": expected_per_entry,
            "expected_pct_per_candidate": expected_per_candidate,
            "profit_factor_simple": gross_win / gross_loss if gross_loss > 0 else None,
            "avg_post_TX_max_return_pct": avg([base.safe_float(r.get("post_TX_max_return_pct")) for r in entries]),
            "avg_post_TX_mae_pct": avg([base.safe_float(r.get("post_TX_mae_pct")) for r in entries]),
        })
    result.sort(key=lambda r: base.safe_float(r.get("expected_pct_per_entry")) or -999999.0, reverse=True)
    return result


def summarize_daily(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[str, float, float], List[Dict[str, Any]]] = {}
    for r in rows:
        key = (str(r.get("trade_date")), float(r.get("breakout_threshold_pct") or 0.0), float(r.get("stop_loss_pct") or 0.0))
        if key not in groups:
            groups[key] = []
        groups[key].append(r)
    result: List[Dict[str, Any]] = []
    for key in sorted(groups.keys()):
        trade_date, threshold_pct, stop_pct = key
        rs = groups[key]
        entries = [r for r in rs if r.get("TX") is not None]
        wins = [r for r in entries if int(r.get("post_TX_plus2_success") or 0) = 1]
        rejects = [r for r in entries if str(r.get("post_TX_outcome_label") or "") = "VIX_WEAK_REJECT"]
        result.append({
            "trade_date": trade_date,
            "breakout_threshold_pct": threshold_pct,
            "stop_loss_pct": stop_pct,
            "candidate_count": len(rs),
            "entry_count": len(entries),
            "plus2_success_count": len(wins),
            "plus2_success_rate": len(wins) / len(entries) if len(entries) > 0 else 0.0,
            "reject_count": len(rejects),
            "reject_rate": len(rejects) / len(entries) if len(entries) > 0 else 0.0,
            "expected_pct_per_entry": avg([base.safe_float(r.get("expected_trade_pnl_pct")) for r in entries]),
        })
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


def fmt_num(v: Any, d: int = 2) -> str:
    x = base.safe_float(v)
    if x is None:
        return "-"
    return f"{x:.{d}f}"


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
            v = r.get(f)
            if f.endswith("rate"):
                text = fmt_rate(v)
            elif f in ("expected_pct_per_entry", "expected_pct_per_candidate", "profit_factor_simple") or f.endswith("pct"):
                text = fmt_num(v)
            elif "amount" in f and base.safe_float(v) is not None:
                text = fmt_num((base.safe_float(v) or 0.0) / 100000000.0) + "억"
            else:
                text = "-" if v is None else str(v)
            align = "left" if f in ("name", "post_TX_outcome_label") else ""
            parts.append("<td class='" + align + "'>" + html.escape(text) + "</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def build_html(summary: Sequence[Dict[str, Any]], daily: Sequence[Dict[str, Any]], detail: Sequence[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    top_detail = [r for r in detail if r.get("TX") is not None]
    top_detail.sort(key=lambda r: base.safe_float(r.get("expected_trade_pnl_pct")) or -999999.0, reverse=True)
    top_detail = top_detail[:300]
    summary_fields = ["breakout_threshold_pct", "stop_loss_pct", "candidate_rows", "entry_count", "entry_rate", "plus2_success_count", "plus2_success_rate", "reject_count", "reject_rate", "stall_count", "stall_rate", "expected_pct_per_entry", "expected_pct_per_candidate", "profit_factor_simple", "avg_post_TX_max_return_pct", "avg_post_TX_mae_pct"]
    daily_fields = ["trade_date", "breakout_threshold_pct", "stop_loss_pct", "candidate_count", "entry_count", "plus2_success_count", "plus2_success_rate", "reject_count", "reject_rate", "expected_pct_per_entry"]
    detail_fields = ["trade_date", "breakout_threshold_pct", "stop_loss_pct", "code", "name", "T_capture", "TX", "minutes_capture_to_TX", "amount_capture_to_TX", "amount_velocity_per_min", "post_TX_max_return_pct", "post_TX_mae_pct", "post_TX_outcome_label", "expected_trade_pnl_pct"]
    html_text = "\n".join([
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'><title>VIX Entry Stop Sweep v1</title>",
        "<style>body{font-family:Segoe UI,Malgun Gothic,Arial;background:#111827;color:#e5e7eb;margin:0;padding:18px}h1,h2{color:#fbbf24}.box{border:1px solid #334155;border-radius:10px;padding:12px;background:#0f172a;margin-bottom:12px}table{border-collapse:collapse;width:100%;font-size:12px;margin:12px 0;background:#0f172a}th,td{border:1px solid #334155;padding:5px;text-align:right}th{background:#1e293b}.left{text-align:left}</style></head><body>",
        "<h1>VIX Entry Stop Sweep v1</h1>",
        "<div class='box'>손절률 S를 고정하지 않고 +X% 돌파 진입 기준과 함께 sweep합니다. expected_pct_per_entry = target 성공은 +P%, stop hit는 S%, stall은 0으로 본 단순 기대값입니다.</div>",
        "<h2>Stop Sweep Summary</h2>",
        table_html(summary, summary_fields),
        "<h2>Daily Summary</h2>",
        table_html(daily[:500], daily_fields),
        "<h2>Top Detail Sample</h2>",
        table_html(top_detail, detail_fields),
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

        print("=== VIX Entry Stop Sweep v1 ===")
        print("sqlite_db=" + str(sqlite_path))
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
            detail_rows.extend(evaluate_candidate_stop_sweep(cand, candles, prev_close, thresholds, stops, args.target_pct))
            if i % 200 = 0:
                print("processed_candidates=" + str(i))

        summary_rows = summarize_stop_sweep(detail_rows)
        daily_rows = summarize_daily(detail_rows)

        outdir = Path(args.output_dir)
        write_csv(outdir / "vix_entry_stop_sweep_detail_v1.csv", detail_rows)
        write_csv(outdir / "vix_entry_stop_sweep_summary_v1.csv", summary_rows)
        write_csv(outdir / "vix_entry_stop_sweep_daily_v1.csv", daily_rows)
        build_html(summary_rows, daily_rows, detail_rows, outdir / "vix_entry_stop_sweep_v1.html")

        print("=== Top Stop Sweep Summary ===")
        for r in summary_rows[:20]:
            print(r)
        print("output_detail=" + str((outdir / "vix_entry_stop_sweep_detail_v1.csv").resolve()))
        print("output_summary=" + str((outdir / "vix_entry_stop_sweep_summary_v1.csv").resolve()))
        print("output_daily=" + str((outdir / "vix_entry_stop_sweep_daily_v1.csv").resolve()))
        print("output_html=" + str((outdir / "vix_entry_stop_sweep_v1.html").resolve()))
        return 0
    finally:
        sqlite_conn.close()
        mysql_conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
