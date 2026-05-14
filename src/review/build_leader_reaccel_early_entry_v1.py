# -*- coding: utf-8 -*-
"""Clean early-entry diagnostic for Leader Reaccel v1.

This script is intentionally independent from the patched parametric engine.
It diagnoses why the previous engine selected late entries such as 12:00.

Entry focus:
    close > SMA20
    RSI(14) crosses/reclaims 60 or 65, or is already above reclaim after cooldown
    day close return from previous day close >= 10 OR single bar return >= 3
    bar amount >= 1B OR intraday cumulative amount >= 5B

Outputs:
    reports/leader_reaccel_early_entry_detail_v1.csv
    reports/leader_reaccel_early_entry_bar_trace_v1.csv
    reports/leader_reaccel_early_entry_summary_v1.csv
    reports/leader_reaccel_early_entry_v1.html
"""

from __future__ import annotations

import argparse
import csv
import html
import sqlite3
from datetime import datetime, timedelta, time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from src.review import build_vix_entry_continuation_benchmark_v1 as base
from src.review import build_rsi70_ma20_amount_breakout_v1 as rsi_base


def parse_float_list(text: str) -> List[float]:
    out: List[float] = []
    for raw in text.split(","):
        item = raw.strip()
        if item:
            out.append(float(item))
    return out


def parse_int_list(text: str) -> List[int]:
    return [int(x) for x in parse_float_list(text)]


def get_num(row: Dict[str, Any], key: str) -> Optional[float]:
    return base.safe_float(row.get(key))


def candle_dt(row: Dict[str, Any]) -> Optional[datetime]:
    return base.candle_dt(row)


def pct(price: Optional[float], base_price: Optional[float]) -> Optional[float]:
    if price is None or base_price is None or base_price <= 0:
        return None
    return (price / base_price - 1.0) * 100.0


def safe_avg(values: Iterable[Optional[float]]) -> Optional[float]:
    arr: List[float] = []
    for v in values:
        if v is not None:
            arr.append(v)
    if not arr:
        return None
    return sum(arr) / float(len(arr))


