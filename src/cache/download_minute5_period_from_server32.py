# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

from src.common.db import mysql_connect
from src.common.env_loader import env_float, env_int, env_str, load_env_file


SESSION_OPEN = "09:00:00"
SESSION_CLOSE = "15:30:00"
DEFAULT_SEED_HOUR = "14:00:00"


def _to_int(value: Any) -> int:
    if value is None:
        return 0
    text = str(value).strip().replace(",", "").replace("+", "").replace('"', "")
    if text == "" or text == "-":
        return 0
    try:
        return abs(int(float(text)))
    except ValueError:
        return 0


def _pick(row: Dict[str, Any], names: List[str]) -> Any:
    for name in names:
        if name in row:
            return row[name]
    return None


def _parse_time_text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if len(text) >= 14 and text[:14].isdigit():
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]} {text[8:10]}:{text[10:12]}:{text[12:14]}"
    if len(text) >= 12 and text[:12].isdigit():
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]} {text[8:10]}:{text[10:12]}:00"
    try:
        return datetime.fromisoformat(text.replace("T", " ")).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _to_stop_time(dt: datetime) -> str:
    return dt.strftime("%Y%m%d%H%M%S")


def _dt_from_text(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def _parse_candle(row: Dict[str, Any], code: str) -> Optional[Dict[str, Any]]:
    candle_time = _parse_time_text(_pick(row, ["체결시간", "time", "Time", "timestamp", "datetime"]))
    if candle_time is None:
        return None

    open_price = _to_int(_pick(row, ["시가", "open", "Open"]))
    high_price = _to_int(_pick(row, ["고가", "high", "High"]))
    low_price = _to_int(_pick(row, ["저가", "low", "Low"]))
    close_price = _to_int(_pick(row, ["현재가", "종가", "close", "Close"]))
    volume = _to_int(_pick(row, ["거래량", "volume", "Volume"]))
    amount = _to_int(_pick(row, ["거래대금", "tramount", "amount", "Amount"]))

    if open_price <= 0 or high_price <= 0 or low_price <= 0 or close_price <= 0:
        return None

    if amount <= 0:
        avg_price = Decimal(open_price + high_price + low_price + close_price) / Decimal(4)
        amount = int(avg_price * Decimal(volume))

    return {
        "code": code,
        "candle_time": candle_time,
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
        "volume": volume,
        "tramount": amount,
        "source": "server32",
    }


def fetch_codes(start_date: str, end_date: str, limit_codes: int = 0) -> List[str]:
    sql = """
    SELECT DISTINCT code
    FROM performance_result
    WHERE search_date BETWEEN %s AND %s
    ORDER BY code
    """
    params: List[Any] = [start_date, end_date]
    if limit_codes > 0:
        sql += " LIMIT %s"
        params.append(limit_codes)

    conn = mysql_connect(env_str("MYSQL_DB_STOCK_INFO", "stock_info"))
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            return [str(r["code"]) for r in rows]
    finally:
        conn.close()


def fetch_server32_page(code: str, tick: int, stop_time: str, timeout: float) -> Tuple[bool, str, List[Dict[str, Any]]]:
    base_url = env_str("SERVER32_BASE_URL", "http://localhost:8081").rstrip("/")
    endpoint = env_str("SERVER32_MINUTE_ENDPOINT", "/api/market/candles/minute")
    params = {"code": code, "tick": str(tick), "stopTime": stop_time}
    try:
        response = requests.get(base_url + endpoint, params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception as ex:
        return False, f"REQUEST_ERROR: {type(ex).__name__}: {ex}", []

    data = payload.get("Data") or []
    if not isinstance(data, list):
        return False, "INVALID_DATA", []

    candles: List[Dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict):
            parsed = _parse_candle(item, code)
            if parsed is not None:
                candles.append(parsed)

    # server32 may return recent-first. Store and process in chronological order.
    candles.sort(key=lambda x: x["candle_time"])
    return bool(payload.get("Success", False)), str(payload.get("Message", "")), candles


def upsert_candles(candles: List[Dict[str, Any]]) -> int:
    if not candles:
        return 0
    sql = """
    INSERT INTO minute5_candles (code, candle_time, open, high, low, close, volume, tramount, source)
    VALUES (%(code)s, %(candle_time)s, %(open)s, %(high)s, %(low)s, %(close)s, %(volume)s, %(tramount)s, %(source)s)
    ON DUPLICATE KEY UPDATE
        open = VALUES(open),
        high = VALUES(high),
        low = VALUES(low),
        close = VALUES(close),
        volume = VALUES(volume),
        tramount = VALUES(tramount),
        source = VALUES(source),
        updated_at = CURRENT_TIMESTAMP;
    """
    conn = mysql_connect(env_str("MYSQL_DB_STOCK_INFO", "stock_info"))
    try:
        with conn.cursor() as cur:
            cur.executemany(sql, candles)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return len(candles)


def _seed_stop_time(start_date: str, seed_prev_days: int, seed_time: str) -> datetime:
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    seed_dt = start_dt - timedelta(days=seed_prev_days)
    hour, minute, second = [int(x) for x in seed_time.split(":")]
    return seed_dt.replace(hour=hour, minute=minute, second=second)


def _period_bounds(start_date: str, end_date: str, include_prev_from_time: str) -> Tuple[datetime, datetime]:
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    prev_dt = start_dt - timedelta(days=1)
    h, m, s = [int(x) for x in include_prev_from_time.split(":")]
    lower_bound = prev_dt.replace(hour=h, minute=m, second=s)

    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    h2, m2, s2 = [int(x) for x in SESSION_CLOSE.split(":")]
    upper_bound = end_dt.replace(hour=h2, minute=m2, second=s2)
    return lower_bound, upper_bound


def _filter_period(candles: List[Dict[str, Any]], lower_bound: datetime, upper_bound: datetime) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    for c in candles:
        t = _dt_from_text(str(c["candle_time"]))
        if lower_bound <= t <= upper_bound:
            selected.append(c)
    return selected


def download_code_period(
    code: str,
    tick: int,
    start_date: str,
    end_date: str,
    seed_prev_days: int,
    seed_time: str,
    include_prev_from_time: str,
    timeout: float,
    interval_sec: float,
    max_pages: int,
    verbose: bool,
) -> Tuple[int, int, int]:
    lower_bound, upper_bound = _period_bounds(start_date, end_date, include_prev_from_time)
    stop_dt = _seed_stop_time(start_date, seed_prev_days, seed_time)
    all_seen_times: set[str] = set()

    total_raw = 0
    total_saved = 0
    pages = 0

    while pages < max_pages:
        pages += 1
        stop_time = _to_stop_time(stop_dt)
        ok, msg, candles = fetch_server32_page(code, tick, stop_time, timeout)
        if not ok:
            print(f"  page={pages} FAIL code={code} stopTime={stop_time} msg={msg}")
            break
        if not candles:
            print(f"  page={pages} EMPTY code={code} stopTime={stop_time}")
            break

        total_raw += len(candles)
        filtered = _filter_period(candles, lower_bound, upper_bound)
        if filtered:
            total_saved += upsert_candles(filtered)

        last_time_text = str(candles[-1]["candle_time"])
        first_time_text = str(candles[0]["candle_time"])
        last_dt = _dt_from_text(last_time_text)

        if verbose:
            print(f"  page={pages} raw={len(candles)} filtered={len(filtered)} first={first_time_text} last={last_time_text}")

        for c in candles:
            all_seen_times.add(str(c["candle_time"]))

        if last_dt >= upper_bound:
            break

        # Advance just after the last candle so the next count/history request continues forward.
        next_stop_dt = last_dt + timedelta(minutes=tick)
        if next_stop_dt <= stop_dt:
            print(f"  no progress code={code} stopTime={stop_time} last={last_time_text}")
            break
        stop_dt = next_stop_dt

        if interval_sec > 0:
            time.sleep(interval_sec)

    return pages, total_raw, total_saved


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--start", default="2026-01-05")
    parser.add_argument("--end", default="2026-05-06")
    parser.add_argument("--tick", type=int, default=5)
    parser.add_argument("--limit-codes", type=int, default=0)
    parser.add_argument("--seed-prev-days", type=int, default=2)
    parser.add_argument("--seed-time", default=DEFAULT_SEED_HOUR)
    parser.add_argument("--include-prev-from-time", default="14:00:00")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--interval-sec", type=float, default=0.1)
    parser.add_argument("--max-pages", type=int, default=300)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    load_env_file(args.env)
    timeout = args.timeout or env_float("SERVER32_TIMEOUT", 15.0)
    codes = fetch_codes(args.start, args.end, args.limit_codes)

    print("=== download_minute5_period_from_server32 ===")
    print(f"period={args.start}~{args.end} codes={len(codes)} tick={args.tick}")
    print(f"seed_prev_days={args.seed_prev_days} seed_time={args.seed_time} include_prev_from_time={args.include_prev_from_time}")

    grand_pages = 0
    grand_raw = 0
    grand_saved = 0
    fail_codes = 0

    for idx, code in enumerate(codes, start=1):
        print(f"[{idx}/{len(codes)}] code={code}")
        try:
            pages, raw_count, saved_count = download_code_period(
                code=code,
                tick=args.tick,
                start_date=args.start,
                end_date=args.end,
                seed_prev_days=args.seed_prev_days,
                seed_time=args.seed_time,
                include_prev_from_time=args.include_prev_from_time,
                timeout=timeout,
                interval_sec=args.interval_sec,
                max_pages=args.max_pages,
                verbose=args.verbose,
            )
            grand_pages += pages
            grand_raw += raw_count
            grand_saved += saved_count
            print(f"  OK pages={pages} raw={raw_count} saved_or_updated={saved_count}")
        except Exception as ex:
            fail_codes += 1
            print(f"  FAIL code={code} {type(ex).__name__}: {ex}")

    print("=== DONE ===")
    print(f"codes={len(codes)} fail_codes={fail_codes} pages={grand_pages} raw_candles={grand_raw} saved_or_updated={grand_saved}")


if __name__ == "__main__":
    main()
