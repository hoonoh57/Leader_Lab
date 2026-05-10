# -*- coding: utf-8 -*-
"""Build Time-Aware Winner Feature Score v2.

V1 explains winners using full-day features.
V2 ranks candidates at specific decision times using only candles available up to that time,
then evaluates outcome after that time.

Run:
    python -m src.analysis.build_winner_feature_score_time --env .env --rebuild
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
    ddl = Path("sql/create_winner_feature_score_time.sql").read_text(encoding="utf-8-sig")
    with conn.cursor() as cur:
        if rebuild:
            cur.execute("DROP TABLE IF EXISTS winner_feature_score_time_summary")
            cur.execute("DROP TABLE IF EXISTS winner_feature_score_time_result")
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


def rate(values: List[Optional[float]], threshold: float, above: bool) -> Optional[float]:
    items = [v for v in values if v is not None]
    if not items:
        return None
    count = 0
    for value in items:
        if above:
            if value >= threshold:
                count += 1
        else:
            if value <= threshold:
                count += 1
    return count / float(len(items))


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
                   close_return_pct AS full_day_close_return_pct,
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
        idx = 1
        for code, _value in items:
            ranks[(d, code)] = idx
            idx += 1
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


def parse_time(text: str) -> time:
    h, m = text.split(":")
    return time(int(h), int(m), 0)


def amount_score_time(amount: Optional[float]) -> float:
    # Time-aware cumulative amount thresholds are lower than full-day v1.
    v = nz(amount)
    if v >= 60000000000.0:
        return 25.0
    if v >= 40000000000.0:
        return 20.0
    if v >= 25000000000.0:
        return 15.0
    if v >= 15000000000.0:
        return 10.0
    if v >= 8000000000.0:
        return 5.0
    return 0.0


def high_score_time(value: Optional[float]) -> float:
    v = nz(value)
    if v >= 12.0:
        return 20.0
    if v >= 9.0:
        return 15.0
    if v >= 6.0:
        return 10.0
    if v >= 3.0:
        return 5.0
    return 0.0


def range_score_time(value: Optional[float]) -> float:
    v = nz(value)
    if v >= 18.0:
        return 15.0
    if v >= 14.0:
        return 12.0
    if v >= 10.0:
        return 8.0
    if v >= 6.0:
        return 4.0
    return 0.0


def current_close_score_time(value: Optional[float]) -> float:
    v = nz(value)
    if v >= 10.0:
        return 12.0
    if v >= 7.0:
        return 9.0
    if v >= 4.0:
        return 6.0
    if v >= 1.0:
        return 3.0
    if v <= -3.0:
        return -6.0
    return 0.0


def singlebar_score_time(features: Dict[str, Any]) -> float:
    score = 0.0
    if to_int(features.get("singlebar_3pct_exists_until_time")) == 1:
        score += 8.0
    if to_int(features.get("singlebar_4pct_exists_until_time")) == 1:
        score += 8.0
    if to_int(features.get("singlebar_5pct_exists_until_time")) == 1:
        score += 7.0
    if to_int(features.get("singlebar_6pct_exists_until_time")) == 1:
        score += 3.0
    return score


def radar_pullback_score_time(features: Dict[str, Any]) -> float:
    score = 0.0
    if to_int(features.get("radar_pullback_exists_until_time")) == 1:
        score += 12.0
    best = to_float(features.get("radar_pullback_best_max_return_until_time"))
    if best is not None:
        if best >= 5.0:
            score += 8.0
        elif best >= 3.0:
            score += 5.0
        elif best >= 1.5:
            score += 3.0
    return score


def overheat_penalty_time(features: Dict[str, Any]) -> Tuple[float, float, float]:
    p6 = 0.0
    po = 0.0
    pl = 0.0
    if to_int(features.get("singlebar_6pct_exists_until_time")) == 1:
        p6 = 5.0
    high_open = to_float(features.get("high_so_far_from_open_pct"))
    high_low = to_float(features.get("high_so_far_from_low_pct"))
    if high_open is not None:
        if high_open >= 18.0:
            po = 12.0
        elif high_open >= 15.0:
            po = 8.0
        elif high_open >= 12.0:
            po = 5.0
        elif high_open >= 10.0:
            po = 3.0
    if high_low is not None:
        if high_low >= 25.0:
            pl = 12.0
        elif high_low >= 20.0:
            pl = 8.0
        elif high_low >= 15.0:
            pl = 5.0
        elif high_low >= 12.0:
            pl = 3.0
    return p6, po, pl


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


def analyze_until_time(rows: List[Dict[str, Any]], decision_time_value: time) -> Optional[Dict[str, Any]]:
    before: List[Dict[str, Any]] = []
    after: List[Dict[str, Any]] = []
    for row in rows:
        candle_time = row.get("candle_time")
        if candle_time is None:
            continue
        t = candle_time.time() if isinstance(candle_time, datetime) else datetime.fromisoformat(str(candle_time)).time()
        if t <= decision_time_value:
            before.append(row)
        else:
            after.append(row)
    if not before or not after:
        return None

    day_open = to_float(rows[0].get("open_price"))
    decision = before[-1]
    decision_price = to_float(decision.get("close_price"))
    if decision_price is None:
        return None

    highs_before = [to_float(r.get("high_price")) for r in before]
    lows_before = [to_float(r.get("low_price")) for r in before]
    high_so_far = max([v for v in highs_before if v is not None]) if any(v is not None for v in highs_before) else None
    low_so_far = min([v for v in lows_before if v is not None]) if any(v is not None for v in lows_before) else None

    cum_amount = 0.0
    cum_volume = 0
    max_singlebar = None
    max_singlebar_close = None
    for row in before:
        amount = amount_from_row(row)
        if amount is not None:
            cum_amount += amount
        cum_volume += to_int(row.get("volume"))
        r = pct(to_float(row.get("close_price")), to_float(row.get("open_price")))
        if r is not None and (max_singlebar is None or r > max_singlebar):
            max_singlebar = r
            max_singlebar_close = to_float(row.get("close_price"))

    future_high = max([to_float(r.get("high_price")) or -999999999.0 for r in after])
    future_low = min([to_float(r.get("low_price")) or 999999999.0 for r in after])
    future_close = to_float(rows[-1].get("close_price"))

    features: Dict[str, Any] = {
        "decision_candle_time": decision.get("candle_time"),
        "decision_price": decision_price,
        "future_max_price": future_high,
        "future_min_price": future_low,
        "future_close_price": future_close,
        "future_max_return_pct": pct(future_high, decision_price),
        "future_close_return_pct": pct(future_close, decision_price),
        "future_max_drawdown_pct": pct(future_low, decision_price),
        "cum_amount_until_time": cum_amount,
        "cum_volume_until_time": cum_volume,
        "current_close_from_open_pct": pct(decision_price, day_open),
        "high_so_far_from_open_pct": pct(high_so_far, day_open),
        "high_so_far_from_low_pct": pct(high_so_far, low_so_far),
        "range_so_far_pct": pct(high_so_far, low_so_far),
        "singlebar_2pct_exists_until_time": 1 if max_singlebar is not None and max_singlebar >= 2.0 else 0,
        "singlebar_3pct_exists_until_time": 1 if max_singlebar is not None and max_singlebar >= 3.0 else 0,
        "singlebar_4pct_exists_until_time": 1 if max_singlebar is not None and max_singlebar >= 4.0 else 0,
        "singlebar_5pct_exists_until_time": 1 if max_singlebar is not None and max_singlebar >= 5.0 else 0,
        "singlebar_6pct_exists_until_time": 1 if max_singlebar is not None and max_singlebar >= 6.0 else 0,
        "max_singlebar_return_until_time": max_singlebar,
        "max_singlebar_from_open_until_time": pct(max_singlebar_close, day_open),
        "max_singlebar_from_low_until_time": pct(max_singlebar_close, low_so_far),
    }

    # Simple time-aware radar-pullback proxy:
    # if a 2%+ radar candle occurred and then a later low was at least -2% from prior high,
    # and price recovered above the pullback reaction high before decision time.
    radar_idx = -1
    radar_high = None
    for idx, row in enumerate(before):
        r = pct(to_float(row.get("close_price")), to_float(row.get("open_price")))
        if r is not None and r >= 2.0:
            radar_idx = idx
            radar_high = to_float(row.get("high_price"))
            break
    radar_exists = 0
    radar_best_max_return = None
    if radar_idx >= 0 and radar_high is not None:
        pullback_idx = -1
        pullback_low = None
        for idx in range(radar_idx + 1, len(before)):
            low_value = to_float(before[idx].get("low_price"))
            depth = pct(low_value, radar_high)
            if depth is not None and depth <= -2.0:
                pullback_idx = idx
                pullback_low = low_value
                break
        if pullback_idx >= 0:
            reaction_high = max([to_float(before[i].get("high_price")) or -999999999.0 for i in range(radar_idx, pullback_idx + 1)])
            for idx in range(pullback_idx + 1, len(before)):
                close_value = to_float(before[idx].get("close_price"))
                if close_value is not None and close_value > reaction_high:
                    radar_exists = 1
                    high_after_entry = max([to_float(before[j].get("high_price")) or -999999999.0 for j in range(idx, len(before))])
                    radar_best_max_return = pct(high_after_entry, close_value)
                    break
    features["radar_pullback_exists_until_time"] = radar_exists
    features["radar_pullback_best_max_return_until_time"] = radar_best_max_return
    return features


def score_features(features: Dict[str, Any]) -> Dict[str, float]:
    amount = amount_score_time(to_float(features.get("cum_amount_until_time")))
    high = high_score_time(to_float(features.get("high_so_far_from_open_pct")))
    rng = range_score_time(to_float(features.get("range_so_far_pct")))
    sb = singlebar_score_time(features)
    rp = radar_pullback_score_time(features)
    cur = current_close_score_time(to_float(features.get("current_close_from_open_pct")))
    p6, po, pl = overheat_penalty_time(features)

    leader = amount + high + rng + sb
    pullback = rp
    current = cur
    penalty = p6 + po + pl
    total = clamp(leader + pullback + current - penalty, 0.0, 100.0)
    return {
        "amount_score_time": amount,
        "high_score_time": high,
        "range_score_time": rng,
        "singlebar_score_time": sb,
        "radar_pullback_score_time": rp,
        "current_close_score_time": cur,
        "singlebar6_penalty_time": p6,
        "overheat_open_penalty_time": po,
        "overheat_low_penalty_time": pl,
        "leader_strength_score_time": leader,
        "pullback_structure_score_time": pullback,
        "current_strength_score_time": current,
        "overheat_penalty_time": penalty,
        "winner_feature_score_time": total,
    }


def make_result_row(target: Dict[str, Any], actual_rank: Optional[int], decision_time_text: str, features: Dict[str, Any], scores: Dict[str, float]) -> Dict[str, Any]:
    total_score = scores["winner_feature_score_time"]
    return {
        "decision_time": decision_time_text + ":00",
        "search_date": target.get("search_date"),
        "search_time": target.get("search_time"),
        "code": str(target.get("code")),
        "name": target.get("name"),
        "actual_rank": actual_rank,
        "actual_max_after_return_pct": to_float(target.get("actual_max_after_return_pct")),
        "full_day_close_return_pct": to_float(target.get("full_day_close_return_pct")),
        **features,
        **scores,
        "score_bucket_time": bucket_score(total_score),
        "actual_rank_bucket": bucket_actual_rank(actual_rank),
        "valid_flag": 1,
        "invalid_reason": None,
    }


def upsert_result(conn: Any, row: Dict[str, Any]) -> None:
    cols = [
        "decision_time", "search_date", "search_time", "code", "name",
        "actual_rank", "actual_max_after_return_pct", "full_day_close_return_pct",
        "decision_candle_time", "decision_price", "future_max_price", "future_min_price", "future_close_price",
        "future_max_return_pct", "future_close_return_pct", "future_max_drawdown_pct",
        "leader_strength_score_time", "pullback_structure_score_time", "current_strength_score_time", "overheat_penalty_time", "winner_feature_score_time",
        "cum_amount_until_time", "cum_volume_until_time", "current_close_from_open_pct", "high_so_far_from_open_pct", "high_so_far_from_low_pct", "range_so_far_pct",
        "singlebar_2pct_exists_until_time", "singlebar_3pct_exists_until_time", "singlebar_4pct_exists_until_time", "singlebar_5pct_exists_until_time", "singlebar_6pct_exists_until_time",
        "max_singlebar_return_until_time", "max_singlebar_from_open_until_time", "max_singlebar_from_low_until_time",
        "radar_pullback_exists_until_time", "radar_pullback_best_max_return_until_time",
        "amount_score_time", "high_score_time", "range_score_time", "singlebar_score_time", "radar_pullback_score_time", "current_close_score_time",
        "singlebar6_penalty_time", "overheat_open_penalty_time", "overheat_low_penalty_time",
        "score_bucket_time", "actual_rank_bucket", "valid_flag", "invalid_reason",
    ]
    placeholders = ["%s"] * len(cols)
    updates = [c + "=VALUES(" + c + ")" for c in cols if c not in ("decision_time", "search_date", "search_time", "code")]
    sql = "INSERT INTO winner_feature_score_time_result (" + ",".join(cols) + ") VALUES (" + ",".join(placeholders) + ") ON DUPLICATE KEY UPDATE " + ",".join(updates) + ", updated_at=CURRENT_TIMESTAMP"
    with conn.cursor() as cur:
        cur.execute(sql, [row.get(c) for c in cols])


def update_time_ranks(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT decision_time, search_date FROM winner_feature_score_time_result WHERE valid_flag=1 ORDER BY decision_time, search_date")
        keys = cur.fetchall()
        for key in keys:
            cur.execute("""
                SELECT id, winner_feature_score_time, code
                FROM winner_feature_score_time_result
                WHERE decision_time=%s AND search_date=%s AND valid_flag=1
                ORDER BY winner_feature_score_time DESC, code
            """, (key["decision_time"], key["search_date"]))
            rows = cur.fetchall()
            rank = 1
            for row in rows:
                cur.execute("UPDATE winner_feature_score_time_result SET score_rank_time=%s WHERE id=%s", (rank, row["id"]))
                rank += 1
    conn.commit()


def refresh_summary(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE winner_feature_score_time_summary")
        cur.execute("SELECT * FROM winner_feature_score_time_result WHERE valid_flag=1")
        rows = list(cur.fetchall())

    grouped_by_time: Dict[Any, List[Dict[str, Any]]] = {}
    for row in rows:
        grouped_by_time.setdefault(row.get("decision_time"), []).append(row)

    sql = """
        INSERT INTO winner_feature_score_time_summary (
            decision_time, score_group, sample_count, active_days, avg_candidates_per_day,
            actual_top1_count, actual_top3_count, actual_top5_count, actual_top10_count, actual_top10_rate,
            avg_future_max_return_pct, median_future_max_return_pct, avg_future_close_return_pct, avg_future_max_drawdown_pct,
            win_rate_future_3pct, win_rate_future_5pct, win_rate_future_10pct,
            loss_rate_future_close_m3pct, loss_rate_future_close_m5pct,
            avg_winner_feature_score_time, avg_leader_strength_score_time, avg_pullback_structure_score_time,
            avg_current_strength_score_time, avg_overheat_penalty_time
        ) VALUES (
            %(decision_time)s, %(score_group)s, %(sample_count)s, %(active_days)s, %(avg_candidates_per_day)s,
            %(actual_top1_count)s, %(actual_top3_count)s, %(actual_top5_count)s, %(actual_top10_count)s, %(actual_top10_rate)s,
            %(avg_future_max_return_pct)s, %(median_future_max_return_pct)s, %(avg_future_close_return_pct)s, %(avg_future_max_drawdown_pct)s,
            %(win_rate_future_3pct)s, %(win_rate_future_5pct)s, %(win_rate_future_10pct)s,
            %(loss_rate_future_close_m3pct)s, %(loss_rate_future_close_m5pct)s,
            %(avg_winner_feature_score_time)s, %(avg_leader_strength_score_time)s, %(avg_pullback_structure_score_time)s,
            %(avg_current_strength_score_time)s, %(avg_overheat_penalty_time)s
        )
    """
    with conn.cursor() as cur:
        for decision_time_value, time_rows in grouped_by_time.items():
            groups: Dict[str, List[Dict[str, Any]]] = {
                "ALL": time_rows,
                "SCORE_TOP1_DAILY": [r for r in time_rows if to_int(r.get("score_rank_time")) == 1],
                "SCORE_TOP3_DAILY": [r for r in time_rows if 1 <= to_int(r.get("score_rank_time")) <= 3],
                "SCORE_TOP5_DAILY": [r for r in time_rows if 1 <= to_int(r.get("score_rank_time")) <= 5],
                "SCORE_BUCKET_S80": [r for r in time_rows if r.get("score_bucket_time") == "S80"],
                "SCORE_BUCKET_A65": [r for r in time_rows if r.get("score_bucket_time") == "A65"],
                "SCORE_BUCKET_B50": [r for r in time_rows if r.get("score_bucket_time") == "B50"],
            }
            for name, vals in groups.items():
                if not vals:
                    continue
                top1 = sum(1 for r in vals if to_int(r.get("actual_rank")) == 1)
                top3 = sum(1 for r in vals if 1 <= to_int(r.get("actual_rank")) <= 3)
                top5 = sum(1 for r in vals if 1 <= to_int(r.get("actual_rank")) <= 5)
                top10 = sum(1 for r in vals if 1 <= to_int(r.get("actual_rank")) <= 10)
                max_returns = [to_float(r.get("future_max_return_pct")) for r in vals]
                close_returns = [to_float(r.get("future_close_return_pct")) for r in vals]
                row = {
                    "decision_time": decision_time_value,
                    "score_group": name,
                    "sample_count": len(vals),
                    "active_days": len({r.get("search_date") for r in vals}),
                    "avg_candidates_per_day": len(vals) / 82.0,
                    "actual_top1_count": top1,
                    "actual_top3_count": top3,
                    "actual_top5_count": top5,
                    "actual_top10_count": top10,
                    "actual_top10_rate": top10 / float(len(vals)) if vals else None,
                    "avg_future_max_return_pct": avg(max_returns),
                    "median_future_max_return_pct": median(max_returns),
                    "avg_future_close_return_pct": avg(close_returns),
                    "avg_future_max_drawdown_pct": avg([to_float(r.get("future_max_drawdown_pct")) for r in vals]),
                    "win_rate_future_3pct": rate(max_returns, 3.0, True),
                    "win_rate_future_5pct": rate(max_returns, 5.0, True),
                    "win_rate_future_10pct": rate(max_returns, 10.0, True),
                    "loss_rate_future_close_m3pct": rate(close_returns, -3.0, False),
                    "loss_rate_future_close_m5pct": rate(close_returns, -5.0, False),
                    "avg_winner_feature_score_time": avg([to_float(r.get("winner_feature_score_time")) for r in vals]),
                    "avg_leader_strength_score_time": avg([to_float(r.get("leader_strength_score_time")) for r in vals]),
                    "avg_pullback_structure_score_time": avg([to_float(r.get("pullback_structure_score_time")) for r in vals]),
                    "avg_current_strength_score_time": avg([to_float(r.get("current_strength_score_time")) for r in vals]),
                    "avg_overheat_penalty_time": avg([to_float(r.get("overheat_penalty_time")) for r in vals]),
                }
                cur.execute(sql, row)
    conn.commit()


def print_summary(conn: Any) -> None:
    with conn.cursor() as cur:
        print("\n=== time-aware summary top groups ===")
        cur.execute("""
            SELECT decision_time, score_group, sample_count, active_days, avg_candidates_per_day,
                   actual_top10_rate, avg_future_max_return_pct, median_future_max_return_pct,
                   avg_future_close_return_pct, avg_future_max_drawdown_pct,
                   win_rate_future_3pct, win_rate_future_5pct, loss_rate_future_close_m5pct,
                   avg_winner_feature_score_time, avg_overheat_penalty_time
            FROM winner_feature_score_time_summary
            WHERE score_group IN ('SCORE_TOP1_DAILY','SCORE_TOP3_DAILY','SCORE_TOP5_DAILY','ALL')
            ORDER BY decision_time,
                     FIELD(score_group, 'SCORE_TOP1_DAILY','SCORE_TOP3_DAILY','SCORE_TOP5_DAILY','ALL')
        """)
        for row in cur.fetchall():
            print(row)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--decision-times", default="09:20,09:30,10:00,10:30,11:00,13:00")
    args = parser.parse_args()

    load_env(args.env)
    conn = open_conn()
    try:
        ensure_schema(conn, args.rebuild)
        targets = load_targets(conn)
        ranks = build_actual_ranks(targets)
        decision_times = [x.strip() for x in args.decision_times.split(",") if x.strip()]
        print("=== build_winner_feature_score_time ===")
        print("targets=" + str(len(targets)))
        print("decision_times=" + str(decision_times))
        count = 0
        candle_cache: Dict[Tuple[Any, str], List[Dict[str, Any]]] = {}
        for target in targets:
            d = target.get("search_date")
            code = str(target.get("code"))
            rows = load_day_candles(conn, d, code)
            if not rows:
                continue
            candle_cache[(d, code)] = rows

        for dt_text in decision_times:
            dt_value = parse_time(dt_text)
            dt_count = 0
            for target in targets:
                d = target.get("search_date")
                code = str(target.get("code"))
                rows = candle_cache.get((d, code))
                if not rows:
                    continue
                features = analyze_until_time(rows, dt_value)
                if features is None:
                    continue
                scores = score_features(features)
                row = make_result_row(target, ranks.get((d, code)), dt_text, features, scores)
                upsert_result(conn, row)
                dt_count += 1
                count += 1
            conn.commit()
            print("[decision_time] " + dt_text + " rows=" + str(dt_count))

        update_time_ranks(conn)
        refresh_summary(conn)
        print("\n=== DONE build_winner_feature_score_time ===")
        print("scored_rows=" + str(count))
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
