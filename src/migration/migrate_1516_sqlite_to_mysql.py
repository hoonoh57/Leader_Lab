# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
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


def _table_columns(conn, table_name: str) -> List[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name});").fetchall()
    return [str(r[1]) for r in rows]


def _coalesce_column_expr(alias: str, available_columns: List[str], candidates: List[str], default_sql: str = "NULL") -> str:
    parts: List[str] = []
    for name in candidates:
        if name in available_columns:
            parts.append(f"{alias}.{name}")
    if not parts:
        return default_sql
    if len(parts) == 1:
        return parts[0]
    return "COALESCE(" + ", ".join(parts) + ")"


def fetch_sqlite_rows(sqlite_path: Optional[str]) -> List[Dict[str, Any]]:
    conn = sqlite_connect(sqlite_path)
    try:
        table_names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
        if "kiwoom_1516_raw_result" not in table_names:
            raise RuntimeError("SQLite table not found: kiwoom_1516_raw_result")

        raw_cols = _table_columns(conn, "kiwoom_1516_raw_result")
        has_map = "stock_code_map" in table_names
        map_cols = _table_columns(conn, "stock_code_map") if has_map else []

        raw_code_expr = _coalesce_column_expr("r", raw_cols, ["code", "stock_code", "종목코드"], "''")
        raw_name_expr = _coalesce_column_expr("r", raw_cols, ["stock_name", "name", "종목명"], "''")

        if has_map and "code" in map_cols and "stock_name" in map_cols:
            mapped_expr = f"COALESCE(m.code, {raw_code_expr}, '') AS mapped_code"
            join_sql = "LEFT JOIN stock_code_map m ON m.stock_name = " + raw_name_expr
        else:
            mapped_expr = f"COALESCE({raw_code_expr}, '') AS mapped_code"
            join_sql = ""

        sql = f"""
            SELECT
                r.*,
                {mapped_expr}
            FROM kiwoom_1516_raw_result r
            {join_sql}
            ORDER BY r.search_date, r.search_time, {raw_name_expr};
        """
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _first(row: Dict[str, Any], names: List[str]) -> Any:
    for name in names:
        if name in row and row.get(name) is not None:
            return row.get(name)
    return None


def convert_row(row: Dict[str, Any], condition_name: str, hold_period: str) -> Optional[Dict[str, Any]]:
    code = normalize_code(_first(row, ["mapped_code", "code", "stock_code", "종목코드"]))
    name = str(_first(row, ["stock_name", "name", "종목명"]) or "").strip()
    if code == "" or name == "":
        return None

    max_ret = to_decimal(_first(row, ["max_ret_in_period", "max_ret", "period_max_ret", "기간내최고수익률"]))
    ret_1m = to_decimal(_first(row, ["ret_1m", "min1", "1분간"]))
    ret_3m = to_decimal(_first(row, ["ret_3m", "min3", "3분간"]))
    ret_7h = to_decimal(_first(row, ["ret_7h", "hour7", "7시간"]))

    return {
        "search_date": str(_first(row, ["search_date", "date", "검색일자"]))[:10],
        "search_time": str(_first(row, ["search_time", "time", "검색시간"]) or env_str("DEFAULT_SEARCH_TIME", "09:05:00")),
        "condition_name": condition_name,
        "hold_period": hold_period,
        "code": code,
        "name": name,
        "ret_1m": ret_1m,
        "ret_3m": ret_3m,
        "ret_7h": ret_7h,
        "max_ret_in_period": max_ret,
        "search_volume": to_int(_first(row, ["search_volume", "volume", "검색시점거래량"])),
        "etc_value": to_decimal(_first(row, ["etc_value", "etc", "기타"])),
        "label_3": 1 if max_ret is not None and max_ret >= Decimal("3") else 0,
        "label_5": 1 if max_ret is not None and max_ret >= Decimal("5") else 0,
        "label_10": 1 if max_ret is not None and max_ret >= Decimal("10") else 0,
        "raw_line": row.get("raw_line"),
        "source_file": _first(row, ["source_file", "raw_path"]),
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
