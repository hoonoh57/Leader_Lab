# -*- coding: utf-8 -*-
"""Build SuperTrend Segment Ranking Discovery v1.2.

v1.2 does not create a trading strategy. It audits v1.1 EARLY_EXPANSION_ST
false positives and tests deterministic filter candidates that can be evaluated
from data available at or very near the SuperTrend-up start window.

Important sync rule:
    - This file is intended to be committed on GitHub first.
    - Local execution should be only: git pull -> run the script that exists.
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
    ddl = Path("sql/create_supertrend_segment_ranking_discovery_v1_2.sql").read_text(encoding="utf-8-sig")
    with conn.cursor() as cur:
        if rebuild:
            cur.execute("DROP TABLE IF EXISTS st_segment_ranking_false_positive_examples_v1_2")
            cur.execute("DROP TABLE IF EXISTS st_segment_ranking_filter_summary_v1_2")
            cur.execute("DROP TABLE IF EXISTS st_segment_ranking_v1_2")
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


def safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or abs(b) < 0.0000001:
        return None
    return a / b


def avg(values: List[Optional[float]]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return sum(vals) / float(len(vals))


def median(values: List[Optional[float]]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return statistics.median(vals)


def rate(values: List[int]) -> Optional[float]:
    if not values:
        return None
    return sum(1 for v in values if v == 1) / float(len(values))


def amount_uk(value: Any) -> float:
    return (to_float(value) or 0.0) / 100000000.0


def build_live_risk(row: Dict[str, Any]) -> Tuple[float, str]:
    start_open = to_float(row.get("start_from_day_open_pct")) or 0.0
    start_low = to_float(row.get("start_from_day_low_pct")) or 0.0
    start_amt_uk = amount_uk(row.get("start_cum_amount"))
    start_minutes = to_int(row.get("st_start_minutes_from_open"))
    score = 0.0
    reasons: List[str] = []

    if start_open >= 9.0:
        score += 35.0
        reasons.append("OPEN_OVERHEATED_9")
    elif start_open >= 8.0:
        score += 20.0
        reasons.append("OPEN_OVERHEATED_8")

    if start_low >= 12.0:
        score += 30.0
        reasons.append("LOW_OVEREXTENDED_12")
    elif start_low >= 10.0:
        score += 18.0
        reasons.append("LOW_OVEREXTENDED_10")

    if start_amt_uk >= 300.0:
        score += 30.0
        reasons.append("AMOUNT_EXHAUSTED_300UK")
    elif start_amt_uk >= 150.0:
        score += 15.0
        reasons.append("AMOUNT_HEAVY_150UK")

    if start_minutes >= 90:
        score += 20.0
        reasons.append("LATE_90")
    elif start_minutes >= 60:
        score += 10.0
        reasons.append("LATE_60")

    if score >= 50.0:
        return score, "LIVE_EXCLUDE_" + "+".join(reasons)
    if score >= 25.0:
        return score, "LIVE_CAUTION_" + "+".join(reasons)
    return score, "LIVE_PASS"


def build_post_diagnostic(row: Dict[str, Any], post_ext: Optional[float]) -> str:
    if post_ext is None:
        return "POST_UNKNOWN"
    if post_ext <= 0.3:
        return "POST_EARLY3_PEAK_EXHAUSTED_03"
    if post_ext <= 0.5:
        return "POST_EARLY3_PEAK_EXHAUSTED_05"
    if post_ext >= 2.0:
        return "POST_CONFIRMED_EXTENSION_20"
    return "POST_WEAK_EXTENSION"


def load_source_rows(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT *
            FROM st_segment_ranking_v1_1
            WHERE segment_state_label_v1_1 = 'EARLY_EXPANSION_ST'
              AND is_score_rank1 = 1
            ORDER BY trade_date, code, st_period, st_multiplier, st_up_start_time
        """)
        return list(cur.fetchall())


