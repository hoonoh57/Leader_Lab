#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Leader_Lab v1.5 MySQL-safe builder
ST_START vs EARLY3 failure diagnostics

- MySQL only
- No sqlite / no db-path
- Supports v1.3 entry_type paired table
- Supports v1.4 daily examples table such as st_continuation_entry_daily_examples_v1_4
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
    print("[FATAL] pymysql is required: py -3 -m pip install pymysql", file=sys.stderr)
    raise

DETAIL_TABLE = "supertrend_start_vs_early3_failure_detail_v1_5"
SUMMARY_TABLE = "supertrend_start_vs_early3_failure_summary_v1_5"
EXAMPLE_TABLE = "supertrend_start_vs_early3_failure_examples_v1_5"

SOURCE_HINTS = [
    "st_continuation_entry_daily_examples_v1_4",
    "supertrend_continuation_entry_daily_examples_v1_4",
    "st_continuation_entry_discovery_v1_4",
    "supertrend_continuation_entry_discovery_v1_4",
    "st_continuation_entry_discovery_v1_3",
    "supertrend_continuation_entry_discovery_v1_3",
    "supertrend_continuation_entry_examples_v1_3",
    "supertrend_segment_ranking_discovery_v1_2",
]


def parse_conn_string(conn_str: str) -> Dict[str, Any]:
    d: Dict[str, Any] = {}
    for part in [x.strip() for x in conn_str.split(";") if x.strip()]:
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        kk = k.strip().lower().replace(" ", "").replace("_", "")
        vv = v.strip()
        if kk in ("server", "host", "datasource"):
            d["host"] = vv
        elif kk == "port":
            d["port"] = int(vv)
        elif kk in ("database", "initialcatalog", "dbname", "db"):
            d["database"] = vv
        elif kk in ("uid", "userid", "user", "username"):
            d["user"] = vv
        elif kk in ("pwd", "password", "passwd"):
            d["password"] = vv
        elif kk in ("charset", "characterset"):
            d["charset"] = vv
    return d


def mysql_config(args: argparse.Namespace) -> Dict[str, Any]:
    env_conn = args.mysql_conn or os.environ.get("MYSQL_CONN") or os.environ.get("DB_CONN") or os.environ.get("MYSQL_CONNECTION_STRING") or ""
    base = parse_conn_string(env_conn)
    database = args.database or base.get("database") or os.environ.get("DB_NAME") or os.environ.get("MYSQL_DATABASE")
    if not database:
        raise RuntimeError("DB_NAME/MYSQL_DATABASE 또는 --database가 필요합니다.")
    return {
        "host": args.host or base.get("host") or os.environ.get("DB_HOST") or os.environ.get("MYSQL_HOST") or "127.0.0.1",
        "port": int(args.port or base.get("port") or os.environ.get("DB_PORT") or os.environ.get("MYSQL_PORT") or 3306),
        "database": database,
        "user": args.user or base.get("user") or os.environ.get("DB_USER") or os.environ.get("MYSQL_USER") or "root",
        "password": args.password or base.get("password") or os.environ.get("DB_PASS") or os.environ.get("MYSQL_PASSWORD") or "",
        "charset": args.charset or base.get("charset") or "utf8mb4",
        "cursorclass": DictCursor,
        "autocommit": False,
    }


