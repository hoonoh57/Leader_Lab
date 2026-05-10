# -*- coding: utf-8 -*-
"""Build Winner Feature Score v1.

This script converts Winner Pattern Discovery features into an explainable daily ranking score.
It does not replace previous experiments. It reuses them as feature assets.

Run:
    python -m src.analysis.build_winner_feature_score --env .env --rebuild
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
    ddl = Path("sql/create_winner_feature_score.sql").read_text(encoding="utf-8-sig")
    with conn.cursor() as cur:
        if rebuild:
            cur.execute("DROP TABLE IF EXISTS winner_feature_score_summary")
            cur.execute("DROP TABLE IF EXISTS winner_feature_score_result")
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
    if isinstance(value, Decimal):
        return int(value)
    try:
        return int(float(value))
    except Exception:
        return 0


def clamp(value: float, min_value: float, max_value: float) -> float:
    if value < min_value:
        return min_value
    if value > max_value:
        return max_value
    return value


def nz(value: Optional[float], default: float = 0.0) -> float:
    return default if value is None else float(value)


def avg(values: List[Optional[float]]) -> Optional[float]:
    items = [v for v in values if v is not None]
    if not items:
        return None
    return sum(items) / float(len(items))


def median(values: List[Optional[float]]) -> Optional[float]:
    items = [v for v in values if v is not None]
    if not items:
        return None
    return float(statistics.median(items))


def amount_score(amount: Optional[float]) -> float:
    # Winner discovery showed amount is the strongest separator.
    # 300억~1200억 area is meaningful in the current data.
    v = nz(amount)
    if v <= 0:
        return 0.0
    if v >= 120000000000.0:
        return 25.0
    if v >= 80000000000.0:
        return 20.0
    if v >= 50000000000.0:
        return 15.0
    if v >= 30000000000.0:
        return 10.0
    if v >= 15000000000.0:
        return 5.0
    return 0.0


def first_hour_score(value: Optional[float]) -> float:
    v = nz(value)
    if v >= 14.0:
        return 20.0
    if v >= 10.0:
        return 15.0
    if v >= 7.0:
        return 10.0
    if v >= 4.0:
        return 5.0
    return 0.0


def day_range_score(value: Optional[float]) -> float:
    v = nz(value)
    if v >= 24.0:
        return 15.0
    if v >= 18.0:
        return 12.0
    if v >= 14.0:
        return 8.0
    if v >= 10.0:
        return 4.0
    return 0.0


def singlebar_strength_score(row: Dict[str, Any]) -> float:
    score = 0.0
    if to_int(row.get("singlebar_3pct_exists")) == 1:
        score += 8.0
    if to_int(row.get("singlebar_4pct_exists")) == 1:
        score += 8.0
    if to_int(row.get("singlebar_5pct_exists")) == 1:
        score += 7.0
    # 6% is not added here; it is treated as both strength and overheat risk.
    if to_int(row.get("singlebar_6pct_exists")) == 1:
        score += 3.0
    return score


def radar_pullback_score(row: Dict[str, Any]) -> float:
    score = 0.0
    if to_int(row.get("radar_pullback_exists")) == 1:
        score += 15.0
    best = to_float(row.get("best_radar_pullback_max_return_pct"))
    if best is not None:
        if best >= 7.0:
            score += 10.0
        elif best >= 5.0:
            score += 7.0
        elif best >= 3.0:
            score += 4.0
    return score


def close_strength_score(row: Dict[str, Any]) -> float:
    score = 0.0
    close_open = to_float(row.get("close_from_open_pct"))
    radar_close = to_float(row.get("best_radar_pullback_close_return_pct"))
    if close_open is not None:
        if close_open >= 10.0:
            score += 12.0
        elif close_open >= 5.0:
            score += 8.0
        elif close_open >= 0.0:
            score += 3.0
        elif close_open <= -5.0:
            score -= 8.0
        elif close_open <= -3.0:
            score -= 5.0
    if radar_close is not None:
        if radar_close >= 3.0:
            score += 8.0
        elif radar_close >= 0.0:
            score += 4.0
        elif radar_close <= -5.0:
            score -= 8.0
        elif radar_close <= -3.0:
            score -= 5.0
    return score


def overheat_penalty(row: Dict[str, Any]) -> Tuple[float, float, float]:
    p6 = 0.0
    p_open = 0.0
    p_low = 0.0
    if to_int(row.get("singlebar_6pct_exists")) == 1:
        p6 = 5.0
    from_open = to_float(row.get("max_5m_singlebar_from_open_pct"))
    from_low = to_float(row.get("max_5m_singlebar_from_low_pct"))
    if from_open is not None:
        if from_open >= 18.0:
            p_open = 12.0
        elif from_open >= 15.0:
            p_open = 8.0
        elif from_open >= 12.0:
            p_open = 5.0
        elif from_open >= 10.0:
            p_open = 3.0
    if from_low is not None:
        if from_low >= 25.0:
            p_low = 12.0
        elif from_low >= 20.0:
            p_low = 8.0
        elif from_low >= 15.0:
            p_low = 5.0
        elif from_low >= 12.0:
            p_low = 3.0
    return p6, p_open, p_low


def bucket_actual_rank(rank: Optional[int]) -> str:
    if rank is None:
        return "NA"
    if rank == 1:
        return "TOP1"
    if rank <= 3:
        return "TOP3"
    if rank <= 5:
        return "TOP5"
    if rank <= 10:
        return "TOP10"
    return "OTHER"


def bucket_score(score: float) -> str:
    if score >= 80.0:
        return "S80"
    if score >= 65.0:
        return "A65"
    if score >= 50.0:
        return "B50"
    if score >= 35.0:
        return "C35"
    return "DLOW"


def load_source_cases(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT search_date, search_time, code, name,
                   actual_rank, actual_max_after_return_pct, close_return_pct,
                   intraday_amount_proxy, first_hour_high_from_open_pct, day_range_pct, close_from_open_pct,
                   max_5m_singlebar_return_pct, max_5m_singlebar_from_open_pct, max_5m_singlebar_from_low_pct,
                   best_radar_pullback_max_return_pct, best_radar_pullback_close_return_pct,
                   singlebar_2pct_exists, singlebar_3pct_exists, singlebar_4pct_exists,
                   singlebar_5pct_exists, singlebar_6pct_exists, radar_pullback_exists
            FROM winner_pattern_case
            ORDER BY search_date, search_time, code
        """)
        return list(cur.fetchall())


