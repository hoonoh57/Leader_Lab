# -*- coding: utf-8 -*-
"""Build GREAT ST Early Score v1.

Input:
    great_st_early_signature

Output:
    great_st_early_score_v1
    great_st_early_score_v1_daily_rank
    great_st_early_score_v1_summary
    great_st_early_score_v1_topn_summary

Purpose:
    Convert early 1~3 bar GREAT ST signatures into an explainable score,
    then evaluate whether Top1/Top3/Top5 segments capture GREAT or GOOD_OR_GREAT labels.
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
    ddl = Path("sql/create_great_st_early_score_v1.sql").read_text(encoding="utf-8-sig")
    with conn.cursor() as cur:
        if rebuild:
            cur.execute("DROP TABLE IF EXISTS great_st_early_score_v1_topn_summary")
            cur.execute("DROP TABLE IF EXISTS great_st_early_score_v1_summary")
            cur.execute("DROP TABLE IF EXISTS great_st_early_score_v1_daily_rank")
            cur.execute("DROP TABLE IF EXISTS great_st_early_score_v1")
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


def cap(value: Optional[float], low: float, high: float) -> float:
    if value is None:
        return low
    if value < low:
        return low
    if value > high:
        return high
    return value


def scaled(value: Optional[float], threshold: float, max_points: float) -> float:
    if value is None or threshold <= 0:
        return 0.0
    return cap(value / threshold, 0.0, 1.0) * max_points


def load_signatures(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT *
            FROM great_st_early_signature
            ORDER BY trade_date, st_period, st_multiplier, code, segment_no
        """)
        return list(cur.fetchall())


def score_bucket(score: float) -> str:
    if score >= 80:
        return "S80_100"
    if score >= 60:
        return "S60_80"
    if score >= 40:
        return "S40_60"
    if score >= 20:
        return "S20_40"
    return "S0_20"


def calculate_score(row: Dict[str, Any]) -> Dict[str, float]:
    # StartPenalty: high pre-ST amount/position can mean late/exhausted segment.
    penalty = 0.0
    start_amount_uk = (to_float(row.get("start_cum_amount")) or 0.0) / 100000000.0
    start_open = to_float(row.get("start_from_day_open_pct")) or 0.0
    start_low = to_float(row.get("start_from_day_low_pct")) or 0.0
    if start_amount_uk >= 300.0:
        penalty -= 8.0
    elif start_amount_uk >= 200.0:
        penalty -= 5.0
    elif start_amount_uk >= 120.0:
        penalty -= 2.0
    if start_open >= 12.0:
        penalty -= 7.0
    elif start_open >= 8.0:
        penalty -= 4.0
    elif start_open >= 5.0:
        penalty -= 2.0
    if start_low >= 18.0:
        penalty -= 5.0
    elif start_low >= 12.0:
        penalty -= 3.0

    # EarlyPower: amount after ST start, not before ST start.
    early1_amt_uk = (to_float(row.get("early1_amount")) or 0.0) / 100000000.0
    early2_amt_uk = (to_float(row.get("early2_cum_amount")) or 0.0) / 100000000.0
    early3_amt_uk = (to_float(row.get("early3_cum_amount")) or 0.0) / 100000000.0
    early_power = 0.0
    early_power += scaled(early1_amt_uk, 40.0, 8.0)
    early_power += scaled(early2_amt_uk, 80.0, 10.0)
    early_power += scaled(early3_amt_uk, 100.0, 12.0)

    # EarlyExpansion: high expansion within first 2~3 bars.
    early2_high = to_float(row.get("early2_high_return_pct"))
    early3_high = to_float(row.get("early3_high_return_pct"))
    early3_ret = to_float(row.get("early3_return_pct"))
    expansion = 0.0
    expansion += scaled(early2_high, 3.0, 10.0)
    expansion += scaled(early3_high, 5.0, 15.0)
    expansion += scaled(early3_ret, 2.0, 5.0)

    # BreakConfirm.
    break_score = 0.0
    if to_int(row.get("early2_break_start_high")) == 1:
        break_score += 8.0
    if to_int(row.get("early3_break_start_high")) == 1:
        break_score += 12.0

    # SinglebarPower.
    singlebar = 0.0
    singlebar += scaled(to_float(row.get("early2_max_singlebar_return_pct")), 2.0, 8.0)
    singlebar += scaled(to_float(row.get("early3_max_singlebar_return_pct")), 3.0, 12.0)

    total = penalty + early_power + expansion + break_score + singlebar
    if total < 0:
        total = 0.0
    if total > 100:
        total = 100.0
    return {
        "start_penalty_score": penalty,
        "early_power_score": early_power,
        "early_expansion_score": expansion,
        "break_confirm_score": break_score,
        "singlebar_power_score": singlebar,
        "score_total": total,
    }


