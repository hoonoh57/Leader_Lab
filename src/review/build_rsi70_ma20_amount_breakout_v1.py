# -*- coding: utf-8 -*-
"""Build RSI70 + MA20 + Amount Breakout Strategy Benchmark v1.

Entry signal on 5-minute candles:
    1. close > SMA20(close)
    2. crossup(RSI14, 70)
    3. single 5-minute bar close return > 3%
    4. bar amount >= 1 billion KRW OR intraday cumulative amount >= 5 billion KRW
    5. last 5 trading days available high-rise rate > 10%

Execution:
    Default entry = next bar open after the signal bar.

Exit:
    Reuse promoted VIX_JMA_PARTIAL_TRAIL_v1 style:
        P1 = +3%, JMA(7,50,2) down => sell Q=30%.
        Remainder 70% exits by 1% trailing from post-partial high or SuperTrend(14,3) down.
        Day-end close if still open.

Outputs:
    reports/rsi70_ma20_amount_breakout_detail_v1.csv
    reports/rsi70_ma20_amount_breakout_summary_v1.csv
    reports/rsi70_ma20_amount_breakout_daily_v1.csv
    reports/rsi70_ma20_amount_breakout_v1.html
"""

from __future__ import annotations

import argparse
import csv
import html
import sqlite3
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from src.review import build_vix_entry_continuation_benchmark_v1 as base
from src.review import build_vix_jma_partial_st_remainder_v1 as partial
from src.review import build_vix_entry_jma_st_hold_overlay_v1 as core


DEFAULT_SMA_PERIOD = 20
DEFAULT_RSI_PERIOD = 14
DEFAULT_RSI_CROSS_LEVEL = 70.0
DEFAULT_BAR_RETURN_MIN_PCT = 3.0
DEFAULT_BAR_AMOUNT_MIN = 1000000000.0
DEFAULT_CUM_AMOUNT_MIN = 5000000000.0
DEFAULT_LAST5D_HIGH_RISE_MIN_PCT = 10.0
DEFAULT_P1 = 3.0
DEFAULT_P2 = 6.0
DEFAULT_Q = 0.3
DEFAULT_TRAIL = 1.0
DEFAULT_JMA_PERIOD = 7
DEFAULT_JMA_PHASE = 50
DEFAULT_JMA_POWER = 2
DEFAULT_ST_PERIOD = 14
DEFAULT_ST_MULTIPLIER = 3.0


def safe_avg(values: Iterable[Optional[float]]) -> Optional[float]:
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


def get_num(row: Dict[str, Any], key: str) -> Optional[float]:
    return base.safe_float(row.get(key))


def candle_dt(row: Dict[str, Any]) -> Optional[datetime]:
    return base.candle_dt(row)


def row_amount(row: Dict[str, Any]) -> float:
    return base.amount_from_candle(row)


def load_recent_candles(conn: Any, candle_table: str, code: str, trade_date: str, lookback_calendar_days: int) -> List[Dict[str, Any]]:
    d = base.parse_date(trade_date)
    if d is None:
        return []
    start_day = d - timedelta(days=lookback_calendar_days)
    start_dt = datetime.combine(start_day, time(0, 0, 0))
    end_dt = datetime.combine(d, time(15, 30, 0))
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
        rows = list(cur.fetchall())
    return rows


def calc_sma(values: Sequence[float], period: int) -> List[Optional[float]]:
    result: List[Optional[float]] = [None] * len(values)
    rolling = 0.0
    for i, value in enumerate(values):
        rolling += value
        if i >= period:
            rolling -= values[i - period]
        if i >= period - 1:
            result[i] = rolling / float(period)
    return result


def calc_rsi_wilder(values: Sequence[float], period: int) -> List[Optional[float]]:
    n = len(values)
    result: List[Optional[float]] = [None] * n
    if n <= period:
        return result
    gains: List[float] = [0.0] * n
    losses: List[float] = [0.0] * n
    for i in range(1, n):
        diff = values[i] - values[i - 1]
        gains[i] = diff if diff > 0 else 0.0
        losses[i] = -diff if diff < 0 else 0.0
    avg_gain = sum(gains[1 : period + 1]) / float(period)
    avg_loss = sum(losses[1 : period + 1]) / float(period)
    result[period] = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
    for i in range(period + 1, n):
        avg_gain = ((avg_gain * (period - 1)) + gains[i]) / float(period)
        avg_loss = ((avg_loss * (period - 1)) + losses[i]) / float(period)
        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100.0 - (100.0 / (1.0 + rs))
    return result