def score_case(row: Dict[str, Any]) -> Dict[str, Any]:
    amount = amount_score(to_float(row.get("intraday_amount_proxy")))
    fh = first_hour_score(to_float(row.get("first_hour_high_from_open_pct")))
    dr = day_range_score(to_float(row.get("day_range_pct")))
    sb = singlebar_strength_score(row)
    rp = radar_pullback_score(row)
    rp_return = 0.0
    best_rp = to_float(row.get("best_radar_pullback_max_return_pct"))
    if best_rp is not None:
        rp_return = clamp(best_rp, 0.0, 10.0)
    cs = close_strength_score(row)
    p6, po, pl = overheat_penalty(row)

    leader = amount + fh + dr + sb
    pullback = rp + rp_return
    close_score = cs
    penalty = p6 + po + pl
    total = leader + pullback + close_score - penalty
    total = clamp(total, 0.0, 100.0)

    result = dict(row)
    result.update({
        "amount_score": amount,
        "first_hour_score": fh,
        "day_range_score": dr,
        "singlebar_score": sb,
        "radar_pullback_score": rp,
        "radar_pullback_return_score": rp_return,
        "close_from_open_score": cs,
        "radar_close_return_score": 0.0,
        "singlebar6_penalty": p6,
        "singlebar_open_overheat_penalty": po,
        "singlebar_low_overheat_penalty": pl,
        "leader_strength_score": leader,
        "pullback_structure_score": pullback,
        "close_strength_score": close_score,
        "overheat_penalty": penalty,
        "winner_feature_score": total,
        "actual_rank_bucket": bucket_actual_rank(to_int(row.get("actual_rank")) if row.get("actual_rank") is not None else None),
        "score_bucket": bucket_score(total),
    })
    return result


