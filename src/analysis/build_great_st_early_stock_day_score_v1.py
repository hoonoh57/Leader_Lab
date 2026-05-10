# -*- coding: utf-8 -*-
"""Build GREAT ST Early Stock-Day Score v1.

This stage aggregates segment/parameter-level GREAT ST Early Score rows into one
stock-day row while preserving multi-parameter confirmation as a signal.

Input:
    great_st_early_score_v1

Output:
    great_st_early_stock_day_score_v1
    great_st_early_stock_day_rank_v1
    great_st_early_stock_day_summary_v1
    great_st_early_stock_day_topn_summary_v1
    great_st_param_confirmation_summary_v1
"""

from __future__ import annotations

import argparse
import math
import os
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
    ddl = Path("sql/create_great_st_early_stock_day_score_v1.sql").read_text(encoding="utf-8-sig")
    with conn.cursor() as cur:
        if rebuild:
            cur.execute("DROP TABLE IF EXISTS great_st_param_confirmation_summary_v1")
            cur.execute("DROP TABLE IF EXISTS great_st_early_stock_day_topn_summary_v1")
            cur.execute("DROP TABLE IF EXISTS great_st_early_stock_day_summary_v1")
            cur.execute("DROP TABLE IF EXISTS great_st_early_stock_day_rank_v1")
            cur.execute("DROP TABLE IF EXISTS great_st_early_stock_day_score_v1")
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


def rate(values: List[int]) -> Optional[float]:
    if not values:
        return None
    return sum(1 for v in values if v == 1) / float(len(values))


def clamp(value: float, low: float, high: float) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