def build_rows(source_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for r in source_rows:
        max_ret = to_float(r.get("st_up_max_return_pct"))
        early3_high = to_float(r.get("early3_high_return_pct"))
        post_ext = None
        ratio = None
        if max_ret is not None and early3_high is not None:
            post_ext = max_ret - early3_high
            ratio = safe_div(post_ext, early3_high)
        live_risk, live_label = build_live_risk(r)
        post_label = build_post_diagnostic(r, post_ext)
        start_open = to_float(r.get("start_from_day_open_pct")) or 0.0
        start_low = to_float(r.get("start_from_day_low_pct")) or 0.0
        start_minutes = to_int(r.get("st_start_minutes_from_open"))
        rows.append({
            "base_ranking_id": r.get("base_ranking_id"),
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
            "st_start_minutes_from_open": r.get("st_start_minutes_from_open"),
            "st_up_bars": r.get("st_up_bars"),
            "quality_label": r.get("quality_label"),
            "st_up_max_return_pct": r.get("st_up_max_return_pct"),
            "score_total": r.get("score_total"),
            "rank_return_in_stock_param": r.get("rank_return_in_stock_param"),
            "rank_score_in_stock_param": r.get("rank_score_in_stock_param"),
            "is_score_rank1": r.get("is_score_rank1"),
            "label_great": r.get("label_great"),
            "label_good_or_great": r.get("label_good_or_great"),
            "label_bad": r.get("label_bad"),
            "segment_state_label_v1_1": r.get("segment_state_label_v1_1"),
            "start_from_day_open_pct": r.get("start_from_day_open_pct"),
            "start_from_day_low_pct": r.get("start_from_day_low_pct"),
            "start_cum_amount": r.get("start_cum_amount"),
            "early1_amount": r.get("early1_amount"),
            "early2_cum_amount": r.get("early2_cum_amount"),
            "early3_cum_amount": r.get("early3_cum_amount"),
            "early1_high_return_pct": r.get("early1_high_return_pct"),
            "early2_high_return_pct": r.get("early2_high_return_pct"),
            "early3_high_return_pct": r.get("early3_high_return_pct"),
            "early2_to_early3_amount_growth": r.get("early2_to_early3_amount_growth"),
            "early3_break_start_high": r.get("early3_break_start_high"),
            "post_early3_extension_pct": post_ext,
            "early3_to_final_extension_ratio": ratio,
            "is_open_overheated_8": 1 if start_open >= 8.0 else 0,
            "is_open_overheated_9": 1 if start_open >= 9.0 else 0,
            "is_low_overextended_10": 1 if start_low >= 10.0 else 0,
            "is_low_overextended_12": 1 if start_low >= 12.0 else 0,
            "is_early3_peak_exhausted_03": 1 if post_ext is not None and post_ext <= 0.3 else 0,
            "is_early3_peak_exhausted_05": 1 if post_ext is not None and post_ext <= 0.5 else 0,
            "is_late_segment_60": 1 if start_minutes >= 60 else 0,
            "is_late_segment_90": 1 if start_minutes >= 90 else 0,
            "live_risk_score_v1_2": live_risk,
            "live_filter_label_v1_2": live_label,
            "post_diagnostic_label_v1_2": post_label,
        })
    return rows


def insert_rows(conn: Any, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    cols = list(rows[0].keys())
    sql = "INSERT INTO st_segment_ranking_v1_2 (" + ",".join(cols) + ") VALUES (" + ",".join(["%s"] * len(cols)) + ") ON DUPLICATE KEY UPDATE " + ",".join([c + "=VALUES(" + c + ")" for c in cols if c != "base_ranking_id"]) + ", updated_at=CURRENT_TIMESTAMP"
    with conn.cursor() as cur:
        total = 0
        for r in rows:
            cur.execute(sql, [r.get(c) for c in cols])
            total += 1
            if total % 1000 == 0:
                conn.commit()
                print("v12_rows_so_far=" + str(total))
    conn.commit()


def load_v12(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM st_segment_ranking_v1_2")
        return list(cur.fetchall())


def passes_rule(row: Dict[str, Any], rule: str) -> bool:
    if rule == "BASE_EARLY_EXPANSION_RANK1":
        return True
    if rule == "LIVE_PASS_ONLY":
        return str(row.get("live_filter_label_v1_2")) == "LIVE_PASS"
    if rule == "NO_OPEN_OVERHEAT_9":
        return to_int(row.get("is_open_overheated_9")) == 0
    if rule == "NO_OPEN_OVERHEAT_8":
        return to_int(row.get("is_open_overheated_8")) == 0
    if rule == "NO_LOW_OVEREXTEND_12":
        return to_int(row.get("is_low_overextended_12")) == 0
    if rule == "NO_LOW_OVEREXTEND_10":
        return to_int(row.get("is_low_overextended_10")) == 0
    if rule == "NO_LATE_60":
        return to_int(row.get("is_late_segment_60")) == 0
    if rule == "NO_POST_PEAK_EXHAUST_03_DIAGNOSTIC":
        return to_int(row.get("is_early3_peak_exhausted_03")) == 0
    if rule == "NO_POST_PEAK_EXHAUST_05_DIAGNOSTIC":
        return to_int(row.get("is_early3_peak_exhausted_05")) == 0
    if rule == "LIVE_PASS_AND_NO_POST_PEAK_05_DIAGNOSTIC":
        return str(row.get("live_filter_label_v1_2")) == "LIVE_PASS" and to_int(row.get("is_early3_peak_exhausted_05")) == 0
    return True


def summarize_rows(vals: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "row_count": len(vals),
        "avg_st_up_max_return_pct": avg([to_float(v.get("st_up_max_return_pct")) for v in vals]),
        "median_st_up_max_return_pct": median([to_float(v.get("st_up_max_return_pct")) for v in vals]),
        "great_rate": rate([to_int(v.get("label_great")) for v in vals]),
        "good_or_great_rate": rate([to_int(v.get("label_good_or_great")) for v in vals]),
        "bad_rate": rate([to_int(v.get("label_bad")) for v in vals]),
        "avg_score_total": avg([to_float(v.get("score_total")) for v in vals]),
        "avg_st_up_bars": avg([to_float(v.get("st_up_bars")) for v in vals]),
        "avg_st_start_minutes_from_open": avg([to_float(v.get("st_start_minutes_from_open")) for v in vals]),
        "avg_start_from_day_open_pct": avg([to_float(v.get("start_from_day_open_pct")) for v in vals]),
        "avg_start_from_day_low_pct": avg([to_float(v.get("start_from_day_low_pct")) for v in vals]),
        "avg_early3_high_return_pct": avg([to_float(v.get("early3_high_return_pct")) for v in vals]),
        "avg_post_early3_extension_pct": avg([to_float(v.get("post_early3_extension_pct")) for v in vals]),
        "avg_live_risk_score_v1_2": avg([to_float(v.get("live_risk_score_v1_2")) for v in vals]),
    }


def refresh_filter_summary(conn: Any, rows: List[Dict[str, Any]]) -> None:
    rules = [
        "BASE_EARLY_EXPANSION_RANK1",
        "LIVE_PASS_ONLY",
        "NO_OPEN_OVERHEAT_9",
        "NO_OPEN_OVERHEAT_8",
        "NO_LOW_OVEREXTEND_12",
        "NO_LOW_OVEREXTEND_10",
        "NO_LATE_60",
        "NO_POST_PEAK_EXHAUST_03_DIAGNOSTIC",
        "NO_POST_PEAK_EXHAUST_05_DIAGNOSTIC",
        "LIVE_PASS_AND_NO_POST_PEAK_05_DIAGNOSTIC",
    ]
    groups: Dict[Tuple[int, float], List[Dict[str, Any]]] = {}
    for r in rows:
        key = (to_int(r.get("st_period")), float(r.get("st_multiplier")))
        groups.setdefault(key, []).append(r)

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE st_segment_ranking_filter_summary_v1_2")
        sql = """
            INSERT INTO st_segment_ranking_filter_summary_v1_2 (
                st_period, st_multiplier, filter_rule, filter_side, row_count,
                avg_st_up_max_return_pct, median_st_up_max_return_pct,
                great_rate, good_or_great_rate, bad_rate,
                avg_score_total, avg_st_up_bars, avg_st_start_minutes_from_open,
                avg_start_from_day_open_pct, avg_start_from_day_low_pct,
                avg_early3_high_return_pct, avg_post_early3_extension_pct,
                avg_live_risk_score_v1_2
            ) VALUES (
                %(st_period)s, %(st_multiplier)s, %(filter_rule)s, %(filter_side)s, %(row_count)s,
                %(avg_st_up_max_return_pct)s, %(median_st_up_max_return_pct)s,
                %(great_rate)s, %(good_or_great_rate)s, %(bad_rate)s,
                %(avg_score_total)s, %(avg_st_up_bars)s, %(avg_st_start_minutes_from_open)s,
                %(avg_start_from_day_open_pct)s, %(avg_start_from_day_low_pct)s,
                %(avg_early3_high_return_pct)s, %(avg_post_early3_extension_pct)s,
                %(avg_live_risk_score_v1_2)s
            )
        """
        for (period, mult), vals in groups.items():
            for rule in rules:
                kept = [v for v in vals if passes_rule(v, rule)]
                removed = [v for v in vals if not passes_rule(v, rule)]
                for side, side_vals in (("KEEP", kept), ("REMOVE", removed)):
                    s = summarize_rows(side_vals)
                    params: Dict[str, Any] = {
                        "st_period": period,
                        "st_multiplier": mult,
                        "filter_rule": rule,
                        "filter_side": side,
                    }
                    params.update(s)
                    cur.execute(sql, params)
    conn.commit()


def refresh_false_positive_examples(conn: Any, rows: List[Dict[str, Any]]) -> None:
    fps = [r for r in rows if to_int(r.get("label_bad")) == 1]
    fps = sorted(fps, key=lambda r: (-(to_float(r.get("score_total")) or 0.0), to_float(r.get("st_up_max_return_pct")) or 0.0))[:300]
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE st_segment_ranking_false_positive_examples_v1_2")
        if not fps:
            conn.commit()
            return
        cols = [
            "base_ranking_id", "trade_date", "code", "name", "st_period", "st_multiplier", "segment_no",
            "st_up_start_time", "score_total", "st_up_max_return_pct", "quality_label",
            "segment_state_label_v1_1", "live_filter_label_v1_2", "post_diagnostic_label_v1_2",
            "rank_return_in_stock_param", "early3_high_return_pct", "post_early3_extension_pct",
            "start_from_day_open_pct", "start_from_day_low_pct", "start_cum_amount", "live_risk_score_v1_2"
        ]
        sql = "INSERT INTO st_segment_ranking_false_positive_examples_v1_2 (" + ",".join(cols) + ") VALUES (" + ",".join(["%s"] * len(cols)) + ") ON DUPLICATE KEY UPDATE " + ",".join([c + "=VALUES(" + c + ")" for c in cols if c != "base_ranking_id"]) + ", updated_at=CURRENT_TIMESTAMP"
        for r in fps:
            cur.execute(sql, [r.get(c) for c in cols])
    conn.commit()


def print_report(conn: Any) -> None:
    with conn.cursor() as cur:
        print("\n=== ST Segment Filter Summary v1.2 ===")
        cur.execute("""
            SELECT *
            FROM st_segment_ranking_filter_summary_v1_2
            ORDER BY st_period, st_multiplier, filter_rule, filter_side
        """)
        for r in cur.fetchall():
            print(r)

        print("\n=== v1.2 Best KEEP Rules by BAD Rate ===")
        cur.execute("""
            SELECT st_period, st_multiplier, filter_rule, filter_side, row_count,
                   avg_st_up_max_return_pct, median_st_up_max_return_pct,
                   good_or_great_rate, bad_rate,
                   avg_post_early3_extension_pct, avg_live_risk_score_v1_2
            FROM st_segment_ranking_filter_summary_v1_2
            WHERE filter_side = 'KEEP'
              AND row_count >= 100
            ORDER BY bad_rate ASC, good_or_great_rate DESC, avg_st_up_max_return_pct DESC
            LIMIT 80
        """)
        for r in cur.fetchall():
            print(r)

        print("\n=== v1.2 High-score BAD Examples ===")
        cur.execute("""
            SELECT trade_date, code, name, st_period, st_multiplier, segment_no,
                   st_up_start_time, score_total, st_up_max_return_pct, quality_label,
                   live_filter_label_v1_2, post_diagnostic_label_v1_2,
                   rank_return_in_stock_param, early3_high_return_pct,
                   post_early3_extension_pct, start_from_day_open_pct,
                   start_from_day_low_pct, start_cum_amount, live_risk_score_v1_2
            FROM st_segment_ranking_false_positive_examples_v1_2
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
        source_rows = load_source_rows(conn)
        print("=== build_supertrend_segment_ranking_discovery_v1_2 ===")
        print("source_rows=" + str(len(source_rows)))
        rows = build_rows(source_rows)
        insert_rows(conn, rows)
        v12_rows = load_v12(conn)
        refresh_filter_summary(conn, v12_rows)
        refresh_false_positive_examples(conn, v12_rows)
        print("\n=== DONE build_supertrend_segment_ranking_discovery_v1_2 ===")
        print("rows=" + str(len(v12_rows)))
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
