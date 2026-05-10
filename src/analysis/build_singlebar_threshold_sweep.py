# -*- coding: utf-8 -*-
"""Sweep 5-minute single-bar open->close rise thresholds.

This evaluator compares thresholds such as 3.0~6.0 instead of hardcoding 5%.
It reuses hypothesis_validation_v1_result raw metrics and summarizes high-precision
filter quality by threshold and filter variant.

Run:
    python -m src.analysis.build_singlebar_threshold_sweep --env .env --rebuild
"""

from __future__ import annotations

import argparse
import math
import os
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

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
    ddl = Path("sql/create_singlebar_threshold_sweep.sql").read_text(encoding="utf-8-sig")
    with conn.cursor() as cur:
        if rebuild:
            cur.execute("DROP TABLE IF EXISTS singlebar_threshold_sweep_summary")
        for statement in ddl.split(";"):
            sql = statement.strip()
            if sql:
                cur.execute(sql)
    conn.commit()


def to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
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
    filtered = [v for v in values if v is not None]
    if not filtered:
        return None
    return sum(filtered) / float(len(filtered))


def median(values: List[Optional[float]]) -> Optional[float]:
    filtered = [v for v in values if v is not None]
    if not filtered:
        return None
    return float(statistics.median(filtered))


def rate(values: List[Optional[float]], predicate) -> Optional[float]:
    filtered = [v for v in values if v is not None]
    if not filtered:
        return None
    count = 0
    for value in filtered:
        if predicate(value):
            count += 1
    return count / float(len(filtered))