def build_score_row(sig: Dict[str, Any]) -> Dict[str, Any]:
    scores = calculate_score(sig)
    return {
        "signature_id": sig.get("id"),
        "segment_id": sig.get("segment_id"),
        "trade_date": sig.get("trade_date"),
        "search_time": sig.get("search_time"),
        "code": sig.get("code"),
        "name": sig.get("name"),
        "timeframe": sig.get("timeframe"),
        "st_period": sig.get("st_period"),
        "st_multiplier": sig.get("st_multiplier"),
        "segment_no": sig.get("segment_no"),
        "quality_label": sig.get("quality_label"),
        "label_great": sig.get("label_great"),
        "label_good_or_great": sig.get("label_good_or_great"),
        "label_bad": sig.get("label_bad"),
        "st_up_start_time": sig.get("st_up_start_time"),
        "st_up_end_time": sig.get("st_up_end_time"),
        "st_up_bars": sig.get("st_up_bars"),
        "st_up_max_return_pct": sig.get("st_up_max_return_pct"),
        "st_up_end_return_pct": sig.get("st_up_end_return_pct"),
        **scores,
        "start_from_day_open_pct": sig.get("start_from_day_open_pct"),
        "start_from_day_low_pct": sig.get("start_from_day_low_pct"),
        "start_cum_amount": sig.get("start_cum_amount"),
        "early1_amount": sig.get("early1_amount"),
        "early2_cum_amount": sig.get("early2_cum_amount"),
        "early3_cum_amount": sig.get("early3_cum_amount"),
        "early1_high_return_pct": sig.get("early1_high_return_pct"),
        "early2_high_return_pct": sig.get("early2_high_return_pct"),
        "early3_high_return_pct": sig.get("early3_high_return_pct"),
        "early2_break_start_high": sig.get("early2_break_start_high"),
        "early3_break_start_high": sig.get("early3_break_start_high"),
        "early2_max_singlebar_return_pct": sig.get("early2_max_singlebar_return_pct"),
        "early3_max_singlebar_return_pct": sig.get("early3_max_singlebar_return_pct"),
        "score_bucket": score_bucket(scores["score_total"]),
    }


def upsert_score(conn: Any, row: Dict[str, Any]) -> None:
    cols = list(row.keys())
    updates = [c + "=VALUES(" + c + ")" for c in cols if c != "signature_id"]
    sql = "INSERT INTO great_st_early_score_v1 (" + ",".join(cols) + ") VALUES (" + ",".join(["%s"] * len(cols)) + ") ON DUPLICATE KEY UPDATE " + ",".join(updates) + ", updated_at=CURRENT_TIMESTAMP"
    with conn.cursor() as cur:
        cur.execute(sql, [row.get(c) for c in cols])