def last5d_high_rise_until(candles: Sequence[Dict[str, Any]], signal_idx: int, trade_date_text: str) -> Optional[float]:
    if signal_idx < 0 or signal_idx >= len(candles):
        return None
    d = base.parse_date(trade_date_text)
    if d is None:
        return None
    day_keys: List[date] = []
    for i in range(0, signal_idx + 1):
        ts = candle_dt(candles[i])
        if ts is None:
            continue
        dd = ts.date()
        if dd not in day_keys and dd <= d:
            day_keys.append(dd)
    day_keys.sort()
    last_days = day_keys[-5:]
    highs: List[float] = []
    lows: List[float] = []
    for i in range(0, signal_idx + 1):
        ts = candle_dt(candles[i])
        if ts is None or ts.date() not in last_days:
            continue
        h = get_num(candles[i], "high")
        l = get_num(candles[i], "low")
        if h is not None and h > 0:
            highs.append(h)
        if l is not None and l > 0:
            lows.append(l)
    if len(highs) == 0 or len(lows) == 0:
        return None
    low_min = min(lows)
    high_max = max(highs)
    if low_min <= 0:
        return None
    return (high_max / low_min - 1.0) * 100.0


def find_signal(
    candles: Sequence[Dict[str, Any]],
    trade_date_text: str,
    capture_dt: datetime,
    sma_period: int,
    rsi_period: int,
    rsi_cross_level: float,
    bar_return_min_pct: float,
    bar_amount_min: float,
    cum_amount_min: float,
    last5d_high_rise_min_pct: float,
) -> Optional[Dict[str, Any]]:
    closes: List[float] = []
    for row in candles:
        close = get_num(row, "close")
        closes.append(close if close is not None else 0.0)
    sma = calc_sma(closes, sma_period)
    rsi = calc_rsi_wilder(closes, rsi_period)

    d = base.parse_date(trade_date_text)
    if d is None:
        return None
    cum_amount = 0.0
    for i, row in enumerate(candles):
        ts = candle_dt(row)
        if ts is None:
            continue
        if ts.date() != d:
            continue
        amt = row_amount(row)
        cum_amount += amt
        if ts < capture_dt:
            continue
        if i <= 0 or i + 1 >= len(candles):
            continue
        signal_close = get_num(row, "close")
        prev_close = get_num(candles[i - 1], "close")
        if signal_close is None or prev_close is None or prev_close <= 0:
            continue
        ma20 = sma[i]
        rsi_prev = rsi[i - 1]
        rsi_now = rsi[i]
        if ma20 is None or rsi_prev is None or rsi_now is None:
            continue
        single_return = (signal_close / prev_close - 1.0) * 100.0
        last5 = last5d_high_rise_until(candles, i, trade_date_text)
        cond1 = signal_close > ma20
        cond2 = rsi_prev <= rsi_cross_level and rsi_now > rsi_cross_level
        cond3 = single_return > bar_return_min_pct
        cond4 = amt >= bar_amount_min or cum_amount >= cum_amount_min
        cond5 = last5 is not None and last5 > last5d_high_rise_min_pct
        if cond1 and cond2 and cond3 and cond4 and cond5:
            entry_row = candles[i + 1]
            entry_time = candle_dt(entry_row)
            entry_price = get_num(entry_row, "open")
            if entry_time is None or entry_price is None or entry_price <= 0:
                continue
            return {
                "signal_idx": i,
                "signal_time": ts,
                "signal_close": signal_close,
                "entry_idx": i + 1,
                "entry_time": entry_time,
                "entry_price": entry_price,
                "ma20": ma20,
                "rsi14_prev": rsi_prev,
                "rsi14": rsi_now,
                "single_bar_return_pct": single_return,
                "bar_amount": amt,
                "cum_amount": cum_amount,
                "last5d_high_rise_pct": last5,
            }
    return None


