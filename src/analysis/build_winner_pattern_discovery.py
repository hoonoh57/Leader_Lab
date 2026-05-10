# -*- coding: utf-8 -*-
"""Winner-first pattern discovery.

This analyzer keeps all previous experiments as reference assets and starts a new layer:
actual winners vs losers in the same condition-search universe.

V1 uses existing analysis_5m_result + minute5_candles + radar_pullback_entry_result.
Daily/swing features can be added later without replacing this table.

Run:
    python -m src.analysis.build_winner_pattern_discovery --env .env --rebuild
"""

from __future__ import annotations

import argparse
import html
import math
import os
import statistics
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
    ddl = Path("sql/create_winner_pattern_discovery.sql").read_text(encoding="utf-8-sig")
    with conn.cursor() as cur:
        if rebuild:
            cur.execute("DROP TABLE IF EXISTS winner_pattern_feature_summary")
            cur.execute("DROP TABLE IF EXISTS winner_pattern_case")
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


def pct(new_value: Optional[float], base_value: Optional[float]) -> Optional[float]:
    if new_value is None or base_value is None or base_value == 0:
        return None
    return (new_value - base_value) / base_value * 100.0


def avg(values: List[Optional[float]]) -> Optional[float]:
    items = [v for v in values if v is not None]
    if not items:
        return None
    return sum(items) / float(len(items))


def fmt(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}"


def amount_from_row(row: Dict[str, Any]) -> Optional[float]:
    o = to_float(row.get("open_price"))
    h = to_float(row.get("high_price"))
    l = to_float(row.get("low_price"))
    c = to_float(row.get("close_price"))
    v = to_float(row.get("volume"))
    if o is None or h is None or l is None or c is None or v is None:
        return None
    return ((o + h + l + c) / 4.0) * v