def load_rows(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT search_date, code, actual_rank, in_actual_top10, actual_max_after_return_pct,
                   singlebar_close_return_pct,
                   break_time, break_type, break_volume, singlebar_volume,
                   break_rsi14, break_rsi14_prev, break_rsi_gt_60, break_rsi_rising,
                   break_ma10, break_ma10_prev, break_close_gt_ma10, break_close_cross_ma10,
                   d1_prev5_up10_high_break_5m3, d2_prev10_high20_closeup_5d_highvol,
                   break_after_max_return_pct, break_after_close_return_pct, break_after_max_drawdown_pct
            FROM hypothesis_validation_v1_result
            WHERE valid_flag = 1
            """
        )
        return list(cur.fetchall())


def volume_ratio(row: Dict[str, Any]) -> Optional[float]:
    base_volume = to_float(row.get("singlebar_volume"))
    break_volume = to_float(row.get("break_volume"))
    if base_volume is None or break_volume is None or base_volume <= 0:
        return None
    return break_volume / base_volume


def pass_filter(row: Dict[str, Any], threshold_pct: float, filter_name: str) -> bool:
    single_ret = to_float(row.get("singlebar_close_return_pct"))
    if single_ret is None or single_ret < threshold_pct:
        return False

    if filter_name == "T_ONLY":
        return True

    has_break = row.get("break_time") is not None
    if not has_break:
        return False

    if filter_name == "T_BREAK":
        return True

    vr = volume_ratio(row)
    if filter_name == "T_BREAK_VOL_03":
        return vr is not None and vr >= 0.3
    if filter_name == "T_BREAK_VOL_05":
        return vr is not None and vr >= 0.5
    if filter_name == "T_BREAK_VOL_07":
        return vr is not None and vr >= 0.7
    if filter_name == "T_BREAK_VOL_10":
        return vr is not None and vr >= 1.0

    if filter_name == "T_BREAK_RSI_ANY":
        return to_int(row.get("break_rsi_gt_60")) == 1 or to_int(row.get("break_rsi_rising")) == 1
    if filter_name == "T_BREAK_RSI_GT60":
        return to_int(row.get("break_rsi_gt_60")) == 1
    if filter_name == "T_BREAK_RSI_RISING":
        return to_int(row.get("break_rsi_rising")) == 1
    if filter_name == "T_BREAK_RSI_BOTH":
        return to_int(row.get("break_rsi_gt_60")) == 1 and to_int(row.get("break_rsi_rising")) == 1

    if filter_name == "T_BREAK_MA10_GT":
        return to_int(row.get("break_close_gt_ma10")) == 1
    if filter_name == "T_BREAK_MA10_CROSS":
        return to_int(row.get("break_close_cross_ma10")) == 1

    if filter_name == "T_BREAK_VOL05_RSI_ANY":
        return vr is not None and vr >= 0.5 and (to_int(row.get("break_rsi_gt_60")) == 1 or to_int(row.get("break_rsi_rising")) == 1)
    if filter_name == "T_BREAK_VOL05_D1":
        return vr is not None and vr >= 0.5 and to_int(row.get("d1_prev5_up10_high_break_5m3")) == 1
    if filter_name == "T_BREAK_RSI_D1":
        return (to_int(row.get("break_rsi_gt_60")) == 1 or to_int(row.get("break_rsi_rising")) == 1) and to_int(row.get("d1_prev5_up10_high_break_5m3")) == 1
    if filter_name == "T_BREAK_VOL05_RSI_D1":
        return vr is not None and vr >= 0.5 and (to_int(row.get("break_rsi_gt_60")) == 1 or to_int(row.get("break_rsi_rising")) == 1) and to_int(row.get("d1_prev5_up10_high_break_5m3")) == 1

    raise RuntimeError("Unknown filter_name: " + filter_name)


def summarize(threshold_pct: float, filter_name: str, rows: List[Dict[str, Any]], total_days: int) -> Dict[str, Any]:
    passed = [row for row in rows if pass_filter(row, threshold_pct, filter_name)]
    active_dates = sorted({row.get("search_date") for row in passed})
    sample_count = len(passed)
    active_days = len(active_dates)
    actual_top1 = sum(1 for r in passed if to_int(r.get("actual_rank")) == 1)
    actual_top3 = sum(1 for r in passed if 1 <= to_int(r.get("actual_rank")) <= 3)
    actual_top5 = sum(1 for r in passed if 1 <= to_int(r.get("actual_rank")) <= 5)
    actual_top10 = sum(1 for r in passed if 1 <= to_int(r.get("actual_rank")) <= 10)

    actual_values = [to_float(r.get("actual_max_after_return_pct")) for r in passed]
    break_values = [to_float(r.get("break_after_max_return_pct")) for r in passed]
    close_values = [to_float(r.get("break_after_close_return_pct")) for r in passed]
    drawdown_values = [to_float(r.get("break_after_max_drawdown_pct")) for r in passed]

    return {
        "threshold_pct": threshold_pct,
        "filter_name": filter_name,
        "sample_count": sample_count,
        "active_days": active_days,
        "avg_pass_per_day": sample_count / float(total_days) if total_days > 0 else None,
        "actual_top1_count": actual_top1,
        "actual_top3_count": actual_top3,
        "actual_top5_count": actual_top5,
        "actual_top10_count": actual_top10,
        "hit_rate_to_actual_top10": actual_top10 / float(sample_count) if sample_count > 0 else None,
        "avg_actual_max_after_return_pct": avg(actual_values),
        "median_actual_max_after_return_pct": median(actual_values),
        "avg_break_after_max_return_pct": avg(break_values),
        "median_break_after_max_return_pct": median(break_values),
        "avg_break_after_close_return_pct": avg(close_values),
        "avg_break_after_max_drawdown_pct": avg(drawdown_values),
        "win_rate_after_3pct": rate(break_values, lambda v: v >= 3.0),
        "win_rate_after_5pct": rate(break_values, lambda v: v >= 5.0),
        "win_rate_after_10pct": rate(break_values, lambda v: v >= 10.0),
        "win_rate_after_20pct": rate(break_values, lambda v: v >= 20.0),
        "loss_rate_after_close_minus3pct": rate(close_values, lambda v: v <= -3.0),
        "loss_rate_after_close_minus5pct": rate(close_values, lambda v: v <= -5.0),
    }


def upsert_summary(conn: Any, row: Dict[str, Any]) -> None:
    sql = """
        INSERT INTO singlebar_threshold_sweep_summary (
            threshold_pct, filter_name,
            sample_count, active_days, avg_pass_per_day,
            actual_top1_count, actual_top3_count, actual_top5_count, actual_top10_count, hit_rate_to_actual_top10,
            avg_actual_max_after_return_pct, median_actual_max_after_return_pct,
            avg_break_after_max_return_pct, median_break_after_max_return_pct,
            avg_break_after_close_return_pct, avg_break_after_max_drawdown_pct,
            win_rate_after_3pct, win_rate_after_5pct, win_rate_after_10pct, win_rate_after_20pct,
            loss_rate_after_close_minus3pct, loss_rate_after_close_minus5pct
        ) VALUES (
            %(threshold_pct)s, %(filter_name)s,
            %(sample_count)s, %(active_days)s, %(avg_pass_per_day)s,
            %(actual_top1_count)s, %(actual_top3_count)s, %(actual_top5_count)s, %(actual_top10_count)s, %(hit_rate_to_actual_top10)s,
            %(avg_actual_max_after_return_pct)s, %(median_actual_max_after_return_pct)s,
            %(avg_break_after_max_return_pct)s, %(median_break_after_max_return_pct)s,
            %(avg_break_after_close_return_pct)s, %(avg_break_after_max_drawdown_pct)s,
            %(win_rate_after_3pct)s, %(win_rate_after_5pct)s, %(win_rate_after_10pct)s, %(win_rate_after_20pct)s,
            %(loss_rate_after_close_minus3pct)s, %(loss_rate_after_close_minus5pct)s
        )
        ON DUPLICATE KEY UPDATE
            sample_count=VALUES(sample_count), active_days=VALUES(active_days), avg_pass_per_day=VALUES(avg_pass_per_day),
            actual_top1_count=VALUES(actual_top1_count), actual_top3_count=VALUES(actual_top3_count), actual_top5_count=VALUES(actual_top5_count),
            actual_top10_count=VALUES(actual_top10_count), hit_rate_to_actual_top10=VALUES(hit_rate_to_actual_top10),
            avg_actual_max_after_return_pct=VALUES(avg_actual_max_after_return_pct), median_actual_max_after_return_pct=VALUES(median_actual_max_after_return_pct),
            avg_break_after_max_return_pct=VALUES(avg_break_after_max_return_pct), median_break_after_max_return_pct=VALUES(median_break_after_max_return_pct),
            avg_break_after_close_return_pct=VALUES(avg_break_after_close_return_pct), avg_break_after_max_drawdown_pct=VALUES(avg_break_after_max_drawdown_pct),
            win_rate_after_3pct=VALUES(win_rate_after_3pct), win_rate_after_5pct=VALUES(win_rate_after_5pct),
            win_rate_after_10pct=VALUES(win_rate_after_10pct), win_rate_after_20pct=VALUES(win_rate_after_20pct),
            loss_rate_after_close_minus3pct=VALUES(loss_rate_after_close_minus3pct), loss_rate_after_close_minus5pct=VALUES(loss_rate_after_close_minus5pct),
            updated_at=CURRENT_TIMESTAMP
    """
    with conn.cursor() as cur:
        cur.execute(sql, row)


def print_summary(conn: Any) -> None:
    queries = [
        ("threshold sweep all", """
            SELECT threshold_pct, filter_name, sample_count, active_days, avg_pass_per_day,
                   actual_top1_count, actual_top3_count, actual_top5_count, actual_top10_count,
                   hit_rate_to_actual_top10,
                   avg_actual_max_after_return_pct, median_actual_max_after_return_pct,
                   avg_break_after_max_return_pct, median_break_after_max_return_pct,
                   avg_break_after_close_return_pct, avg_break_after_max_drawdown_pct,
                   win_rate_after_5pct, win_rate_after_10pct,
                   loss_rate_after_close_minus3pct, loss_rate_after_close_minus5pct
            FROM singlebar_threshold_sweep_summary
            ORDER BY threshold_pct, filter_name
        """),
        ("high precision candidates avg 0.5~3 per day", """
            SELECT threshold_pct, filter_name, sample_count, active_days, avg_pass_per_day,
                   actual_top1_count, actual_top3_count, actual_top5_count, actual_top10_count,
                   hit_rate_to_actual_top10,
                   avg_actual_max_after_return_pct,
                   avg_break_after_max_return_pct,
                   avg_break_after_close_return_pct,
                   win_rate_after_5pct, win_rate_after_10pct,
                   loss_rate_after_close_minus5pct
            FROM singlebar_threshold_sweep_summary
            WHERE avg_pass_per_day BETWEEN 0.5 AND 3.0
            ORDER BY loss_rate_after_close_minus5pct ASC,
                     win_rate_after_5pct DESC,
                     win_rate_after_10pct DESC,
                     avg_actual_max_after_return_pct DESC
            LIMIT 30
        """),
        ("strict high win candidates", """
            SELECT threshold_pct, filter_name, sample_count, active_days, avg_pass_per_day,
                   actual_top5_count, actual_top10_count,
                   hit_rate_to_actual_top10,
                   avg_actual_max_after_return_pct,
                   win_rate_after_5pct, win_rate_after_10pct,
                   loss_rate_after_close_minus5pct
            FROM singlebar_threshold_sweep_summary
            WHERE sample_count >= 20
            ORDER BY win_rate_after_5pct DESC,
                     loss_rate_after_close_minus5pct ASC,
                     avg_actual_max_after_return_pct DESC
            LIMIT 30
        """),
    ]
    with conn.cursor() as cur:
        for title, sql in queries:
            print("\n=== " + title + " ===")
            cur.execute(sql)
            for row in cur.fetchall():
                print(row)


def parse_thresholds(text: str) -> List[float]:
    result: List[float] = []
    for item in text.split(","):
        item = item.strip()
        if item:
            result.append(float(item))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--thresholds", default="3.0,3.5,4.0,4.5,5.0,5.5,6.0")
    args = parser.parse_args()

    load_env(args.env)
    thresholds = parse_thresholds(args.thresholds)
    filters = [
        "T_ONLY",
        "T_BREAK",
        "T_BREAK_VOL_03",
        "T_BREAK_VOL_05",
        "T_BREAK_VOL_07",
        "T_BREAK_VOL_10",
        "T_BREAK_RSI_ANY",
        "T_BREAK_RSI_GT60",
        "T_BREAK_RSI_RISING",
        "T_BREAK_RSI_BOTH",
        "T_BREAK_MA10_GT",
        "T_BREAK_MA10_CROSS",
        "T_BREAK_VOL05_RSI_ANY",
        "T_BREAK_VOL05_D1",
        "T_BREAK_RSI_D1",
        "T_BREAK_VOL05_RSI_D1",
    ]

    conn = open_conn()
    try:
        ensure_schema(conn, args.rebuild)
        rows = load_rows(conn)
        total_days = len({row.get("search_date") for row in rows})
        print("=== build_singlebar_threshold_sweep ===")
        print("rows=" + str(len(rows)))
        print("days=" + str(total_days))
        print("thresholds=" + ", ".join([str(v) for v in thresholds]))

        for threshold in thresholds:
            for filter_name in filters:
                summary = summarize(threshold, filter_name, rows, total_days)
                upsert_summary(conn, summary)
        conn.commit()
        print("\n=== DONE build_singlebar_threshold_sweep ===")
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
