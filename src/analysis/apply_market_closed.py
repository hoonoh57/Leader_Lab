# -*- coding: utf-8 -*-
"""Apply KRX market closed calendar to analysis_5m_result.

This script converts rows on known market-closed dates from generic
missing_intraday/no_same_day_candles to explicit market_closed.

Run:
    python -m src.analysis.apply_market_closed --env .env
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

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
    db_name = env_value(["DB_NAME", "MYSQL_DATABASE", "MYSQL_DB"])
    if db_name is None:
        raise RuntimeError(".env에 DB_NAME 또는 MYSQL_DATABASE가 필요합니다.")

    return pymysql.connect(
        host=env_value(["DB_HOST", "MYSQL_HOST"], "127.0.0.1"),
        port=int(env_value(["DB_PORT", "MYSQL_PORT"], "3306") or "3306"),
        user=env_value(["DB_USER", "MYSQL_USER"], "root"),
        password=env_value(["DB_PASS", "DB_PASSWORD", "MYSQL_PASSWORD", "MYSQL_PASS"], ""),
        database=db_name,
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


def load_closed_dates(calendar_path: str) -> Dict[str, str]:
    path = Path(calendar_path)
    if not path.exists():
        raise RuntimeError("휴장일 설정 파일이 없습니다: " + str(path))
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    closed_dates = data.get("closed_dates", {})
    if not isinstance(closed_dates, dict):
        raise RuntimeError("closed_dates 형식이 dict가 아닙니다: " + str(path))
    return {str(k): str(v) for k, v in closed_dates.items()}


def print_summary(conn: Any) -> None:
    queries = [
        ("market_closed summary", """
            SELECT history_grade, invalid_reason, COUNT(*) AS rows_count
            FROM analysis_5m_result
            WHERE history_grade = 'market_closed'
               OR invalid_reason = 'market_closed'
            GROUP BY history_grade, invalid_reason
            ORDER BY rows_count DESC
        """),
        ("analysis summary after market closed", """
            SELECT history_grade,
                   valid_analysis_flag,
                   invalid_reason,
                   COUNT(*) AS rows_count
            FROM analysis_5m_result
            GROUP BY history_grade, valid_analysis_flag, invalid_reason
            ORDER BY rows_count DESC
        """),
        ("remaining missing_intraday by date", """
            SELECT search_date,
                   COUNT(*) AS rows_count,
                   COUNT(DISTINCT code) AS code_count
            FROM analysis_5m_result
            WHERE history_grade = 'missing_intraday'
            GROUP BY search_date
            ORDER BY rows_count DESC, search_date
        """),
    ]
    with conn.cursor() as cur:
        for title, sql in queries:
            print("\n=== " + title + " ===")
            cur.execute(sql)
            for row in cur.fetchall():
                print(row)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--calendar", default="configs/krx_market_closed_2026.json")
    args = parser.parse_args()

    load_env(args.env)
    closed_dates = load_closed_dates(args.calendar)
    if not closed_dates:
        print("[WARN] closed_dates가 비어 있습니다.")
        return 0

    conn = open_conn()
    try:
        print("=== apply_market_closed ===")
        print("calendar=" + args.calendar)
        print("closed_dates=" + ", ".join(sorted(closed_dates.keys())))

        date_values = sorted(closed_dates.keys())
        placeholders = ",".join(["%s"] * len(date_values))

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT search_date, COUNT(*) AS rows_count
                FROM analysis_5m_result
                WHERE search_date IN (""" + placeholders + """)
                GROUP BY search_date
                ORDER BY search_date
                """,
                date_values,
            )
            print("\n=== rows on closed dates before update ===")
            for row in cur.fetchall():
                print(row)

            cur.execute(
                """
                UPDATE analysis_5m_result
                SET history_grade = 'market_closed',
                    valid_analysis_flag = 0,
                    invalid_reason = 'market_closed',
                    updated_at = CURRENT_TIMESTAMP
                WHERE search_date IN (""" + placeholders + """)
                """,
                date_values,
            )
            updated = cur.rowcount

        conn.commit()
        print("\nupdated_rows=" + str(updated))
        print_summary(conn)
        print("\n=== DONE apply_market_closed ===")
        return 0
    except Exception as ex:
        conn.rollback()
        print("[FATAL] " + str(ex), file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
