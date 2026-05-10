# -*- coding: utf-8 -*-
"""Build WYSIWYG evaluation tables from analysis_5m_result.

Goal:
- Compare actual intraday leaders by max_after_return_pct with simple visible baselines.
- Establish a non-leakage baseline before building LeaderScore.

Run:
    python -m src.evaluation.build_wysiwyg_eval --env .env --rebuild

Notes:
- leakage_close_return_after uses close_return_pct and is NOT tradable at capture time.
- It is available only when explicitly requested as a sanity/oracle-like reference.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
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
    ddl = Path("sql/create_wysiwyg_eval_tables.sql").read_text(encoding="utf-8-sig")
    with conn.cursor() as cur:
        if rebuild:
            cur.execute("DROP TABLE IF EXISTS wysiwyg_eval_rank_detail")
            cur.execute("DROP TABLE IF EXISTS wysiwyg_eval_daily_summary")
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


def load_eval_dates(conn: Any) -> List[Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT search_date
            FROM analysis_5m_result
            WHERE valid_analysis_flag = 1
            GROUP BY search_date
            HAVING COUNT(*) >= 3
            ORDER BY search_date
            """
        )
        rows = cur.fetchall()
    return [row["search_date"] for row in rows]


def load_day_rows(conn: Any, eval_date: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT search_date, search_time, code, name,
                   capture_price, max_after_price, max_after_return_pct,
                   close_return_pct, max_drawdown_pct,
                   base_volume, base_amount, cum_amount_until_capture,
                   history_grade
            FROM analysis_5m_result
            WHERE valid_analysis_flag = 1
              AND search_date = %s
            ORDER BY code
            """,
            (eval_date,),
        )
        return list(cur.fetchall())


def scalar_score(row: Dict[str, Any], baseline_name: str) -> Optional[float]:
    if baseline_name == "base_amount":
        return to_float(row.get("base_amount"))
    if baseline_name == "base_volume":
        return to_float(row.get("base_volume"))
    if baseline_name == "cum_amount_until_capture":
        return to_float(row.get("cum_amount_until_capture"))
    if baseline_name == "leakage_close_return_after":
        return to_float(row.get("close_return_pct"))
    raise RuntimeError("Unknown scalar baseline: " + baseline_name)


def rank_rows(rows: List[Dict[str, Any]], key_name: str, descending: bool = True) -> Dict[str, int]:
    scored: List[Tuple[str, float]] = []
    for row in rows:
        value = to_float(row.get(key_name))
        code = str(row.get("code"))
        if value is not None:
            scored.append((code, value))
    scored.sort(key=lambda item: (-item[1], item[0]) if descending else (item[1], item[0]))
    ranks: Dict[str, int] = {}
    for idx, item in enumerate(scored, start=1):
        ranks[item[0]] = idx
    return ranks


def scalar_ranks(rows: List[Dict[str, Any]], baseline_name: str) -> Tuple[Dict[str, int], Dict[str, Optional[float]]]:
    scored: List[Tuple[str, float]] = []
    scores: Dict[str, Optional[float]] = {}
    for row in rows:
        code = str(row.get("code"))
        value = scalar_score(row, baseline_name)
        scores[code] = value
        if value is not None:
            scored.append((code, value))
    scored.sort(key=lambda item: (-item[1], item[0]))
    ranks: Dict[str, int] = {}
    for idx, item in enumerate(scored, start=1):
        ranks[item[0]] = idx
    return ranks, scores


def rank_score_from_rank(rank_value: Optional[int], total_count: int) -> float:
    if rank_value is None or total_count <= 0:
        return 0.0
    return float(total_count - rank_value + 1) / float(total_count)


def liquidity_rank_mix(rows: List[Dict[str, Any]]) -> Tuple[Dict[str, int], Dict[str, Optional[float]]]:
    volume_ranks, _ = scalar_ranks(rows, "base_volume")
    amount_ranks, _ = scalar_ranks(rows, "base_amount")
    total_count = len(rows)

    scored: List[Tuple[str, float]] = []
    scores: Dict[str, Optional[float]] = {}
    for row in rows:
        code = str(row.get("code"))
        v_score = rank_score_from_rank(volume_ranks.get(code), total_count)
        a_score = rank_score_from_rank(amount_ranks.get(code), total_count)
        # Volume was empirically stronger than amount in the first run, so give it a larger weight.
        score = (0.60 * v_score) + (0.40 * a_score)
        scores[code] = score
        scored.append((code, score))

    scored.sort(key=lambda item: (-item[1], item[0]))
    ranks: Dict[str, int] = {}
    for idx, item in enumerate(scored, start=1):
        ranks[item[0]] = idx
    return ranks, scores


def rank_by_baseline(rows: List[Dict[str, Any]], baseline_name: str) -> Tuple[Dict[str, int], Dict[str, Optional[float]]]:
    if baseline_name == "liquidity_rank_mix":
        return liquidity_rank_mix(rows)
    return scalar_ranks(rows, baseline_name)


def upsert_detail(conn: Any, row: Dict[str, Any]) -> None:
    sql = """
        INSERT INTO wysiwyg_eval_rank_detail (
            eval_date, baseline_name, code, name,
            actual_rank, baseline_rank, actual_max_after_return_pct, baseline_score,
            capture_price, max_after_price, close_return_pct, max_drawdown_pct,
            base_volume, base_amount, cum_amount_until_capture, history_grade,
            in_actual_top10, in_baseline_top10, is_hit_top10
        ) VALUES (
            %(eval_date)s, %(baseline_name)s, %(code)s, %(name)s,
            %(actual_rank)s, %(baseline_rank)s, %(actual_max_after_return_pct)s, %(baseline_score)s,
            %(capture_price)s, %(max_after_price)s, %(close_return_pct)s, %(max_drawdown_pct)s,
            %(base_volume)s, %(base_amount)s, %(cum_amount_until_capture)s, %(history_grade)s,
            %(in_actual_top10)s, %(in_baseline_top10)s, %(is_hit_top10)s
        )
        ON DUPLICATE KEY UPDATE
            name=VALUES(name), actual_rank=VALUES(actual_rank), baseline_rank=VALUES(baseline_rank),
            actual_max_after_return_pct=VALUES(actual_max_after_return_pct), baseline_score=VALUES(baseline_score),
            capture_price=VALUES(capture_price), max_after_price=VALUES(max_after_price),
            close_return_pct=VALUES(close_return_pct), max_drawdown_pct=VALUES(max_drawdown_pct),
            base_volume=VALUES(base_volume), base_amount=VALUES(base_amount),
            cum_amount_until_capture=VALUES(cum_amount_until_capture), history_grade=VALUES(history_grade),
            in_actual_top10=VALUES(in_actual_top10), in_baseline_top10=VALUES(in_baseline_top10),
            is_hit_top10=VALUES(is_hit_top10), updated_at=CURRENT_TIMESTAMP
    """
    with conn.cursor() as cur:
        cur.execute(sql, row)


def upsert_summary(conn: Any, row: Dict[str, Any]) -> None:
    sql = """
        INSERT INTO wysiwyg_eval_daily_summary (
            eval_date, eligible_rows, actual_top10_count, baseline_name,
            hit_at_1, hit_at_3, hit_at_5, hit_at_10,
            label10_rate, avg_selected_max_return_pct, avg_actual_top10_return_pct
        ) VALUES (
            %(eval_date)s, %(eligible_rows)s, %(actual_top10_count)s, %(baseline_name)s,
            %(hit_at_1)s, %(hit_at_3)s, %(hit_at_5)s, %(hit_at_10)s,
            %(label10_rate)s, %(avg_selected_max_return_pct)s, %(avg_actual_top10_return_pct)s
        )
        ON DUPLICATE KEY UPDATE
            eligible_rows=VALUES(eligible_rows), actual_top10_count=VALUES(actual_top10_count),
            hit_at_1=VALUES(hit_at_1), hit_at_3=VALUES(hit_at_3), hit_at_5=VALUES(hit_at_5),
            hit_at_10=VALUES(hit_at_10), label10_rate=VALUES(label10_rate),
            avg_selected_max_return_pct=VALUES(avg_selected_max_return_pct),
            avg_actual_top10_return_pct=VALUES(avg_actual_top10_return_pct), updated_at=CURRENT_TIMESTAMP
    """
    with conn.cursor() as cur:
        cur.execute(sql, row)


def avg(values: List[Optional[float]]) -> Optional[float]:
    filtered = [v for v in values if v is not None]
    if not filtered:
        return None
    return sum(filtered) / float(len(filtered))


def topn_set(ranks: Dict[str, int], n: int) -> set[str]:
    return {code for code, rank in ranks.items() if rank <= n}


def build_for_date(conn: Any, eval_date: Any, baselines: List[str]) -> None:
    rows = load_day_rows(conn, eval_date)
    if not rows:
        return

    actual_ranks = rank_rows(rows, "max_after_return_pct", True)
    actual_top10 = topn_set(actual_ranks, 10)
    actual_top10_returns: List[Optional[float]] = []
    for row in rows:
        code = str(row.get("code"))
        if code in actual_top10:
            actual_top10_returns.append(to_float(row.get("max_after_return_pct")))

    for baseline_name in baselines:
        baseline_ranks, scores = rank_by_baseline(rows, baseline_name)
        baseline_top10 = topn_set(baseline_ranks, 10)
        hits = actual_top10.intersection(baseline_top10)

        selected_returns: List[Optional[float]] = []
        for row in rows:
            code = str(row.get("code"))
            if code in baseline_top10:
                selected_returns.append(to_float(row.get("max_after_return_pct")))

        summary = {
            "eval_date": eval_date,
            "eligible_rows": len(rows),
            "actual_top10_count": len(actual_top10),
            "baseline_name": baseline_name,
            "hit_at_1": len(topn_set(baseline_ranks, 1).intersection(actual_top10)),
            "hit_at_3": len(topn_set(baseline_ranks, 3).intersection(actual_top10)),
            "hit_at_5": len(topn_set(baseline_ranks, 5).intersection(actual_top10)),
            "hit_at_10": len(hits),
            "label10_rate": len(hits) / 10.0 if len(actual_top10) >= 10 else (len(hits) / float(len(actual_top10)) if actual_top10 else None),
            "avg_selected_max_return_pct": avg(selected_returns),
            "avg_actual_top10_return_pct": avg(actual_top10_returns),
        }
        upsert_summary(conn, summary)

        for row in rows:
            code = str(row.get("code"))
            actual_rank = actual_ranks.get(code)
            baseline_rank = baseline_ranks.get(code)
            in_actual = 1 if actual_rank is not None and actual_rank <= 10 else 0
            in_baseline = 1 if baseline_rank is not None and baseline_rank <= 10 else 0
            detail = {
                "eval_date": eval_date,
                "baseline_name": baseline_name,
                "code": code,
                "name": row.get("name"),
                "actual_rank": actual_rank,
                "baseline_rank": baseline_rank,
                "actual_max_after_return_pct": to_float(row.get("max_after_return_pct")),
                "baseline_score": scores.get(code),
                "capture_price": to_float(row.get("capture_price")),
                "max_after_price": to_float(row.get("max_after_price")),
                "close_return_pct": to_float(row.get("close_return_pct")),
                "max_drawdown_pct": to_float(row.get("max_drawdown_pct")),
                "base_volume": row.get("base_volume"),
                "base_amount": to_float(row.get("base_amount")),
                "cum_amount_until_capture": to_float(row.get("cum_amount_until_capture")),
                "history_grade": row.get("history_grade"),
                "in_actual_top10": in_actual,
                "in_baseline_top10": in_baseline,
                "is_hit_top10": 1 if in_actual == 1 and in_baseline == 1 else 0,
            }
            upsert_detail(conn, detail)


def print_summary(conn: Any) -> None:
    queries = [
        ("overall baseline summary", """
            SELECT baseline_name,
                   COUNT(*) AS trading_days,
                   AVG(eligible_rows) AS avg_eligible_rows,
                   AVG(hit_at_1) AS avg_hit_at_1,
                   AVG(hit_at_3) AS avg_hit_at_3,
                   AVG(hit_at_5) AS avg_hit_at_5,
                   AVG(hit_at_10) AS avg_hit_at_10,
                   AVG(label10_rate) AS avg_label10_rate,
                   AVG(avg_selected_max_return_pct) AS avg_selected_max_return_pct,
                   AVG(avg_actual_top10_return_pct) AS avg_actual_top10_return_pct
            FROM wysiwyg_eval_daily_summary
            GROUP BY baseline_name
            ORDER BY avg_hit_at_10 DESC, avg_selected_max_return_pct DESC
        """),
        ("tradable baseline summary only", """
            SELECT baseline_name,
                   COUNT(*) AS trading_days,
                   AVG(hit_at_10) AS avg_hit_at_10,
                   AVG(label10_rate) AS avg_label10_rate,
                   AVG(avg_selected_max_return_pct) AS avg_selected_max_return_pct,
                   AVG(avg_actual_top10_return_pct) AS avg_actual_top10_return_pct
            FROM wysiwyg_eval_daily_summary
            WHERE baseline_name NOT LIKE 'leakage_%'
            GROUP BY baseline_name
            ORDER BY avg_hit_at_10 DESC, avg_selected_max_return_pct DESC
        """),
        ("worst tradable daily hits", """
            SELECT eval_date, baseline_name, eligible_rows, hit_at_10, label10_rate,
                   avg_selected_max_return_pct, avg_actual_top10_return_pct
            FROM wysiwyg_eval_daily_summary
            WHERE baseline_name NOT LIKE 'leakage_%'
            ORDER BY hit_at_10 ASC, avg_selected_max_return_pct ASC
            LIMIT 30
        """),
    ]
    with conn.cursor() as cur:
        for title, sql in queries:
            print("\n=== " + title + " ===")
            cur.execute(sql)
            for row in cur.fetchall():
                print(row)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--baselines", default="base_volume,base_amount,cum_amount_until_capture,liquidity_rank_mix")
    parser.add_argument("--include-leakage", action="store_true")
    parser.add_argument("--commit-every", type=int, default=10)
    args = parser.parse_args()

    load_env(args.env)
    baselines = [item.strip() for item in args.baselines.split(",") if item.strip()]
    if args.include_leakage and "leakage_close_return_after" not in baselines:
        baselines.append("leakage_close_return_after")

    conn = open_conn()
    try:
        ensure_schema(conn, args.rebuild)
        dates = load_eval_dates(conn)
        print("=== build_wysiwyg_eval ===")
        print("dates=" + str(len(dates)))
        print("baselines=" + ", ".join(baselines))

        for idx, eval_date in enumerate(dates, start=1):
            build_for_date(conn, eval_date, baselines)
            if idx % args.commit_every == 0:
                conn.commit()
                print("[" + str(idx) + "/" + str(len(dates)) + "] committed")
        conn.commit()
        print("\n=== DONE build_wysiwyg_eval ===")
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
