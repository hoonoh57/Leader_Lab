# -*- coding: utf-8 -*-
"""Build analysis_5m_result from performance_result and minute5_candles.

Run:
    python -m src.analysis.build_5m_analysis_result --env .env --rebuild
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pymysql


def load_env(env_path: str) -> None:
    path = Path(env_path)
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def env_value(names: Sequence[str], default: Optional[str] = None) -> Optional[str]:
    for name in names:
        value = os.environ.get(name)
        if value is not None and value.strip() != "":
            return value.strip()
    return default


def open_conn() -> Any:
    host = env_value(["DB_HOST", "MYSQL_HOST"], "127.0.0.1")
    port = int(env_value(["DB_PORT", "MYSQL_PORT"], "3306") or "3306")
    user = env_value(["DB_USER", "MYSQL_USER"], "root")
    password = env_value(["DB_PASS", "DB_PASSWORD", "MYSQL_PASSWORD", "MYSQL_PASS"], "")
    db_name = env_value(["DB_NAME", "MYSQL_DATABASE", "MYSQL_DB"])
    if db_name is None:
        raise RuntimeError(".env에 DB_NAME 또는 MYSQL_DATABASE가 필요합니다.")

    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db_name,
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


def normalize_code(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.startswith("A") and len(text) == 7 and text[1:].isdigit():
        text = text[1:]
    if text.isdigit() and len(text) < 6:
        text = text.zfill(6)
    return text


def to_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if "-" in text:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    if len(text) >= 8 and text[:8].isdigit():
        return datetime.strptime(text[:8], "%Y%m%d").date()
    raise ValueError(f"date 변환 실패: {value!r}")


def to_time(value: Any) -> time:
    if isinstance(value, datetime):
        return value.time().replace(microsecond=0)
    if isinstance(value, time):
        return value.replace(microsecond=0)
    if isinstance(value, timedelta):
        total = int(value.total_seconds())
        return time(total // 3600, (total % 3600) // 60, total % 60)
    text = str(value).strip().split(".", 1)[0]
    if ":" in text:
        parts = text.split(":")
        return time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0, int(parts[2]) if len(parts) > 2 else 0)
    if text.isdigit():
        if len(text) <= 4:
            text = text.zfill(4)
            return time(int(text[:2]), int(text[2:4]), 0)
        text = text.zfill(6)
        return time(int(text[:2]), int(text[2:4]), int(text[4:6]))
    raise ValueError(f"time 변환 실패: {value!r}")


def to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.replace(microsecond=0)
    text = str(value).strip().split(".", 1)[0]
    if len(text) >= 19 and "-" in text:
        return datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S")
    if len(text) >= 14 and text[:14].isdigit():
        return datetime.strptime(text[:14], "%Y%m%d%H%M%S")
    raise ValueError(f"datetime 변환 실패: {value!r}")


def to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        value = float(value)
    try:
        result = float(value)
    except Exception:
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def to_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, Decimal):
        return int(value)
    try:
        return int(float(value))
    except Exception:
        return 0


def pct(new_value: Optional[float], base_value: Optional[float]) -> Optional[float]:
    if new_value is None or base_value is None or base_value == 0:
        return None
    return (new_value - base_value) / base_value * 100.0


def quote_name(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


def columns(conn: Any, table_name: str) -> List[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """,
            (table_name,),
        )
        rows = cur.fetchall()
    return [str(row["COLUMN_NAME"]) for row in rows]


def pick(cols: List[str], candidates: Sequence[str], required: bool = True) -> Optional[str]:
    lower_map = {col.lower(): col for col in cols}
    for cand in candidates:
        value = lower_map.get(cand.lower())
        if value is not None:
            return value
    if required:
        raise RuntimeError("필수 컬럼 탐지 실패: 후보=" + ",".join(candidates) + " 실제=" + ",".join(cols))
    return None


