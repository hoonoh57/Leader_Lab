# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

import pymysql

from src.common.env_loader import env_int, env_str, load_env_file


ROOT = Path(__file__).resolve().parents[2]
SQL_FILES = [
    ROOT / "sql" / "create_performance_result.sql",
    ROOT / "sql" / "create_minute5_candles.sql",
    ROOT / "sql" / "create_leader_feature_tables.sql",
]


def split_sql_script(text: str) -> List[str]:
    statements: List[str] = []
    buffer: List[str] = []
    in_single = False
    in_double = False

    for ch in text:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double

        if ch == ";" and not in_single and not in_double:
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer = []
        else:
            buffer.append(ch)

    tail = "".join(buffer).strip()
    if tail:
        statements.append(tail)

    return statements


def connect_mysql():
    return pymysql.connect(
        host=env_str("MYSQL_HOST", "127.0.0.1"),
        port=env_int("MYSQL_PORT", 3306),
        user=env_str("MYSQL_USER", "root"),
        password=env_str("MYSQL_PASSWORD", ""),
        charset="utf8mb4",
        autocommit=True,
    )


def run_schema() -> None:
    conn = connect_mysql()
    try:
        with conn.cursor() as cur:
            for path in SQL_FILES:
                if not path.exists():
                    raise FileNotFoundError(str(path))
                print(f"[DDL] {path}")
                text = path.read_text(encoding="utf-8-sig")
                statements = split_sql_script(text)
                for stmt in statements:
                    cur.execute(stmt)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    args = parser.parse_args()

    load_env_file(args.env)
    run_schema()
    print("[OK] schema setup completed")


if __name__ == "__main__":
    main()
