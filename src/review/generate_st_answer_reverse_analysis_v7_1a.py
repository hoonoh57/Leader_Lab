# -*- coding: utf-8 -*-
"""Compatibility wrapper for ST Answer Reverse Analysis v7-1a.

The original v7_1 module expected information_schema column rows to expose
`column_name`. On some MySQL/PyMySQL combinations the key is returned as
`COLUMN_NAME`, which produced a list of None values. This wrapper patches only
that metadata reader and then executes the v7-1a generator.
"""

from __future__ import annotations

from typing import Any, List

from src.review import generate_st_answer_reverse_analysis_v7_1 as base


def robust_table_columns(conn: Any, table_name: str) -> List[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name AS column_name
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = %s
            ORDER BY ordinal_position
            """,
            (table_name,),
        )
        rows = cur.fetchall()

    columns: List[str] = []
    for row in rows:
        value = None
        if isinstance(row, dict):
            value = row.get("column_name")
            if value is None:
                value = row.get("COLUMN_NAME")
            if value is None and len(row) > 0:
                value = list(row.values())[0]
        else:
            try:
                value = row[0]
            except Exception:
                value = None
        if value is not None:
            columns.append(str(value))
    return columns


base.table_columns = robust_table_columns


if __name__ == "__main__":
    raise SystemExit(base.main())