def build_meta(conn: Any) -> Dict[str, Dict[str, Optional[str]]]:
    perf_cols = columns(conn, "performance_result")
    candle_cols = columns(conn, "minute5_candles")

    perf = {
        "search_date": pick(perf_cols, ["search_date", "date", "검증일자"]),
        "search_time": pick(perf_cols, ["search_time", "time", "검증시간"]),
        "code": pick(perf_cols, ["code", "stock_code", "ticker", "종목코드"]),
        "name": pick(perf_cols, ["name", "stock_name", "종목명"], False),
    }

    candle_dt = pick(candle_cols, ["candle_time", "time_stamp", "timestamp", "datetime", "date_time", "dt", "trade_time", "일시"], False)
    candle_date = pick(candle_cols, ["candle_date", "trade_date", "date", "일자"], False)
    candle_time = pick(candle_cols, ["candle_hhmmss", "trade_time", "time", "hhmmss", "시간"], False)
    if candle_dt is None and (candle_date is None or candle_time is None):
        raise RuntimeError("minute5_candles 시간 컬럼 탐지 실패: candle_time 또는 date+time 필요")

    candle = {
        "code": pick(candle_cols, ["code", "stock_code", "ticker", "종목코드"]),
        "dt": candle_dt,
        "date": candle_date,
        "time": candle_time,
        "open": pick(candle_cols, ["open", "open_price", "시가"]),
        "high": pick(candle_cols, ["high", "high_price", "고가"]),
        "low": pick(candle_cols, ["low", "low_price", "저가"]),
        "close": pick(candle_cols, ["close", "close_price", "종가"]),
        "volume": pick(candle_cols, ["volume", "vol", "거래량"], False),
        "amount": pick(candle_cols, ["amount", "trade_amount", "value", "거래대금"], False),
    }
    return {"perf": perf, "candle": candle}


def dt_expr(meta: Dict[str, Dict[str, Optional[str]]]) -> str:
    candle = meta["candle"]
    if candle["dt"] is not None:
        return quote_name(candle["dt"])
    return "TIMESTAMP(" + quote_name(str(candle["date"])) + ", " + quote_name(str(candle["time"])) + ")"


def ensure_schema(conn: Any, rebuild: bool) -> None:
    sql_path = Path("sql/create_analysis_5m_result.sql")
    ddl = sql_path.read_text(encoding="utf-8-sig")
    with conn.cursor() as cur:
        if rebuild:
            cur.execute("DROP TABLE IF EXISTS analysis_5m_result")
        cur.execute(ddl)
    conn.commit()


def performance_rows(conn: Any, meta: Dict[str, Dict[str, Optional[str]]], limit: int) -> List[Dict[str, Any]]:
    perf = meta["perf"]
    name_expr = "NULL" if perf["name"] is None else quote_name(str(perf["name"]))
    sql = (
        "SELECT "
        + quote_name(str(perf["search_date"])) + " AS search_date, "
        + quote_name(str(perf["search_time"])) + " AS search_time, "
        + quote_name(str(perf["code"])) + " AS code, "
        + name_expr + " AS name "
        + "FROM performance_result "
        + "ORDER BY " + quote_name(str(perf["search_date"])) + ", " + quote_name(str(perf["search_time"])) + ", " + quote_name(str(perf["code"]))
    )
    params: Tuple[Any, ...] = ()
    if limit > 0:
        sql += " LIMIT %s"
        params = (limit,)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def fetch_day_candles(conn: Any, meta: Dict[str, Dict[str, Optional[str]]], code: str, day_value: date) -> List[Dict[str, Any]]:
    candle = meta["candle"]
    expr = dt_expr(meta)
    volume_expr = "0" if candle["volume"] is None else quote_name(str(candle["volume"]))
    if candle["amount"] is None:
        amount_expr = "((" + quote_name(str(candle["open"])) + "+" + quote_name(str(candle["high"])) + "+" + quote_name(str(candle["low"])) + "+" + quote_name(str(candle["close"])) + ")/4.0)*IFNULL(" + volume_expr + ",0)"
    else:
        amount_expr = quote_name(str(candle["amount"]))

    start_dt = datetime.combine(day_value, time(9, 0, 0))
    end_dt = datetime.combine(day_value, time(15, 30, 0))
    sql = (
        "SELECT " + expr + " AS candle_time, "
        + quote_name(str(candle["open"])) + " AS open_price, "
        + quote_name(str(candle["high"])) + " AS high_price, "
        + quote_name(str(candle["low"])) + " AS low_price, "
        + quote_name(str(candle["close"])) + " AS close_price, "
        + volume_expr + " AS volume, "
        + amount_expr + " AS amount "
        + "FROM minute5_candles "
        + "WHERE " + quote_name(str(candle["code"])) + "=%s AND " + expr + ">=%s AND " + expr + "<=%s "
        + "ORDER BY candle_time"
    )
    with conn.cursor() as cur:
        cur.execute(sql, (code, start_dt, end_dt))
        return list(cur.fetchall())


def history_grade(cached_count: int) -> str:
    if cached_count >= 200:
        return "normal"
    if cached_count >= 80:
        return "partial_but_usable"
    return "weak_history"


def capture_index(rows: List[Dict[str, Any]], capture_dt: datetime) -> int:
    if not rows:
        return -1
    for idx, row in enumerate(rows):
        if to_datetime(row["candle_time"]) >= capture_dt:
            return idx
    return len(rows) - 1


