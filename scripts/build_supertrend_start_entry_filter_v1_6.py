#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Leader_Lab v1.6
SuperTrend START Entry Filter Builder

- MySQL 전용
- SQLite / --db-path 사용 금지
- v1.5 ST_START vs EARLY3 Failure Diagnostics 산출물을 읽어 ST_START 진입 후보를 등급화
- 로컬에서는 git pull 후 ps1 실행만 수행

입력 기본 테이블:
- supertrend_start_vs_early3_failure_diag_v1_5

출력:
- supertrend_start_entry_filter_detail_v1_6
- supertrend_start_entry_filter_summary_v1_6
- supertrend_start_entry_filter_examples_v1_6
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import pymysql
    from pymysql.cursors import DictCursor
except Exception:
    print("[FATAL] pymysql import failed. Install with: py -3 -m pip install pymysql", file=sys.stderr)
    raise

SOURCE_TABLE_DEFAULT = "supertrend_start_vs_early3_failure_diag_v1_5"
DETAIL_TABLE = "supertrend_start_entry_filter_detail_v1_6"
SUMMARY_TABLE = "supertrend_start_entry_filter_summary_v1_6"
EXAMPLE_TABLE = "supertrend_start_entry_filter_examples_v1_6"

REQUIRED_COLS = [
    "trade_date", "code", "name", "st_period", "st_multiplier", "segment_no", "st_up_start_time",
    "score_total", "st_up_max_return_pct", "st_start_estimated_return_pct", "early3_estimated_return_pct",
    "early3_high_return_pct", "post_early3_extension_pct", "early3_lost_move_pct",
    "failure_reason_v1_5", "action_hint_v1_5", "start_from_day_open_pct", "start_from_day_low_pct",
    "start_cum_amount", "live_risk_score_v1_2", "live_filter_label_v1_2", "post_diagnostic_label_v1_2"
]