def upsert_result(conn: Any, row: Dict[str, Any]) -> None:
    cols = [
        "search_date", "search_time", "code", "name", "actual_rank", "actual_max_after_return_pct", "close_return_pct",
        "leader_strength_score", "pullback_structure_score", "close_strength_score", "overheat_penalty", "winner_feature_score",
        "amount_score", "first_hour_score", "day_range_score", "singlebar_score", "radar_pullback_score", "radar_pullback_return_score",
        "close_from_open_score", "radar_close_return_score", "singlebar6_penalty", "singlebar_open_overheat_penalty", "singlebar_low_overheat_penalty",
        "intraday_amount_proxy", "first_hour_high_from_open_pct", "day_range_pct", "close_from_open_pct",
        "max_5m_singlebar_return_pct", "max_5m_singlebar_from_open_pct", "max_5m_singlebar_from_low_pct",
        "best_radar_pullback_max_return_pct", "best_radar_pullback_close_return_pct",
        "singlebar_2pct_exists", "singlebar_3pct_exists", "singlebar_4pct_exists", "singlebar_5pct_exists", "singlebar_6pct_exists", "radar_pullback_exists",
        "actual_rank_bucket", "score_bucket",
    ]
    placeholders = ["%s"] * len(cols)
    updates = [c + "=VALUES(" + c + ")" for c in cols if c not in ("search_date", "search_time", "code")]
    sql = "INSERT INTO winner_feature_score_result (" + ",".join(cols) + ") VALUES (" + ",".join(placeholders) + ") ON DUPLICATE KEY UPDATE " + ",".join(updates) + ", updated_at=CURRENT_TIMESTAMP"
    with conn.cursor() as cur:
        cur.execute(sql, [row.get(c) for c in cols])


