# -*- coding: utf-8 -*-
"""Diagnose missing_intraday rows in analysis_5m_result.

Run:
    python -m src.analysis.diagnose_5m_missing_intraday --env .env
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

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
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def print_rows(conn: Any, title: str, sql: str, params: Optional[Sequence[Any]] = None) -> None:
    print("\n=== " + title + " ===")
    with conn.cursor() as cur:
        cur.execute(sql, tuple(params or []))
        for row in cur.fetchall():
            print(row)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--sample-limit", type=int, default=100)
    args = parser.parse_args()

    load_env(args.env)
    conn = open_conn()
    try:
        print("=== diagnose_5m_missing_intraday ===")

        print_rows(conn, "analysis summary", """
            SELECT history_grade,
                   valid_analysis_flag,
                   invalid_reason,
                   COUNT(*) AS rows_count
            FROM analysis_5m_result
            GROUP BY history_grade, valid_analysis_flag, invalid_reason
            ORDER BY rows_count DESC
        """)

        print_rows(conn, "missing by search_date", """
            SELECT search_date,
                   COUNT(*) AS missing_rows,
                   COUNT(DISTINCT code) AS missing_codes
            FROM analysis_5m_result
            WHERE history_grade = 'missing_intraday'
            GROUP BY search_date
            ORDER BY missing_rows DESC, search_date
        """)

        print_rows(conn, "missing by code", """
            SELECT code,
                   MAX(name) AS name,
                   COUNT(*) AS missing_rows,
                   MIN(search_date) AS first_date,
                   MAX(search_date) AS last_date
            FROM analysis_5m_result
            WHERE history_grade = 'missing_intraday'
            GROUP BY code
            ORDER BY missing_rows DESC, code
            LIMIT 100
        """)

        print_rows(conn, "missing sample", """
            SELECT search_date, search_time, code, name, invalid_reason
            FROM analysis_5m_result
            WHERE history_grade = 'missing_intraday'
            ORDER BY search_date, search_time, code
            LIMIT %s
        """, [args.sample_limit])

        print_rows(conn, "minute5 coverage by date for missing dates", """
            SELECT DATE(m.candle_time) AS candle_date,
                   COUNT(*) AS candle_rows,
                   COUNT(DISTINCT m.code) AS code_count,
                   MIN(m.candle_time) AS first_time,
                   MAX(m.candle_time) AS last_time
            FROM minute5_candles m
            INNER JOIN (
                SELECT DISTINCT search_date
                FROM analysis_5m_result
                WHERE history_grade = 'missing_intraday'
            ) d ON DATE(m.candle_time) = d.search_date
            GROUP BY DATE(m.candle_time)
            ORDER BY candle_date
        """)

        print_rows(conn, "missing code exists in any minute5 cache", """
            SELECT a.code,
                   MAX(a.name) AS name,
                   COUNT(*) AS missing_rows,
                   COALESCE(MIN(m.candle_time), NULL) AS first_cached_time,
                   COALESCE(MAX(m.candle_time), NULL) AS last_cached_time,
                   COUNT(m.candle_time) AS total_cached_rows
            FROM analysis_5m_result a
            LEFT JOIN minute5_candles m ON m.code = a.code
            WHERE a.history_grade = 'missing_intraday'
            GROUP BY a.code
            ORDER BY missing_rows DESC, a.code
            LIMIT 100
        """)

        print("\n=== DONE diagnose_5m_missing_intraday ===")
        return 0
    except Exception as ex:
        print("[FATAL] " + str(ex), file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
