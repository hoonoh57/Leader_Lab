# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

from src.common.db import mysql_connect
from src.common.env_loader import env_int, env_str, load_env_file


@dataclass(frozen=True)
class Minute5Target:
    performance_id: int
    code: str
    search_date: str
    search_time: str
    stop_time: str


def build_stop_time(search_date: str, search_time: str) -> str:
    date_part = search_date.replace("-", "")
    time_part = search_time.replace(":", "")
    if len(time_part) == 4:
        time_part += "00"
    if len(time_part) < 6:
        time_part = "090500"
    return date_part + time_part[:6]


def fetch_targets(limit: int = 0, only_missing: bool = True, min_count: int = 200) -> List[Minute5Target]:
    sql = """
    SELECT
        p.id AS performance_id,
        p.code,
        DATE_FORMAT(p.search_date, '%%Y-%%m-%%d') AS search_date,
        TIME_FORMAT(p.search_time, '%%H:%%i:%%s') AS search_time,
        COUNT(m.id) AS cached_count
    FROM performance_result p
    LEFT JOIN minute5_candles m
        ON m.code = p.code
       AND m.candle_time BETWEEN TIMESTAMP(p.search_date) - INTERVAL 5 DAY
                             AND TIMESTAMP(p.search_date) + INTERVAL 1 DAY
    GROUP BY p.id, p.code, p.search_date, p.search_time
    """
    params: List[object] = []
    if only_missing:
        sql += " HAVING cached_count < %s "
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
        targets.append(
            Minute5Target(
                performance_id=int(row["performance_id"]),
                code=str(row["code"]),
                search_date=str(row["search_date"]),
                search_time=str(row["search_time"]),
                stop_time=build_stop_time(str(row["search_date"]), str(row["search_time"])),
            )
        )
    return targets


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--min-count", type=int, default=env_int("MINUTE5_PREFETCH_COUNT", 200))
    args = parser.parse_args()

    load_env_file(args.env)
    targets = fetch_targets(limit=args.limit, only_missing=not args.all, min_count=args.min_count)

    print("=== minute5 targets ===")
    print(f"count={len(targets)} only_missing={not args.all} min_count={args.min_count}")
    for item in targets[:20]:
        print(item)


if __name__ == "__main__":
    main()
