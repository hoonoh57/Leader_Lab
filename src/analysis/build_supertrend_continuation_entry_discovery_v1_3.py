# -*- coding: utf-8 -*-
"""Build SuperTrend Continuation Entry Discovery v1.3.

This builder is committed on GitHub first. Local flow is only:
    git pull origin main
    .\scripts\build_supertrend_continuation_entry_discovery_v1_3.ps1

v1.3 converts the v1.2 post-diagnostic discovery into comparable entry models.
It does not execute trades. It compares estimated entry timing quality from
already materialized v1.2 segment features.
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
    ddl = Path("sql/create_supertrend_continuation_entry_discovery_v1_3.sql").read_text(encoding="utf-8-sig")
    with conn.cursor() as cur:
        if rebuild:
            cur.execute("DROP TABLE IF EXISTS st_continuation_entry_examples_v1_3")
            cur.execute("DROP TABLE IF EXISTS st_continuation_entry_summary_v1_3")
            cur.execute("DROP TABLE IF EXISTS st_continuation_entry_v1_3")
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


def load_source_rows(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT *
            FROM st_segment_ranking_v1_2
            WHERE segment_state_label_v1_1 = 'EARLY_EXPANSION_ST'
              AND is_score_rank1 = 1
            ORDER BY trade_date, code, st_period, st_multiplier, segment_no, st_up_start_time
        """)
        return list(cur.fetchall())


def continuation_score(row: Dict[str, Any], entry_type: str, max_after_entry: Optional[float], lost_move: Optional[float]) -> Tuple[float, str, int, int]:
    score_total = to_float(row.get("score_total")) or 0.0
    live_risk = to_float(row.get("live_risk_score_v1_2")) or 0.0
    post_ext = to_float(row.get("post_early3_extension_pct")) or 0.0
    growth = to_float(row.get("early2_to_early3_amount_growth")) or 1.0
    early3_break = to_int(row.get("early3_break_start_high"))

    score = 0.0
    score += min(35.0, max(0.0, score_total - 60.0) * 0.75)
    score += min(30.0, max(0.0, post_ext) * 5.0)
    score += min(15.0, max(0.0, growth - 1.0) * 10.0)
    if early3_break == 1:
        score += 8.0
    score -= min(30.0, live_risk * 0.35)
    if entry_type == "EARLY3_BREAK_ENTRY":
        score += 8.0
    elif entry_type == "EARLY3_COMPOSITE_ENTRY":
        score += 12.0
    elif entry_type == "ST_START_ENTRY":
        score -= 5.0

    if max_after_entry is not None and max_after_entry >= 5.0:
        score += 12.0
    if lost_move is not None and lost_move >= 8.0:
        score -= 8.0

    success = 1 if max_after_entry is not None and max_after_entry >= 5.0 and post_ext >= 0.5 else 0
    fail = 1 if max_after_entry is None or max_after_entry < 3.0 or post_ext <= 0.3 else 0

    if score >= 75.0 and success == 1:
        label = "CONTINUATION_STRONG"
    elif score >= 60.0 and fail == 0:
        label = "CONTINUATION_CANDIDATE"
    elif fail == 1:
        label = "CONTINUATION_FAIL_RISK"
    else:
        label = "CONTINUATION_NEUTRAL"
    return score, label, success, fail


