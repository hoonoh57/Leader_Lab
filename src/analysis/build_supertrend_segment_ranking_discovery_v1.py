# -*- coding: utf-8 -*-
"""Build SuperTrend Segment Ranking Discovery v1.

Purpose:
    Analyze all ST uptrend segments inside the same stock/date/parameter group.
    Compare realized-return rank vs early-score rank.

This stage is diagnostic. It does NOT claim live trading profitability.
It discovers whether early-observable features can select the best ST segment
without choosing the best segment after seeing the future.
"""

from __future__ import annotations

import argparse
import math
import os
import statistics
import sys
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
    ddl = Path("sql/create_supertrend_segment_ranking_discovery_v1.sql").read_text(encoding="utf-8-sig")
    with conn.cursor() as cur:
        if rebuild:
            cur.execute("DROP TABLE IF EXISTS st_segment_ranking_alignment_summary_v1")
            cur.execute("DROP TABLE IF EXISTS st_segment_ranking_state_summary_v1")
            cur.execute("DROP TABLE IF EXISTS st_segment_ranking_rank_summary_v1")
            cur.execute("DROP TABLE IF EXISTS st_segment_ranking_v1")
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


def load_scores(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT *
            FROM great_st_early_score_v1
            ORDER BY trade_date, code, st_period, st_multiplier, st_up_start_time, segment_no
        """)
        return list(cur.fetchall())


def amount_uk(value: Any) -> float:
    return (to_float(value) or 0.0) / 100000000.0


def classify_state(row: Dict[str, Any]) -> str:
    score = to_float(row.get("score_total")) or 0.0
    early3_high = to_float(row.get("early3_high_return_pct")) or 0.0
    early3_ret = to_float(row.get("early3_return_pct"))
    early3_amt = amount_uk(row.get("early3_cum_amount"))
    start_amt = amount_uk(row.get("start_cum_amount"))
    start_open = to_float(row.get("start_from_day_open_pct")) or 0.0
    start_low = to_float(row.get("start_from_day_low_pct")) or 0.0
    break3 = to_int(row.get("early3_break_start_high"))

    if start_amt >= 300.0 or start_open >= 12.0 or start_low >= 18.0:
        return "EXHAUSTED_ST"
    if score >= 80.0 and early3_high >= 4.0 and early3_amt >= 100.0 and break3 == 1 and (early3_ret is not None and early3_ret > 0.0):
        return "RISING_EMBRYO_ST"
    if early3_high >= 4.0 and (early3_ret is None or early3_ret <= 0.5):
        return "WEAK_FOLLOW_THROUGH_ST"
    if early3_amt < 30.0 and score < 40.0:
        return "LOW_POWER_ST"
    return "NEUTRAL_ST"


def build_ranked_rows(scores: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[Any, str, int, float], List[Dict[str, Any]]] = {}
    for row in scores:
        key = (row.get("trade_date"), str(row.get("code")), to_int(row.get("st_period")), float(row.get("st_multiplier")))
        groups.setdefault(key, []).append(row)

    result: List[Dict[str, Any]] = []
    for _key, rows in groups.items():
        by_return = sorted(rows, key=lambda r: (-(to_float(r.get("st_up_max_return_pct")) or -9999.0), r.get("st_up_start_time")))
        by_score = sorted(rows, key=lambda r: (-(to_float(r.get("score_total")) or -9999.0), r.get("st_up_start_time")))
        return_rank: Dict[Any, int] = {}
        score_rank: Dict[Any, int] = {}
        rank = 1
        for r in by_return:
            return_rank[r.get("id")] = rank
            rank += 1
        rank = 1
        for r in by_score:
            score_rank[r.get("id")] = rank
            rank += 1
        score_rank1 = by_score[0] if by_score else None
        return_rank_of_score_rank1 = return_rank.get(score_rank1.get("id")) if score_rank1 is not None else None
        seg_count = len(rows)
        for r in rows:
            rr = return_rank.get(r.get("id"), 9999)
            sr = score_rank.get(r.get("id"), 9999)
            result.append({
                "score_id": r.get("id"),
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
                "st_up_bars": r.get("st_up_bars"),
                "quality_label": r.get("quality_label"),
                "st_up_max_return_pct": r.get("st_up_max_return_pct"),
                "st_up_end_return_pct": r.get("st_up_end_return_pct"),
                "score_total": r.get("score_total"),
                "start_penalty_score": r.get("start_penalty_score"),
                "early_power_score": r.get("early_power_score"),
                "early_expansion_score": r.get("early_expansion_score"),
                "break_confirm_score": r.get("break_confirm_score"),
                "singlebar_power_score": r.get("singlebar_power_score"),
                "rank_return_in_stock_param": rr,
                "rank_score_in_stock_param": sr,
                "is_return_rank1": 1 if rr == 1 else 0,
                "is_score_rank1": 1 if sr == 1 else 0,
                "score_rank_matches_return_rank1": 1 if sr == 1 and rr == 1 else 0,
                "segment_count_in_stock_param": seg_count,
                "return_rank_of_score_rank1": return_rank_of_score_rank1,
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
                "early2_break_start_high": r.get("early2_break_start_high"),
                "early3_break_start_high": r.get("early3_break_start_high"),
                "early2_max_singlebar_return_pct": r.get("early2_max_singlebar_return_pct"),
                "early3_max_singlebar_return_pct": r.get("early3_max_singlebar_return_pct"),
                "segment_state_label": classify_state(r),
            })
    return result


def insert_rows(conn: Any, rows: List[Dict[str, Any]]) -> None:
    cols = list(rows[0].keys()) if rows else []
    if not cols:
        return
    sql = "INSERT INTO st_segment_ranking_v1 (" + ",".join(cols) + ") VALUES (" + ",".join(["%s"] * len(cols)) + ") ON DUPLICATE KEY UPDATE " + ",".join([c + "=VALUES(" + c + ")" for c in cols if c != "score_id"]) + ", updated_at=CURRENT_TIMESTAMP"
    with conn.cursor() as cur:
        total = 0
        for r in rows:
            cur.execute(sql, [r.get(c) for c in cols])
            total += 1
            if total % 1000 == 0:
                conn.commit()
                print("ranking_rows_so_far=" + str(total))
    conn.commit()


def load_rankings(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM st_segment_ranking_v1")
        return list(cur.fetchall())


def refresh_summaries(conn: Any, rows: List[Dict[str, Any]]) -> None:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE st_segment_ranking_rank_summary_v1")
        cur.execute("TRUNCATE TABLE st_segment_ranking_state_summary_v1")
        cur.execute("TRUNCATE TABLE st_segment_ranking_alignment_summary_v1")
    refresh_rank_summary(conn, rows)
    refresh_state_summary(conn, rows)
    refresh_alignment_summary(conn, rows)
    conn.commit()


def refresh_rank_summary(conn: Any, rows: List[Dict[str, Any]]) -> None:
    groups: Dict[Tuple[int, float, str, int], List[Dict[str, Any]]] = {}
    for r in rows:
        for rank_type, field in [("score_rank", "rank_score_in_stock_param"), ("return_rank", "rank_return_in_stock_param")]:
            value = to_int(r.get(field))
            if value > 10:
                value = 999
            key = (to_int(r.get("st_period")), float(r.get("st_multiplier")), rank_type, value)
            groups.setdefault(key, []).append(r)
    sql = """
        INSERT INTO st_segment_ranking_rank_summary_v1 (
            st_period, st_multiplier, rank_type, rank_value, row_count,
            avg_st_up_max_return_pct, median_st_up_max_return_pct,
            great_rate, good_or_great_rate, bad_rate,
            avg_score_total, return_rank1_rate
        ) VALUES (
            %(st_period)s, %(st_multiplier)s, %(rank_type)s, %(rank_value)s, %(row_count)s,
            %(avg_st_up_max_return_pct)s, %(median_st_up_max_return_pct)s,
            %(great_rate)s, %(good_or_great_rate)s, %(bad_rate)s,
            %(avg_score_total)s, %(return_rank1_rate)s
        )
    """
    with conn.cursor() as cur:
        for (period, mult, rank_type, rank_value), vals in groups.items():
            cur.execute(sql, {
                "st_period": period,
                "st_multiplier": mult,
                "rank_type": rank_type,
                "rank_value": rank_value,
                "row_count": len(vals),
                "avg_st_up_max_return_pct": avg([to_float(v.get("st_up_max_return_pct")) for v in vals]),
                "median_st_up_max_return_pct": median([to_float(v.get("st_up_max_return_pct")) for v in vals]),
                "great_rate": rate([to_int(v.get("label_great")) for v in vals]),
                "good_or_great_rate": rate([to_int(v.get("label_good_or_great")) for v in vals]),
                "bad_rate": rate([to_int(v.get("label_bad")) for v in vals]),
                "avg_score_total": avg([to_float(v.get("score_total")) for v in vals]),
                "return_rank1_rate": rate([to_int(v.get("is_return_rank1")) for v in vals]),
            })


def refresh_state_summary(conn: Any, rows: List[Dict[str, Any]]) -> None:
    groups: Dict[Tuple[int, float, str], List[Dict[str, Any]]] = {}
    for r in rows:
        key = (to_int(r.get("st_period")), float(r.get("st_multiplier")), str(r.get("segment_state_label")))
        groups.setdefault(key, []).append(r)
    sql = """
        INSERT INTO st_segment_ranking_state_summary_v1 (
            st_period, st_multiplier, segment_state_label, row_count,
            avg_st_up_max_return_pct, median_st_up_max_return_pct,
            great_rate, good_or_great_rate, bad_rate,
            avg_score_total, avg_st_up_bars
        ) VALUES (
            %(st_period)s, %(st_multiplier)s, %(segment_state_label)s, %(row_count)s,
            %(avg_st_up_max_return_pct)s, %(median_st_up_max_return_pct)s,
            %(great_rate)s, %(good_or_great_rate)s, %(bad_rate)s,
            %(avg_score_total)s, %(avg_st_up_bars)s
        )
    """
    with conn.cursor() as cur:
        for (period, mult, state), vals in groups.items():
            cur.execute(sql, {
                "st_period": period,
                "st_multiplier": mult,
                "segment_state_label": state,
                "row_count": len(vals),
                "avg_st_up_max_return_pct": avg([to_float(v.get("st_up_max_return_pct")) for v in vals]),
                "median_st_up_max_return_pct": median([to_float(v.get("st_up_max_return_pct")) for v in vals]),
                "great_rate": rate([to_int(v.get("label_great")) for v in vals]),
                "good_or_great_rate": rate([to_int(v.get("label_good_or_great")) for v in vals]),
                "bad_rate": rate([to_int(v.get("label_bad")) for v in vals]),
                "avg_score_total": avg([to_float(v.get("score_total")) for v in vals]),
                "avg_st_up_bars": avg([to_float(v.get("st_up_bars")) for v in vals]),
            })


def refresh_alignment_summary(conn: Any, rows: List[Dict[str, Any]]) -> None:
    groups: Dict[Tuple[int, float], List[Dict[str, Any]]] = {}
    for r in rows:
        key = (to_int(r.get("st_period")), float(r.get("st_multiplier")))
        groups.setdefault(key, []).append(r)
    sql = """
        INSERT INTO st_segment_ranking_alignment_summary_v1 (
            st_period, st_multiplier, stock_param_group_count, avg_segment_count,
            score_rank1_is_return_rank1_rate, score_rank1_is_great_rate,
            score_rank1_is_good_or_great_rate, score_rank1_is_bad_rate,
            avg_return_rank_of_score_rank1, avg_score_rank1_return_pct
        ) VALUES (
            %(st_period)s, %(st_multiplier)s, %(stock_param_group_count)s, %(avg_segment_count)s,
            %(score_rank1_is_return_rank1_rate)s, %(score_rank1_is_great_rate)s,
            %(score_rank1_is_good_or_great_rate)s, %(score_rank1_is_bad_rate)s,
            %(avg_return_rank_of_score_rank1)s, %(avg_score_rank1_return_pct)s
        )
    """
    with conn.cursor() as cur:
        for (period, mult), vals in groups.items():
            score_rank1_rows = [v for v in vals if to_int(v.get("is_score_rank1")) == 1]
            group_keys = {(v.get("trade_date"), str(v.get("code")), period, mult) for v in vals}
            cur.execute(sql, {
                "st_period": period,
                "st_multiplier": mult,
                "stock_param_group_count": len(group_keys),
                "avg_segment_count": avg([to_float(v.get("segment_count_in_stock_param")) for v in score_rank1_rows]),
                "score_rank1_is_return_rank1_rate": rate([to_int(v.get("is_return_rank1")) for v in score_rank1_rows]),
                "score_rank1_is_great_rate": rate([to_int(v.get("label_great")) for v in score_rank1_rows]),
                "score_rank1_is_good_or_great_rate": rate([to_int(v.get("label_good_or_great")) for v in score_rank1_rows]),
                "score_rank1_is_bad_rate": rate([to_int(v.get("label_bad")) for v in score_rank1_rows]),
                "avg_return_rank_of_score_rank1": avg([to_float(v.get("rank_return_in_stock_param")) for v in score_rank1_rows]),
                "avg_score_rank1_return_pct": avg([to_float(v.get("st_up_max_return_pct")) for v in score_rank1_rows]),
            })


def print_report(conn: Any) -> None:
    with conn.cursor() as cur:
        print("\n=== ST Segment Ranking Alignment Summary ===")
        cur.execute("""
            SELECT *
            FROM st_segment_ranking_alignment_summary_v1
            ORDER BY st_period, st_multiplier
        """)
        for r in cur.fetchall():
            print(r)
        print("\n=== ST Segment Score Rank Summary ===")
        cur.execute("""
            SELECT st_period, st_multiplier, rank_value, row_count,
                   avg_st_up_max_return_pct, median_st_up_max_return_pct,
                   great_rate, good_or_great_rate, bad_rate, avg_score_total, return_rank1_rate
            FROM st_segment_ranking_rank_summary_v1
            WHERE rank_type='score_rank'
            ORDER BY st_period, st_multiplier, rank_value
        """)
        for r in cur.fetchall():
            print(r)
        print("\n=== ST Segment State Summary ===")
        cur.execute("""
            SELECT *
            FROM st_segment_ranking_state_summary_v1
            ORDER BY st_period, st_multiplier, avg_st_up_max_return_pct DESC
        """)
        for r in cur.fetchall():
            print(r)
        print("\n=== Score-rank1 but not return-rank1 examples ===")
        cur.execute("""
            SELECT trade_date, code, name, st_period, st_multiplier, segment_no,
                   st_up_start_time, score_total, rank_score_in_stock_param,
                   rank_return_in_stock_param, st_up_max_return_pct, quality_label,
                   segment_state_label
            FROM st_segment_ranking_v1
            WHERE is_score_rank1=1 AND is_return_rank1=0
            ORDER BY score_total DESC, st_up_max_return_pct DESC
            LIMIT 80
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
        scores = load_scores(conn)
        print("=== build_supertrend_segment_ranking_discovery_v1 ===")
        print("score_rows=" + str(len(scores)))
        ranked = build_ranked_rows(scores)
        print("ranked_rows=" + str(len(ranked)))
        insert_rows(conn, ranked)
        rows = load_rankings(conn)
        refresh_summaries(conn, rows)
        print("\n=== DONE build_supertrend_segment_ranking_discovery_v1 ===")
        print("rows=" + str(len(rows)))
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
