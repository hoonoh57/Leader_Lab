# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import requests

from src.common.db import mysql_connect
from src.common.env_loader import env_int, env_str, env_float, load_env_file


def _pick(row: Dict[str, Any], names: List[str]) -> Any:
    for name in names:
        if name in row:
            return row.get(name)
    return None


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


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("+", "").replace("%", "").replace('"', "")
    if text == "" or text == "-":
        return None
    try:
        return Decimal(text)
    except Exception:
        return None


def _parse_date(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if text == "":
        return None

    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 8:
        return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"

    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _format_server_code(code: str) -> str:
    code_text = str(code or "").strip()
    if code_text.startswith("A"):
        code_text = code_text[1:]
    code_text = code_text.zfill(6)
    prefix = env_str("SERVER32_DAILY_CODE_PREFIX", "")
    return prefix + code_text


def _normalize_code(code: str) -> str:
    text = str(code or "").strip()
    if text.startswith("A") and len(text) == 7:
        text = text[1:]
    return text.zfill(6) if text else ""


def _parse_daily_row(row: Dict[str, Any], code: str) -> Optional[Dict[str, Any]]:
    day = _parse_date(_pick(row, ["날짜", "일자", "date", "Date", "체결시간", "time", "Time"]))
    if day is None:
        return None

    open_price = _to_int(_pick(row, ["시가", "open", "Open"]))
    high_price = _to_int(_pick(row, ["고가", "high", "High"]))
    low_price = _to_int(_pick(row, ["저가", "low", "Low"]))
    close_price = _to_int(_pick(row, ["종가", "현재가", "close", "Close"]))
    volume = _to_int(_pick(row, ["거래량", "volume", "Volume"]))
    tramount = _to_int(_pick(row, ["거래대금", "tramount", "amount", "Amount"]))
    change_pct = _to_decimal(_pick(row, ["등락률", "change_pct", "ChangePct", "changeRate", "rate"]))

    if open_price <= 0 or high_price <= 0 or low_price <= 0 or close_price <= 0:
        return None
    if tramount <= 0:
        tramount = close_price * volume

    return {
        "code": _normalize_code(code),
        "date": day,
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
        "volume": volume,
        "tramount": tramount,
        "change_pct": change_pct,
    }


def _extract_data(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("Data", "data", "rows", "Rows", "candles", "Candles"):
        value = payload.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
    return []


def fetch_daily_page(code: str, start_date: str, end_date: str, timeout: float) -> Tuple[bool, str, List[Dict[str, Any]], str]:
    """Fetch daily candles from server32 using flexible endpoint modes.

    Supported modes through SERVER32_DAILY_MODE:
    - period: endpoint with code, fromdate, enddate, timeframe=D
    - stopTime: endpoint with code, tick=D, stopTime=yyyyMMdd153000, count
    - auto: try period first, then stopTime
    """
    base_url = env_str("SERVER32_BASE_URL", "http://localhost:8082").rstrip("/")
    endpoint = env_str("SERVER32_DAILY_ENDPOINT", "/api/market/candles/daily")
    mode = env_str("SERVER32_DAILY_MODE", "auto")
    timeout = timeout or env_float("SERVER32_TIMEOUT", 15.0)
    server_code = _format_server_code(code)

    candidates: List[Tuple[str, Dict[str, Any]]] = []
    if mode in ("auto", "period"):
        candidates.append((endpoint, {"code": server_code, "timeframe": "D", "fromdate": start_date.replace("-", ""), "enddate": end_date.replace("-", "")}))
    if mode in ("auto", "stopTime"):
        stop_time = end_date.replace("-", "") + "153000"
        count = env_int("SERVER32_DAILY_COUNT", 900)
        candidates.append((endpoint, {"code": server_code, "tick": "D", "stopTime": stop_time, "count": str(count)}))

    # Fallbacks for older server32 variants.
    if mode == "auto":
        candidates.append(("/api/candles_period", {"code": server_code, "timeframe": "D", "fromdate": start_date.replace("-", ""), "enddate": end_date.replace("-", "")}))
        candidates.append(("/api/candles", {"code": server_code, "timeframe": "D", "count": str(env_int("SERVER32_DAILY_COUNT", 900)), "enddate": end_date.replace("-", "")}))

    last_error = ""
    for ep, params in candidates:
        try:
            response = requests.get(base_url + ep, params=params, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            raw_rows = _extract_data(payload)
            parsed: List[Dict[str, Any]] = []
            for raw in raw_rows:
                item = _parse_daily_row(raw, code)
                if item is None:
                    continue
                if start_date <= item["date"] <= end_date:
                    parsed.append(item)
            parsed.sort(key=lambda x: x["date"])
            if parsed:
                return True, str(payload.get("Message", "OK")) if isinstance(payload, dict) else "OK", parsed, ep
            last_error = f"EMPTY ep={ep} raw={len(raw_rows)}"
        except Exception as ex:
            last_error = f"{ep} {type(ex).__name__}: {ex}"
            continue
    return False, last_error, [], ""


def fetch_target_codes(universe: str, start_date: str, end_date: str, limit_codes: int) -> List[str]:
    if universe == "performance":
        sql = """
        SELECT DISTINCT code
        FROM performance_result
        WHERE search_date BETWEEN %s AND %s
        ORDER BY code
        """
        params: List[Any] = [start_date, end_date]
    else:
        sql = """
        SELECT code
        FROM stock_base_info
        WHERE IFNULL(is_excluded, 0) = 0
          AND IFNULL(is_common_stock, 1) = 1
          AND IFNULL(is_trading_halt, 0) = 0
        ORDER BY code
        """
        params = []

    if limit_codes > 0:
        sql += " LIMIT %s"
        params.append(limit_codes)

    conn = mysql_connect(env_str("MYSQL_DB_STOCK_INFO", "stock_info"))
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [str(r["code"]) for r in cur.fetchall()]
    finally:
        conn.close()


def get_last_daily_date(code: str) -> Optional[str]:
    conn = mysql_connect(env_str("MYSQL_DB_STOCK_INFO", "stock_info"))
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(date) AS last_date FROM daily_candles WHERE code=%s", (code,))
            row = cur.fetchone()
            if row and row.get("last_date") is not None:
                return str(row["last_date"])
            return None
    finally:
        conn.close()


def upsert_daily(rows: List[Dict[str, Any]]) -> int:
    if not rows:
        return 0
    sql = """
    INSERT INTO daily_candles (code, date, open, high, low, close, volume, tramount, change_pct)
    VALUES (%(code)s, %(date)s, %(open)s, %(high)s, %(low)s, %(close)s, %(volume)s, %(tramount)s, %(change_pct)s)
    ON DUPLICATE KEY UPDATE
        open = VALUES(open),
        high = VALUES(high),
        low = VALUES(low),
        close = VALUES(close),
        volume = VALUES(volume),
        tramount = VALUES(tramount),
        change_pct = VALUES(change_pct);
    """
    conn = mysql_connect(env_str("MYSQL_DB_STOCK_INFO", "stock_info"))
    try:
        with conn.cursor() as cur:
            cur.executemany(sql, rows)
        conn.commit()
        return len(rows)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _next_day(date_text: str) -> str:
    return (datetime.strptime(date_text, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--start", default="", help="비어 있으면 code별 daily_candles의 마지막 일자 다음 날부터")
    parser.add_argument("--end", required=True, help="예: 2026-05-14")
    parser.add_argument("--universe", default="performance", choices=["performance", "stock_base_info"])
    parser.add_argument("--limit-codes", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--interval-sec", type=float, default=0.05)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    load_env_file(args.env)
    start_for_code_list = args.start or "1900-01-01"
    codes = fetch_target_codes(args.universe, start_for_code_list, args.end, args.limit_codes)

    print("=== download_daily_from_server32 ===")
    print(f"universe={args.universe} codes={len(codes)} start={args.start or 'last_date+1'} end={args.end}")

    ok_codes = 0
    skip_codes = 0
    fail_codes = 0
    saved_total = 0

    for idx, code in enumerate(codes, start=1):
        if args.start:
            request_start = args.start
        else:
            last_date = get_last_daily_date(code)
            request_start = _next_day(last_date) if last_date else env_str("DAILY_DEFAULT_START", "2019-01-01")

        if request_start > args.end:
            skip_codes += 1
            if args.verbose:
                print(f"[{idx}/{len(codes)}] SKIP {code} already up-to-date start={request_start} end={args.end}")
            continue

        ok, msg, rows, endpoint_used = fetch_daily_page(code, request_start, args.end, args.timeout)
        if ok and rows:
            saved = upsert_daily(rows)
            ok_codes += 1
            saved_total += saved
            if args.verbose:
                print(f"[{idx}/{len(codes)}] OK {code} rows={len(rows)} saved={saved} first={rows[0]['date']} last={rows[-1]['date']} ep={endpoint_used}")
        else:
            fail_codes += 1
            print(f"[{idx}/{len(codes)}] FAIL {code} start={request_start} end={args.end} msg={msg}")

        if args.interval_sec > 0:
            time.sleep(args.interval_sec)

    print("=== DONE ===")
    print(f"ok_codes={ok_codes} skip_codes={skip_codes} fail_codes={fail_codes} saved_or_updated={saved_total}")


if __name__ == "__main__":
    main()