def evaluate_exit(
    candles: Sequence[Dict[str, Any]],
    entry_idx: int,
    entry_price: float,
    p1: float,
    p2: float,
    q: float,
    trail: float,
    jma_period: int,
    jma_phase: int,
    jma_power: int,
    st_period: int,
    st_multiplier: float,
) -> Dict[str, Any]:
    closes: List[float] = []
    for row in candles:
        c = get_num(row, "close")
        closes.append(c if c is not None else 0.0)
    jma = core.calc_jma_states(closes, jma_period, jma_phase, jma_power)
    st = core.calc_supertrend_states(candles, st_period, st_multiplier)
    return partial.evaluate_partial_policy(
        candles=candles,
        entry_idx=entry_idx,
        entry_price=entry_price,
        policy="PP3_PARTIAL_TRAIL_REMAINDER",
        p1=p1,
        p2=p2,
        q=q,
        trail_pct=trail,
        jma_state=jma["state"],
        st_state=st["state"],
    )


def evaluate_candidate(
    candidate: Dict[str, Any],
    candles: Sequence[Dict[str, Any]],
    args: argparse.Namespace,
) -> Optional[Dict[str, Any]]:
    if len(candles) == 0:
        return None
    signal = find_signal(
        candles=candles,
        trade_date_text=candidate["trade_date"],
        capture_dt=candidate["T_capture"],
        sma_period=args.sma_period,
        rsi_period=args.rsi_period,
        rsi_cross_level=args.rsi_cross_level,
        bar_return_min_pct=args.bar_return_min_pct,
        bar_amount_min=args.bar_amount_min,
        cum_amount_min=args.cum_amount_min,
        last5d_high_rise_min_pct=args.last5d_high_rise_min_pct,
    )
    if signal is None:
        return None
    exit_result = evaluate_exit(
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
        "signal_time": signal["signal_time"].isoformat(sep=" "),
        "signal_close": signal["signal_close"],
        "entry_time": signal["entry_time"].isoformat(sep=" "),
        "entry_price": signal["entry_price"],
        "entry_mode": "NEXT_BAR_OPEN",
        "ma20": signal["ma20"],
        "rsi14_prev": signal["rsi14_prev"],
        "rsi14": signal["rsi14"],
        "single_bar_return_pct": signal["single_bar_return_pct"],
        "bar_amount": signal["bar_amount"],
        "cum_amount": signal["cum_amount"],
        "last5d_high_rise_pct": signal["last5d_high_rise_pct"],
        "exit_policy": "VIX_JMA_PARTIAL_TRAIL_v1",
        "p1": args.p1,
        "p2": args.p2,
        "q": args.q,
        "trail": args.trail,
        "jma_period": args.jma_period,
        "st_period": args.st_period,
        "st_multiplier": args.st_multiplier,
    }
    row.update(exit_result)
    return row


