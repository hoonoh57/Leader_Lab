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
            print("=== performance_result summary ===")
            cur.execute(
                """
                SELECT
                    COUNT(*) AS row_count,
                    COUNT(DISTINCT search_date) AS day_count,
                    MIN(search_date) AS first_date,
                    MAX(search_date) AS last_date,
                    COUNT(DISTINCT code) AS code_count,
                    SUM(CASE WHEN label_10 = 1 THEN 1 ELSE 0 END) AS label10_count,
                    AVG(max_ret_in_period) AS avg_max_ret
                FROM performance_result;
                """
            )
            print(cur.fetchone())

            print("\n=== first 10 days ===")
            cur.execute(
                """
                SELECT search_date, COUNT(*) AS cnt
                FROM performance_result
                GROUP BY search_date
                ORDER BY search_date
                LIMIT 10;
                """
            )
            for row in cur.fetchall():
                print(row)

            print("\n=== last 10 days ===")
            cur.execute(
                """
                SELECT search_date, COUNT(*) AS cnt
                FROM performance_result
                GROUP BY search_date
                ORDER BY search_date DESC
                LIMIT 10;
                """
            )
            for row in cur.fetchall():
                print(row)

            print("\n=== rank null check ===")
            cur.execute(
                """
                SELECT COUNT(*) AS null_rank_count
                FROM performance_result
                WHERE actual_rank_by_max_ret IS NULL;
                """
            )
            print(cur.fetchone())
    finally:
        conn.close()


if __name__ == "__main__":
    main()