def q(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError("unsafe identifier: " + name)
    return "`" + name + "`"


def rows(conn: Any, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def exec_sql(conn: Any, sql: str, params: Sequence[Any] = ()) -> int:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return int(cur.rowcount)


def f(v: Any, default: float = 0.0) -> float:
    if v is None:
        return default
    try:
        return float(v)
    except Exception:
        return default


def i(v: Any, default: int = 0) -> int:
    try:
        return int(float(v))
    except Exception:
        return default


def s(v: Any, default: str = "") -> str:
    if v is None:
        return default
    return str(v)


def table_list(conn: Any) -> List[str]:
    rs = rows(conn, "SELECT table_name AS table_name FROM information_schema.tables WHERE table_schema=DATABASE() ORDER BY table_name")
    return [str(r.get("table_name") or r.get("TABLE_NAME")) for r in rs]


def col_list(conn: Any, table: str) -> List[str]:
    rs = rows(conn, "SELECT column_name AS column_name FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=%s ORDER BY ordinal_position", [table])
    return [str(r.get("column_name") or r.get("COLUMN_NAME")) for r in rs]


def has_cols(conn: Any, table: str, required: Sequence[str]) -> bool:
    cs = set(x.lower() for x in col_list(conn, table))
    return all(x.lower() in cs for x in required)


def pick_source(conn: Any, source_table: str) -> str:
    if source_table.strip():
        return source_table.strip()
    tables = table_list(conn)
    by_l = {t.lower(): t for t in tables}
    required_min = ["trade_date", "code", "st_period", "st_multiplier", "st_up_max_return_pct", "early3_high_return_pct", "post_early3_extension_pct"]
    for h in SOURCE_HINTS:
        t = by_l.get(h.lower())
        if t and has_cols(conn, t, required_min):
            return t
    scored: List[Tuple[int, str]] = []
    for t in tables:
        tl = t.lower()
        if not has_cols(conn, t, required_min):
            continue
        score = 0
        if "continuation" in tl:
            score += 30
        if "daily_examples" in tl:
            score += 30
        if "v1_4" in tl:
            score += 25
        if "v1_3" in tl:
            score += 20
        if "supertrend" in tl or tl.startswith("st_"):
            score += 10
        if score > 0:
            scored.append((score, t))
    if not scored:
        raise RuntimeError("source table을 찾지 못했습니다. --source-table을 지정하세요. tables=" + ", ".join(tables[:60]))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored[0][1]


def sel_expr(cols: List[str], col: str, alias: str, default: str = "NULL") -> str:
    cs = set(c.lower() for c in cols)
    if col.lower() in cs:
        return f"{q(col)} AS {q(alias)}"
    return f"{default} AS {q(alias)}"


def source_count_by_entry(conn: Any, table: str) -> Dict[str, int]:
    cols = col_list(conn, table)
    if "entry_type" not in set(c.lower() for c in cols):
        return {}
    rs = rows(conn, f"SELECT entry_type, COUNT(*) AS cnt FROM {q(table)} GROUP BY entry_type ORDER BY entry_type")
    return {s(r.get("entry_type")): i(r.get("cnt")) for r in rs}


def load_join_rows(conn: Any, table: str, limit: int) -> List[Dict[str, Any]]:
    cols = col_list(conn, table)
    cs = set(c.lower() for c in cols)
    if "entry_type" not in cs:
        return []
    lim = "" if limit <= 0 else " LIMIT " + str(int(limit))
    sql = f"""
SELECT
 s.trade_date, s.code,
 {"s.name" if "name" in cs else "NULL"} AS name,
 s.st_period, s.st_multiplier,
 {"s.segment_no" if "segment_no" in cs else "1"} AS segment_no,
 {"s.st_up_start_time" if "st_up_start_time" in cs else "NULL"} AS st_up_start_time,
 {"s.score_total" if "score_total" in cs else "NULL"} AS score_total,
 s.st_up_max_return_pct,
 s.st_up_max_return_pct AS st_start_estimated_return_pct,
 {"e.estimated_max_return_after_entry_pct" if "estimated_max_return_after_entry_pct" in cs else "e.post_early3_extension_pct"} AS early3_estimated_return_pct,
 e.early3_high_return_pct,
 e.post_early3_extension_pct,
 {"e.estimated_lost_move_before_entry_pct" if "estimated_lost_move_before_entry_pct" in cs else "e.early3_high_return_pct"} AS early3_lost_move_pct,
 {"e.live_filter_label_v1_2" if "live_filter_label_v1_2" in cs else "NULL"} AS live_filter_label_v1_2,
 {"e.post_diagnostic_label_v1_2" if "post_diagnostic_label_v1_2" in cs else "NULL"} AS post_diagnostic_label_v1_2,
 {"e.start_from_day_open_pct" if "start_from_day_open_pct" in cs else "NULL"} AS start_from_day_open_pct,
 {"e.start_from_day_low_pct" if "start_from_day_low_pct" in cs else "NULL"} AS start_from_day_low_pct,
 {"e.start_cum_amount" if "start_cum_amount" in cs else "NULL"} AS start_cum_amount,
 {"e.live_risk_score_v1_2" if "live_risk_score_v1_2" in cs else "NULL"} AS live_risk_score_v1_2,
 {"e.continuation_score_v1_3" if "continuation_score_v1_3" in cs else "NULL"} AS continuation_score_v1_3,
 {"e.continuation_label_v1_3" if "continuation_label_v1_3" in cs else "NULL"} AS continuation_label_v1_3
FROM {q(table)} s
JOIN {q(table)} e
  ON s.trade_date=e.trade_date AND s.code=e.code AND s.st_period=e.st_period AND s.st_multiplier=e.st_multiplier
 AND COALESCE(s.segment_no,1)=COALESCE(e.segment_no,1)
WHERE s.entry_type='ST_START_ENTRY'
  AND e.entry_type IN ('EARLY3_COMPOSITE_ENTRY','EARLY3_HOLD_ENTRY','EARLY3_AMOUNT_EXPANSION_ENTRY','EARLY3_BREAK_ENTRY')
ORDER BY s.trade_date, s.code, s.st_period, s.st_multiplier, COALESCE(s.segment_no,1)
{lim}
"""
    return rows(conn, sql)


def load_direct_rows(conn: Any, table: str, limit: int) -> List[Dict[str, Any]]:
    cols = col_list(conn, table)
    cs = set(c.lower() for c in cols)
    lim = "" if limit <= 0 else " LIMIT " + str(int(limit))
    exprs = [
        sel_expr(cols, "trade_date", "trade_date"),
        sel_expr(cols, "code", "code"),
        sel_expr(cols, "name", "name"),
        sel_expr(cols, "st_period", "st_period"),
        sel_expr(cols, "st_multiplier", "st_multiplier"),
        sel_expr(cols, "segment_no", "segment_no", "1"),
        sel_expr(cols, "st_up_start_time", "st_up_start_time"),
        sel_expr(cols, "score_total", "score_total"),
        sel_expr(cols, "st_up_max_return_pct", "st_up_max_return_pct"),
        sel_expr(cols, "st_up_max_return_pct", "st_start_estimated_return_pct"),
    ]
    if "estimated_max_return_after_entry_pct" in cs:
        exprs.append(sel_expr(cols, "estimated_max_return_after_entry_pct", "early3_estimated_return_pct"))
    else:
        exprs.append(sel_expr(cols, "post_early3_extension_pct", "early3_estimated_return_pct", "0"))
    exprs.extend([
        sel_expr(cols, "early3_high_return_pct", "early3_high_return_pct", "0"),
        sel_expr(cols, "post_early3_extension_pct", "post_early3_extension_pct", "0"),
    ])
    if "estimated_lost_move_before_entry_pct" in cs:
        exprs.append(sel_expr(cols, "estimated_lost_move_before_entry_pct", "early3_lost_move_pct", "0"))
    else:
        exprs.append(sel_expr(cols, "early3_high_return_pct", "early3_lost_move_pct", "0"))
    exprs.extend([
        sel_expr(cols, "live_filter_label_v1_2", "live_filter_label_v1_2"),
        sel_expr(cols, "post_diagnostic_label_v1_2", "post_diagnostic_label_v1_2"),
        sel_expr(cols, "start_from_day_open_pct", "start_from_day_open_pct"),
        sel_expr(cols, "start_from_day_low_pct", "start_from_day_low_pct"),
        sel_expr(cols, "start_cum_amount", "start_cum_amount"),
        sel_expr(cols, "live_risk_score_v1_2", "live_risk_score_v1_2"),
        sel_expr(cols, "continuation_score_v1_3", "continuation_score_v1_3"),
        sel_expr(cols, "continuation_label_v1_3", "continuation_label_v1_3"),
    ])
    where = ""
    if "entry_type" in cs:
        where = "WHERE entry_type IN ('EARLY3_COMPOSITE_ENTRY','EARLY3_HOLD_ENTRY','EARLY3_AMOUNT_EXPANSION_ENTRY','EARLY3_BREAK_ENTRY')"
    sql = f"SELECT {', '.join(exprs)} FROM {q(table)} {where} ORDER BY trade_date, code, st_period, st_multiplier, segment_no {lim}"
    return rows(conn, sql)


def classify(r: Dict[str, Any], weak: float, success: float) -> Tuple[str, str, Dict[str, int]]:
    st_ret = f(r.get("st_start_estimated_return_pct"))
    e_ret = f(r.get("early3_estimated_return_pct"))
    early_high = f(r.get("early3_high_return_pct"))
    post_ext = f(r.get("post_early3_extension_pct"))
    open_pct = f(r.get("start_from_day_open_pct"))
    low_pct = f(r.get("start_from_day_low_pct"))
    live = s(r.get("live_filter_label_v1_2"))
    post = s(r.get("post_diagnostic_label_v1_2"))
    flags = {
        "st_start_success_flag": 1 if st_ret >= success else 0,
        "early3_success_flag": 1 if e_ret >= success else 0,
        "early3_fail_flag": 1 if e_ret < weak else 0,
        "start_wins_early3_fails_flag": 1 if st_ret >= success and e_ret < weak else 0,
        "early3_missed_big_move_flag": 1 if early_high >= 5.0 and e_ret < weak else 0,
        "post_peak_exhausted_flag": 1 if post_ext <= weak or "EXHAUST" in post.upper() else 0,
        "open_overheated_flag": 1 if open_pct >= 7.0 or "OPEN_OVERHEATED" in live else 0,
        "low_overextended_flag": 1 if low_pct >= 9.0 or "LOW_OVEREXTENDED" in live else 0,
    }
    if flags["start_wins_early3_fails_flag"]:
        return "ST_START_WINS_EARLY3_FAILS", "ST_START 우선. EARLY3 대기는 수익구간 소실", flags
    if flags["early3_missed_big_move_flag"] and flags["post_peak_exhausted_flag"]:
        return "EARLY3_ALREADY_EXHAUSTED", "EARLY3 진입 금지. 초기 상승 소진 후 확인진입", flags
    if flags["open_overheated_flag"] and flags["low_overextended_flag"]:
        return "OPEN_AND_LOW_OVEREXTENDED", "시초/저점대비 과확장. 눌림 재확인", flags
    if st_ret >= success and e_ret >= success:
        return "BOTH_START_AND_EARLY3_OK", "양쪽 가능. 틱강도/호가흡수로 선택", flags
    if e_ret >= success and st_ret < success:
        return "EARLY3_BETTER_THAN_START", "확인진입형. ST_START 성급진입 제한", flags
    if st_ret < weak and e_ret < weak:
        return "BOTH_WEAK", "ST 구간 자체 약함. 제외", flags
    if flags["post_peak_exhausted_flag"]:
        return "POST_EARLY3_WEAK_EXTENSION", "EARLY3 후 확장 부족. 추격 제한", flags
    return "NEUTRAL", "추가 필터 필요", flags


def create_tables(conn: Any) -> None:
    for t in [EXAMPLE_TABLE, SUMMARY_TABLE, DETAIL_TABLE]:
        exec_sql(conn, f"DROP TABLE IF EXISTS {q(t)}")
    exec_sql(conn, f"""
CREATE TABLE {q(DETAIL_TABLE)} (
 id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 source_table VARCHAR(128) NOT NULL,
 source_mode VARCHAR(32) NOT NULL,
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
 st_start_success_flag TINYINT NOT NULL,
 early3_success_flag TINYINT NOT NULL,
 early3_fail_flag TINYINT NOT NULL,
 start_wins_early3_fails_flag TINYINT NOT NULL,
 early3_missed_big_move_flag TINYINT NOT NULL,
 post_peak_exhausted_flag TINYINT NOT NULL,
 open_overheated_flag TINYINT NOT NULL,
 low_overextended_flag TINYINT NOT NULL,
 failure_reason_v1_5 VARCHAR(128) NOT NULL,
 action_hint_v1_5 VARCHAR(255) NOT NULL,
 live_filter_label_v1_2 VARCHAR(255) NULL,
 post_diagnostic_label_v1_2 VARCHAR(255) NULL,
 start_from_day_open_pct DOUBLE NULL,
 start_from_day_low_pct DOUBLE NULL,
 start_cum_amount DOUBLE NULL,
 live_risk_score_v1_2 DOUBLE NULL,
 continuation_score_v1_3 DOUBLE NULL,
 continuation_label_v1_3 VARCHAR(128) NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 KEY ix_detail_key (trade_date, code, st_period, st_multiplier, segment_no),
 KEY ix_detail_reason (failure_reason_v1_5),
 KEY ix_detail_score (score_total),
 KEY ix_detail_ret (st_start_estimated_return_pct, early3_estimated_return_pct)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
""")
    exec_sql(conn, f"""
CREATE TABLE {q(SUMMARY_TABLE)} (
 id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 source_table VARCHAR(128) NOT NULL,
 source_mode VARCHAR(32) NOT NULL,
 st_period INT NOT NULL,
 st_multiplier DOUBLE NOT NULL,
 failure_reason_v1_5 VARCHAR(128) NOT NULL,
 action_hint_v1_5 VARCHAR(255) NOT NULL,
 row_count INT NOT NULL,
 avg_score_total DOUBLE NULL,
 avg_st_start_return_pct DOUBLE NULL,
 avg_early3_return_pct DOUBLE NULL,
 avg_st_up_max_return_pct DOUBLE NULL,
 avg_early3_high_return_pct DOUBLE NULL,
 avg_post_early3_extension_pct DOUBLE NULL,
 st_start_success_rate DOUBLE NULL,
 early3_success_rate DOUBLE NULL,
 early3_fail_rate DOUBLE NULL,
 start_wins_early3_fails_rate DOUBLE NULL,
 early3_missed_big_move_rate DOUBLE NULL,
 post_peak_exhausted_rate DOUBLE NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 KEY ix_summary_rank (st_period, st_multiplier, row_count)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
""")
    exec_sql(conn, f"CREATE TABLE {q(EXAMPLE_TABLE)} LIKE {q(DETAIL_TABLE)}")


def insert_details(conn: Any, source_table: str, source_mode: str, data: List[Dict[str, Any]], weak: float, success: float) -> int:
    sql = f"""
INSERT INTO {q(DETAIL_TABLE)} (
 source_table, source_mode, trade_date, code, name, st_period, st_multiplier, segment_no, st_up_start_time,
 score_total, st_up_max_return_pct, st_start_estimated_return_pct, early3_estimated_return_pct,
 early3_high_return_pct, post_early3_extension_pct, early3_lost_move_pct,
 st_start_success_flag, early3_success_flag, early3_fail_flag, start_wins_early3_fails_flag,
 early3_missed_big_move_flag, post_peak_exhausted_flag, open_overheated_flag, low_overextended_flag,
 failure_reason_v1_5, action_hint_v1_5, live_filter_label_v1_2, post_diagnostic_label_v1_2,
 start_from_day_open_pct, start_from_day_low_pct, start_cum_amount, live_risk_score_v1_2,
 continuation_score_v1_3, continuation_label_v1_3
) VALUES ({','.join(['%s'] * 34)})
"""
    vals: List[Tuple[Any, ...]] = []
    for r in data:
        reason, action, fl = classify(r, weak, success)
        vals.append((
            source_table, source_mode, r.get("trade_date"), s(r.get("code")), r.get("name"), i(r.get("st_period")), f(r.get("st_multiplier")), i(r.get("segment_no"), 1), r.get("st_up_start_time"),
            f(r.get("score_total")), f(r.get("st_up_max_return_pct")), f(r.get("st_start_estimated_return_pct")), f(r.get("early3_estimated_return_pct")),
            f(r.get("early3_high_return_pct")), f(r.get("post_early3_extension_pct")), f(r.get("early3_lost_move_pct")),
            fl["st_start_success_flag"], fl["early3_success_flag"], fl["early3_fail_flag"], fl["start_wins_early3_fails_flag"],
            fl["early3_missed_big_move_flag"], fl["post_peak_exhausted_flag"], fl["open_overheated_flag"], fl["low_overextended_flag"],
            reason, action, r.get("live_filter_label_v1_2"), r.get("post_diagnostic_label_v1_2"),
            f(r.get("start_from_day_open_pct")), f(r.get("start_from_day_low_pct")), f(r.get("start_cum_amount")), f(r.get("live_risk_score_v1_2")),
            None if r.get("continuation_score_v1_3") is None else f(r.get("continuation_score_v1_3")), r.get("continuation_label_v1_3"),
        ))
    if not vals:
        return 0
    with conn.cursor() as cur:
        cur.executemany(sql, vals)
        return int(cur.rowcount)


def build_summary(conn: Any) -> None:
    exec_sql(conn, f"""
INSERT INTO {q(SUMMARY_TABLE)} (
 source_table, source_mode, st_period, st_multiplier, failure_reason_v1_5, action_hint_v1_5, row_count,
 avg_score_total, avg_st_start_return_pct, avg_early3_return_pct, avg_st_up_max_return_pct,
 avg_early3_high_return_pct, avg_post_early3_extension_pct,
 st_start_success_rate, early3_success_rate, early3_fail_rate, start_wins_early3_fails_rate,
 early3_missed_big_move_rate, post_peak_exhausted_rate
)
SELECT source_table, source_mode, st_period, st_multiplier, failure_reason_v1_5, action_hint_v1_5, COUNT(*),
 AVG(score_total), AVG(st_start_estimated_return_pct), AVG(early3_estimated_return_pct), AVG(st_up_max_return_pct),
 AVG(early3_high_return_pct), AVG(post_early3_extension_pct),
 AVG(st_start_success_flag), AVG(early3_success_flag), AVG(early3_fail_flag), AVG(start_wins_early3_fails_flag),
 AVG(early3_missed_big_move_flag), AVG(post_peak_exhausted_flag)
FROM {q(DETAIL_TABLE)}
GROUP BY source_table, source_mode, st_period, st_multiplier, failure_reason_v1_5, action_hint_v1_5
ORDER BY row_count DESC
""")
    exec_sql(conn, f"""
INSERT INTO {q(EXAMPLE_TABLE)}
SELECT * FROM {q(DETAIL_TABLE)}
WHERE start_wins_early3_fails_flag=1 OR early3_missed_big_move_flag=1 OR post_peak_exhausted_flag=1
ORDER BY score_total DESC, st_start_estimated_return_pct DESC, early3_high_return_pct DESC
LIMIT 200
""")


def print_sample(conn: Any) -> None:
    print("\n=== v1.5 Summary ===")
    for r in rows(conn, f"SELECT source_mode, st_period, st_multiplier, failure_reason_v1_5, row_count, avg_st_start_return_pct, avg_early3_return_pct, early3_fail_rate, start_wins_early3_fails_rate, early3_missed_big_move_rate FROM {q(SUMMARY_TABLE)} ORDER BY row_count DESC, start_wins_early3_fails_rate DESC LIMIT 40"):
        print(dict(r))
    print("\n=== v1.5 Examples ===")
    for r in rows(conn, f"SELECT trade_date, code, name, st_period, st_multiplier, score_total, st_start_estimated_return_pct, early3_estimated_return_pct, early3_high_return_pct, post_early3_extension_pct, failure_reason_v1_5, action_hint_v1_5 FROM {q(EXAMPLE_TABLE)} LIMIT 60"):
        print(dict(r))


def args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--mysql-conn", default="")
    p.add_argument("--host", default="")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--database", default="")
    p.add_argument("--user", default="")
    p.add_argument("--password", default="")
    p.add_argument("--charset", default="utf8mb4")
    p.add_argument("--source-table", default="")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--early-top-n", type=int, default=30)
    p.add_argument("--weak-return-pct", type=float, default=1.0)
    p.add_argument("--success-return-pct", type=float, default=5.0)
    return p.parse_args()


def main() -> None:
    a = args()
    cfg = mysql_config(a)
    print("=== BUILD v1.5 ST_START vs EARLY3 Failure Diagnostics ===")
    conn = pymysql.connect(**cfg)
    try:
        source = pick_source(conn, a.source_table)
        print("source_table=", source)
        print("detail_table=", DETAIL_TABLE)
        print("summary_table=", SUMMARY_TABLE)
        print("example_table=", EXAMPLE_TABLE)
        print("weak_return_pct=", a.weak_return_pct)
        print("success_return_pct=", a.success_return_pct)
        print("early_top_n=", a.early_top_n)
        print("entry_type_counts=", source_count_by_entry(conn, source))

        create_tables(conn)
        data = load_join_rows(conn, source, a.limit)
        source_mode = "paired_entry_type"
        if not data:
            data = load_direct_rows(conn, source, a.limit)
            source_mode = "direct_examples"
        print("loaded_rows=", len(data), "source_mode=", source_mode)
        if not data:
            raise RuntimeError("source rows=0 입니다. source table과 entry_type/컬럼 구성을 확인하세요.")

        inserted = insert_details(conn, source, source_mode, data, a.weak_return_pct, a.success_return_pct)
        build_summary(conn)
        conn.commit()
        print("detail_inserted=", inserted)
        print_sample(conn)
        print("\n=== DONE scripts/build_supertrend_start_vs_early3_failure_v1_5.ps1 ===")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
