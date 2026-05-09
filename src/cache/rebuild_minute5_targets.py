# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

from src.common.db import mysql_connect
from src.common.env_loader import env_int, env_str, load_env_file


MARKET_OPEN_HHMMSS = "090000"
LOOKBACK_CALENDAR_DAYS = 10


@dataclass(frozen=True)
class Minute5Target:
    performance_id: int
    code: str
    search_date: str
    search_time: str
    stop_time: str


def build_stop_time(search_date: str, search_time: str) -> str:
    """Build server32 request stopTime for the required 5m cache window.

    Required cache window:
    - previous trading candles before the target day
    - full target day session 09:00~15:30
    - total compacted window around 200 candles

    This server32 instance returns candles forward from stopTime. Therefore we start
    the request several calendar days before the target day, then the downloader
    compacts the response to: prior candles + full target-day session.
    """
    search_dt = datetime.strptime(search_date, "%Y-%m-%d")
    request_dt = search_dt - timedelta(days=LOOKBACK_CALENDAR_DAYS)
    return request_dt.strftime("%Y%m%d") + MARKET_OPEN_HHMMSS


def fetch_targets(limit: int = 0, only_missing: bool = True, min_count: int = 200) -> List[Minute5Target]:
    """Return performance rows needing 5-minute candle cache.

    A target is complete only when both conditions are true:
    - target-day session candles exist for 09:00~15:30
    - total prior+target-day compact window has at least min_count candles
    """
    sql = """
    SELECT
        p.id AS performance_id,
        p.code,
        DATE_FORMAT(p.search_date, '%%Y-%%m-%%d') AS search_date,
        TIME_FORMAT(p.search_time, '%%H:%%i:%%s') AS search_time,
        SUM(CASE
            WHEN m.candle_time BETWEEN TIMESTAMP(p.search_date) + INTERVAL 9 HOUR
                                   AND TIMESTAMP(p.search_date) + INTERVAL 15 HOUR + INTERVAL 30 MINUTE
            THEN 1 ELSE 0 END
        ) AS same_day_count,
        COUNT(m.id) AS total_window_count
    FROM performance_result p
    LEFT JOIN minute5_candles m
        ON m.code = p.code
       AND m.candle_time BETWEEN TIMESTAMP(p.search_date) - INTERVAL 10 DAY
                             AND TIMESTAMP(p.search_date) + INTERVAL 15 HOUR + INTERVAL 30 MINUTE
    GROUP BY p.id, p.code, p.search_date, p.search_time
    """
    params: List[object] = []
    if only_missing:
        sql += " HAVING same_day_count < 70 OR total_window_count < %s "
        params.append(min_count)
    sql += " ORDER BY p.search_date, p.code "
    if limit > 0:
        sql += " LIMIT %s "
        params.append(limit)

    conn = mysql_connect(env_str("MYSQL_DB_STOCK_INFO", "stock_info"))
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()

    targets: List[Minute5Target] = []
    for row in rows:
        search_date = str(row["search_date"])
        search_time = str(row["search_time"])
        targets.append(
            Minute5Target(
                performance_id=int(row["performance_id"]),
                code=str(row["code"]),
                search_date=search_date,
                search_time=search_time,
                stop_time=build_stop_time(search_date, search_time),
            )
        )
    return targets


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--min-count", type=int, default=200)
    args = parser.parse_args()

    load_env_file(args.env)
    min_count = args.min_count or env_int("MINUTE5_PREFETCH_COUNT", 200)
    targets = fetch_targets(limit=args.limit, only_missing=not args.all, min_count=min_count)

    print("=== minute5 targets ===")
    print(f"count={len(targets)} only_missing={not args.all} min_count={min_count}")
    for item in targets[:20]:
        print(item)


if __name__ == "__main__":
    main()