def analyze_one(conn: Any, meta: Dict[str, Dict[str, Optional[str]]], perf_row: Dict[str, Any]) -> Dict[str, Any]:
    day_value = to_date(perf_row["search_date"])
    time_value = to_time(perf_row["search_time"])
    code = normalize_code(perf_row["code"])
    name = perf_row.get("name")
    capture_dt = datetime.combine(day_value, time_value)

    rows = fetch_day_candles(conn, meta, code, day_value)
    cached_count = len(rows)
    grade = history_grade(cached_count)

    result: Dict[str, Any] = {
        "search_date": day_value,
        "search_time": time_value,
        "code": code,
        "name": name,
        "capture_time": capture_dt,
        "capture_price": None,
        "max_after_time": None,
        "max_after_price": None,
        "max_after_return_pct": None,
        "close_1530": None,
        "close_return_pct": None,
        "min_after_time": None,
        "min_after_price": None,
        "max_drawdown_pct": None,
        "base_candle_time": None,
        "base_open": None,
        "base_high": None,
        "base_low": None,
        "base_close": None,
        "base_volume": None,
        "base_amount": None,
        "cum_volume_until_capture": 0,
        "cum_amount_until_capture": 0.0,
        "after_candle_count": 0,
        "cached_count": cached_count,
        "history_grade": grade,
        "valid_analysis_flag": 0,
        "invalid_reason": "no_candles",
    }
    if not rows:
        return result

    idx = capture_index(rows, capture_dt)
    base = rows[idx]
    base_time = to_datetime(base["candle_time"])
    base_close = to_float(base["close_price"])

    cum_volume = 0
    cum_amount = 0.0
    for i in range(0, idx + 1):
        cum_volume += to_int(rows[i].get("volume"))
        amount_value = to_float(rows[i].get("amount"))
        if amount_value is not None:
            cum_amount += amount_value

    max_price: Optional[float] = None
    max_time: Optional[datetime] = None
    min_price: Optional[float] = None
    min_time: Optional[datetime] = None
    after_rows = rows[idx:]
    for row in after_rows:
        row_time = to_datetime(row["candle_time"])
        high_value = to_float(row["high_price"])
        low_value = to_float(row["low_price"])
        if high_value is not None and (max_price is None or high_value > max_price):
            max_price = high_value
            max_time = row_time
        if low_value is not None and (min_price is None or low_value < min_price):
            min_price = low_value
            min_time = row_time

    close_1530 = to_float(rows[-1]["close_price"])
    valid = 1 if base_close is not None and base_close > 0 and len(after_rows) > 0 else 0
    reason = None if valid == 1 else "invalid_capture_price_or_no_after_candles"

    result.update(
        {
            "capture_price": base_close,
            "max_after_time": max_time,
            "max_after_price": max_price,
            "max_after_return_pct": pct(max_price, base_close),
            "close_1530": close_1530,
            "close_return_pct": pct(close_1530, base_close),
            "min_after_time": min_time,
            "min_after_price": min_price,
            "max_drawdown_pct": pct(min_price, base_close),
            "base_candle_time": base_time,
            "base_open": to_float(base["open_price"]),
            "base_high": to_float(base["high_price"]),
            "base_low": to_float(base["low_price"]),
            "base_close": base_close,
            "base_volume": to_int(base.get("volume")),
            "base_amount": to_float(base.get("amount")),
            "cum_volume_until_capture": cum_volume,
            "cum_amount_until_capture": cum_amount,
            "after_candle_count": len(after_rows),
            "valid_analysis_flag": valid,
            "invalid_reason": reason,
        }
    )
    return result


def upsert(conn: Any, result: Dict[str, Any]) -> None:
    sql = """
        INSERT INTO analysis_5m_result (
            search_date, search_time, code, name,
            capture_time, capture_price,
            max_after_time, max_after_price, max_after_return_pct,
            close_1530, close_return_pct,
            min_after_time, min_after_price, max_drawdown_pct,
            base_candle_time, base_open, base_high, base_low, base_close, base_volume, base_amount,
            cum_volume_until_capture, cum_amount_until_capture,
            after_candle_count, cached_count, history_grade, valid_analysis_flag, invalid_reason
        ) VALUES (
            %(search_date)s, %(search_time)s, %(code)s, %(name)s,
            %(capture_time)s, %(capture_price)s,
            %(max_after_time)s, %(max_after_price)s, %(max_after_return_pct)s,
            %(close_1530)s, %(close_return_pct)s,
            %(min_after_time)s, %(min_after_price)s, %(max_drawdown_pct)s,
            %(base_candle_time)s, %(base_open)s, %(base_high)s, %(base_low)s, %(base_close)s, %(base_volume)s, %(base_amount)s,
            %(cum_volume_until_capture)s, %(cum_amount_until_capture)s,
            %(after_candle_count)s, %(cached_count)s, %(history_grade)s, %(valid_analysis_flag)s, %(invalid_reason)s
        )
        ON DUPLICATE KEY UPDATE
            name=VALUES(name), capture_time=VALUES(capture_time), capture_price=VALUES(capture_price),
            max_after_time=VALUES(max_after_time), max_after_price=VALUES(max_after_price), max_after_return_pct=VALUES(max_after_return_pct),
            close_1530=VALUES(close_1530), close_return_pct=VALUES(close_return_pct),
            min_after_time=VALUES(min_after_time), min_after_price=VALUES(min_after_price), max_drawdown_pct=VALUES(max_drawdown_pct),
            base_candle_time=VALUES(base_candle_time), base_open=VALUES(base_open), base_high=VALUES(base_high), base_low=VALUES(base_low), base_close=VALUES(base_close),
            base_volume=VALUES(base_volume), base_amount=VALUES(base_amount),
            cum_volume_until_capture=VALUES(cum_volume_until_capture), cum_amount_until_capture=VALUES(cum_amount_until_capture),
            after_candle_count=VALUES(after_candle_count), cached_count=VALUES(cached_count), history_grade=VALUES(history_grade),
            valid_analysis_flag=VALUES(valid_analysis_flag), invalid_reason=VALUES(invalid_reason), updated_at=CURRENT_TIMESTAMP
    """
    with conn.cursor() as cur:
        cur.execute(sql, result)


def print_summary(conn: Any) -> None:
    queries = [
        ("summary", """
            SELECT COUNT(*) AS rows_count,
                   SUM(CASE WHEN valid_analysis_flag=1 THEN 1 ELSE 0 END) AS valid_rows,
                   SUM(CASE WHEN valid_analysis_flag=0 THEN 1 ELSE 0 END) AS invalid_rows,
                   MIN(search_date) AS first_date,
                   MAX(search_date) AS last_date,
                   AVG(max_after_return_pct) AS avg_max_after_return_pct,
                   AVG(close_return_pct) AS avg_close_return_pct
            FROM analysis_5m_result
        """),
        ("history_grade", """
            SELECT history_grade,
                   COUNT(*) AS rows_count,
                   AVG(max_after_return_pct) AS avg_max_after_return_pct,
                   AVG(close_return_pct) AS avg_close_return_pct
            FROM analysis_5m_result
            GROUP BY history_grade
            ORDER BY rows_count DESC
        """),
        ("top20_max_after_return", """
            SELECT search_date, search_time, code, name, capture_price, max_after_price,
                   max_after_return_pct, close_return_pct, base_volume, base_amount,
                   cum_volume_until_capture, cum_amount_until_capture, history_grade
            FROM analysis_5m_result
            WHERE valid_analysis_flag=1
            ORDER BY max_after_return_pct DESC
            LIMIT 20
        """),
        ("bottom20_close_return", """
            SELECT search_date, search_time, code, name, capture_price, close_1530,
                   close_return_pct, max_drawdown_pct, base_volume, base_amount, history_grade
            FROM analysis_5m_result
            WHERE valid_analysis_flag=1
            ORDER BY close_return_pct ASC
            LIMIT 20
        """),
    ]
    with conn.cursor() as cur:
        for title, sql in queries:
            print("\n=== " + title + " ===")
            cur.execute(sql)
            for row in cur.fetchall():
                print(row)


def print_meta(meta: Dict[str, Dict[str, Optional[str]]]) -> None:
    print("=== detected schema ===")
    for table_name in ["perf", "candle"]:
        print("[" + table_name + "]")
        for key, value in meta[table_name].items():
            print("  " + key + " = " + str(value))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--commit-every", type=int, default=200)
    args = parser.parse_args()

    load_env(args.env)
    conn = open_conn()
    try:
        ensure_schema(conn, args.rebuild)
        meta = build_meta(conn)
        print_meta(meta)
        rows = performance_rows(conn, meta, args.limit)
        print("performance rows = " + str(len(rows)))

        ok_count = 0
        fail_count = 0
        for idx, perf_row in enumerate(rows, start=1):
            try:
                result = analyze_one(conn, meta, perf_row)
                upsert(conn, result)
                ok_count += 1
            except Exception as ex:
                fail_count += 1
                print("[ERROR] idx=" + str(idx) + " row=" + str(perf_row) + " ex=" + str(ex))
            if idx % args.commit_every == 0:
                conn.commit()
                print("[" + str(idx) + "/" + str(len(rows)) + "] committed ok=" + str(ok_count) + " fail=" + str(fail_count))
        conn.commit()
        print("\n=== DONE build_5m_analysis_result ===")
        print("total=" + str(len(rows)) + " ok=" + str(ok_count) + " fail=" + str(fail_count))
        print_summary(conn)
        return 0
    except Exception as ex:
        conn.rollback()
        print("[FATAL] " + str(ex), file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
