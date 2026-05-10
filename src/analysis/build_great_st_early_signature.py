# -*- coding: utf-8 -*-
"""Build GREAT ST Early Signature Discovery.

This script converts SuperTrend regime answer labels into early-detectable features.
It uses supertrend_regime_segment as the label source and calculates features from
ST start + first 1~3 bars only.

Run:
    python -m src.analysis.build_great_st_early_signature --env .env --rebuild
"""

from __future__ import annotations

import argparse
import math
import os
import statistics
import sys
from datetime import date, datetime, time, timedelta
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
    ddl = Path("sql/create_great_st_early_signature.sql").read_text(encoding="utf-8-sig")
    with conn.cursor() as cur:
        if rebuild:
            cur.execute("DROP TABLE IF EXISTS great_st_early_signature_feature_diff")
            cur.execute("DROP TABLE IF EXISTS great_st_early_signature_summary")
            cur.execute("DROP TABLE IF EXISTS great_st_early_signature")
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


def pct(new_value: Optional[float], base_value: Optional[float]) -> Optional[float]:
    if new_value is None or base_value is None or base_value == 0:
        return None
    return (new_value - base_value) / base_value * 100.0


def avg(values: List[Optional[float]]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return None if not vals else sum(vals) / float(len(vals))


def rate(values: List[int]) -> Optional[float]:
    if not values:
        return None
    return sum(1 for v in values if v == 1) / float(len(values))


def amount_from_row(row: Dict[str, Any]) -> Optional[float]:
    o = to_float(row.get("open_price"))
    h = to_float(row.get("high_price"))
    l = to_float(row.get("low_price"))
    c = to_float(row.get("close_price"))
    v = to_float(row.get("volume"))
    if o is None or h is None or l is None or c is None or v is None:
        return None
    return ((o + h + l + c) / 4.0) * v


def quality_label(seg: Dict[str, Any]) -> str:
    if to_int(seg.get("label_st_gain_10pct")) == 1:
        return "GREAT"
    if to_int(seg.get("label_st_gain_5pct")) == 1:
        return "GOOD"
    if to_int(seg.get("label_st_fail_1pct")) == 1 or to_int(seg.get("label_st_end_negative")) == 1:
        return "BAD"
    return "NEUTRAL"


def load_segments(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT *
            FROM supertrend_regime_segment
            WHERE st_up_start_time IS NOT NULL
            ORDER BY trade_date, code, st_period, st_multiplier, segment_no
        """)
        return list(cur.fetchall())


def load_day_candles(conn: Any, code: str, trade_date: Any) -> List[Dict[str, Any]]:
    start_dt = datetime.combine(trade_date, time(9, 0, 0))
    end_dt = datetime.combine(trade_date, time(15, 30, 0))
    with conn.cursor() as cur:
        cur.execute("""
            SELECT candle_time, open AS open_price, high AS high_price,
                   low AS low_price, close AS close_price, volume
            FROM minute5_candles
            WHERE code=%s AND candle_time >= %s AND candle_time <= %s
            ORDER BY candle_time
        """, (code, start_dt, end_dt))
        return list(cur.fetchall())


def slice_early_rows(rows: List[Dict[str, Any]], start_time: Any, bars: int) -> List[Dict[str, Any]]:
    found = -1
    for i, row in enumerate(rows):
        if row.get("candle_time") == start_time:
            found = i
            break
    if found < 0:
        # fallback: first candle at/after ST start
        for i, row in enumerate(rows):
            if row.get("candle_time") >= start_time:
                found = i
                break
    if found < 0:
        return []
    return rows[found:found + bars]


def build_window_features(rows: List[Dict[str, Any]], start_price: Optional[float], start_high: Optional[float], bars: int) -> Dict[str, Any]:
    prefix = "early" + str(bars)
    if not rows or start_price is None:
        return {
            prefix + "_return_pct": None,
            prefix + "_high_return_pct": None,
            prefix + "_low_drawdown_pct": None,
            prefix + ("_amount" if bars == 1 else "_cum_amount"): None,
            prefix + ("_volume" if bars == 1 else "_cum_volume"): None,
            prefix + ("_singlebar_return_pct" if bars == 1 else "_max_singlebar_return_pct"): None,
            prefix + "_break_start_high": 0,
        }
    closes = [to_float(r.get("close_price")) for r in rows]
    highs = [to_float(r.get("high_price")) for r in rows]
    lows = [to_float(r.get("low_price")) for r in rows]
    end_close = closes[-1] if closes else None
    max_high = max([v for v in highs if v is not None]) if any(v is not None for v in highs) else None
    min_low = min([v for v in lows if v is not None]) if any(v is not None for v in lows) else None
    cum_amount = 0.0
    cum_volume = 0
    green_count = 0
    max_singlebar: Optional[float] = None
    amounts: List[float] = []
    for r in rows:
        amount = amount_from_row(r)
        if amount is not None:
            cum_amount += amount
            amounts.append(amount)
        cum_volume += to_int(r.get("volume"))
        o = to_float(r.get("open_price"))
        c = to_float(r.get("close_price"))
        if o is not None and c is not None and c >= o:
            green_count += 1
        sb = pct(c, o)
        if sb is not None and (max_singlebar is None or sb > max_singlebar):
            max_singlebar = sb
    break_start_high = 1 if max_high is not None and start_high is not None and max_high > start_high else 0
    data = {
        prefix + "_return_pct": pct(end_close, start_price),
        prefix + "_high_return_pct": pct(max_high, start_price),
        prefix + "_low_drawdown_pct": pct(min_low, start_price),
        prefix + "_break_start_high": break_start_high,
    }
    if bars == 1:
        data["early1_amount"] = cum_amount
        data["early1_volume"] = cum_volume
        data["early1_singlebar_return_pct"] = max_singlebar
    else:
        data[prefix + "_cum_amount"] = cum_amount
        data[prefix + "_cum_volume"] = cum_volume
        data[prefix + "_avg_amount"] = cum_amount / float(len(rows)) if rows else None
        data[prefix + "_max_singlebar_return_pct"] = max_singlebar
        data[prefix + "_green_count"] = green_count
    if bars == 3:
        first_amount = amounts[0] if len(amounts) >= 1 else None
        last_amount = amounts[-1] if len(amounts) >= 1 else None
        data["early3_amount_accel_ratio"] = (last_amount / first_amount) if first_amount is not None and first_amount > 0 and last_amount is not None else None
    return data


def build_signature_row(seg: Dict[str, Any], day_rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    q = quality_label(seg)
    start_time = seg.get("st_up_start_time")
    early1 = slice_early_rows(day_rows, start_time, 1)
    early2 = slice_early_rows(day_rows, start_time, 2)
    early3 = slice_early_rows(day_rows, start_time, 3)
    if not early1:
        return None
    start_price = to_float(seg.get("st_up_start_price"))
    start_high = to_float(early1[0].get("high_price")) if early1 else None
    row: Dict[str, Any] = {
        "segment_id": seg.get("id"),
        "trade_date": seg.get("trade_date"),
        "search_time": seg.get("search_time"),
        "code": seg.get("code"),
        "name": seg.get("name"),
        "timeframe": seg.get("timeframe"),
        "st_period": seg.get("st_period"),
        "st_multiplier": seg.get("st_multiplier"),
        "segment_no": seg.get("segment_no"),
        "quality_label": q,
        "st_up_start_time": seg.get("st_up_start_time"),
        "st_up_end_time": seg.get("st_up_end_time"),
        "st_up_bars": seg.get("st_up_bars"),
        "st_up_start_price": seg.get("st_up_start_price"),
        "st_up_max_return_pct": seg.get("st_up_max_return_pct"),
        "st_up_end_return_pct": seg.get("st_up_end_return_pct"),
        "start_from_day_open_pct": seg.get("start_from_day_open_pct"),
        "start_from_day_low_pct": seg.get("start_from_day_low_pct"),
        "start_cum_amount": seg.get("start_cum_amount"),
        "start_cum_volume": seg.get("start_cum_volume"),
        "start_range_so_far_pct": seg.get("start_range_so_far_pct"),
        "max_singlebar_return_before_start": seg.get("max_singlebar_return_before_start"),
        "singlebar_3pct_exists_before_start": seg.get("singlebar_3pct_exists_before_start"),
        "singlebar_5pct_exists_before_start": seg.get("singlebar_5pct_exists_before_start"),
        "label_great": 1 if q == "GREAT" else 0,
        "label_good_or_great": 1 if q in ("GOOD", "GREAT") else 0,
        "label_bad": 1 if q == "BAD" else 0,
    }
    row.update(build_window_features(early1, start_price, start_high, 1))
    row.update(build_window_features(early2, start_price, start_high, 2))
    row.update(build_window_features(early3, start_price, start_high, 3))
    return row


def upsert_signature(conn: Any, row: Dict[str, Any]) -> None:
    cols = list(row.keys())
    updates = [c + "=VALUES(" + c + ")" for c in cols if c != "segment_id"]
    sql = "INSERT INTO great_st_early_signature (" + ",".join(cols) + ") VALUES (" + ",".join(["%s"] * len(cols)) + ") ON DUPLICATE KEY UPDATE " + ",".join(updates) + ", updated_at=CURRENT_TIMESTAMP"
    with conn.cursor() as cur:
        cur.execute(sql, [row.get(c) for c in cols])


def load_signatures(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM great_st_early_signature")
        return list(cur.fetchall())


def insert_summary(conn: Any, rows: List[Dict[str, Any]]) -> None:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE great_st_early_signature_summary")
        cur.execute("TRUNCATE TABLE great_st_early_signature_feature_diff")
    grouped: Dict[Tuple[int, float, str], List[Dict[str, Any]]] = {}
    for r in rows:
        groups = ["ALL", r.get("quality_label")]
        if r.get("quality_label") in ("GOOD", "GREAT"):
            groups.append("GOOD_OR_GREAT")
        for g in groups:
            grouped.setdefault((to_int(r.get("st_period")), float(r.get("st_multiplier")), str(g)), []).append(r)
    sql = """
        INSERT INTO great_st_early_signature_summary (
            st_period, st_multiplier, group_name, row_count,
            avg_st_up_max_return_pct, avg_st_up_end_return_pct,
            avg_start_from_day_open_pct, avg_start_from_day_low_pct, avg_start_cum_amount,
            avg_early1_return_pct, avg_early1_high_return_pct, avg_early1_amount, avg_early1_singlebar_return_pct,
            avg_early2_return_pct, avg_early2_high_return_pct, avg_early2_cum_amount, avg_early2_max_singlebar_return_pct, early2_break_start_high_rate,
            avg_early3_return_pct, avg_early3_high_return_pct, avg_early3_cum_amount, avg_early3_max_singlebar_return_pct, avg_early3_amount_accel_ratio, early3_break_start_high_rate
        ) VALUES (
            %(st_period)s, %(st_multiplier)s, %(group_name)s, %(row_count)s,
            %(avg_st_up_max_return_pct)s, %(avg_st_up_end_return_pct)s,
            %(avg_start_from_day_open_pct)s, %(avg_start_from_day_low_pct)s, %(avg_start_cum_amount)s,
            %(avg_early1_return_pct)s, %(avg_early1_high_return_pct)s, %(avg_early1_amount)s, %(avg_early1_singlebar_return_pct)s,
            %(avg_early2_return_pct)s, %(avg_early2_high_return_pct)s, %(avg_early2_cum_amount)s, %(avg_early2_max_singlebar_return_pct)s, %(early2_break_start_high_rate)s,
            %(avg_early3_return_pct)s, %(avg_early3_high_return_pct)s, %(avg_early3_cum_amount)s, %(avg_early3_max_singlebar_return_pct)s, %(avg_early3_amount_accel_ratio)s, %(early3_break_start_high_rate)s
        )
    """
    with conn.cursor() as cur:
        for (period, mult, group_name), vals in grouped.items():
            item = {
                "st_period": period,
                "st_multiplier": mult,
                "group_name": group_name,
                "row_count": len(vals),
                "avg_st_up_max_return_pct": avg([to_float(v.get("st_up_max_return_pct")) for v in vals]),
                "avg_st_up_end_return_pct": avg([to_float(v.get("st_up_end_return_pct")) for v in vals]),
                "avg_start_from_day_open_pct": avg([to_float(v.get("start_from_day_open_pct")) for v in vals]),
                "avg_start_from_day_low_pct": avg([to_float(v.get("start_from_day_low_pct")) for v in vals]),
                "avg_start_cum_amount": avg([to_float(v.get("start_cum_amount")) for v in vals]),
                "avg_early1_return_pct": avg([to_float(v.get("early1_return_pct")) for v in vals]),
                "avg_early1_high_return_pct": avg([to_float(v.get("early1_high_return_pct")) for v in vals]),
                "avg_early1_amount": avg([to_float(v.get("early1_amount")) for v in vals]),
                "avg_early1_singlebar_return_pct": avg([to_float(v.get("early1_singlebar_return_pct")) for v in vals]),
                "avg_early2_return_pct": avg([to_float(v.get("early2_return_pct")) for v in vals]),
                "avg_early2_high_return_pct": avg([to_float(v.get("early2_high_return_pct")) for v in vals]),
                "avg_early2_cum_amount": avg([to_float(v.get("early2_cum_amount")) for v in vals]),
                "avg_early2_max_singlebar_return_pct": avg([to_float(v.get("early2_max_singlebar_return_pct")) for v in vals]),
                "early2_break_start_high_rate": rate([to_int(v.get("early2_break_start_high")) for v in vals]),
                "avg_early3_return_pct": avg([to_float(v.get("early3_return_pct")) for v in vals]),
                "avg_early3_high_return_pct": avg([to_float(v.get("early3_high_return_pct")) for v in vals]),
                "avg_early3_cum_amount": avg([to_float(v.get("early3_cum_amount")) for v in vals]),
                "avg_early3_max_singlebar_return_pct": avg([to_float(v.get("early3_max_singlebar_return_pct")) for v in vals]),
                "avg_early3_amount_accel_ratio": avg([to_float(v.get("early3_amount_accel_ratio")) for v in vals]),
                "early3_break_start_high_rate": rate([to_int(v.get("early3_break_start_high")) for v in vals]),
            }
            cur.execute(sql, item)
    insert_feature_diffs(conn, rows)
    conn.commit()


def insert_feature_diffs(conn: Any, rows: List[Dict[str, Any]]) -> None:
    features = [
        "start_from_day_open_pct", "start_from_day_low_pct", "start_cum_amount",
        "early1_return_pct", "early1_high_return_pct", "early1_amount", "early1_singlebar_return_pct", "early1_break_start_high",
        "early2_return_pct", "early2_high_return_pct", "early2_cum_amount", "early2_max_singlebar_return_pct", "early2_break_start_high",
        "early3_return_pct", "early3_high_return_pct", "early3_cum_amount", "early3_max_singlebar_return_pct", "early3_amount_accel_ratio", "early3_break_start_high",
    ]
    params = sorted({(to_int(r.get("st_period")), float(r.get("st_multiplier"))) for r in rows})
    sql = """
        INSERT INTO great_st_early_signature_feature_diff (
            st_period, st_multiplier, compare_name, feature_name,
            positive_group, negative_group, positive_count, negative_count,
            positive_avg_value, negative_avg_value, diff_avg_value, ratio_value
        ) VALUES (
            %(st_period)s, %(st_multiplier)s, %(compare_name)s, %(feature_name)s,
            %(positive_group)s, %(negative_group)s, %(positive_count)s, %(negative_count)s,
            %(positive_avg_value)s, %(negative_avg_value)s, %(diff_avg_value)s, %(ratio_value)s
        )
    """
    with conn.cursor() as cur:
        for period, mult in params:
            p_rows = [r for r in rows if to_int(r.get("st_period")) == period and float(r.get("st_multiplier")) == mult]
            comparisons = [
                ("GREAT_vs_BAD", [r for r in p_rows if r.get("quality_label") == "GREAT"], [r for r in p_rows if r.get("quality_label") == "BAD"], "GREAT", "BAD"),
                ("GOOD_OR_GREAT_vs_BAD", [r for r in p_rows if r.get("quality_label") in ("GOOD", "GREAT")], [r for r in p_rows if r.get("quality_label") == "BAD"], "GOOD_OR_GREAT", "BAD"),
            ]
            for compare_name, pos, neg, pos_name, neg_name in comparisons:
                for feature in features:
                    pos_avg = avg([to_float(r.get(feature)) for r in pos])
                    neg_avg = avg([to_float(r.get(feature)) for r in neg])
                    diff = pos_avg - neg_avg if pos_avg is not None and neg_avg is not None else None
                    ratio_val = pos_avg / neg_avg if pos_avg is not None and neg_avg not in (None, 0) else None
                    cur.execute(sql, {
                        "st_period": period,
                        "st_multiplier": mult,
                        "compare_name": compare_name,
                        "feature_name": feature,
                        "positive_group": pos_name,
                        "negative_group": neg_name,
                        "positive_count": len(pos),
                        "negative_count": len(neg),
                        "positive_avg_value": pos_avg,
                        "negative_avg_value": neg_avg,
                        "diff_avg_value": diff,
                        "ratio_value": ratio_val,
                    })


def print_summary(conn: Any) -> None:
    with conn.cursor() as cur:
        print("\n=== great_st_early_signature_summary ===")
        cur.execute("""
            SELECT st_period, st_multiplier, group_name, row_count,
                   avg_st_up_max_return_pct, avg_start_from_day_open_pct,
                   avg_early1_high_return_pct, avg_early1_amount,
                   avg_early2_high_return_pct, avg_early2_cum_amount, early2_break_start_high_rate,
                   avg_early3_high_return_pct, avg_early3_cum_amount, early3_break_start_high_rate
            FROM great_st_early_signature_summary
            ORDER BY st_period, st_multiplier,
                     FIELD(group_name,'ALL','GREAT','GOOD','GOOD_OR_GREAT','BAD','NEUTRAL')
        """)
        for row in cur.fetchall():
            print(row)
        print("\n=== top early feature diffs ===")
        cur.execute("""
            SELECT st_period, st_multiplier, compare_name, feature_name,
                   positive_count, negative_count, positive_avg_value, negative_avg_value,
                   diff_avg_value, ratio_value
            FROM great_st_early_signature_feature_diff
            ORDER BY ABS(COALESCE(diff_avg_value, 0)) DESC
            LIMIT 80
        """)
        for row in cur.fetchall():
            print(row)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    load_env(args.env)
    conn = open_conn()
    try:
        ensure_schema(conn, args.rebuild)
        segments = load_segments(conn)
        if args.limit > 0:
            segments = segments[:args.limit]
        print("=== build_great_st_early_signature ===")
        print("segments=" + str(len(segments)))
        cache: Dict[Tuple[str, Any], List[Dict[str, Any]]] = {}
        total = 0
        for seg in segments:
            key = (str(seg.get("code")), seg.get("trade_date"))
            if key not in cache:
                cache[key] = load_day_candles(conn, str(seg.get("code")), seg.get("trade_date"))
            row = build_signature_row(seg, cache[key])
            if row is None:
                continue
            upsert_signature(conn, row)
            total += 1
            if total > 0 and total % 1000 == 0:
                conn.commit()
                print("rows_so_far=" + str(total))
        conn.commit()
        rows = load_signatures(conn)
        insert_summary(conn, rows)
        print("\n=== DONE build_great_st_early_signature ===")
        print("rows=" + str(len(rows)))
        print_summary(conn)
        return 0
    except Exception as ex:
        conn.rollback()
        print("[FATAL] " + str(ex), file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
