# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.common.db import mysql_connect, sqlite_connect
from src.common.env_loader import env_str, load_env_file


def to_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("%", "").replace("+", "").replace('"', "")
    if text == "" or text == "-":
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("+", "").replace('"', "")
    if text == "" or text == "-":
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def normalize_code(value: Any) -> str:
    text = str(value or "").strip()
    if text.startswith("A") and len(text) == 7:
        text = text[1:]
    return text.zfill(6) if text else ""


def fetch_sqlite_rows(sqlite_path: Optional[str]) -> List[Dict[str, Any]]:
    conn = sqlite_connect(sqlite_path)
    try:
        table_names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
        if "kiwoom_1516_raw_result" not in table_names:
            raise RuntimeError("SQLite table not found: kiwoom_1516_raw_result")

        rows = conn.execute(
            """
            SELECT
                r.*,
                COALESCE(m.code, r.code, '') AS mapped_code
            FROM kiwoom_1516_raw_result r
            LEFT JOIN stock_code_map m
                ON m.stock_name = r.stock_name
            ORDER BY r.search_date, r.search_time, r.stock_name;
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def convert_row(row: Dict[str, Any], condition_name: str, hold_period: str) -> Optional[Dict[str, Any]]:
    code = normalize_code(row.get("mapped_code") or row.get("code"))
    name = str(row.get("stock_name") or row.get("name") or "").strip()
    if code == "" or name == "":
        return None

    max_ret = to_decimal(row.get("max_ret_in_period") or row.get("max_ret"))
    ret_1m = to_decimal(row.get("ret_1m"))
    ret_3m = to_decimal(row.get("ret_3m"))
    ret_7h = to_decimal(row.get("ret_7h"))

    return {
        "search_date": str(row.get("search_date"))[:10],
        "search_time": str(row.get("search_time") or env_str("DEFAULT_SEARCH_TIME", "09:05:00")),
        "condition_name": condition_name,
        "hold_period": hold_period,
        "code": code,
        "name": name,
        "ret_1m": ret_1m,
        "ret_3m": ret_3m,
        "ret_7h": ret_7h,
        "max_ret_in_period": max_ret,
        "search_volume": to_int(row.get("search_volume") or row.get("volume")),
        "etc_value": to_decimal(row.get("etc_value") or row.get("etc")),
        "label_3": 1 if max_ret is not None and max_ret >= Decimal("3") else 0,
        "label_5": 1 if max_ret is not None and max_ret >= Decimal("5") else 0,
        "label_10": 1 if max_ret is not None and max_ret >= Decimal("10") else 0,
        "raw_line": row.get("raw_line"),
        "source_file": row.get("source_file") or row.get("raw_path"),
    }


def upsert_rows(rows: Iterable[Dict[str, Any]], batch_size: int = 500) -> int:
    sql = """
    INSERT INTO performance_result (
        search_date, search_time, condition_name, hold_period,
        code, name,
        ret_1m, ret_3m, ret_7h, max_ret_in_period,
        search_volume, etc_value,
        label_3, label_5, label_10,
        raw_line, source_file
    ) VALUES (
        %(search_date)s, %(search_time)s, %(condition_name)s, %(hold_period)s,
        %(code)s, %(name)s,
        %(ret_1m)s, %(ret_3m)s, %(ret_7h)s, %(max_ret_in_period)s,
        %(search_volume)s, %(etc_value)s,
        %(label_3)s, %(label_5)s, %(label_10)s,
        %(raw_line)s, %(source_file)s
    )
    ON DUPLICATE KEY UPDATE
        name = VALUES(name),
        ret_1m = VALUES(ret_1m),
        ret_3m = VALUES(ret_3m),
        ret_7h = VALUES(ret_7h),
        max_ret_in_period = VALUES(max_ret_in_period),
        search_volume = VALUES(search_volume),
        etc_value = VALUES(etc_value),
        label_3 = VALUES(label_3),
        label_5 = VALUES(label_5),
        label_10 = VALUES(label_10),
        raw_line = VALUES(raw_line),
        source_file = VALUES(source_file),
        updated_at = CURRENT_TIMESTAMP;
    """
    conn = mysql_connect(env_str("MYSQL_DB_STOCK_INFO", "stock_info"))
    count = 0
    batch: List[Dict[str, Any]] = []
    try:
        with conn.cursor() as cur:
            for row in rows:
                batch.append(row)
                if len(batch) >= batch_size:
                    cur.executemany(sql, batch)
                    count += len(batch)
                    batch = []
            if batch:
                cur.executemany(sql, batch)
                count += len(batch)
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return count


def update_actual_ranks() -> None:
    conn = mysql_connect(env_str("MYSQL_DB_STOCK_INFO", "stock_info"))
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE performance_result p
                JOIN (
                    SELECT
                        id,
                        ROW_NUMBER() OVER (
                            PARTITION BY search_date, search_time, condition_name, hold_period
                            ORDER BY max_ret_in_period DESC, code ASC
                        ) AS rn
                    FROM performance_result
                ) r ON p.id = r.id
                SET p.actual_rank_by_max_ret = r.rn;
                """
            )
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--sqlite-db", default="")
    parser.add_argument("--condition-name", default="")
    parser.add_argument("--hold-period", default="")
    args = parser.parse_args()

    load_env_file(args.env)
    condition_name = args.condition_name or env_str("DEFAULT_CONDITION_NAME", "1516")
    hold_period = args.hold_period or env_str("DEFAULT_HOLD_PERIOD", "7시간")
    sqlite_path = args.sqlite_db or env_str("SQLITE_1516_DB", "")

    source_rows = fetch_sqlite_rows(sqlite_path)
    converted: List[Dict[str, Any]] = []
    skipped = 0
    for row in source_rows:
        item = convert_row(row, condition_name, hold_period)
        if item is None:
            skipped += 1
            continue
        converted.append(item)

    saved = upsert_rows(converted)
    update_actual_ranks()

    print("=== migrate_1516_sqlite_to_mysql ===")
    print(f"source_rows={len(source_rows)} converted={len(converted)} skipped={skipped} saved_or_updated={saved}")


if __name__ == "__main__":
    main()