def parse_conn_string(conn_str: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    if not conn_str:
        return result
    for part in [p.strip() for p in conn_str.split(";") if p.strip()]:
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        key = k.strip().lower().replace(" ", "").replace("_", "")
        val = v.strip()
        if key in ("server", "host", "datasource", "data source"):
            result["host"] = val
        elif key == "port":
            result["port"] = int(val)
        elif key in ("database", "initialcatalog", "dbname", "db"):
            result["database"] = val
        elif key in ("uid", "userid", "user", "username"):
            result["user"] = val
        elif key in ("pwd", "password", "passwd"):
            result["password"] = val
        elif key in ("charset", "characterset"):
            result["charset"] = val
    return result


def build_mysql_config(args: argparse.Namespace) -> Dict[str, Any]:
    conn_env = (
        args.mysql_conn
        or os.environ.get("MYSQL_CONN")
        or os.environ.get("DB_CONN")
        or os.environ.get("MYSQL_CONNECTION_STRING")
        or ""
    )
    cfg = parse_conn_string(conn_env)
    database = args.database or cfg.get("database") or os.environ.get("DB_NAME") or os.environ.get("MYSQL_DATABASE")
    if not database:
        raise RuntimeError("MySQL DB_NAME/MYSQL_DATABASE 또는 --database 값이 필요합니다.")
    return {
        "host": str(args.host or cfg.get("host") or os.environ.get("DB_HOST") or os.environ.get("MYSQL_HOST") or "127.0.0.1"),
        "port": int(args.port or cfg.get("port") or os.environ.get("DB_PORT") or os.environ.get("MYSQL_PORT") or 3306),
        "database": str(database),
        "user": str(args.user or cfg.get("user") or os.environ.get("DB_USER") or os.environ.get("MYSQL_USER") or "root"),
        "password": str(args.password or cfg.get("password") or os.environ.get("DB_PASS") or os.environ.get("MYSQL_PASSWORD") or ""),
        "charset": str(args.charset or cfg.get("charset") or os.environ.get("DB_CHARSET") or "utf8mb4"),
        "cursorclass": DictCursor,
        "autocommit": False,
    }


def qident(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError("Unsafe identifier: " + name)
    return "`" + name + "`"


def to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except Exception:
        return default


def to_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(float(value))
    except Exception:
        return default


def fetch_all(conn: Any, sql: str, params: Optional[Sequence[Any]] = None) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return list(cur.fetchall())


def execute(conn: Any, sql: str, params: Optional[Sequence[Any]] = None) -> int:
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return int(cur.rowcount)


def table_exists(conn: Any, table_name: str) -> bool:
    rows = fetch_all(conn, "SELECT COUNT(*) AS cnt FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = %s", [table_name])
    return bool(rows and to_int(rows[0].get("cnt"), 0) > 0)


def get_columns(conn: Any, table_name: str) -> List[str]:
    rows = fetch_all(conn, "SELECT column_name AS column_name FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = %s ORDER BY ordinal_position", [table_name])
    return [str(r.get("column_name")) for r in rows if r.get("column_name") is not None]


def assert_source_table(conn: Any, table_name: str) -> None:
    if not table_exists(conn, table_name):
        raise RuntimeError("source table not found: " + table_name)
    cols = set(c.lower() for c in get_columns(conn, table_name))
    missing = [c for c in REQUIRED_COLS if c.lower() not in cols]
    if missing:
        raise RuntimeError("source table required columns missing: " + ", ".join(missing))


def create_output_tables(conn: Any) -> None:
    execute(conn, "DROP TABLE IF EXISTS " + qident(EXAMPLE_TABLE))
    execute(conn, "DROP TABLE IF EXISTS " + qident(SUMMARY_TABLE))
    execute(conn, "DROP TABLE IF EXISTS " + qident(DETAIL_TABLE))

    execute(conn, f"""
CREATE TABLE {qident(DETAIL_TABLE)} (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    source_table VARCHAR(128) NOT NULL,
    trade_date DATE NOT NULL,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(128) NULL,
    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    segment_no INT NOT NULL,
    st_up_start_time DATETIME NULL,
    score_total DOUBLE NULL,
    st_up_max_return_pct DOUBLE NULL,
    st_start_estimated_return_pct DOUBLE NULL,
    early3_estimated_return_pct DOUBLE NULL,
    early3_high_return_pct DOUBLE NULL,
    post_early3_extension_pct DOUBLE NULL,
    early3_lost_move_pct DOUBLE NULL,
    start_from_day_open_pct DOUBLE NULL,
    start_from_day_low_pct DOUBLE NULL,
    start_cum_amount DOUBLE NULL,
    live_risk_score_v1_2 DOUBLE NULL,
    failure_reason_v1_5 VARCHAR(255) NULL,
    action_hint_v1_5 VARCHAR(255) NULL,
    live_filter_label_v1_2 VARCHAR(255) NULL,
    post_diagnostic_label_v1_2 VARCHAR(255) NULL,
    filter_label_v1_6 VARCHAR(64) NOT NULL,
    filter_grade_v1_6 VARCHAR(8) NOT NULL,
    filter_score_v1_6 DOUBLE NOT NULL,
    entry_decision_v1_6 VARCHAR(255) NOT NULL,
    filter_reason_v1_6 VARCHAR(255) NOT NULL,
    need_tick_hoga_confirm TINYINT NOT NULL DEFAULT 0,
    auto_entry_candidate TINYINT NOT NULL DEFAULT 0,
    skip_candidate TINYINT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY ix_v16_key (trade_date, code, st_period, st_multiplier, segment_no),
    KEY ix_v16_label (filter_label_v1_6),
    KEY ix_v16_grade (filter_grade_v1_6),
    KEY ix_v16_score (filter_score_v1_6),
    KEY ix_v16_decision (auto_entry_candidate, skip_candidate, need_tick_hoga_confirm)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
""")

    execute(conn, f"""
CREATE TABLE {qident(SUMMARY_TABLE)} (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    filter_label_v1_6 VARCHAR(64) NOT NULL,
    filter_grade_v1_6 VARCHAR(8) NOT NULL,
    row_count INT NOT NULL,
    avg_filter_score_v1_6 DOUBLE NULL,
    avg_score_total DOUBLE NULL,
    avg_st_start_estimated_return_pct DOUBLE NULL,
    avg_early3_estimated_return_pct DOUBLE NULL,
    avg_st_up_max_return_pct DOUBLE NULL,
    avg_early3_high_return_pct DOUBLE NULL,
    avg_post_early3_extension_pct DOUBLE NULL,
    avg_start_from_day_open_pct DOUBLE NULL,
    avg_start_from_day_low_pct DOUBLE NULL,
    avg_start_cum_amount DOUBLE NULL,
    avg_live_risk_score_v1_2 DOUBLE NULL,
    auto_entry_rate DOUBLE NULL,
    skip_rate DOUBLE NULL,
    need_tick_hoga_confirm_rate DOUBLE NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY ix_v16_sum (st_period, st_multiplier, filter_label_v1_6),
    KEY ix_v16_sum_score (avg_filter_score_v1_6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
""")

    execute(conn, f"CREATE TABLE {qident(EXAMPLE_TABLE)} LIKE {qident(DETAIL_TABLE)}")


def label_row(row: Dict[str, Any], args: argparse.Namespace) -> Tuple[str, str, float, str, str, int, int, int]:
    score_total = to_float(row.get("score_total"))
    st_ret = to_float(row.get("st_start_estimated_return_pct"))
    e_ret = to_float(row.get("early3_estimated_return_pct"))
    post_ext = to_float(row.get("post_early3_extension_pct"))
    open_pct = to_float(row.get("start_from_day_open_pct"))
    low_pct = to_float(row.get("start_from_day_low_pct"))
    amount = to_float(row.get("start_cum_amount"))
    risk = to_float(row.get("live_risk_score_v1_2"))
    fail_reason = str(row.get("failure_reason_v1_5") or "")
    live_label = str(row.get("live_filter_label_v1_2") or "")
    post_label = str(row.get("post_diagnostic_label_v1_2") or "")

    open_overheated = ("OPEN_OVERHEATED" in live_label) or open_pct >= args.open_overheat_pct
    low_overextended = ("LOW_OVEREXTENDED" in live_label) or low_pct >= args.low_overextend_pct
    peak_exhausted = ("PEAK_EXHAUSTED" in post_label) or ("EARLY3_ALREADY_EXHAUSTED" in fail_reason) or post_ext <= args.weak_return_pct
    big_start_edge = st_ret >= args.success_return_pct and e_ret <= args.weak_return_pct
    strong_post = post_ext >= args.post_extension_good_pct
    amount_ok = amount >= args.min_start_amount
    score_ok = score_total >= args.min_score_total
    risk_low = risk <= args.low_risk_score
    risk_high = risk >= args.high_risk_score

    base_score = 0.0
    base_score += min(35.0, max(0.0, st_ret) * 3.0)
    base_score += min(25.0, max(0.0, post_ext) * 4.0)
    base_score += min(15.0, max(0.0, score_total - 70.0) * 0.5)
    base_score += 10.0 if amount_ok else 0.0
    base_score += 8.0 if big_start_edge else 0.0
    base_score += 7.0 if "ST_START_WINS_EARLY3_FAILS" in fail_reason else 0.0
    base_score -= 18.0 if open_overheated else 0.0
    base_score -= 18.0 if low_overextended else 0.0
    base_score -= min(20.0, max(0.0, risk) * 0.25)
    base_score = max(0.0, min(100.0, base_score))

    if (open_overheated and low_overextended) or "LIVE_EXCLUDE" in live_label or risk_high:
        return ("ST_START_C_OVEREXTENDED_SKIP", "C", base_score, "진입 제외", "시초/저점대비 과확장 또는 실시간 위험점수 과다", 0, 0, 1)

    if st_ret < args.success_return_pct or post_ext < args.weak_return_pct or "BOTH_WEAK" in fail_reason:
        return ("ST_START_D_WEAK_CONTINUATION_SKIP", "D", base_score, "진입 제외", "ST_START 이후 기대수익 또는 후속 확장 부족", 0, 0, 1)

    if big_start_edge and score_ok and amount_ok and risk_low and not open_overheated and not low_overextended and not peak_exhausted:
        return ("ST_START_A_FAST_LEADER", "A", max(base_score, 85.0), "ST_START 즉시 진입 후보", "EARLY3 대기 시 수익구간 소실 가능성이 큰 장초반 선도형", 0, 1, 0)

    if st_ret >= args.success_return_pct and (open_overheated or low_overextended or peak_exhausted):
        return ("ST_START_B_VALID_BUT_WAIT_PULLBACK", "B", base_score, "즉시 추격 금지, 눌림/재돌파 확인", "ST_START 자체는 유효하나 단기 과열 또는 피크소진 리스크 존재", 0, 0, 0)

    if st_ret >= args.success_return_pct and (strong_post or score_ok) and risk <= args.mid_risk_score:
        return ("ST_START_E_NEEDS_TICK_HOGA_CONFIRM", "E", base_score, "틱강도/호가흡수 확인 후 진입", "가격조건은 통과하나 실시간 수급 확인 필요", 1, 0, 0)

    return ("ST_START_E_NEEDS_TICK_HOGA_CONFIRM", "E", base_score, "틱강도/호가흡수 확인 후 진입", "단독 가격특성만으로는 A/C/D 확정 불가", 1, 0, 0)


def load_source_rows(conn: Any, source_table: str, limit: int) -> List[Dict[str, Any]]:
    lim = "" if limit <= 0 else " LIMIT " + str(int(limit))
    sql = f"""
SELECT
    trade_date, code, name, st_period, st_multiplier, segment_no, st_up_start_time,
    score_total, st_up_max_return_pct, st_start_estimated_return_pct, early3_estimated_return_pct,
    early3_high_return_pct, post_early3_extension_pct, early3_lost_move_pct,
    start_from_day_open_pct, start_from_day_low_pct, start_cum_amount, live_risk_score_v1_2,
    failure_reason_v1_5, action_hint_v1_5, live_filter_label_v1_2, post_diagnostic_label_v1_2
FROM {qident(source_table)}
ORDER BY trade_date, code, st_period, st_multiplier, segment_no
{lim}
"""
    return fetch_all(conn, sql)


def insert_details(conn: Any, source_table: str, rows: List[Dict[str, Any]], args: argparse.Namespace) -> int:
    sql = f"""
INSERT INTO {qident(DETAIL_TABLE)} (
    source_table, trade_date, code, name, st_period, st_multiplier, segment_no, st_up_start_time,
    score_total, st_up_max_return_pct, st_start_estimated_return_pct, early3_estimated_return_pct,
    early3_high_return_pct, post_early3_extension_pct, early3_lost_move_pct,
    start_from_day_open_pct, start_from_day_low_pct, start_cum_amount, live_risk_score_v1_2,
    failure_reason_v1_5, action_hint_v1_5, live_filter_label_v1_2, post_diagnostic_label_v1_2,
    filter_label_v1_6, filter_grade_v1_6, filter_score_v1_6, entry_decision_v1_6, filter_reason_v1_6,
    need_tick_hoga_confirm, auto_entry_candidate, skip_candidate
) VALUES (
    %s,%s,%s,%s,%s,%s,%s,%s,
    %s,%s,%s,%s,
    %s,%s,%s,
    %s,%s,%s,%s,
    %s,%s,%s,%s,
    %s,%s,%s,%s,%s,
    %s,%s,%s
)
"""
    vals: List[Tuple[Any, ...]] = []
    for r in rows:
        label, grade, fscore, decision, reason, need_tick, auto_entry, skip = label_row(r, args)
        vals.append((
            source_table, r.get("trade_date"), r.get("code"), r.get("name"), to_int(r.get("st_period")), to_float(r.get("st_multiplier")),
            to_int(r.get("segment_no")), r.get("st_up_start_time"), to_float(r.get("score_total")), to_float(r.get("st_up_max_return_pct")),
            to_float(r.get("st_start_estimated_return_pct")), to_float(r.get("early3_estimated_return_pct")), to_float(r.get("early3_high_return_pct")),
            to_float(r.get("post_early3_extension_pct")), to_float(r.get("early3_lost_move_pct")), to_float(r.get("start_from_day_open_pct")),
            to_float(r.get("start_from_day_low_pct")), to_float(r.get("start_cum_amount")), to_float(r.get("live_risk_score_v1_2")),
            r.get("failure_reason_v1_5"), r.get("action_hint_v1_5"), r.get("live_filter_label_v1_2"), r.get("post_diagnostic_label_v1_2"),
            label, grade, fscore, decision, reason, need_tick, auto_entry, skip
        ))
    if not vals:
        return 0
    with conn.cursor() as cur:
        cur.executemany(sql, vals)
        return int(cur.rowcount)


def build_summary(conn: Any) -> None:
    execute(conn, f"""
INSERT INTO {qident(SUMMARY_TABLE)} (
    st_period, st_multiplier, filter_label_v1_6, filter_grade_v1_6, row_count,
    avg_filter_score_v1_6, avg_score_total, avg_st_start_estimated_return_pct,
    avg_early3_estimated_return_pct, avg_st_up_max_return_pct, avg_early3_high_return_pct,
    avg_post_early3_extension_pct, avg_start_from_day_open_pct, avg_start_from_day_low_pct,
    avg_start_cum_amount, avg_live_risk_score_v1_2, auto_entry_rate, skip_rate, need_tick_hoga_confirm_rate
)
SELECT
    st_period, st_multiplier, filter_label_v1_6, filter_grade_v1_6, COUNT(*) AS row_count,
    AVG(filter_score_v1_6), AVG(score_total), AVG(st_start_estimated_return_pct),
    AVG(early3_estimated_return_pct), AVG(st_up_max_return_pct), AVG(early3_high_return_pct),
    AVG(post_early3_extension_pct), AVG(start_from_day_open_pct), AVG(start_from_day_low_pct),
    AVG(start_cum_amount), AVG(live_risk_score_v1_2), AVG(auto_entry_candidate), AVG(skip_candidate), AVG(need_tick_hoga_confirm)
FROM {qident(DETAIL_TABLE)}
GROUP BY st_period, st_multiplier, filter_label_v1_6, filter_grade_v1_6
""")


def build_examples(conn: Any, top_n: int) -> None:
    execute(conn, f"TRUNCATE TABLE {qident(EXAMPLE_TABLE)}")
    cols = get_columns(conn, DETAIL_TABLE)
    if not cols:
        raise RuntimeError("detail table columns not found")
    col_csv = ", ".join(qident(c) for c in cols)
    # SELECT d.*, ROW_NUMBER() creates an extra rn column, so INSERT/SELECT must use explicit detail columns only.
    execute(conn, f"""
INSERT INTO {qident(EXAMPLE_TABLE)} ({col_csv})
SELECT {col_csv} FROM (
    SELECT d.*, ROW_NUMBER() OVER (
        PARTITION BY d.filter_label_v1_6
        ORDER BY d.auto_entry_candidate DESC, d.skip_candidate ASC, d.filter_score_v1_6 DESC,
                 d.st_start_estimated_return_pct DESC, d.post_early3_extension_pct DESC
    ) AS rn
    FROM {qident(DETAIL_TABLE)} d
) x
WHERE x.rn <= %s
""", [top_n])


def print_rows(title: str, rows: List[Dict[str, Any]], max_rows: int = 30) -> None:
    print("\n=== " + title + " ===")
    for r in rows[:max_rows]:
        print(dict(r))
    if len(rows) > max_rows:
        print("... " + str(len(rows) - max_rows) + " more rows")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build ST_START entry filter v1.6 from MySQL v1.5 diagnostics")
    p.add_argument("--mysql-conn", default="")
    p.add_argument("--host", default="")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--database", default="")
    p.add_argument("--user", default="")
    p.add_argument("--password", default="")
    p.add_argument("--charset", default="utf8mb4")
    p.add_argument("--source-table", default=SOURCE_TABLE_DEFAULT)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--example-top-n", type=int, default=30)
    p.add_argument("--weak-return-pct", type=float, default=1.0)
    p.add_argument("--success-return-pct", type=float, default=5.0)
    p.add_argument("--post-extension-good-pct", type=float, default=3.0)
    p.add_argument("--open-overheat-pct", type=float, default=9.0)
    p.add_argument("--low-overextend-pct", type=float, default=10.0)
    p.add_argument("--min-start-amount", type=float, default=1000000000.0)
    p.add_argument("--min-score-total", type=float, default=85.0)
    p.add_argument("--low-risk-score", type=float, default=5.0)
    p.add_argument("--mid-risk-score", type=float, default=25.0)
    p.add_argument("--high-risk-score", type=float, default=50.0)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    print("=== BUILD v1.6 ST_START Entry Filter ===")
    cfg = build_mysql_config(args)
    conn = pymysql.connect(**cfg)
    try:
        source_table = args.source_table.strip() or SOURCE_TABLE_DEFAULT
        assert_source_table(conn, source_table)
        create_output_tables(conn)
        rows = load_source_rows(conn, source_table, args.limit)
        inserted = insert_details(conn, source_table, rows, args)
        if inserted <= 0:
            raise RuntimeError("detail table row_count=0 입니다. v1.5 source table을 확인하세요.")
        build_summary(conn)
        build_examples(conn, args.example_top_n)
        conn.commit()

        print("source_table=", source_table)
        print("detail_table=", DETAIL_TABLE)
        print("summary_table=", SUMMARY_TABLE)
        print("example_table=", EXAMPLE_TABLE)
        print("source_rows=", len(rows))
        print("detail_rows=", inserted)

        summary = fetch_all(conn, f"""
SELECT st_period, st_multiplier, filter_label_v1_6, filter_grade_v1_6, row_count,
       avg_filter_score_v1_6, avg_st_start_estimated_return_pct, avg_early3_estimated_return_pct,
       avg_post_early3_extension_pct, avg_start_from_day_open_pct, avg_start_from_day_low_pct,
       avg_start_cum_amount, auto_entry_rate, skip_rate, need_tick_hoga_confirm_rate
FROM {qident(SUMMARY_TABLE)}
ORDER BY filter_grade_v1_6, avg_filter_score_v1_6 DESC, row_count DESC
""")
        print_rows("v1.6 ST_START Entry Filter Summary", summary, 80)

        examples = fetch_all(conn, f"""
SELECT trade_date, code, name, st_period, st_multiplier, segment_no, st_up_start_time,
       filter_label_v1_6, filter_grade_v1_6, filter_score_v1_6, entry_decision_v1_6,
       score_total, st_start_estimated_return_pct, early3_estimated_return_pct,
       early3_high_return_pct, post_early3_extension_pct, start_from_day_open_pct,
       start_from_day_low_pct, start_cum_amount, live_risk_score_v1_2, failure_reason_v1_5
FROM {qident(EXAMPLE_TABLE)}
ORDER BY filter_grade_v1_6, filter_score_v1_6 DESC, st_start_estimated_return_pct DESC
LIMIT 80
""")
        print_rows("v1.6 Entry Filter Examples", examples, 80)
        print("=== DONE scripts/build_supertrend_start_entry_filter_v1_6.py ===")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