def summarize(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if len(rows) == 0:
        return []
    wins = [r for r in rows if (base.safe_float(r.get("realized_pnl_pct")) or 0.0) > 0]
    losses = [r for r in rows if (base.safe_float(r.get("realized_pnl_pct")) or 0.0) < 0]
    gross_win = sum([(base.safe_float(r.get("realized_pnl_pct")) or 0.0) for r in wins])
    gross_loss = abs(sum([(base.safe_float(r.get("realized_pnl_pct")) or 0.0) for r in losses]))
    return [{
        "strategy_name": "RSI70_MA20_AMOUNT_BREAKOUT_v1",
        "entry_count": len(rows),
        "win_count": len(wins),
        "win_rate": len(wins) / len(rows),
        "loss_count": len(losses),
        "loss_rate": len(losses) / len(rows),
        "avg_realized_pnl_pct": safe_avg([base.safe_float(r.get("realized_pnl_pct")) for r in rows]),
        "total_realized_pnl_pct": sum([(base.safe_float(r.get("realized_pnl_pct")) or 0.0) for r in rows]),
        "profit_factor": gross_win / gross_loss if gross_loss > 0 else None,
        "avg_mfe_pct": safe_avg([base.safe_float(r.get("max_favorable_excursion_pct")) for r in rows]),
        "avg_mae_pct": safe_avg([base.safe_float(r.get("max_adverse_excursion_pct")) for r in rows]),
        "avg_holding_minutes": safe_avg([base.safe_float(r.get("holding_minutes")) for r in rows]),
    }]


def summarize_daily(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        key = str(row.get("trade_date"))
        if key not in groups:
            groups[key] = []
        groups[key].append(row)
    output: List[Dict[str, Any]] = []
    for key in sorted(groups.keys()):
        rs = groups[key]
        wins = [r for r in rs if (base.safe_float(r.get("realized_pnl_pct")) or 0.0) > 0]
        losses = [r for r in rs if (base.safe_float(r.get("realized_pnl_pct")) or 0.0) < 0]
        output.append({
            "trade_date": key,
            "entry_count": len(rs),
            "win_count": len(wins),
            "win_rate": len(wins) / len(rs) if len(rs) > 0 else 0.0,
            "loss_count": len(losses),
            "loss_rate": len(losses) / len(rs) if len(rs) > 0 else 0.0,
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
        for key in row.keys():
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def fmt_num(value: Any, digits: int = 2) -> str:
    number = base.safe_float(value)
    if number is None:
        return "-"
    return f"{number:.{digits}f}"


def fmt_rate(value: Any) -> str:
    number = base.safe_float(value)
    if number is None:
        return "-"
    return f"{number:.2%}"


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
            align = "left" if field in ("strategy_name", "name", "remainder_exit_reason") else ""
            parts.append("<td class='" + align + "'>" + html.escape(text) + "</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


def build_html(detail: Sequence[Dict[str, Any]], summary: Sequence[Dict[str, Any]], daily: Sequence[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary_fields = ["strategy_name", "entry_count", "win_count", "win_rate", "loss_count", "loss_rate", "avg_realized_pnl_pct", "total_realized_pnl_pct", "profit_factor", "avg_mfe_pct", "avg_mae_pct", "avg_holding_minutes"]
    daily_fields = ["trade_date", "entry_count", "win_count", "win_rate", "loss_count", "loss_rate", "avg_realized_pnl_pct", "total_realized_pnl_pct"]
    detail_fields = ["trade_date", "code", "name", "signal_time", "entry_time", "entry_price", "rsi14_prev", "rsi14", "single_bar_return_pct", "bar_amount", "cum_amount", "last5d_high_rise_pct", "realized_pnl_pct", "max_favorable_excursion_pct", "max_adverse_excursion_pct", "remainder_exit_reason"]
    html_text = "\n".join([
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'><title>RSI70 MA20 Amount Breakout v1</title>",
        "<style>body{font-family:Segoe UI,Malgun Gothic,Arial;background:#111827;color:#e5e7eb;margin:0;padding:18px}h1,h2{color:#fbbf24}.box{border:1px solid #334155;border-radius:10px;padding:12px;background:#0f172a;margin-bottom:12px}table{border-collapse:collapse;width:100%;font-size:12px;margin:12px 0;background:#0f172a}th,td{border:1px solid #334155;padding:5px;text-align:right}th{background:#1e293b}.left{text-align:left}</style></head><body>",
        "<h1>RSI70 MA20 Amount Breakout v1</h1>",
        "<div class='box'>5분봉 종가&gt;20MA, RSI14 70 crossup, 단일봉 +3%, 거래대금 조건, 최근 5일 고가상승률 조건을 신호로 하고, 다음봉 시가 진입 후 VIX_JMA_PARTIAL_TRAIL_v1 청산을 적용합니다.</div>",
        "<h2>Summary</h2>",
        table_html(summary, summary_fields),
        "<h2>Daily Summary</h2>",
        table_html(daily, daily_fields),
        "<h2>Detail</h2>",
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
    parser.add_argument("--capture-time", default=base.DEFAULT_CAPTURE_TIME)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--candle-table", default=None)
    parser.add_argument("--lookback-calendar-days", type=int, default=14)
    parser.add_argument("--sma-period", type=int, default=DEFAULT_SMA_PERIOD)
    parser.add_argument("--rsi-period", type=int, default=DEFAULT_RSI_PERIOD)
    parser.add_argument("--rsi-cross-level", type=float, default=DEFAULT_RSI_CROSS_LEVEL)
    parser.add_argument("--bar-return-min-pct", type=float, default=DEFAULT_BAR_RETURN_MIN_PCT)
    parser.add_argument("--bar-amount-min", type=float, default=DEFAULT_BAR_AMOUNT_MIN)
    parser.add_argument("--cum-amount-min", type=float, default=DEFAULT_CUM_AMOUNT_MIN)
    parser.add_argument("--last5d-high-rise-min-pct", type=float, default=DEFAULT_LAST5D_HIGH_RISE_MIN_PCT)
    parser.add_argument("--p1", type=float, default=DEFAULT_P1)
    parser.add_argument("--p2", type=float, default=DEFAULT_P2)
    parser.add_argument("--q", type=float, default=DEFAULT_Q)
    parser.add_argument("--trail", type=float, default=DEFAULT_TRAIL)
    parser.add_argument("--jma-period", type=int, default=DEFAULT_JMA_PERIOD)
    parser.add_argument("--jma-phase", type=int, default=DEFAULT_JMA_PHASE)
    parser.add_argument("--jma-power", type=int, default=DEFAULT_JMA_POWER)
    parser.add_argument("--st-period", type=int, default=DEFAULT_ST_PERIOD)
    parser.add_argument("--st-multiplier", type=float, default=DEFAULT_ST_MULTIPLIER)
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
        schema = base.find_candidate_schema(sqlite_conn, args.candidate_table)
        candle_table = base.pick_candle_table(mysql_conn, args.candle_table)
        candidates = base.load_candidates(sqlite_conn, schema, args.start_date, args.end_date, args.condition_name, args.capture_time)

        print("=== RSI70 MA20 Amount Breakout v1 ===")
        print("candidate_table=" + schema.table)
        print("candle_table=" + candle_table)
        print("candidate_count=" + str(len(candidates)))

        candle_cache: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        detail_rows: List[Dict[str, Any]] = []
        for idx, cand in enumerate(candidates, 1):
            key = (cand["trade_date"], cand["code"])
            if key not in candle_cache:
                candle_cache[key] = load_recent_candles(mysql_conn, candle_table, cand["code"], cand["trade_date"], args.lookback_calendar_days)
            row = evaluate_candidate(cand, candle_cache[key], args)
            if row is not None:
                detail_rows.append(row)
            if idx % 200 == 0:
                print("processed_candidates=" + str(idx) + " signals=" + str(len(detail_rows)))

        summary_rows = summarize(detail_rows)
        daily_rows = summarize_daily(detail_rows)
        outdir = Path(args.output_dir)
        write_csv(outdir / "rsi70_ma20_amount_breakout_detail_v1.csv", detail_rows)
        write_csv(outdir / "rsi70_ma20_amount_breakout_summary_v1.csv", summary_rows)
        write_csv(outdir / "rsi70_ma20_amount_breakout_daily_v1.csv", daily_rows)
        build_html(detail_rows, summary_rows, daily_rows, outdir / "rsi70_ma20_amount_breakout_v1.html")

        print("=== Summary ===")
        for row in summary_rows:
            print(row)
        print("signal_count=" + str(len(detail_rows)))
        print("output_detail=" + str((outdir / "rsi70_ma20_amount_breakout_detail_v1.csv").resolve()))
        print("output_summary=" + str((outdir / "rsi70_ma20_amount_breakout_summary_v1.csv").resolve()))
        print("output_daily=" + str((outdir / "rsi70_ma20_amount_breakout_daily_v1.csv").resolve()))
        print("output_html=" + str((outdir / "rsi70_ma20_amount_breakout_v1.html").resolve()))
        return 0
    finally:
        sqlite_conn.close()
        mysql_conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