def load_targets(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT search_date, search_time, code, name,
                   max_after_return_pct AS actual_max_after_return_pct,
                   close_return_pct,
                   history_grade
            FROM analysis_5m_result
            WHERE valid_analysis_flag = 1
              AND history_grade IN ('normal_intraday', 'partial_intraday', 'weak_intraday')
            ORDER BY search_date, search_time, code
        """)
        return list(cur.fetchall())


def build_actual_ranks(targets: List[Dict[str, Any]]) -> Dict[Tuple[Any, str], int]:
    grouped: Dict[Any, List[Tuple[str, float]]] = {}
    for row in targets:
        d = row.get("search_date")
        code = str(row.get("code"))
        value = to_float(row.get("actual_max_after_return_pct"))
        if value is None:
            continue
        grouped.setdefault(d, []).append((code, value))
    ranks: Dict[Tuple[Any, str], int] = {}
    for d, items in grouped.items():
        items.sort(key=lambda item: (-item[1], item[0]))
        for idx, item in enumerate(items, start=1):
            ranks[(d, item[0])] = idx
    return ranks


def load_day_candles(conn: Any, search_date: Any, code: str) -> List[Dict[str, Any]]:
    start_dt = datetime.combine(search_date, time(9, 0, 0))
    end_dt = datetime.combine(search_date, time(15, 30, 0))
    with conn.cursor() as cur:
        cur.execute("""
            SELECT candle_time AS candle_time,
                   open AS open_price,
                   high AS high_price,
                   low AS low_price,
                   close AS close_price,
                   volume AS volume
            FROM minute5_candles
            WHERE code = %s
              AND candle_time >= %s
              AND candle_time <= %s
            ORDER BY candle_time
        """, (code, start_dt, end_dt))
        return list(cur.fetchall())


def load_radar_best(conn: Any) -> Dict[Tuple[Any, str], Dict[str, Any]]:
    result: Dict[Tuple[Any, str], Dict[str, Any]] = {}
    with conn.cursor() as cur:
        try:
            cur.execute("""
                SELECT search_date, code,
                       MAX(max_return_after_entry_pct) AS best_max_return,
                       MAX(close_return_from_entry_pct) AS best_close_return,
                       COUNT(*) AS candidate_count
                FROM radar_pullback_entry_result
                WHERE valid_flag = 1
                GROUP BY search_date, code
            """)
            rows = list(cur.fetchall())
        except Exception:
            return result
    for row in rows:
        result[(row.get("search_date"), str(row.get("code")))] = row
    return result


def analyze_candles(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "day_open": None, "day_high": None, "day_low": None, "day_close": None,
        "day_range_pct": None, "close_from_open_pct": None,
        "first_hour_high_from_open_pct": None,
        "max_5m_singlebar_return_pct": None,
        "max_5m_singlebar_from_open_pct": None,
        "max_5m_singlebar_from_low_pct": None,
        "singlebar_2pct_exists": 0, "singlebar_3pct_exists": 0, "singlebar_4pct_exists": 0,
        "singlebar_5pct_exists": 0, "singlebar_6pct_exists": 0,
        "max_5m_volume": None, "total_5m_volume": None, "intraday_amount_proxy": None,
    }
    if not rows:
        return result
    day_open = to_float(rows[0].get("open_price"))
    day_close = to_float(rows[-1].get("close_price"))
    highs = [to_float(r.get("high_price")) for r in rows]
    lows = [to_float(r.get("low_price")) for r in rows]
    volumes = [to_float(r.get("volume")) or 0.0 for r in rows]
    day_high = max([v for v in highs if v is not None]) if any(v is not None for v in highs) else None
    day_low = min([v for v in lows if v is not None]) if any(v is not None for v in lows) else None
    max_ret: Optional[float] = None
    max_ret_close: Optional[float] = None
    total_amount = 0.0
    for row in rows:
        o = to_float(row.get("open_price"))
        c = to_float(row.get("close_price"))
        r = pct(c, o)
        if r is not None and (max_ret is None or r > max_ret):
            max_ret = r
            max_ret_close = c
        amount = amount_from_row(row)
        if amount is not None:
            total_amount += amount
    first_hour_rows = [r for r in rows if str(r.get("candle_time"))[11:16] <= "10:00"]
    first_hour_high = max([to_float(r.get("high_price")) or -999999999.0 for r in first_hour_rows]) if first_hour_rows else None
    result.update({
        "day_open": day_open,
        "day_high": day_high,
        "day_low": day_low,
        "day_close": day_close,
        "day_range_pct": pct(day_high, day_low),
        "close_from_open_pct": pct(day_close, day_open),
        "first_hour_high_from_open_pct": pct(first_hour_high, day_open),
        "max_5m_singlebar_return_pct": max_ret,
        "max_5m_singlebar_from_open_pct": pct(max_ret_close, day_open),
        "max_5m_singlebar_from_low_pct": pct(max_ret_close, day_low),
        "singlebar_2pct_exists": 1 if max_ret is not None and max_ret >= 2.0 else 0,
        "singlebar_3pct_exists": 1 if max_ret is not None and max_ret >= 3.0 else 0,
        "singlebar_4pct_exists": 1 if max_ret is not None and max_ret >= 4.0 else 0,
        "singlebar_5pct_exists": 1 if max_ret is not None and max_ret >= 5.0 else 0,
        "singlebar_6pct_exists": 1 if max_ret is not None and max_ret >= 6.0 else 0,
        "max_5m_volume": int(max(volumes)) if volumes else None,
        "total_5m_volume": int(sum(volumes)) if volumes else None,
        "intraday_amount_proxy": total_amount,
    })
    return result


def make_case(target: Dict[str, Any], rank: Optional[int], candle_features: Dict[str, Any], radar_best: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    actual = to_float(target.get("actual_max_after_return_pct"))
    close_ret = to_float(target.get("close_return_pct"))
    return {
        "search_date": target.get("search_date"),
        "search_time": target.get("search_time"),
        "code": str(target.get("code")),
        "name": target.get("name"),
        "actual_rank": rank,
        "actual_max_after_return_pct": actual,
        "close_return_pct": close_ret,
        "group_top3": 1 if rank is not None and rank <= 3 else 0,
        "group_top5": 1 if rank is not None and rank <= 5 else 0,
        "group_top10": 1 if rank is not None and rank <= 10 else 0,
        "group_ret10": 1 if actual is not None and actual >= 10.0 else 0,
        "group_ret15": 1 if actual is not None and actual >= 15.0 else 0,
        "group_low3": 1 if actual is not None and actual < 3.0 else 0,
        "group_close_m3": 1 if close_ret is not None and close_ret <= -3.0 else 0,
        "group_close_m5": 1 if close_ret is not None and close_ret <= -5.0 else 0,
        **candle_features,
        "radar_pullback_exists": 1 if radar_best is not None else 0,
        "best_radar_pullback_max_return_pct": to_float(radar_best.get("best_max_return")) if radar_best else None,
        "best_radar_pullback_close_return_pct": to_float(radar_best.get("best_close_return")) if radar_best else None,
    }


def upsert_case(conn: Any, row: Dict[str, Any]) -> None:
    cols = list(row.keys())
    placeholders = ["%s"] * len(cols)
    updates = [f"{c}=VALUES({c})" for c in cols if c not in ("search_date", "search_time", "code")]
    sql = "INSERT INTO winner_pattern_case (" + ",".join(cols) + ") VALUES (" + ",".join(placeholders) + ") ON DUPLICATE KEY UPDATE " + ",".join(updates) + ", updated_at=CURRENT_TIMESTAMP"
    with conn.cursor() as cur:
        cur.execute(sql, [row[c] for c in cols])


def load_cases(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM winner_pattern_case")
        return list(cur.fetchall())


def summarize_feature(rows: List[Dict[str, Any]], feature: str, winner_group: str, loser_group: str, feature_type: str) -> Dict[str, Any]:
    winners = [r for r in rows if to_int(r.get(winner_group)) == 1]
    losers = [r for r in rows if to_int(r.get(loser_group)) == 1]
    if feature_type == "binary":
        wr = sum(1 for r in winners if to_int(r.get(feature)) == 1) / float(len(winners)) if winners else None
        lr = sum(1 for r in losers if to_int(r.get(feature)) == 1) / float(len(losers)) if losers else None
        diff = wr - lr if wr is not None and lr is not None else None
        lift = wr / lr if wr is not None and lr is not None and lr > 0 else None
        wav = None
        lav = None
    else:
        wvals = [to_float(r.get(feature)) for r in winners]
        lvals = [to_float(r.get(feature)) for r in losers]
        wav = avg(wvals)
        lav = avg(lvals)
        wr = None
        lr = None
        diff = None
        lift = None
    return {
        "feature_name": feature,
        "feature_type": feature_type,
        "winner_group": winner_group,
        "loser_group": loser_group,
        "winner_count": len(winners),
        "loser_count": len(losers),
        "winner_rate": wr,
        "loser_rate": lr,
        "diff_rate": diff,
        "lift_ratio": lift,
        "winner_avg_value": wav,
        "loser_avg_value": lav,
        "diff_avg_value": wav - lav if wav is not None and lav is not None else None,
    }


def upsert_summary(conn: Any, row: Dict[str, Any]) -> None:
    cols = list(row.keys())
    placeholders = ["%s"] * len(cols)
    updates = [f"{c}=VALUES({c})" for c in cols if c not in ("feature_name", "feature_type", "winner_group", "loser_group")]
    sql = "INSERT INTO winner_pattern_feature_summary (" + ",".join(cols) + ") VALUES (" + ",".join(placeholders) + ") ON DUPLICATE KEY UPDATE " + ",".join(updates) + ", updated_at=CURRENT_TIMESTAMP"
    with conn.cursor() as cur:
        cur.execute(sql, [row[c] for c in cols])


def refresh_feature_summary(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE winner_pattern_feature_summary")
    rows = load_cases(conn)
    binary_features = [
        "singlebar_2pct_exists", "singlebar_3pct_exists", "singlebar_4pct_exists",
        "singlebar_5pct_exists", "singlebar_6pct_exists", "radar_pullback_exists",
    ]
    numeric_features = [
        "day_range_pct", "close_from_open_pct", "first_hour_high_from_open_pct",
        "max_5m_singlebar_return_pct", "max_5m_singlebar_from_open_pct", "max_5m_singlebar_from_low_pct",
        "intraday_amount_proxy", "best_radar_pullback_max_return_pct", "best_radar_pullback_close_return_pct",
    ]
    pairs = [("group_top5", "group_low3"), ("group_ret10", "group_low3"), ("group_top10", "group_close_m3"), ("group_ret15", "group_close_m5")]
    for winner_group, loser_group in pairs:
        for feature in binary_features:
            upsert_summary(conn, summarize_feature(rows, feature, winner_group, loser_group, "binary"))
        for feature in numeric_features:
            upsert_summary(conn, summarize_feature(rows, feature, winner_group, loser_group, "numeric"))
    conn.commit()


def generate_report(conn: Any, output: str) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM winner_pattern_case")
        total = cur.fetchone()["cnt"]
        cur.execute("""
            SELECT feature_name, feature_type, winner_group, loser_group,
                   winner_count, loser_count, winner_rate, loser_rate, diff_rate, lift_ratio,
                   winner_avg_value, loser_avg_value, diff_avg_value
            FROM winner_pattern_feature_summary
            ORDER BY COALESCE(diff_rate, diff_avg_value) DESC
        """)
        summaries = list(cur.fetchall())
    def cell(v: Any) -> str:
        if isinstance(v, float):
            return fmt(v)
        if isinstance(v, Decimal):
            return fmt(float(v))
        return html.escape(str(v)) if v is not None else "-"
    rows_html = []
    for r in summaries:
        rows_html.append("<tr>" + "".join([f"<td>{cell(r.get(k))}</td>" for k in [
            "feature_name", "feature_type", "winner_group", "loser_group", "winner_count", "loser_count",
            "winner_rate", "loser_rate", "diff_rate", "lift_ratio", "winner_avg_value", "loser_avg_value", "diff_avg_value"
        ]]) + "</tr>")
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"""<!doctype html><html lang='ko'><head><meta charset='utf-8'/><title>Winner Pattern Discovery</title>
<style>body{{font-family:Segoe UI,Malgun Gothic,Arial;background:#111827;color:#e5e7eb;margin:0;padding:18px}}table{{border-collapse:collapse;width:100%;font-size:12px;background:#0f172a}}th,td{{border:1px solid #334155;padding:6px;text-align:right}}th{{background:#1e293b}}td:first-child,th:first-child{{text-align:left}}.note{{color:#cbd5e1}}</style></head><body>
<h1>Winner Pattern Discovery Report</h1><p class='note'>Total cases: {total}. 실제 winner/loser를 먼저 정의한 뒤 feature 차이를 보는 리포트입니다. 이전 실험은 폐기하지 않고 비교 자원으로 유지합니다.</p>
<table><thead><tr><th>feature</th><th>type</th><th>winner</th><th>loser</th><th>wN</th><th>lN</th><th>wRate</th><th>lRate</th><th>diffRate</th><th>lift</th><th>wAvg</th><th>lAvg</th><th>diffAvg</th></tr></thead><tbody>{''.join(rows_html)}</tbody></table>
</body></html>""", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--output", default="reports/winner_pattern_discovery_report.html")
    args = parser.parse_args()
    load_env(args.env)
    conn = open_conn()
    try:
        ensure_schema(conn, args.rebuild)
        targets = load_targets(conn)
        ranks = build_actual_ranks(targets)
        radar_map = load_radar_best(conn)
        count = 0
        for target in targets:
            d = target.get("search_date")
            code = str(target.get("code"))
            rows = load_day_candles(conn, d, code)
            candle_features = analyze_candles(rows)
            row = make_case(target, ranks.get((d, code)), candle_features, radar_map.get((d, code)))
            upsert_case(conn, row)
            count += 1
        conn.commit()
        refresh_feature_summary(conn)
        generate_report(conn, args.output)
        print("=== DONE build_winner_pattern_discovery ===")
        print("cases=" + str(count))
        print("output=" + str(Path(args.output).resolve()))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
