# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import requests

from src.cache.rebuild_minute5_targets import Minute5Target, fetch_targets
from src.common.db import mysql_connect
from src.common.env_loader import env_int, env_str, load_env_file


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


def _time_text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if len(text) >= 14 and text[:14].isdigit():
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]} {text[8:10]}:{text[10:12]}:{text[12:14]}"
    if len(text) >= 12 and text[:12].isdigit():
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]} {text[8:10]}:{text[10:12]}:00"
    return None


def _parse_candle(row: Dict[str, Any], code: str) -> Optional[Dict[str, Any]]:
    candle_time = _time_text(_pick(row, ["체결시간", "time", "Time", "timestamp", "datetime"]))
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


def fetch_minute5(target: Minute5Target, timeout: float) -> Tuple[bool, str, List[Dict[str, Any]]]:
    base_url = env_str("SERVER32_BASE_URL", "http://localhost:8081").rstrip("/")
    endpoint = env_str("SERVER32_MINUTE_ENDPOINT", "/api/market/candles/minute")
    params = {"code": target.code, "tick": "5", "stopTime": target.stop_time}
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
            parsed = _parse_candle(item, target.code)
            if parsed is not None:
                candles.append(parsed)
    candles.sort(key=lambda x: x["candle_time"])
    return bool(payload.get("Success", False)), str(payload.get("Message", "")), candles


def upsert_candles(candles: List[Dict[str, Any]]) -> int:
    if not candles:
        return 0
    sql = """
    INSERT INTO minute5_candles (code, candle_time, open, high, low, close, volume, tramount, source)
    VALUES (%(code)s, %(candle_time)s, %(open)s, %(high)s, %(low)s, %(close)s, %(volume)s, %(tramount)s, %(source)s)
    ON DUPLICATE KEY UPDATE
        open = VALUES(open), high = VALUES(high), low = VALUES(low), close = VALUES(close),
        volume = VALUES(volume), tramount = VALUES(tramount), source = VALUES(source), updated_at = CURRENT_TIMESTAMP;
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--min-count", type=int, default=200)
    parser.add_argument("--interval-sec", type=float, default=0.2)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    load_env_file(args.env)
    min_count = args.min_count or env_int("MINUTE5_PREFETCH_COUNT", 200)
    targets = fetch_targets(limit=args.limit, only_missing=not args.all, min_count=min_count)
    print("=== download_minute5_from_server32 ===")
    print(f"targets={len(targets)} only_missing={not args.all} min_count={min_count}")

    ok_count = 0
    fail_count = 0
    saved_count = 0
    for idx, target in enumerate(targets, start=1):
        ok, msg, candles = fetch_minute5(target, args.timeout)
        if ok and candles:
            saved = upsert_candles(candles)
            ok_count += 1
            saved_count += saved
            if args.verbose:
                print(f"[{idx}/{len(targets)}] OK {target.code} candles={len(candles)} saved={saved}")
        else:
            fail_count += 1
            print(f"[{idx}/{len(targets)}] FAIL {target.code} msg={msg} candles={len(candles)}")
        if args.interval_sec > 0:
            time.sleep(args.interval_sec)
    print("=== DONE ===")
    print(f"ok_targets={ok_count} fail_targets={fail_count} saved_candles={saved_count}")


if __name__ == "__main__":
    main()