def make_entry_row(row: Dict[str, Any], entry_type: str) -> Dict[str, Any]:
    st_ret = to_float(row.get("st_up_max_return_pct"))
    early3_high = to_float(row.get("early3_high_return_pct"))
    post_ext = to_float(row.get("post_early3_extension_pct"))
    if post_ext is None and st_ret is not None and early3_high is not None:
        post_ext = st_ret - early3_high

    lost = 0.0
    max_after = st_ret
    available = "ST_UP_START"
    after_bars: Optional[int] = None
    signal_label = "ST_UP_START_DIRECT"

    if entry_type == "ST_START_ENTRY":
        max_after = st_ret
        lost = 0.0
        available = "ST_UP_START"
        after_bars = 0
        signal_label = "ST_START_NOW"
    elif entry_type == "EARLY3_BREAK_ENTRY":
        max_after = max(0.0, post_ext or 0.0)
        lost = early3_high or 0.0
        available = "AFTER_EARLY3_HIGH_BREAK"
        after_bars = 1
        signal_label = "EARLY3_HIGH_REBREAK_CONFIRM"
    elif entry_type == "EARLY3_HOLD_ENTRY":
        max_after = max(0.0, (post_ext or 0.0) + 0.35)
        lost = max(0.0, (early3_high or 0.0) - 0.35)
        available = "AFTER_EARLY3_HOLD"
        after_bars = 1
        signal_label = "EARLY3_HIGH_ZONE_HOLD"
    elif entry_type == "EARLY3_AMOUNT_EXPANSION_ENTRY":
        growth = to_float(row.get("early2_to_early3_amount_growth")) or 1.0
        max_after = max(0.0, (post_ext or 0.0) + min(1.0, max(0.0, growth - 1.0) * 0.25))
        lost = early3_high or 0.0
        available = "AFTER_EARLY3_AMOUNT_CONFIRM"
        after_bars = 1
        signal_label = "EARLY3_AMOUNT_EXPANSION_CONFIRM"
    elif entry_type == "EARLY3_COMPOSITE_ENTRY":
        max_after = max(0.0, post_ext or 0.0)
        lost = early3_high or 0.0
        available = "AFTER_EARLY3_BREAK_AND_LIVE_PASS"
        after_bars = 1
        signal_label = "EARLY3_BREAK_LIVEPASS_COMPOSITE"

    score, label, success, fail = continuation_score(row, entry_type, max_after, lost)
    return {
        "source_v1_2_id": row.get("id"),
        "base_ranking_id": row.get("base_ranking_id"),
        "trade_date": row.get("trade_date"),
        "search_time": row.get("search_time"),
        "code": row.get("code"),
        "name": row.get("name"),
        "timeframe": row.get("timeframe"),
        "st_period": row.get("st_period"),
        "st_multiplier": row.get("st_multiplier"),
        "segment_no": row.get("segment_no"),
        "st_up_start_time": row.get("st_up_start_time"),
        "st_up_end_time": row.get("st_up_end_time"),
        "st_start_minutes_from_open": row.get("st_start_minutes_from_open"),
        "st_up_bars": row.get("st_up_bars"),
        "entry_type": entry_type,
        "entry_signal_label": signal_label,
        "entry_available_at": available,
        "entry_after_early3_bars": after_bars,
        "score_total": row.get("score_total"),
        "live_risk_score_v1_2": row.get("live_risk_score_v1_2"),
        "live_filter_label_v1_2": row.get("live_filter_label_v1_2"),
        "post_diagnostic_label_v1_2": row.get("post_diagnostic_label_v1_2"),
        "quality_label": row.get("quality_label"),
        "label_great": row.get("label_great"),
        "label_good_or_great": row.get("label_good_or_great"),
        "label_bad": row.get("label_bad"),
        "start_from_day_open_pct": row.get("start_from_day_open_pct"),
        "start_from_day_low_pct": row.get("start_from_day_low_pct"),
        "start_cum_amount": row.get("start_cum_amount"),
        "early1_amount": row.get("early1_amount"),
        "early2_cum_amount": row.get("early2_cum_amount"),
        "early3_cum_amount": row.get("early3_cum_amount"),
        "early1_high_return_pct": row.get("early1_high_return_pct"),
        "early2_high_return_pct": row.get("early2_high_return_pct"),
        "early3_high_return_pct": row.get("early3_high_return_pct"),
        "early2_to_early3_amount_growth": row.get("early2_to_early3_amount_growth"),
        "early3_break_start_high": row.get("early3_break_start_high"),
        "st_up_max_return_pct": row.get("st_up_max_return_pct"),
        "post_early3_extension_pct": post_ext,
        "estimated_max_return_after_entry_pct": max_after,
        "estimated_lost_move_before_entry_pct": lost,
        "continuation_success": success,
        "continuation_fail": fail,
        "continuation_score_v1_3": score,
        "continuation_label_v1_3": label,
    }


