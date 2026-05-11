# -*- coding: utf-8 -*-
"""Build SuperTrend Segment Ranking Discovery v1.1.

v1.1 fixes the semantic problem found in v1:
    - v1 WEAK_FOLLOW_THROUGH_ST was actually a strong early expansion state.
    - v1.1 separates EARLY_EXPANSION_ST from FAILED_EARLY_EXPANSION_ST when retention columns exist.
    - v1.1 compares score-rank-1 GOOD/GREAT vs BAD false positives.

This version is schema-tolerant. Some local DBs do not have early2_return_pct /
early3_return_pct in great_st_early_score_v1. In that case those derived fields
are stored as NULL and the classifier falls back to early high/amount/breakout.
"""

from __future__ import annotations

import argparse
import math
import os
import statistics
import sys
from datetime import datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

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


def ensure_schema(conn: Any, rebuild: bool) -> None:
    ddl = Path("sql/create_supertrend_segment_ranking_discovery_v1_1.sql").read_text(encoding="utf-8-sig")
    with conn.cursor() as cur:
        if rebuild:
            cur.execute("DROP TABLE IF EXISTS st_segment_ranking_false_positive_examples_v1_1")
            cur.execute("DROP TABLE IF EXISTS st_segment_ranking_score_rank1_quality_compare_v1_1")
            cur.execute("DROP TABLE IF EXISTS st_segment_ranking_state_summary_v1_1")
            cur.execute("DROP TABLE IF EXISTS st_segment_ranking_v1_1")
        for statement in ddl.split(";"):
            sql = statement.strip()
            if sql:
                cur.execute(sql)
    conn.commit()


def to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        value = float(value)
    try:
        result = float(value)
    except Exception:
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def to_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(float(value))
    except Exception:
        return 0


