# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
from datetime import datetime, timedelta

from src.common.db import mysql_connect
from src.common.env_loader import env_str, load_env_file


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--start", default="2026-01-05")
    parser.add_argument("--end", default="2026-05-06")
    parser.add_argument("--include-prev-from-time", default="14:00:00")
    parser.add_argument("--delete-all", action="store_true")
    args = parser.parse_args()

    load_env_file(args.env)

    conn = mysql_connect(env_str("MYSQL_DB_STOCK_INFO", "stock_info"))
    try:
        with conn.cursor() as cur:
            if args.delete_all:
                cur.execute("SELECT COUNT(*) AS cnt FROM minute5_candles")
                before = cur.fetchone()["cnt"]
                cur.execute("DELETE FROM minute5_candles")
                conn.commit()
                print(f"[PURGE] delete_all before={before} deleted={cur.rowcount}")
                return

            start_dt = datetime.strptime(args.start, "%Y-%m-%d")
            prev_dt = start_dt - timedelta(days=1)
            hh, mm, ss = [int(x) for x in args.include_prev_from_time.split(":")]
            lower = prev_dt.replace(hour=hh, minute=mm, second=ss)
            end_dt = datetime.strptime(args.end, "%Y-%m-%d").replace(hour=15, minute=30, second=0)

            cur.execute("SELECT COUNT(*) AS cnt FROM minute5_candles")
            before = cur.fetchone()["cnt"]
            cur.execute(
                """
                DELETE FROM minute5_candles
                WHERE candle_time < %s OR candle_time > %s
                """,
                (lower.strftime("%Y-%m-%d %H:%M:%S"), end_dt.strftime("%Y-%m-%d %H:%M:%S")),
            )
            deleted = cur.rowcount
            conn.commit()
            print("=== purge_minute5_cache ===")
            print(f"range={lower} ~ {end_dt}")
            print(f"before={before} deleted={deleted}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