def load_param_scores(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT *
            FROM great_st_early_score_v1
            ORDER BY trade_date, code, score_total DESC, st_up_max_return_pct DESC
        """)
        return list(cur.fetchall())


def best_quality_label(rows: List[Dict[str, Any]]) -> str:
    if any(to_int(r.get("label_great")) == 1 for r in rows):
        return "GREAT"
    if any(to_int(r.get("label_good_or_great")) == 1 for r in rows):
        return "GOOD"
    if all(to_int(r.get("label_bad")) == 1 for r in rows):
        return "BAD"
    if any(to_int(r.get("label_bad")) == 1 for r in rows):
        return "MIXED_BAD"
    return "NEUTRAL"


def topn_avg(values: List[float], n: int) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values, reverse=True)
    items = ordered[:n]
    return sum(items) / float(len(items))


def build_stock_day_row(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    ordered = sorted(rows, key=lambda r: (-(to_float(r.get("score_total")) or 0.0), -(to_float(r.get("st_up_max_return_pct")) or 0.0)))
    best = ordered[0]
    scores = [to_float(r.get("score_total")) or 0.0 for r in rows]
    returns = [to_float(r.get("st_up_max_return_pct")) for r in rows]
    param_count = len(rows)
    ge80 = sum(1 for r in rows if (to_float(r.get("score_total")) or 0.0) >= 80.0)
    ge60 = sum(1 for r in rows if (to_float(r.get("score_total")) or 0.0) >= 60.0)
    ge40 = sum(1 for r in rows if (to_float(r.get("score_total")) or 0.0) >= 40.0)
    great_count = sum(1 for r in rows if to_int(r.get("label_great")) == 1)
    gog_count = sum(1 for r in rows if to_int(r.get("label_good_or_great")) == 1)
    bad_count = sum(1 for r in rows if to_int(r.get("label_bad")) == 1)

    base = max(scores) if scores else 0.0
    strong_bonus = max(0, min(ge80 - 1, 3)) * 4.0
    mid_bonus = max(0, min(ge60 - ge80, 3)) * 1.5
    bad_penalty = min(bad_count, 3) * 2.0
    stock_score = clamp(base + strong_bonus + mid_bonus - bad_penalty, 0.0, 100.0)

    stock_has_great = 1 if great_count > 0 else 0
    stock_has_gog = 1 if gog_count > 0 else 0
    stock_has_bad = 1 if bad_count > 0 else 0

    return {
        "trade_date": best.get("trade_date"),
        "code": best.get("code"),
        "name": best.get("name"),
        "stock_score_v1": stock_score,
        "base_score": base,
        "strong_confirm_bonus": strong_bonus,
        "mid_confirm_bonus": mid_bonus,
        "bad_penalty": bad_penalty,
        "param_count": param_count,
        "score_ge_80_param_count": ge80,
        "score_ge_60_param_count": ge60,
        "score_ge_40_param_count": ge40,
        "great_param_count": great_count,
        "good_or_great_param_count": gog_count,
        "bad_param_count": bad_count,
        "param_score_max": max(scores) if scores else None,
        "param_score_avg": avg(scores),
        "param_score_sum": sum(scores),
        "param_score_top2_avg": topn_avg(scores, 2),
        "param_score_top3_avg": topn_avg(scores, 3),
        "stock_max_return_pct": max([v for v in returns if v is not None]) if any(v is not None for v in returns) else None,
        "stock_best_quality_label": best_quality_label(rows),
        "stock_has_great": stock_has_great,
        "stock_has_good_or_great": stock_has_gog,
        "stock_has_bad": stock_has_bad,
        "best_score_id": best.get("id"),
        "best_signature_id": best.get("signature_id"),
        "best_segment_id": best.get("segment_id"),
        "best_st_period": best.get("st_period"),
        "best_st_multiplier": best.get("st_multiplier"),
        "best_quality_label": best.get("quality_label"),
        "best_st_up_max_return_pct": best.get("st_up_max_return_pct"),
        "best_st_up_start_time": best.get("st_up_start_time"),
        "best_early3_cum_amount": best.get("early3_cum_amount"),
        "best_early3_high_return_pct": best.get("early3_high_return_pct"),
        "best_start_cum_amount": best.get("start_cum_amount"),
    }


def upsert_stock_day(conn: Any, row: Dict[str, Any]) -> None:
    cols = list(row.keys())
    updates = [c + "=VALUES(" + c + ")" for c in cols if c not in ("trade_date", "code")]
    sql = "INSERT INTO great_st_early_stock_day_score_v1 (" + ",".join(cols) + ") VALUES (" + ",".join(["%s"] * len(cols)) + ") ON DUPLICATE KEY UPDATE " + ",".join(updates) + ", updated_at=CURRENT_TIMESTAMP"
    with conn.cursor() as cur:
        cur.execute(sql, [row.get(c) for c in cols])


def load_stock_days(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM great_st_early_stock_day_score_v1")
        return list(cur.fetchall())


def refresh_rank(conn: Any, rows: List[Dict[str, Any]]) -> None:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE great_st_early_stock_day_rank_v1")
    grouped: Dict[Any, List[Dict[str, Any]]] = {}
    for r in rows:
        grouped.setdefault(r.get("trade_date"), []).append(r)
    sql = """
        INSERT INTO great_st_early_stock_day_rank_v1 (
            stock_day_score_id, trade_date, code, name, rank_in_day, stock_score_v1,
            stock_max_return_pct, stock_best_quality_label, stock_has_great, stock_has_good_or_great, stock_has_bad,
            param_count, score_ge_80_param_count, score_ge_60_param_count,
            great_param_count, good_or_great_param_count, bad_param_count,
            best_st_period, best_st_multiplier, best_st_up_start_time
        ) VALUES (
            %(stock_day_score_id)s, %(trade_date)s, %(code)s, %(name)s, %(rank_in_day)s, %(stock_score_v1)s,
            %(stock_max_return_pct)s, %(stock_best_quality_label)s, %(stock_has_great)s, %(stock_has_good_or_great)s, %(stock_has_bad)s,
            %(param_count)s, %(score_ge_80_param_count)s, %(score_ge_60_param_count)s,
            %(great_param_count)s, %(good_or_great_param_count)s, %(bad_param_count)s,
            %(best_st_period)s, %(best_st_multiplier)s, %(best_st_up_start_time)s
        )
    """
    with conn.cursor() as cur:
        for _d, vals in grouped.items():
            ordered = sorted(vals, key=lambda x: (-(to_float(x.get("stock_score_v1")) or 0.0), -(to_float(x.get("stock_max_return_pct")) or 0.0)))
            rank = 1
            for r in ordered:
                cur.execute(sql, {
                    "stock_day_score_id": r.get("id"),
                    "trade_date": r.get("trade_date"),
                    "code": r.get("code"),
                    "name": r.get("name"),
                    "rank_in_day": rank,
                    "stock_score_v1": r.get("stock_score_v1"),
                    "stock_max_return_pct": r.get("stock_max_return_pct"),
                    "stock_best_quality_label": r.get("stock_best_quality_label"),
                    "stock_has_great": r.get("stock_has_great"),
                    "stock_has_good_or_great": r.get("stock_has_good_or_great"),
                    "stock_has_bad": r.get("stock_has_bad"),
                    "param_count": r.get("param_count"),
                    "score_ge_80_param_count": r.get("score_ge_80_param_count"),
                    "score_ge_60_param_count": r.get("score_ge_60_param_count"),
                    "great_param_count": r.get("great_param_count"),
                    "good_or_great_param_count": r.get("good_or_great_param_count"),
                    "bad_param_count": r.get("bad_param_count"),
                    "best_st_period": r.get("best_st_period"),
                    "best_st_multiplier": r.get("best_st_multiplier"),
                    "best_st_up_start_time": r.get("best_st_up_start_time"),
                })
                rank += 1
    conn.commit()


def refresh_summary(conn: Any, rows: List[Dict[str, Any]]) -> None:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE great_st_early_stock_day_summary_v1")
        cur.execute("TRUNCATE TABLE great_st_early_stock_day_topn_summary_v1")
        cur.execute("TRUNCATE TABLE great_st_param_confirmation_summary_v1")

    groups: Dict[str, List[Dict[str, Any]]] = {"ALL": rows}
    for r in rows:
        groups.setdefault("SCORE_GE_80_COUNT_" + str(to_int(r.get("score_ge_80_param_count"))), []).append(r)
        groups.setdefault("SCORE_GE_60_COUNT_" + str(to_int(r.get("score_ge_60_param_count"))), []).append(r)
        groups.setdefault("PARAM_COUNT_" + str(to_int(r.get("param_count"))), []).append(r)
        groups.setdefault("QUALITY_" + str(r.get("stock_best_quality_label")), []).append(r)

    sql = """
        INSERT INTO great_st_early_stock_day_summary_v1 (
            summary_group, row_count, avg_stock_score_v1, avg_stock_max_return_pct,
            great_rate, good_or_great_rate, bad_rate,
            avg_param_count, avg_score_ge_80_param_count, avg_score_ge_60_param_count,
            avg_great_param_count, avg_bad_param_count
        ) VALUES (
            %(summary_group)s, %(row_count)s, %(avg_stock_score_v1)s, %(avg_stock_max_return_pct)s,
            %(great_rate)s, %(good_or_great_rate)s, %(bad_rate)s,
            %(avg_param_count)s, %(avg_score_ge_80_param_count)s, %(avg_score_ge_60_param_count)s,
            %(avg_great_param_count)s, %(avg_bad_param_count)s
        )
    """
    with conn.cursor() as cur:
        for group, vals in groups.items():
            cur.execute(sql, {
                "summary_group": group,
                "row_count": len(vals),
                "avg_stock_score_v1": avg([to_float(v.get("stock_score_v1")) for v in vals]),
                "avg_stock_max_return_pct": avg([to_float(v.get("stock_max_return_pct")) for v in vals]),
                "great_rate": rate([to_int(v.get("stock_has_great")) for v in vals]),
                "good_or_great_rate": rate([to_int(v.get("stock_has_good_or_great")) for v in vals]),
                "bad_rate": rate([to_int(v.get("stock_has_bad")) for v in vals]),
                "avg_param_count": avg([to_float(v.get("param_count")) for v in vals]),
                "avg_score_ge_80_param_count": avg([to_float(v.get("score_ge_80_param_count")) for v in vals]),
                "avg_score_ge_60_param_count": avg([to_float(v.get("score_ge_60_param_count")) for v in vals]),
                "avg_great_param_count": avg([to_float(v.get("great_param_count")) for v in vals]),
                "avg_bad_param_count": avg([to_float(v.get("bad_param_count")) for v in vals]),
            })
    refresh_topn(conn)
    refresh_param_confirmation(conn, rows)
    conn.commit()


def refresh_topn(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM great_st_early_stock_day_rank_v1")
        ranks = list(cur.fetchall())
    day_keys = sorted({r.get("trade_date") for r in ranks})
    sql = """
        INSERT INTO great_st_early_stock_day_topn_summary_v1 (
            top_n, day_count, candidate_count, great_hit_day_rate,
            good_or_great_hit_day_rate, bad_candidate_rate,
            avg_top_stock_score, avg_top_stock_max_return_pct
        ) VALUES (
            %(top_n)s, %(day_count)s, %(candidate_count)s, %(great_hit_day_rate)s,
            %(good_or_great_hit_day_rate)s, %(bad_candidate_rate)s,
            %(avg_top_stock_score)s, %(avg_top_stock_max_return_pct)s
        )
    """
    with conn.cursor() as cur:
        for top_n in [1, 3, 5, 10]:
            candidates = [r for r in ranks if to_int(r.get("rank_in_day")) <= top_n]
            great_days = 0
            gog_days = 0
            for d in day_keys:
                d_rows = [r for r in candidates if r.get("trade_date") == d]
                if any(to_int(r.get("stock_has_great")) == 1 for r in d_rows):
                    great_days += 1
                if any(to_int(r.get("stock_has_good_or_great")) == 1 for r in d_rows):
                    gog_days += 1
            cur.execute(sql, {
                "top_n": top_n,
                "day_count": len(day_keys),
                "candidate_count": len(candidates),
                "great_hit_day_rate": great_days / float(len(day_keys)) if day_keys else None,
                "good_or_great_hit_day_rate": gog_days / float(len(day_keys)) if day_keys else None,
                "bad_candidate_rate": rate([to_int(r.get("stock_has_bad")) for r in candidates]),
                "avg_top_stock_score": avg([to_float(r.get("stock_score_v1")) for r in candidates]),
                "avg_top_stock_max_return_pct": avg([to_float(r.get("stock_max_return_pct")) for r in candidates]),
            })


def refresh_param_confirmation(conn: Any, rows: List[Dict[str, Any]]) -> None:
    sql = """
        INSERT INTO great_st_param_confirmation_summary_v1 (
            confirm_type, confirm_value, row_count, avg_stock_score_v1,
            avg_stock_max_return_pct, great_rate, good_or_great_rate, bad_rate
        ) VALUES (
            %(confirm_type)s, %(confirm_value)s, %(row_count)s, %(avg_stock_score_v1)s,
            %(avg_stock_max_return_pct)s, %(great_rate)s, %(good_or_great_rate)s, %(bad_rate)s
        )
    """
    specs = [
        ("param_count", "param_count"),
        ("score_ge_80_param_count", "score_ge_80_param_count"),
        ("score_ge_60_param_count", "score_ge_60_param_count"),
        ("great_param_count", "great_param_count"),
        ("good_or_great_param_count", "good_or_great_param_count"),
        ("bad_param_count", "bad_param_count"),
    ]
    with conn.cursor() as cur:
        for label, field in specs:
            values = sorted({to_int(r.get(field)) for r in rows})
            for value in values:
                vals = [r for r in rows if to_int(r.get(field)) == value]
                cur.execute(sql, {
                    "confirm_type": label,
                    "confirm_value": value,
                    "row_count": len(vals),
                    "avg_stock_score_v1": avg([to_float(v.get("stock_score_v1")) for v in vals]),
                    "avg_stock_max_return_pct": avg([to_float(v.get("stock_max_return_pct")) for v in vals]),
                    "great_rate": rate([to_int(v.get("stock_has_great")) for v in vals]),
                    "good_or_great_rate": rate([to_int(v.get("stock_has_good_or_great")) for v in vals]),
                    "bad_rate": rate([to_int(v.get("stock_has_bad")) for v in vals]),
                })


def print_report(conn: Any) -> None:
    with conn.cursor() as cur:
        print("\n=== Stock-Day TopN Summary ===")
        cur.execute("""
            SELECT top_n, day_count, candidate_count, great_hit_day_rate,
                   good_or_great_hit_day_rate, bad_candidate_rate,
                   avg_top_stock_score, avg_top_stock_max_return_pct
            FROM great_st_early_stock_day_topn_summary_v1
            ORDER BY top_n
        """)
        for r in cur.fetchall():
            print(r)
        print("\n=== Multi-Parameter Confirmation Summary ===")
        cur.execute("""
            SELECT confirm_type, confirm_value, row_count, avg_stock_score_v1,
                   avg_stock_max_return_pct, great_rate, good_or_great_rate, bad_rate
            FROM great_st_param_confirmation_summary_v1
            ORDER BY confirm_type, confirm_value
        """)
        for r in cur.fetchall():
            print(r)
        print("\n=== Top Stock-Day Examples ===")
        cur.execute("""
            SELECT trade_date, code, name, rank_in_day, stock_score_v1,
                   stock_max_return_pct, stock_best_quality_label,
                   score_ge_80_param_count, score_ge_60_param_count,
                   great_param_count, good_or_great_param_count, bad_param_count,
                   best_st_period, best_st_multiplier, best_st_up_start_time
            FROM great_st_early_stock_day_rank_v1
            WHERE rank_in_day <= 5
            ORDER BY trade_date, rank_in_day
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
        param_rows = load_param_scores(conn)
        print("=== build_great_st_early_stock_day_score_v1 ===")
        print("param_score_rows=" + str(len(param_rows)))
        grouped: Dict[Tuple[Any, str], List[Dict[str, Any]]] = {}
        for r in param_rows:
            grouped.setdefault((r.get("trade_date"), str(r.get("code"))), []).append(r)
        total = 0
        for _key, rows in grouped.items():
            upsert_stock_day(conn, build_stock_day_row(rows))
            total += 1
            if total > 0 and total % 1000 == 0:
                conn.commit()
                print("stock_days_so_far=" + str(total))
        conn.commit()
        stock_days = load_stock_days(conn)
        refresh_rank(conn, stock_days)
        refresh_summary(conn, stock_days)
        print("\n=== DONE build_great_st_early_stock_day_score_v1 ===")
        print("stock_day_rows=" + str(len(stock_days)))
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