def avg(values: List[Optional[float]]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return None if not vals else sum(vals) / float(len(vals))


def median(values: List[Optional[float]]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return None if not vals else statistics.median(vals)


def rate(values: List[int]) -> Optional[float]:
    if not values:
        return None
    return sum(1 for v in values if v == 1) / float(len(values))


def safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or abs(b) < 0.0000001:
        return None
    return a / b


def amount_uk(value: Any) -> float:
    return (to_float(value) or 0.0) / 100000000.0


def minutes_from_open(dt_value: Any) -> Optional[int]:
    if dt_value is None or not isinstance(dt_value, datetime):
        return None
    open_dt = datetime.combine(dt_value.date(), time(9, 0, 0))
    return int((dt_value - open_dt).total_seconds() // 60)


def table_has_column(conn: Any, table_name: str, column_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = %s
              AND column_name = %s
            """,
            (table_name, column_name),
        )
        row = cur.fetchone()
    return to_int(row.get("cnt") if row else 0) > 0


def classify_state_v1_1(row: Dict[str, Any]) -> str:
    score = to_float(row.get("score_total")) or 0.0
    early3_high = to_float(row.get("early3_high_return_pct")) or 0.0
    early3_ret = to_float(row.get("early3_return_pct"))
    early3_amt_uk = amount_uk(row.get("early3_cum_amount"))
    start_amt_uk = amount_uk(row.get("start_cum_amount"))
    start_open = to_float(row.get("start_from_day_open_pct")) or 0.0
    start_low = to_float(row.get("start_from_day_low_pct")) or 0.0
    break3 = to_int(row.get("early3_break_start_high"))
    retention = safe_div(early3_ret, early3_high) if early3_ret is not None else None
    start_minutes = minutes_from_open(row.get("st_up_start_time"))

    if start_amt_uk >= 300.0 or start_open >= 12.0 or start_low >= 18.0:
        return "EXHAUSTED_ST"
    if start_minutes is not None and start_minutes >= 240 and start_open >= 5.0:
        return "EXHAUSTED_ST"

    if early3_high >= 4.0 and break3 == 1:
        if early3_ret is None:
            if score >= 60.0 or early3_amt_uk >= 50.0:
                return "EARLY_EXPANSION_ST"
            return "FAILED_EARLY_EXPANSION_ST"
        if early3_ret > 0.0 and retention is not None and retention >= 0.20:
            if score >= 60.0 or early3_amt_uk >= 50.0:
                return "EARLY_EXPANSION_ST"
        return "FAILED_EARLY_EXPANSION_ST"

    if early3_amt_uk < 30.0 and score < 40.0:
        return "LOW_POWER_ST"
    return "NEUTRAL_ST"


def load_joined_rows(conn: Any) -> List[Dict[str, Any]]:
    has_early2_ret = table_has_column(conn, "great_st_early_score_v1", "early2_return_pct")
    has_early3_ret = table_has_column(conn, "great_st_early_score_v1", "early3_return_pct")

    select_cols = ["r.*"]
    join_sql = ""
    if has_early2_ret or has_early3_ret:
        join_sql = " LEFT JOIN great_st_early_score_v1 s ON s.id = r.score_id "
        if has_early2_ret:
            select_cols.append("s.early2_return_pct AS early2_return_pct")
        else:
            select_cols.append("CAST(NULL AS DOUBLE) AS early2_return_pct")
        if has_early3_ret:
            select_cols.append("s.early3_return_pct AS early3_return_pct")
        else:
            select_cols.append("CAST(NULL AS DOUBLE) AS early3_return_pct")
    else:
        select_cols.append("CAST(NULL AS DOUBLE) AS early2_return_pct")
        select_cols.append("CAST(NULL AS DOUBLE) AS early3_return_pct")

    sql = "SELECT " + ", ".join(select_cols) + " FROM st_segment_ranking_v1 r " + join_sql + " ORDER BY r.trade_date, r.code, r.st_period, r.st_multiplier, r.st_up_start_time"
    print("early_return_columns_found=" + str(has_early2_ret or has_early3_ret))
    with conn.cursor() as cur:
        cur.execute(sql)
        return list(cur.fetchall())


def build_rows(base_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for r in base_rows:
        early3_high = to_float(r.get("early3_high_return_pct"))
        early3_ret = to_float(r.get("early3_return_pct"))
        early2_amt = to_float(r.get("early2_cum_amount"))
        early3_amt = to_float(r.get("early3_cum_amount"))
        retention = safe_div(early3_ret, early3_high)
        amount_growth = safe_div(early3_amt, early2_amt)
        is_rank1 = 1 if to_int(r.get("is_score_rank1")) == 1 else 0
        label_good = to_int(r.get("label_good_or_great"))
        label_bad = to_int(r.get("label_bad"))
        false_positive = 1 if is_rank1 == 1 and label_bad == 1 and label_good == 0 else 0
        positive_rank1 = 1 if is_rank1 == 1 and label_good == 1 else 0
        result.append({
            "base_ranking_id": r.get("id"),
            "score_id": r.get("score_id"),
            "signature_id": r.get("signature_id"),
            "segment_id": r.get("segment_id"),
            "trade_date": r.get("trade_date"),
            "search_time": r.get("search_time"),
            "code": r.get("code"),
            "name": r.get("name"),
            "timeframe": r.get("timeframe"),
            "st_period": r.get("st_period"),
            "st_multiplier": r.get("st_multiplier"),
            "segment_no": r.get("segment_no"),
            "st_up_start_time": r.get("st_up_start_time"),
            "st_up_end_time": r.get("st_up_end_time"),
            "st_start_minutes_from_open": minutes_from_open(r.get("st_up_start_time")),
            "st_up_bars": r.get("st_up_bars"),
            "quality_label": r.get("quality_label"),
            "st_up_max_return_pct": r.get("st_up_max_return_pct"),
            "st_up_end_return_pct": r.get("st_up_end_return_pct"),
            "score_total": r.get("score_total"),
            "rank_return_in_stock_param": r.get("rank_return_in_stock_param"),
            "rank_score_in_stock_param": r.get("rank_score_in_stock_param"),
            "is_return_rank1": r.get("is_return_rank1"),
            "is_score_rank1": r.get("is_score_rank1"),
            "score_rank_matches_return_rank1": r.get("score_rank_matches_return_rank1"),
            "segment_count_in_stock_param": r.get("segment_count_in_stock_param"),
            "label_great": r.get("label_great"),
            "label_good_or_great": r.get("label_good_or_great"),
            "label_bad": r.get("label_bad"),
            "start_from_day_open_pct": r.get("start_from_day_open_pct"),
            "start_from_day_low_pct": r.get("start_from_day_low_pct"),
            "start_cum_amount": r.get("start_cum_amount"),
            "early1_amount": r.get("early1_amount"),
            "early2_cum_amount": r.get("early2_cum_amount"),
            "early3_cum_amount": r.get("early3_cum_amount"),
            "early1_high_return_pct": r.get("early1_high_return_pct"),
            "early2_high_return_pct": r.get("early2_high_return_pct"),
            "early3_high_return_pct": r.get("early3_high_return_pct"),
            "early2_return_pct": r.get("early2_return_pct"),
            "early3_return_pct": r.get("early3_return_pct"),
            "early3_close_retention_ratio": retention,
            "early2_to_early3_amount_growth": amount_growth,
            "early2_break_start_high": r.get("early2_break_start_high"),
            "early3_break_start_high": r.get("early3_break_start_high"),
            "early2_max_singlebar_return_pct": r.get("early2_max_singlebar_return_pct"),
            "early3_max_singlebar_return_pct": r.get("early3_max_singlebar_return_pct"),
            "old_segment_state_label": r.get("segment_state_label"),
            "segment_state_label_v1_1": classify_state_v1_1(r),
            "false_positive_flag": false_positive,
            "positive_rank1_flag": positive_rank1,
        })
    return result


def insert_rows(conn: Any, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    cols = list(rows[0].keys())
    sql = "INSERT INTO st_segment_ranking_v1_1 (" + ",".join(cols) + ") VALUES (" + ",".join(["%s"] * len(cols)) + ") ON DUPLICATE KEY UPDATE " + ",".join([c + "=VALUES(" + c + ")" for c in cols if c != "base_ranking_id"]) + ", updated_at=CURRENT_TIMESTAMP"
    with conn.cursor() as cur:
        total = 0
        for r in rows:
            cur.execute(sql, [r.get(c) for c in cols])
            total += 1
            if total % 1000 == 0:
                conn.commit()
                print("v11_rows_so_far=" + str(total))
    conn.commit()


def load_v11(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM st_segment_ranking_v1_1")
        return list(cur.fetchall())


def refresh_summaries(conn: Any, rows: List[Dict[str, Any]]) -> None:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE st_segment_ranking_false_positive_examples_v1_1")
        cur.execute("TRUNCATE TABLE st_segment_ranking_score_rank1_quality_compare_v1_1")
        cur.execute("TRUNCATE TABLE st_segment_ranking_state_summary_v1_1")
    refresh_state_summary(conn, rows)
    refresh_rank1_quality_compare(conn, rows)
    refresh_false_positive_examples(conn, rows)
    conn.commit()


def refresh_state_summary(conn: Any, rows: List[Dict[str, Any]]) -> None:
    groups: Dict[Tuple[int, float, str], List[Dict[str, Any]]] = {}
    for r in rows:
        key = (to_int(r.get("st_period")), float(r.get("st_multiplier")), str(r.get("segment_state_label_v1_1")))
        groups.setdefault(key, []).append(r)
    sql = """
        INSERT INTO st_segment_ranking_state_summary_v1_1 (
            st_period, st_multiplier, segment_state_label_v1_1, row_count,
            avg_st_up_max_return_pct, median_st_up_max_return_pct,
            great_rate, good_or_great_rate, bad_rate,
            avg_score_total, avg_st_up_bars, avg_st_start_minutes_from_open,
            avg_early3_close_retention_ratio, avg_early2_to_early3_amount_growth
        ) VALUES (
            %(st_period)s, %(st_multiplier)s, %(segment_state_label_v1_1)s, %(row_count)s,
            %(avg_st_up_max_return_pct)s, %(median_st_up_max_return_pct)s,
            %(great_rate)s, %(good_or_great_rate)s, %(bad_rate)s,
            %(avg_score_total)s, %(avg_st_up_bars)s, %(avg_st_start_minutes_from_open)s,
            %(avg_early3_close_retention_ratio)s, %(avg_early2_to_early3_amount_growth)s
        )
    """
    with conn.cursor() as cur:
        for (period, mult, state), vals in groups.items():
            cur.execute(sql, {
                "st_period": period,
                "st_multiplier": mult,
                "segment_state_label_v1_1": state,
                "row_count": len(vals),
                "avg_st_up_max_return_pct": avg([to_float(v.get("st_up_max_return_pct")) for v in vals]),
                "median_st_up_max_return_pct": median([to_float(v.get("st_up_max_return_pct")) for v in vals]),
                "great_rate": rate([to_int(v.get("label_great")) for v in vals]),
                "good_or_great_rate": rate([to_int(v.get("label_good_or_great")) for v in vals]),
                "bad_rate": rate([to_int(v.get("label_bad")) for v in vals]),
                "avg_score_total": avg([to_float(v.get("score_total")) for v in vals]),
                "avg_st_up_bars": avg([to_float(v.get("st_up_bars")) for v in vals]),
                "avg_st_start_minutes_from_open": avg([to_float(v.get("st_start_minutes_from_open")) for v in vals]),
                "avg_early3_close_retention_ratio": avg([to_float(v.get("early3_close_retention_ratio")) for v in vals]),
                "avg_early2_to_early3_amount_growth": avg([to_float(v.get("early2_to_early3_amount_growth")) for v in vals]),
            })


def rank1_group_name(row: Dict[str, Any]) -> Optional[str]:
    if to_int(row.get("is_score_rank1")) != 1:
        return None
    if to_int(row.get("label_good_or_great")) == 1:
        return "RANK1_GOOD_OR_GREAT"
    if to_int(row.get("label_bad")) == 1:
        return "RANK1_BAD"
    return "RANK1_NEUTRAL"


def refresh_rank1_quality_compare(conn: Any, rows: List[Dict[str, Any]]) -> None:
    groups: Dict[Tuple[int, float, str], List[Dict[str, Any]]] = {}
    for r in rows:
        group_name = rank1_group_name(r)
        if group_name is None:
            continue
        key = (to_int(r.get("st_period")), float(r.get("st_multiplier")), group_name)
        groups.setdefault(key, []).append(r)
    sql = """
        INSERT INTO st_segment_ranking_score_rank1_quality_compare_v1_1 (
            st_period, st_multiplier, compare_group, row_count,
            avg_st_up_max_return_pct, median_st_up_max_return_pct,
            avg_score_total, avg_st_up_bars, avg_st_start_minutes_from_open,
            avg_start_from_day_open_pct, avg_start_from_day_low_pct, avg_start_cum_amount,
            avg_early1_amount, avg_early2_cum_amount, avg_early3_cum_amount,
            avg_early1_high_return_pct, avg_early2_high_return_pct, avg_early3_high_return_pct,
            avg_early2_return_pct, avg_early3_return_pct,
            avg_early3_close_retention_ratio, avg_early2_to_early3_amount_growth,
            early3_break_start_high_rate
        ) VALUES (
            %(st_period)s, %(st_multiplier)s, %(compare_group)s, %(row_count)s,
            %(avg_st_up_max_return_pct)s, %(median_st_up_max_return_pct)s,
            %(avg_score_total)s, %(avg_st_up_bars)s, %(avg_st_start_minutes_from_open)s,
            %(avg_start_from_day_open_pct)s, %(avg_start_from_day_low_pct)s, %(avg_start_cum_amount)s,
            %(avg_early1_amount)s, %(avg_early2_cum_amount)s, %(avg_early3_cum_amount)s,
            %(avg_early1_high_return_pct)s, %(avg_early2_high_return_pct)s, %(avg_early3_high_return_pct)s,
            %(avg_early2_return_pct)s, %(avg_early3_return_pct)s,
            %(avg_early3_close_retention_ratio)s, %(avg_early2_to_early3_amount_growth)s,
            %(early3_break_start_high_rate)s
        )
    """
    with conn.cursor() as cur:
        for (period, mult, group_name), vals in groups.items():
            cur.execute(sql, {
                "st_period": period,
                "st_multiplier": mult,
                "compare_group": group_name,
                "row_count": len(vals),
                "avg_st_up_max_return_pct": avg([to_float(v.get("st_up_max_return_pct")) for v in vals]),
                "median_st_up_max_return_pct": median([to_float(v.get("st_up_max_return_pct")) for v in vals]),
                "avg_score_total": avg([to_float(v.get("score_total")) for v in vals]),
                "avg_st_up_bars": avg([to_float(v.get("st_up_bars")) for v in vals]),
                "avg_st_start_minutes_from_open": avg([to_float(v.get("st_start_minutes_from_open")) for v in vals]),
                "avg_start_from_day_open_pct": avg([to_float(v.get("start_from_day_open_pct")) for v in vals]),
                "avg_start_from_day_low_pct": avg([to_float(v.get("start_from_day_low_pct")) for v in vals]),
                "avg_start_cum_amount": avg([to_float(v.get("start_cum_amount")) for v in vals]),
                "avg_early1_amount": avg([to_float(v.get("early1_amount")) for v in vals]),
                "avg_early2_cum_amount": avg([to_float(v.get("early2_cum_amount")) for v in vals]),
                "avg_early3_cum_amount": avg([to_float(v.get("early3_cum_amount")) for v in vals]),
                "avg_early1_high_return_pct": avg([to_float(v.get("early1_high_return_pct")) for v in vals]),
                "avg_early2_high_return_pct": avg([to_float(v.get("early2_high_return_pct")) for v in vals]),
                "avg_early3_high_return_pct": avg([to_float(v.get("early3_high_return_pct")) for v in vals]),
                "avg_early2_return_pct": avg([to_float(v.get("early2_return_pct")) for v in vals]),
                "avg_early3_return_pct": avg([to_float(v.get("early3_return_pct")) for v in vals]),
                "avg_early3_close_retention_ratio": avg([to_float(v.get("early3_close_retention_ratio")) for v in vals]),
                "avg_early2_to_early3_amount_growth": avg([to_float(v.get("early2_to_early3_amount_growth")) for v in vals]),
                "early3_break_start_high_rate": rate([to_int(v.get("early3_break_start_high")) for v in vals]),
            })


def refresh_false_positive_examples(conn: Any, rows: List[Dict[str, Any]]) -> None:
    fps = [r for r in rows if to_int(r.get("false_positive_flag")) == 1]
    fps = sorted(fps, key=lambda r: (-(to_float(r.get("score_total")) or 0.0), to_float(r.get("st_up_max_return_pct")) or 0.0))[:300]
    if not fps:
        return
    cols = [
        "base_ranking_id", "trade_date", "code", "name", "st_period", "st_multiplier", "segment_no",
        "st_up_start_time", "score_total", "st_up_max_return_pct", "quality_label", "segment_state_label_v1_1",
        "rank_return_in_stock_param", "early3_high_return_pct", "early3_return_pct", "early3_close_retention_ratio",
        "early3_cum_amount", "start_from_day_open_pct", "start_from_day_low_pct", "start_cum_amount"
    ]
    sql = "INSERT INTO st_segment_ranking_false_positive_examples_v1_1 (" + ",".join(cols) + ") VALUES (" + ",".join(["%s"] * len(cols)) + ") ON DUPLICATE KEY UPDATE " + ",".join([c + "=VALUES(" + c + ")" for c in cols if c != "base_ranking_id"]) + ", updated_at=CURRENT_TIMESTAMP"
    with conn.cursor() as cur:
        for r in fps:
            cur.execute(sql, [r.get(c) for c in cols])


def print_report(conn: Any) -> None:
    with conn.cursor() as cur:
        print("\n=== ST Segment State Summary v1.1 ===")
        cur.execute("""
            SELECT *
            FROM st_segment_ranking_state_summary_v1_1
            ORDER BY st_period, st_multiplier, avg_st_up_max_return_pct DESC
        """)
        for r in cur.fetchall():
            print(r)
        print("\n=== Score Rank1 Quality Compare v1.1 ===")
        cur.execute("""
            SELECT *
            FROM st_segment_ranking_score_rank1_quality_compare_v1_1
            ORDER BY st_period, st_multiplier, compare_group
        """)
        for r in cur.fetchall():
            print(r)
        print("\n=== High-score Rank1 BAD False Positive Examples v1.1 ===")
        cur.execute("""
            SELECT trade_date, code, name, st_period, st_multiplier, segment_no,
                   st_up_start_time, score_total, st_up_max_return_pct, quality_label,
                   segment_state_label_v1_1, rank_return_in_stock_param,
                   early3_high_return_pct, early3_return_pct, early3_close_retention_ratio,
                   start_from_day_open_pct, start_from_day_low_pct, start_cum_amount
            FROM st_segment_ranking_false_positive_examples_v1_1
            ORDER BY score_total DESC, st_up_max_return_pct ASC
            LIMIT 120
        """)
        for r in cur.fetchall():
            print(r)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    load_env(args.env)
    conn = open_conn()
    try:
        ensure_schema(conn, args.rebuild)
        base_rows = load_joined_rows(conn)
        print("=== build_supertrend_segment_ranking_discovery_v1_1 ===")
        print("base_rows=" + str(len(base_rows)))
        rows = build_rows(base_rows)
        insert_rows(conn, rows)
        v11_rows = load_v11(conn)
        refresh_summaries(conn, v11_rows)
        print("\n=== DONE build_supertrend_segment_ranking_discovery_v1_1 ===")
        print("rows=" + str(len(v11_rows)))
        print_report(conn)
        return 0
    except Exception as ex:
        conn.rollback()
        print("[FATAL] " + str(ex), file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
