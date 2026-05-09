# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse

from src.common.db import mysql_connect
from src.common.env_loader import env_str, load_env_file


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    args = parser.parse_args()

    load_env_file(args.env)
    conn = mysql_connect(env_str("MYSQL_DB_STOCK_INFO", "stock_info"))
    try:
        with conn.cursor() as cur:
            print("=== minute5_candles summary ===")
            cur.execute(
                """
                SELECT
                    COUNT(*) AS candle_count,
                    COUNT(DISTINCT code) AS code_count,
                    MIN(candle_time) AS first_time,
                    MAX(candle_time) AS last_time
                FROM minute5_candles;
                """
            )
            print(cur.fetchone())

            print("\n=== cache coverage for performance_result ===")
            cur.execute(
                """
                SELECT
                    COUNT(*) AS perf_rows,
                    SUM(CASE WHEN x.cached_count >= 200 THEN 1 ELSE 0 END) AS enough_rows,
                    SUM(CASE WHEN x.cached_count > 0 AND x.cached_count < 200 THEN 1 ELSE 0 END) AS partial_rows,
                    SUM(CASE WHEN x.cached_count = 0 THEN 1 ELSE 0 END) AS missing_rows,
                    AVG(x.cached_count) AS avg_cached_count
                FROM (
                    SELECT
                        p.id,
                        COUNT(m.id) AS cached_count
                    FROM performance_result p
                    LEFT JOIN minute5_candles m
                        ON m.code = p.code
                       AND m.candle_time BETWEEN TIMESTAMP(p.search_date) - INTERVAL 5 DAY
                                             AND TIMESTAMP(p.search_date) + INTERVAL 1 DAY
                    GROUP BY p.id
                ) x;
                """
            )
            print(cur.fetchone())

            print("\n=== worst coverage sample ===")
            cur.execute(
                """
                SELECT
                    p.search_date,
                    p.search_time,
                    p.code,
                    p.name,
                    COUNT(m.id) AS cached_count
                FROM performance_result p
                LEFT JOIN minute5_candles m
                    ON m.code = p.code
                   AND m.candle_time BETWEEN TIMESTAMP(p.search_date) - INTERVAL 5 DAY
                                         AND TIMESTAMP(p.search_date) + INTERVAL 1 DAY
                GROUP BY p.id, p.search_date, p.search_time, p.code, p.name
                ORDER BY cached_count ASC, p.search_date, p.code
                LIMIT 30;
                """
            )
            for row in cur.fetchall():
                print(row)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