def load_scores(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM great_st_early_score_v1")
        return list(cur.fetchall())


def refresh_daily_rank(conn: Any, rows: List[Dict[str, Any]]) -> None:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE great_st_early_score_v1_daily_rank")
    grouped: Dict[Tuple[Any, int, float], List[Dict[str, Any]]] = {}
    for r in rows:
        key = (r.get("trade_date"), to_int(r.get("st_period")), float(r.get("st_multiplier")))
        grouped.setdefault(key, []).append(r)
    insert_sql = """
        INSERT INTO great_st_early_score_v1_daily_rank (
            score_id, signature_id, segment_id, trade_date, code, name, st_period, st_multiplier,
            quality_label, label_great, label_good_or_great, label_bad,
            score_total, rank_in_day, st_up_max_return_pct, st_up_start_time
        ) VALUES (
            %(score_id)s, %(signature_id)s, %(segment_id)s, %(trade_date)s, %(code)s, %(name)s, %(st_period)s, %(st_multiplier)s,
            %(quality_label)s, %(label_great)s, %(label_good_or_great)s, %(label_bad)s,
            %(score_total)s, %(rank_in_day)s, %(st_up_max_return_pct)s, %(st_up_start_time)s
        )
    """
    with conn.cursor() as cur:
        for _key, vals in grouped.items():
            ordered = sorted(vals, key=lambda x: (-(to_float(x.get("score_total")) or 0.0), -(to_float(x.get("st_up_max_return_pct")) or 0.0)))
            rank = 1
            for r in ordered:
                cur.execute(insert_sql, {
                    "score_id": r.get("id"),
                    "signature_id": r.get("signature_id"),
                    "segment_id": r.get("segment_id"),
                    "trade_date": r.get("trade_date"),
                    "code": r.get("code"),
                    "name": r.get("name"),
                    "st_period": r.get("st_period"),
                    "st_multiplier": r.get("st_multiplier"),
                    "quality_label": r.get("quality_label"),
                    "label_great": r.get("label_great"),
                    "label_good_or_great": r.get("label_good_or_great"),
                    "label_bad": r.get("label_bad"),
                    "score_total": r.get("score_total"),
                    "rank_in_day": rank,
                    "st_up_max_return_pct": r.get("st_up_max_return_pct"),
                    "st_up_start_time": r.get("st_up_start_time"),
                })
                rank += 1
    conn.commit()


def refresh_summary(conn: Any, rows: List[Dict[str, Any]]) -> None:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE great_st_early_score_v1_summary")
        cur.execute("TRUNCATE TABLE great_st_early_score_v1_topn_summary")
    groups: Dict[Tuple[int, float, str], List[Dict[str, Any]]] = {}
    for r in rows:
        base = (to_int(r.get("st_period")), float(r.get("st_multiplier")))
        for g in ["ALL", "BUCKET_" + str(r.get("score_bucket")), "QUALITY_" + str(r.get("quality_label"))]:
            groups.setdefault((base[0], base[1], g), []).append(r)
    insert_summary_sql = """
        INSERT INTO great_st_early_score_v1_summary (
            st_period, st_multiplier, summary_group, row_count,
            avg_score_total, avg_st_up_max_return_pct,
            great_rate, good_or_great_rate, bad_rate,
            avg_start_penalty_score, avg_early_power_score, avg_early_expansion_score,
            avg_break_confirm_score, avg_singlebar_power_score
        ) VALUES (
            %(st_period)s, %(st_multiplier)s, %(summary_group)s, %(row_count)s,
            %(avg_score_total)s, %(avg_st_up_max_return_pct)s,
            %(great_rate)s, %(good_or_great_rate)s, %(bad_rate)s,
            %(avg_start_penalty_score)s, %(avg_early_power_score)s, %(avg_early_expansion_score)s,
            %(avg_break_confirm_score)s, %(avg_singlebar_power_score)s
        )
    """
    with conn.cursor() as cur:
        for (period, mult, group), vals in groups.items():
            cur.execute(insert_summary_sql, {
                "st_period": period,
                "st_multiplier": mult,
                "summary_group": group,
                "row_count": len(vals),
                "avg_score_total": avg([to_float(v.get("score_total")) for v in vals]),
                "avg_st_up_max_return_pct": avg([to_float(v.get("st_up_max_return_pct")) for v in vals]),
                "great_rate": rate([to_int(v.get("label_great")) for v in vals]),
                "good_or_great_rate": rate([to_int(v.get("label_good_or_great")) for v in vals]),
                "bad_rate": rate([to_int(v.get("label_bad")) for v in vals]),
                "avg_start_penalty_score": avg([to_float(v.get("start_penalty_score")) for v in vals]),
                "avg_early_power_score": avg([to_float(v.get("early_power_score")) for v in vals]),
                "avg_early_expansion_score": avg([to_float(v.get("early_expansion_score")) for v in vals]),
                "avg_break_confirm_score": avg([to_float(v.get("break_confirm_score")) for v in vals]),
                "avg_singlebar_power_score": avg([to_float(v.get("singlebar_power_score")) for v in vals]),
            })
    refresh_topn_summary(conn)
    conn.commit()


def refresh_topn_summary(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM great_st_early_score_v1_daily_rank")
        ranks = list(cur.fetchall())
    params = sorted({(to_int(r.get("st_period")), float(r.get("st_multiplier"))) for r in ranks})
    insert_sql = """
        INSERT INTO great_st_early_score_v1_topn_summary (
            st_period, st_multiplier, top_n, group_count, candidate_count,
            great_hit_group_rate, good_or_great_hit_group_rate, bad_in_top_rate,
            avg_top_score, avg_top_st_up_max_return_pct
        ) VALUES (
            %(st_period)s, %(st_multiplier)s, %(top_n)s, %(group_count)s, %(candidate_count)s,
            %(great_hit_group_rate)s, %(good_or_great_hit_group_rate)s, %(bad_in_top_rate)s,
            %(avg_top_score)s, %(avg_top_st_up_max_return_pct)s
        )
    """
    with conn.cursor() as cur:
        for period, mult in params:
            p_rows = [r for r in ranks if to_int(r.get("st_period")) == period and float(r.get("st_multiplier")) == mult]
            day_keys = sorted({r.get("trade_date") for r in p_rows})
            for top_n in [1, 3, 5, 10]:
                candidate_rows = [r for r in p_rows if to_int(r.get("rank_in_day")) <= top_n]
                great_hit_days = 0
                gog_hit_days = 0
                for d in day_keys:
                    d_rows = [r for r in candidate_rows if r.get("trade_date") == d]
                    if any(to_int(r.get("label_great")) == 1 for r in d_rows):
                        great_hit_days += 1
                    if any(to_int(r.get("label_good_or_great")) == 1 for r in d_rows):
                        gog_hit_days += 1
                cur.execute(insert_sql, {
                    "st_period": period,
                    "st_multiplier": mult,
                    "top_n": top_n,
                    "group_count": len(day_keys),
                    "candidate_count": len(candidate_rows),
                    "great_hit_group_rate": great_hit_days / float(len(day_keys)) if day_keys else None,
                    "good_or_great_hit_group_rate": gog_hit_days / float(len(day_keys)) if day_keys else None,
                    "bad_in_top_rate": rate([to_int(r.get("label_bad")) for r in candidate_rows]),
                    "avg_top_score": avg([to_float(r.get("score_total")) for r in candidate_rows]),
                    "avg_top_st_up_max_return_pct": avg([to_float(r.get("st_up_max_return_pct")) for r in candidate_rows]),
                })


def print_report(conn: Any) -> None:
    with conn.cursor() as cur:
        print("\n=== GREAT ST Early Score v1 TopN Summary ===")
        cur.execute("""
            SELECT st_period, st_multiplier, top_n, group_count, candidate_count,
                   great_hit_group_rate, good_or_great_hit_group_rate, bad_in_top_rate,
                   avg_top_score, avg_top_st_up_max_return_pct
            FROM great_st_early_score_v1_topn_summary
            ORDER BY st_period, st_multiplier, top_n
        """)
        for row in cur.fetchall():
            print(row)
        print("\n=== GREAT ST Early Score v1 Bucket Summary ===")
        cur.execute("""
            SELECT st_period, st_multiplier, summary_group, row_count,
                   avg_score_total, avg_st_up_max_return_pct,
                   great_rate, good_or_great_rate, bad_rate
            FROM great_st_early_score_v1_summary
            WHERE summary_group LIKE 'BUCKET_%' OR summary_group='ALL'
            ORDER BY st_period, st_multiplier,
                     FIELD(summary_group,'ALL','BUCKET_S80_100','BUCKET_S60_80','BUCKET_S40_60','BUCKET_S20_40','BUCKET_S0_20')
        """)
        for row in cur.fetchall():
            print(row)
        print("\n=== Top scored examples ===")
        cur.execute("""
            SELECT trade_date, code, name, st_period, st_multiplier, quality_label,
                   score_total, st_up_max_return_pct, st_up_start_time,
                   early3_cum_amount, early3_high_return_pct, start_cum_amount
            FROM great_st_early_score_v1
            ORDER BY score_total DESC, st_up_max_return_pct DESC
            LIMIT 60
        """)
        for row in cur.fetchall():
            print(row)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    load_env(args.env)
    conn = open_conn()
    try:
        ensure_schema(conn, args.rebuild)
        signatures = load_signatures(conn)
        print("=== build_great_st_early_score_v1 ===")
        print("signatures=" + str(len(signatures)))
        total = 0
        for sig in signatures:
            upsert_score(conn, build_score_row(sig))
            total += 1
            if total > 0 and total % 1000 == 0:
                conn.commit()
                print("rows_so_far=" + str(total))
        conn.commit()
        scores = load_scores(conn)
        refresh_daily_rank(conn, scores)
        refresh_summary(conn, scores)
        print("\n=== DONE build_great_st_early_score_v1 ===")
        print("rows=" + str(len(scores)))
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
