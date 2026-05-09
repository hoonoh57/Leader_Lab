# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List, Tuple

from src.common.db import mysql_connect
from src.common.env_loader import env_str, load_env_file
from src.evaluation.rank_match_metrics import aggregate_results, evaluate_daily_topk


BASELINE_SCORE_COLUMNS: Dict[str, str] = {
    "ret_1m": "ret_1m",
    "ret_3m": "ret_3m",
    "volume": "search_volume",
    "oracle": "max_ret_in_period",
}


def _safe_float(value) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except Exception:
        return 0.0


def fetch_rows(score_column: str) -> List[dict]:
    conn = mysql_connect(env_str("MYSQL_DB_STOCK_INFO", "stock_info"))
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    DATE_FORMAT(search_date, '%%Y-%%m-%%d') AS search_date,
                    code,
                    name,
                    max_ret_in_period,
                    {score_column} AS score_value,
                    label_10
                FROM performance_result
                WHERE max_ret_in_period IS NOT NULL
                ORDER BY search_date, code;
                """
            )
            return list(cur.fetchall())
    finally:
        conn.close()


def group_by_date(rows: List[dict]) -> Dict[str, List[dict]]:
    grouped: Dict[str, List[dict]] = {}
    for row in rows:
        key = str(row["search_date"])
        grouped.setdefault(key, []).append(row)
    return grouped


def evaluate_baseline(score_name: str, actual_k: int, score_k: int) -> Tuple[List[dict], Dict[str, float]]:
    score_column = BASELINE_SCORE_COLUMNS[score_name]
    rows = fetch_rows(score_column)
    grouped = group_by_date(rows)

    daily_rows: List[dict] = []
    metric_rows = []

    for search_date, items in sorted(grouped.items()):
        actual_items = [(str(x["code"]), _safe_float(x["max_ret_in_period"])) for x in items]
        score_items = [(str(x["code"]), _safe_float(x["score_value"])) for x in items]
        result = evaluate_daily_topk(search_date, actual_items, score_items, actual_k=actual_k, score_k=score_k)
        metric_rows.append(result)

        score_top_codes = [code for code, _ in sorted(score_items, key=lambda x: (x[1], x[0]), reverse=True)[:score_k]]
        score_top10_label_count = sum(1 for x in items if str(x["code"]) in set(score_top_codes) and int(x.get("label_10") or 0) == 1)
        daily_rows.append(
            {
                "search_date": search_date,
                "candidate_count": result.candidate_count,
                "hit_count": result.hit_count,
                "hit_rate": round(result.hit_rate, 6),
                "top1_capture": result.top1_capture,
                "ndcg": round(result.ndcg, 6),
                "lift": round(result.lift, 6),
                "score_top_label10_count": score_top10_label_count,
                "score_top_label10_rate": round(score_top10_label_count / float(max(1, score_k)), 6),
            }
        )

    summary = aggregate_results(metric_rows)
    if daily_rows:
        summary["avg_score_top_label10_rate"] = sum(x["score_top_label10_rate"] for x in daily_rows) / float(len(daily_rows))
    else:
        summary["avg_score_top_label10_rate"] = 0.0
    return daily_rows, summary


def write_reports(score_name: str, daily_rows: List[dict], summary: Dict[str, float], report_root: Path) -> None:
    report_root.mkdir(parents=True, exist_ok=True)
    csv_path = report_root / f"baseline_{score_name}_topk_daily.csv"
    md_path = report_root / f"baseline_{score_name}_summary.md"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(daily_rows[0].keys()) if daily_rows else ["empty"])
        writer.writeheader()
        if daily_rows:
            writer.writerows(daily_rows)

    lines = [
        f"# Baseline TopK Report: {score_name}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key, value in summary.items():
        lines.append(f"| {key} | {value:.6f} |")
    lines.append("")
    lines.append(f"Daily CSV: `{csv_path}`")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"[REPORT] {csv_path}")
    print(f"[REPORT] {md_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--score", choices=sorted(BASELINE_SCORE_COLUMNS.keys()), default="ret_3m")
    parser.add_argument("--actual-k", type=int, default=10)
    parser.add_argument("--score-k", type=int, default=10)
    args = parser.parse_args()

    load_env_file(args.env)
    daily_rows, summary = evaluate_baseline(args.score, args.actual_k, args.score_k)
    report_root = Path(env_str("REPORT_ROOT", "reports"))
    write_reports(args.score, daily_rows, summary, report_root)

    print("=== baseline summary ===")
    for key, value in summary.items():
        print(f"{key}={value:.6f}")


if __name__ == "__main__":
    main()