def load_recent_candles(conn: Any, candle_table: str, code: str, trade_date: str, lookback_calendar_days: int) -> List[Dict[str, Any]]:
    d = base.parse_date(trade_date)
    if d is None:
        return []
    start_dt = datetime.combine(d - timedelta(days=lookback_calendar_days), time(0, 0))
    end_dt = datetime.combine(d, time(15, 30))
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT candle_time, open, high, low, close, volume
            FROM `{candle_table}`
            WHERE code=%s AND candle_time >= %s AND candle_time <= %s
            ORDER BY candle_time
            """,
            (code, start_dt, end_dt),
        )
        return list(cur.fetchall())


def prev_day_close(candles: Sequence[Dict[str, Any]], trade_date: str) -> Optional[float]:
    d = base.parse_date(trade_date)
    if d is None:
        return None
    result: Optional[float] = None
    for row in candles:
        ts = candle_dt(row)
        if ts is None:
            continue
        if ts.date() < d:
            close = get_num(row, "close")
            if close is not None and close > 0:
                result = close
        elif ts.date() == d:
            break
    return result


def close_position(row: Dict[str, Any]) -> Optional[float]:
    h = get_num(row, "high")
    l = get_num(row, "low")
    c = get_num(row, "close")
    if h is None or l is None or c is None or h <= l:
        return None
    return (c - l) / (h - l)


def find_candidate_schema(conn: sqlite3.Connection, requested: Optional[str]) -> base.CandidateSchema:
    return base.find_candidate_schema(conn, requested)


def load_candidates(conn: sqlite3.Connection, schema: base.CandidateSchema, args: argparse.Namespace) -> List[Dict[str, Any]]:
    if args.trade_date:
        args.start_date = args.trade_date
        args.end_date = args.trade_date
    return base.load_candidates(conn, schema, args.start_date, args.end_date, args.condition_name, args.capture_time)


def build_bar_trace(candidate: Dict[str, Any], candles: Sequence[Dict[str, Any]], args: argparse.Namespace) -> List[Dict[str, Any]]:
    d = base.parse_date(candidate["trade_date"])
    if d is None or not candles:
        return []

    closes: List[float] = [(get_num(r, "close") or 0.0) for r in candles]
    sma = rsi_base.calc_sma(closes, args.trend_period)
    rsi = rsi_base.calc_rsi_wilder(closes, args.rsi_period)
    prev_close = prev_day_close(candles, candidate["trade_date"])
    cum_amount = 0.0
    trace: List[Dict[str, Any]] = []
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
        c = get_num(row, "close")
        pc = get_num(candles[i - 1], "close")
        bar_return = pct(c, pc)
        day_return = pct(c, prev_close)
        ma = sma[i]
        rsi_prev = rsi[i - 1]
        rsi_now = rsi[i]
        amount_ok = amount >= args.bar_amount_min or cum_amount >= args.cum_amount_min
        trend_ok = c is not None and ma is not None and c > ma
        day_or_bar_ok = False
        if bar_return is not None and bar_return >= args.bar_return_min_pct:
            day_or_bar_ok = True
        if day_return is not None and day_return >= args.day_close_return_min_pct:
            day_or_bar_ok = True
        for reclaim in parse_float_list(args.rsi_reclaim_levels):
            cross = rsi_prev is not None and rsi_now is not None and rsi_prev <= reclaim and rsi_now > reclaim
            early_state = rsi_now is not None and rsi_now >= reclaim and trend_ok and day_or_bar_ok and amount_ok
            signal_ok = trend_ok and amount_ok and day_or_bar_ok and (cross or (args.allow_already_reclaimed and early_state))
            fail_reasons: List[str] = []
            if not trend_ok:
                fail_reasons.append("NO_TREND")
            if not amount_ok:
                fail_reasons.append("NO_AMOUNT")
            if not day_or_bar_ok:
                fail_reasons.append("NO_DAY_OR_BAR_RETURN")
            if not cross and not (args.allow_already_reclaimed and early_state):
                fail_reasons.append("NO_RSI_RECLAIM")
            entry_row = candles[i + 1]
            trace.append({
                "trade_date": candidate.get("trade_date"),
                "code": candidate.get("code"),
                "name": candidate.get("name") or "",
                "bar_index": i,
                "bar_time": ts.isoformat(sep=" "),
                "reclaim_level": reclaim,
                "open": get_num(row, "open"),
                "high": get_num(row, "high"),
                "low": get_num(row, "low"),
                "close": c,
                "sma": ma,
                "rsi_prev": rsi_prev,
                "rsi_now": rsi_now,
                "rsi_cross_flag": 1 if cross else 0,
                "bar_return_pct": bar_return,
                "day_close_return_pct": day_return,
                "bar_amount": amount,
                "cum_amount": cum_amount,
                "close_position": close_position(row),
                "trend_ok": 1 if trend_ok else 0,
                "amount_ok": 1 if amount_ok else 0,
                "day_or_bar_ok": 1 if day_or_bar_ok else 0,
                "signal_ok": 1 if signal_ok else 0,
                "fail_reasons": "|".join(fail_reasons),
                "entry_time": candle_dt(entry_row).isoformat(sep=" ") if candle_dt(entry_row) is not None else None,
                "entry_price": get_num(entry_row, "open"),
            })
    return trace


def first_signals_from_trace(trace: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: Dict[str, Dict[str, Any]] = {}
    for row in trace:
        if int(row.get("signal_ok") or 0) != 1:
            continue
        key = f"{row.get('trade_date')}|{row.get('code')}|{row.get('reclaim_level')}"
        if key not in seen:
            out = dict(row)
            out["signal_time"] = out.get("bar_time")
            seen[key] = out
    return list(seen.values())


def summarize(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        key = str(row.get("reclaim_level"))
        groups.setdefault(key, []).append(row)
    out: List[Dict[str, Any]] = []
    for key, rs in sorted(groups.items()):
        out.append({
            "reclaim_level": key,
            "signal_count": len(rs),
            "avg_signal_time": "",
            "avg_bar_return_pct": safe_avg([base.safe_float(r.get("bar_return_pct")) for r in rs]),
            "avg_day_close_return_pct": safe_avg([base.safe_float(r.get("day_close_return_pct")) for r in rs]),
            "avg_bar_amount_eok": safe_avg([(base.safe_float(r.get("bar_amount")) or 0.0) / 100000000.0 for r in rs]),
            "avg_cum_amount_eok": safe_avg([(base.safe_float(r.get("cum_amount")) or 0.0) / 100000000.0 for r in rs]),
        })
    return out


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


def fmt(v: Any) -> str:
    if v is None:
        return "-"
    x = base.safe_float(v)
    if x is not None:
        return f"{x:.2f}"
    return str(v)


def table_html(rows: Sequence[Dict[str, Any]], fields: Sequence[str]) -> str:
    parts = ["<table><thead><tr>"]
    for f in fields:
        parts.append("<th>" + html.escape(f) + "</th>")
    parts.append("</tr></thead><tbody>")
    for row in rows:
        parts.append("<tr>")
        for f in fields:
            parts.append("<td>" + html.escape(fmt(row.get(f))) + "</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def build_html(detail: Sequence[Dict[str, Any]], trace: Sequence[Dict[str, Any]], summary: Sequence[Dict[str, Any]], path: Path) -> None:
    fields_detail = ["trade_date", "code", "name", "reclaim_level", "signal_time", "entry_time", "rsi_prev", "rsi_now", "bar_return_pct", "day_close_return_pct", "bar_amount", "cum_amount", "fail_reasons"]
    fields_trace = ["trade_date", "code", "name", "bar_time", "reclaim_level", "close", "sma", "rsi_prev", "rsi_now", "rsi_cross_flag", "bar_return_pct", "day_close_return_pct", "bar_amount", "cum_amount", "signal_ok", "fail_reasons"]
    fields_summary = ["reclaim_level", "signal_count", "avg_bar_return_pct", "avg_day_close_return_pct", "avg_bar_amount_eok", "avg_cum_amount_eok"]
    html_text = "\n".join([
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'><title>Leader Reaccel Early Entry v1</title>",
        "<style>body{font-family:Segoe UI,Malgun Gothic,Arial;background:#111827;color:#e5e7eb;padding:18px}h1,h2{color:#fbbf24}table{border-collapse:collapse;width:100%;font-size:12px;background:#0f172a;margin:12px 0}th,td{border:1px solid #334155;padding:5px;text-align:right}th{background:#1e293b}</style></head><body>",
        "<h1>Leader Reaccel Early Entry v1</h1>",
        "<p>Late-entry bug isolation: every candidate bar is traced with pass/fail reasons.</p>",
        "<h2>Summary</h2>", table_html(summary, fields_summary),
        "<h2>First Valid Signals</h2>", table_html(detail, fields_detail),
        "<h2>Bar Trace Sample</h2>", table_html(trace[:2000], fields_trace),
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
    parser.add_argument("--code", default=None)
    parser.add_argument("--trend-period", type=int, default=20)
    parser.add_argument("--rsi-period", type=int, default=14)
    parser.add_argument("--rsi-reclaim-levels", default="60,65")
    parser.add_argument("--bar-return-min-pct", type=float, default=3.0)
    parser.add_argument("--day-close-return-min-pct", type=float, default=10.0)
    parser.add_argument("--bar-amount-min", type=float, default=1000000000.0)
    parser.add_argument("--cum-amount-min", type=float, default=5000000000.0)
    parser.add_argument("--lookback-calendar-days", type=int, default=20)
    parser.add_argument("--allow-already-reclaimed", action="store_true")
    parser.add_argument("--output-dir", default="reports")
    args = parser.parse_args()

    base.load_env(args.env)
    sqlite_path = args.sqlite_db or base.env_value(["SQLITE_1516_DB"])
    if not sqlite_path:
        raise RuntimeError("SQLITE_1516_DB 또는 --sqlite-db가 필요합니다.")

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row
    mysql_conn = base.open_mysql_conn()
    try:
        schema = find_candidate_schema(sqlite_conn, args.candidate_table)
        candle_table = base.pick_candle_table(mysql_conn, args.candle_table)
        candidates = load_candidates(sqlite_conn, schema, args)
        if args.code:
            candidates = [c for c in candidates if str(c.get("code")) == args.code]
        print("=== Leader Reaccel Early Entry v1 ===")
        print("candidate_table=" + schema.table)
        print("candle_table=" + candle_table)
        print("candidate_count=" + str(len(candidates)))

        all_trace: List[Dict[str, Any]] = []
        for idx, cand in enumerate(candidates, 1):
            candles = load_recent_candles(mysql_conn, candle_table, cand["code"], cand["trade_date"], args.lookback_calendar_days)
            trace = build_bar_trace(cand, candles, args)
            all_trace.extend(trace)
            print(f"candidate {idx}/{len(candidates)} {cand.get('trade_date')} {cand.get('code')} {cand.get('name') or ''} trace={len(trace)}")

        detail = first_signals_from_trace(all_trace)
        summary = summarize(detail)
        outdir = Path(args.output_dir)
        write_csv(outdir / "leader_reaccel_early_entry_bar_trace_v1.csv", all_trace)
        write_csv(outdir / "leader_reaccel_early_entry_detail_v1.csv", detail)
        write_csv(outdir / "leader_reaccel_early_entry_summary_v1.csv", summary)
        build_html(detail, all_trace, summary, outdir / "leader_reaccel_early_entry_v1.html")
        print("signal_count=" + str(len(detail)))
        print("output_html=" + str((outdir / "leader_reaccel_early_entry_v1.html").resolve()))
        return 0
    finally:
        sqlite_conn.close()
        mysql_conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