def build_rows(source_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    entry_types = [
        "ST_START_ENTRY",
        "EARLY3_BREAK_ENTRY",
        "EARLY3_HOLD_ENTRY",
        "EARLY3_AMOUNT_EXPANSION_ENTRY",
        "EARLY3_COMPOSITE_ENTRY",
    ]
    rows: List[Dict[str, Any]] = []
    for src in source_rows:
        for entry_type in entry_types:
            if entry_type == "EARLY3_COMPOSITE_ENTRY" and str(src.get("live_filter_label_v1_2")) != "LIVE_PASS":
                continue
            rows.append(make_entry_row(src, entry_type))
    return rows


def insert_rows(conn: Any, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    cols = list(rows[0].keys())
    update_cols = [c for c in cols if c not in ("source_v1_2_id", "entry_type")]
    sql = "INSERT INTO st_continuation_entry_v1_3 (" + ",".join(cols) + ") VALUES (" + ",".join(["%s"] * len(cols)) + ") ON DUPLICATE KEY UPDATE " + ",".join([c + "=VALUES(" + c + ")" for c in update_cols]) + ", updated_at=CURRENT_TIMESTAMP"
    with conn.cursor() as cur:
        total = 0
        for r in rows:
            cur.execute(sql, [r.get(c) for c in cols])
            total += 1
            if total % 1000 == 0:
                conn.commit()
                print("v13_rows_so_far=" + str(total))
    conn.commit()


def load_v13(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM st_continuation_entry_v1_3")
        return list(cur.fetchall())


def summarize(vals: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "row_count": len(vals),
        "avg_estimated_max_return_after_entry_pct": avg([to_float(v.get("estimated_max_return_after_entry_pct")) for v in vals]),
        "median_estimated_max_return_after_entry_pct": median([to_float(v.get("estimated_max_return_after_entry_pct")) for v in vals]),
        "avg_lost_move_before_entry_pct": avg([to_float(v.get("estimated_lost_move_before_entry_pct")) for v in vals]),
        "avg_st_up_max_return_pct": avg([to_float(v.get("st_up_max_return_pct")) for v in vals]),
        "median_st_up_max_return_pct": median([to_float(v.get("st_up_max_return_pct")) for v in vals]),
        "good_or_great_rate": rate([to_int(v.get("label_good_or_great")) for v in vals]),
        "bad_rate": rate([to_int(v.get("label_bad")) for v in vals]),
        "continuation_success_rate": rate([to_int(v.get("continuation_success")) for v in vals]),
        "continuation_fail_rate": rate([to_int(v.get("continuation_fail")) for v in vals]),
        "avg_score_total": avg([to_float(v.get("score_total")) for v in vals]),
        "avg_continuation_score_v1_3": avg([to_float(v.get("continuation_score_v1_3")) for v in vals]),
        "avg_live_risk_score_v1_2": avg([to_float(v.get("live_risk_score_v1_2")) for v in vals]),
        "avg_post_early3_extension_pct": avg([to_float(v.get("post_early3_extension_pct")) for v in vals]),
        "avg_start_from_day_open_pct": avg([to_float(v.get("start_from_day_open_pct")) for v in vals]),
        "avg_start_from_day_low_pct": avg([to_float(v.get("start_from_day_low_pct")) for v in vals]),
        "avg_early3_high_return_pct": avg([to_float(v.get("early3_high_return_pct")) for v in vals]),
        "avg_early2_to_early3_amount_growth": avg([to_float(v.get("early2_to_early3_amount_growth")) for v in vals]),
    }


def refresh_summary(conn: Any, rows: List[Dict[str, Any]]) -> None:
    groups: Dict[Tuple[int, float, str], List[Dict[str, Any]]] = {}
    for r in rows:
        key = (to_int(r.get("st_period")), float(r.get("st_multiplier")), str(r.get("entry_type")))
        groups.setdefault(key, []).append(r)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE st_continuation_entry_summary_v1_3")
        sql = """
            INSERT INTO st_continuation_entry_summary_v1_3 (
                st_period, st_multiplier, entry_type, row_count,
                avg_estimated_max_return_after_entry_pct,
                median_estimated_max_return_after_entry_pct,
                avg_lost_move_before_entry_pct,
                avg_st_up_max_return_pct,
                median_st_up_max_return_pct,
                good_or_great_rate, bad_rate,
                continuation_success_rate, continuation_fail_rate,
                avg_score_total, avg_continuation_score_v1_3,
                avg_live_risk_score_v1_2, avg_post_early3_extension_pct,
                avg_start_from_day_open_pct, avg_start_from_day_low_pct,
                avg_early3_high_return_pct, avg_early2_to_early3_amount_growth
            ) VALUES (
                %(st_period)s, %(st_multiplier)s, %(entry_type)s, %(row_count)s,
                %(avg_estimated_max_return_after_entry_pct)s,
                %(median_estimated_max_return_after_entry_pct)s,
                %(avg_lost_move_before_entry_pct)s,
                %(avg_st_up_max_return_pct)s,
                %(median_st_up_max_return_pct)s,
                %(good_or_great_rate)s, %(bad_rate)s,
                %(continuation_success_rate)s, %(continuation_fail_rate)s,
                %(avg_score_total)s, %(avg_continuation_score_v1_3)s,
                %(avg_live_risk_score_v1_2)s, %(avg_post_early3_extension_pct)s,
                %(avg_start_from_day_open_pct)s, %(avg_start_from_day_low_pct)s,
                %(avg_early3_high_return_pct)s, %(avg_early2_to_early3_amount_growth)s
            )
        """
        for (period, mult, entry_type), vals in groups.items():
            params: Dict[str, Any] = {"st_period": period, "st_multiplier": mult, "entry_type": entry_type}
            params.update(summarize(vals))
            cur.execute(sql, params)
    conn.commit()


def refresh_examples(conn: Any, rows: List[Dict[str, Any]]) -> None:
    examples = sorted(rows, key=lambda r: (-(to_float(r.get("continuation_score_v1_3")) or 0.0), -(to_float(r.get("estimated_max_return_after_entry_pct")) or 0.0)))[:400]
    cols = [
        "source_v1_2_id", "trade_date", "code", "name", "st_period", "st_multiplier", "segment_no",
        "st_up_start_time", "entry_type", "score_total", "live_filter_label_v1_2", "post_diagnostic_label_v1_2",
        "quality_label", "st_up_max_return_pct", "early3_high_return_pct", "post_early3_extension_pct",
        "estimated_max_return_after_entry_pct", "estimated_lost_move_before_entry_pct",
        "continuation_score_v1_3", "continuation_label_v1_3", "start_from_day_open_pct",
        "start_from_day_low_pct", "start_cum_amount", "early2_to_early3_amount_growth"
    ]
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE st_continuation_entry_examples_v1_3")
        if not examples:
            conn.commit()
            return
        sql = "INSERT INTO st_continuation_entry_examples_v1_3 (" + ",".join(cols) + ") VALUES (" + ",".join(["%s"] * len(cols)) + ") ON DUPLICATE KEY UPDATE " + ",".join([c + "=VALUES(" + c + ")" for c in cols if c not in ("source_v1_2_id", "entry_type")]) + ", updated_at=CURRENT_TIMESTAMP"
        for r in examples:
            cur.execute(sql, [r.get(c) for c in cols])
    conn.commit()


def print_report(conn: Any) -> None:
    with conn.cursor() as cur:
        print("\n=== ST Continuation Entry Summary v1.3 ===")
        cur.execute("""
            SELECT *
            FROM st_continuation_entry_summary_v1_3
            ORDER BY st_period, st_multiplier, entry_type
        """)
        for r in cur.fetchall():
            print(r)

        print("\n=== v1.3 Best Continuation Entry Models ===")
        cur.execute("""
            SELECT st_period, st_multiplier, entry_type, row_count,
                   avg_estimated_max_return_after_entry_pct,
                   median_estimated_max_return_after_entry_pct,
                   avg_lost_move_before_entry_pct,
                   continuation_success_rate, continuation_fail_rate,
                   good_or_great_rate, bad_rate,
                   avg_continuation_score_v1_3,
                   avg_post_early3_extension_pct
            FROM st_continuation_entry_summary_v1_3
            WHERE row_count >= 100
            ORDER BY continuation_success_rate DESC,
                     continuation_fail_rate ASC,
                     avg_estimated_max_return_after_entry_pct DESC
            LIMIT 40
        """)
        for r in cur.fetchall():
            print(r)

        print("\n=== v1.3 Top Continuation Examples ===")
        cur.execute("""
            SELECT trade_date, code, name, st_period, st_multiplier, segment_no,
                   st_up_start_time, entry_type, score_total,
                   st_up_max_return_pct, early3_high_return_pct,
                   post_early3_extension_pct, estimated_max_return_after_entry_pct,
                   estimated_lost_move_before_entry_pct, continuation_score_v1_3,
                   continuation_label_v1_3, live_filter_label_v1_2,
                   post_diagnostic_label_v1_2, start_from_day_open_pct,
                   start_from_day_low_pct, start_cum_amount
            FROM st_continuation_entry_examples_v1_3
            ORDER BY continuation_score_v1_3 DESC, estimated_max_return_after_entry_pct DESC
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
        print("=== build_supertrend_continuation_entry_discovery_v1_3 ===")
        print("source_rows=" + str(len(source_rows)))
        rows = build_rows(source_rows)
        insert_rows(conn, rows)
        v13_rows = load_v13(conn)
        refresh_summary(conn, v13_rows)
        refresh_examples(conn, v13_rows)
        print("\n=== DONE build_supertrend_continuation_entry_discovery_v1_3 ===")
        print("rows=" + str(len(v13_rows)))
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
