# -*- coding: utf-8 -*-

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

import pymysql

from src.common.env_loader import env_int, env_str


def mysql_connect(database: Optional[str] = None):
    db_name = database or env_str("MYSQL_DB_STOCK_INFO", "stock_info")
    return pymysql.connect(
        host=env_str("MYSQL_HOST", "127.0.0.1"),
        port=env_int("MYSQL_PORT", 3306),
        user=env_str("MYSQL_USER", "root"),
        password=env_str("MYSQL_PASSWORD", ""),
        database=db_name,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def sqlite_connect(path_text: Optional[str] = None) -> sqlite3.Connection:
    db_path = Path(path_text or env_str("SQLITE_1516_DB", ""))
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite DB not found: {db_path}")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn
