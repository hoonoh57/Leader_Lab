# -*- coding: utf-8 -*-
"""Leader Reaccel Bullish RSI Reclaim Backtest v1.

Clean replacement for the late-entry RSI70 / single-bar-spike logic.

Entry signal:
    1. close > SMA20
    2. RSI(14) crosses above reclaim level, default 60
    3. candle is bullish: close > open
    4. day close return from previous day close >= 10%
    5. participation: bar amount >= 1B or intraday cumulative amount >= 5B
    6. optional recent high-rise context, default disabled for timing diagnosis

Execution:
    next bar open after signal bar.

Exit:
    promoted partial/trailing exit via rsi_base.evaluate_exit
    P1=3, Q=0.3, trail=1, ST=14/3, JMA=7/50/2

Outputs:
    reports/leader_reaccel_bullish_rsi_reclaim_detail_v1.csv
    reports/leader_reaccel_bullish_rsi_reclaim_summary_v1.csv
    reports/leader_reaccel_bullish_rsi_reclaim_daily_v1.csv
    reports/leader_reaccel_bullish_rsi_reclaim_v1.html
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


def parse_float_list(text: str) -> List[float]:
    result: List[float] = []
    for raw in text.split(","):
        item = raw.strip()
        if item:
            result.append(float(item))
    return result


def get_num(row: Dict[str, Any], key: str) -> Optional[float]:
    return base.safe_float(row.get(key))


def candle_dt(row: Dict[str, Any]) -> Optional[datetime]:
    return base.candle_dt(row)


def pct(price: Optional[float], base_price: Optional[float]) -> Optional[float]:
    if price is None or base_price is None or base_price <= 0:
        return None
    return (price / base_price - 1.0) * 100.0


def safe_avg(values: Iterable[Optional[float]]) -> Optional[float]:
    arr: List[float] = [v for v in values if v is not None]
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
            close_value = get_num(row, "close")
            if close_value is not None and close_value > 0:
                result = close_value
        elif ts.date() == d:
            break
    return result


def first_day_open_return(candles: Sequence[Dict[str, Any]], trade_date: str, prev_close: Optional[float]) -> Optional[float]:
    d = base.parse_date(trade_date)
    if d is None or prev_close is None:
        return None
    for row in candles:
        ts = candle_dt(row)
        if ts is not None and ts.date() == d:
            return pct(get_num(row, "open"), prev_close)
    return None


def find_first_signal(candidate: Dict[str, Any], candles: Sequence[Dict[str, Any]], args: argparse.Namespace, reclaim_level: float) -> Optional[Dict[str, Any]]:
    d = base.parse_date(candidate["trade_date"])
    if d is None or len(candles) < args.sma_period + args.rsi_period + 2:
        return None

    closes: List[float] = [(get_num(row, "close") or 0.0) for row in candles]
    sma = rsi_base.calc_sma(closes, args.sma_period)
    rsi = rsi_base.calc_rsi_wilder(closes, args.rsi_period)
    prev_close = prev_day_close(candles, candidate["trade_date"])
    first_open_ret = first_day_open_return(candles, candidate["trade_date"], prev_close)
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

        op = get_num(row, "open")
        close = get_num(row, "close")
        prev_bar_close = get_num(candles[i - 1], "close")
        ma = sma[i]
        rsi_prev = rsi[i - 1]
        rsi_now = rsi[i]
        if op is None or close is None or prev_bar_close is None or ma is None or rsi_prev is None or rsi_now is None:
            continue

        trend_ok = close > ma
        rsi_cross_ok = rsi_prev <= reclaim_level and rsi_now > reclaim_level
        bullish_ok = close > op
        day_return = pct(close, prev_close)
        day_return_ok = day_return is not None and day_return >= args.day_close_return_min_pct
        amount_ok = amount >= args.bar_amount_min or cum_amount >= args.cum_amount_min
        high_rise = rsi_base.last5d_high_rise_until(candles, i, candidate["trade_date"])
        context_ok = True
        if args.high_rise_min_pct > 0:
            context_ok = high_rise is not None and high_rise >= args.high_rise_min_pct
        extension_ok = True
        if args.exclude_first_open_return_gte > 0 and first_open_ret is not None:
            extension_ok = first_open_ret < args.exclude_first_open_return_gte

        if trend_ok and rsi_cross_ok and bullish_ok and day_return_ok and amount_ok and context_ok and extension_ok:
            entry_row = candles[i + 1]
            entry_time = candle_dt(entry_row)
            entry_price = get_num(entry_row, "open")
            if entry_time is None or entry_price is None or entry_price <= 0:
                continue
            return {
                "signal_idx": i,
                "signal_time": ts.isoformat(sep=" "),
                "entry_idx": i + 1,
                "entry_time": entry_time.isoformat(sep=" "),
                "entry_price": entry_price,
                "reclaim_level": reclaim_level,
                "open": op,
                "close": close,
                "sma": ma,
                "rsi_prev": rsi_prev,
                "rsi_now": rsi_now,
                "bar_return_pct": pct(close, prev_bar_close),
                "day_close_return_pct": day_return,
                "bar_amount": amount,
                "cum_amount": cum_amount,
                "last5d_high_rise_pct": high_rise,
                "first_day_open_return_pct": first_open_ret,
            }
    return None


def evaluate_candidate(candidate: Dict[str, Any], candles: Sequence[Dict[str, Any]], args: argparse.Namespace, reclaim_level: float) -> Optional[Dict[str, Any]]:
    signal = find_first_signal(candidate, candles, args, reclaim_level)
    if signal is None:
        return None
    exit_result = rsi_base.evaluate_exit(
        candles=candles,
        entry_idx=int(signal["entry_idx"]),
        entry_price=float(signal["entry_price"]),
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
        "trade_date": candidate.get("trade_date"),
        "condition_name": candidate.get("condition_name") or "",
        "code": candidate.get("code"),
        "name": candidate.get("name") or "",
        "T_capture": candidate["T_capture"].isoformat(sep=" "),
        "entry_rule": "close_gt_sma20_and_rsi_cross_reclaim_and_bullish_and_day_return",
        **signal,
    }
    row.update(exit_result)
    return row


def summarize(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        key = str(row.get("reclaim_level"))
        groups.setdefault(key, []).append(row)
    out: List[Dict[str, Any]] = []
    for key, rs in sorted(groups.items()):
        wins = [r for r in rs if (base.safe_float(r.get("realized_pnl_pct")) or 0.0) > 0]
        losses = [r for r in rs if (base.safe_float(r.get("realized_pnl_pct")) or 0.0) < 0]
        gross_win = sum([(base.safe_float(r.get("realized_pnl_pct")) or 0.0) for r in wins])
        gross_loss = abs(sum([(base.safe_float(r.get("realized_pnl_pct")) or 0.0) for r in losses]))
        out.append({
            "reclaim_level": key,
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
            "avg_signal_day_return_pct": safe_avg([base.safe_float(r.get("day_close_return_pct")) for r in rs]),
        })
    return out


def summarize_daily(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row.get("trade_date")), []).append(row)
    out: List[Dict[str, Any]] = []
    for day, rs in sorted(groups.items()):
        out.append({
            "trade_date": day,
            "entry_count": len(rs),
            "avg_realized_pnl_pct": safe_avg([base.safe_float(r.get("realized_pnl_pct")) for r in rs]),
            "total_realized_pnl_pct": sum([(base.safe_float(r.get("realized_pnl_pct")) or 0.0) for r in rs]),
        })
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


def fmt(v: Any) -> str:
    x = base.safe_float(v)
    if x is not None:
        return f"{x:.2f}"
    return "-" if v is None else str(v)


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


def build_html(detail: Sequence[Dict[str, Any]], summary: Sequence[Dict[str, Any]], daily: Sequence[Dict[str, Any]], path: Path) -> None:
    summary_fields = ["reclaim_level", "entry_count", "win_rate", "avg_realized_pnl_pct", "total_realized_pnl_pct", "profit_factor", "avg_mfe_pct", "avg_mae_pct", "avg_signal_day_return_pct"]
    detail_fields = ["trade_date", "code", "name", "reclaim_level", "signal_time", "entry_time", "rsi_prev", "rsi_now", "open", "close", "sma", "day_close_return_pct", "bar_amount", "cum_amount", "realized_pnl_pct", "max_favorable_excursion_pct", "max_adverse_excursion_pct"]
    daily_fields = ["trade_date", "entry_count", "avg_realized_pnl_pct", "total_realized_pnl_pct"]
    html_text = "\n".join([
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'><title>Leader Reaccel Bullish RSI Reclaim v1</title>",
        "<style>body{font-family:Segoe UI,Malgun Gothic,Arial;background:#111827;color:#e5e7eb;padding:18px}h1,h2{color:#fbbf24}table{border-collapse:collapse;width:100%;font-size:12px;background:#0f172a;margin:12px 0}th,td{border:1px solid #334155;padding:5px;text-align:right}th{background:#1e293b}</style></head><body>",
        "<h1>Leader Reaccel Bullish RSI Reclaim v1</h1>",
        "<p>Entry: close &gt; SMA20, RSI cross reclaim, bullish candle, day close return &gt;= threshold, amount condition.</p>",
        "<h2>Summary</h2>", table_html(summary, summary_fields),
        "<h2>Daily</h2>", table_html(daily, daily_fields),
        "<h2>Detail</h2>", table_html(detail[:1000], detail_fields),
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
    parser.add_argument("--sma-period", type=int, default=20)
    parser.add_argument("--rsi-period", type=int, default=14)
    parser.add_argument("--rsi-reclaim-levels", default="60")
    parser.add_argument("--day-close-return-min-pct", type=float, default=10.0)
    parser.add_argument("--bar-amount-min", type=float, default=1000000000.0)
    parser.add_argument("--cum-amount-min", type=float, default=5000000000.0)
    parser.add_argument("--high-rise-min-pct", type=float, default=0.0)
    parser.add_argument("--exclude-first-open-return-gte", type=float, default=0.0)
    parser.add_argument("--lookback-calendar-days", type=int, default=20)
    parser.add_argument("--p1", type=float, default=3.0)
    parser.add_argument("--p2", type=float, default=6.0)
    parser.add_argument("--q", type=float, default=0.3)
    parser.add_argument("--trail", type=float, default=1.0)
    parser.add_argument("--jma-period", type=int, default=7)
    parser.add_argument("--jma-phase", type=int, default=50)
    parser.add_argument("--jma-power", type=int, default=2)
    parser.add_argument("--st-period", type=int, default=14)
    parser.add_argument("--st-multiplier", type=float, default=3.0)
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
        if args.code:
            candidates = [c for c in candidates if str(c.get("code")) == args.code]
        print("=== Leader Reaccel Bullish RSI Reclaim v1 ===")
        print("candidate_table=" + schema.table)
        print("candle_table=" + candle_table)
        print("candidate_count=" + str(len(candidates)))
        detail: List[Dict[str, Any]] = []
        reclaim_levels = parse_float_list(args.rsi_reclaim_levels)
        for idx, cand in enumerate(candidates, 1):
            candles = load_recent_candles(mysql_conn, candle_table, cand["code"], cand["trade_date"], args.lookback_calendar_days)
            for reclaim in reclaim_levels:
                row = evaluate_candidate(cand, candles, args, reclaim)
                if row is not None:
                    detail.append(row)
            print(f"candidate {idx}/{len(candidates)} {cand.get('trade_date')} {cand.get('code')} {cand.get('name') or ''} signals={len(detail)}")
        summary = summarize(detail)
        daily = summarize_daily(detail)
        outdir = Path(args.output_dir)
        write_csv(outdir / "leader_reaccel_bullish_rsi_reclaim_detail_v1.csv", detail)
        write_csv(outdir / "leader_reaccel_bullish_rsi_reclaim_summary_v1.csv", summary)
        write_csv(outdir / "leader_reaccel_bullish_rsi_reclaim_daily_v1.csv", daily)
        build_html(detail, summary, daily, outdir / "leader_reaccel_bullish_rsi_reclaim_v1.html")
        print("signal_count=" + str(len(detail)))
        print("output_html=" + str((outdir / "leader_reaccel_bullish_rsi_reclaim_v1.html").resolve()))
        return 0
    finally:
        sqlite_conn.close()
        mysql_conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