def update_daily_ranks(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT search_date FROM winner_feature_score_result ORDER BY search_date")
        dates = [r["search_date"] for r in cur.fetchall()]
        for d in dates:
            cur.execute("""
                SELECT id, winner_feature_score, code
                FROM winner_feature_score_result
                WHERE search_date = %s
                ORDER BY winner_feature_score DESC, code
            """, (d,))
            rows = cur.fetchall()
            rank = 1
            for row in rows:
                cur.execute("UPDATE winner_feature_score_result SET score_rank=%s WHERE id=%s", (rank, row["id"]))
                rank += 1
    conn.commit()


def refresh_summary(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE winner_feature_score_summary")
        cur.execute("SELECT * FROM winner_feature_score_result")
        rows = list(cur.fetchall())

    groups: Dict[str, List[Dict[str, Any]]] = {
        "ALL": rows,
        "SCORE_TOP1_DAILY": [r for r in rows if to_int(r.get("score_rank")) == 1],
        "SCORE_TOP3_DAILY": [r for r in rows if 1 <= to_int(r.get("score_rank")) <= 3],
        "SCORE_TOP5_DAILY": [r for r in rows if 1 <= to_int(r.get("score_rank")) <= 5],
        "SCORE_BUCKET_S80": [r for r in rows if r.get("score_bucket") == "S80"],
        "SCORE_BUCKET_A65": [r for r in rows if r.get("score_bucket") == "A65"],
        "SCORE_BUCKET_B50": [r for r in rows if r.get("score_bucket") == "B50"],
    }
    sql = """
        INSERT INTO winner_feature_score_summary (
            score_group, sample_count, active_days, avg_candidates_per_day,
            actual_top1_count, actual_top3_count, actual_top5_count, actual_top10_count, actual_top10_rate,
            avg_actual_max_after_return_pct, median_actual_max_after_return_pct, avg_close_return_pct,
            avg_winner_feature_score, avg_leader_strength_score, avg_pullback_structure_score, avg_close_strength_score, avg_overheat_penalty
        ) VALUES (
            %(score_group)s, %(sample_count)s, %(active_days)s, %(avg_candidates_per_day)s,
            %(actual_top1_count)s, %(actual_top3_count)s, %(actual_top5_count)s, %(actual_top10_count)s, %(actual_top10_rate)s,
            %(avg_actual_max_after_return_pct)s, %(median_actual_max_after_return_pct)s, %(avg_close_return_pct)s,
            %(avg_winner_feature_score)s, %(avg_leader_strength_score)s, %(avg_pullback_structure_score)s, %(avg_close_strength_score)s, %(avg_overheat_penalty)s
        )
    """
    with conn.cursor() as cur:
        for name, vals in groups.items():
            if not vals:
                continue
            top1 = sum(1 for r in vals if to_int(r.get("actual_rank")) == 1)
            top3 = sum(1 for r in vals if 1 <= to_int(r.get("actual_rank")) <= 3)
            top5 = sum(1 for r in vals if 1 <= to_int(r.get("actual_rank")) <= 5)
            top10 = sum(1 for r in vals if 1 <= to_int(r.get("actual_rank")) <= 10)
            row = {
                "score_group": name,
                "sample_count": len(vals),
                "active_days": len({r.get("search_date") for r in vals}),
                "avg_candidates_per_day": len(vals) / 82.0,
                "actual_top1_count": top1,
                "actual_top3_count": top3,
                "actual_top5_count": top5,
                "actual_top10_count": top10,
                "actual_top10_rate": top10 / float(len(vals)) if vals else None,
                "avg_actual_max_after_return_pct": avg([to_float(r.get("actual_max_after_return_pct")) for r in vals]),
                "median_actual_max_after_return_pct": median([to_float(r.get("actual_max_after_return_pct")) for r in vals]),
                "avg_close_return_pct": avg([to_float(r.get("close_return_pct")) for r in vals]),
                "avg_winner_feature_score": avg([to_float(r.get("winner_feature_score")) for r in vals]),
                "avg_leader_strength_score": avg([to_float(r.get("leader_strength_score")) for r in vals]),
                "avg_pullback_structure_score": avg([to_float(r.get("pullback_structure_score")) for r in vals]),
                "avg_close_strength_score": avg([to_float(r.get("close_strength_score")) for r in vals]),
                "avg_overheat_penalty": avg([to_float(r.get("overheat_penalty")) for r in vals]),
            }
            cur.execute(sql, row)
    conn.commit()


def print_summary(conn: Any) -> None:
    with conn.cursor() as cur:
        print("\n=== winner_feature_score_summary ===")
        cur.execute("""
            SELECT score_group, sample_count, active_days, avg_candidates_per_day,
                   actual_top1_count, actual_top3_count, actual_top5_count, actual_top10_count, actual_top10_rate,
                   avg_actual_max_after_return_pct, median_actual_max_after_return_pct, avg_close_return_pct,
                   avg_winner_feature_score, avg_leader_strength_score, avg_pullback_structure_score,
                   avg_close_strength_score, avg_overheat_penalty
            FROM winner_feature_score_summary
            ORDER BY FIELD(score_group, 'SCORE_TOP1_DAILY','SCORE_TOP3_DAILY','SCORE_TOP5_DAILY','SCORE_BUCKET_S80','SCORE_BUCKET_A65','SCORE_BUCKET_B50','ALL')
        """)
        for row in cur.fetchall():
            print(row)

        print("\n=== daily score top samples ===")
        cur.execute("""
            SELECT search_date, score_rank, code, name, winner_feature_score, actual_rank,
                   actual_max_after_return_pct, close_return_pct,
                   leader_strength_score, pullback_structure_score, close_strength_score, overheat_penalty
            FROM winner_feature_score_result
            WHERE score_rank <= 3
            ORDER BY search_date, score_rank
            LIMIT 120
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
        source_rows = load_source_cases(conn)
        print("=== build_winner_feature_score ===")
        print("source_cases=" + str(len(source_rows)))
        count = 0
        for row in source_rows:
            scored = score_case(row)
            upsert_result(conn, scored)
            count += 1
        conn.commit()
        update_daily_ranks(conn)
        refresh_summary(conn)
        print("\n=== DONE build_winner_feature_score ===")
        print("scored_cases=" + str(count))
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
