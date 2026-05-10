# -*- coding: utf-8 -*-
"""Build aggregate quality report for Radar-Pullback entries.

This report summarizes whether the Radar-Pullback logic improves entry quality,
and tests overheat caps such as entry_from_day_open_pct <= 8/10/12/15.

Run:
    python -m src.analysis.build_radar_pullback_quality_report --env .env
"""

from __future__ import annotations

import argparse
import html
import math
import os
import statistics
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
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


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


def fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "-"
    try:
        f = float(value)
    except Exception:
        return str(value)
    if math.isnan(f) or math.isinf(f):
        return "-"
    return f"{f:.{digits}f}"


def load_rows(conn: Any) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT radar_threshold_pct, pullback_depth_pct, max_pullback_bars, volume_shrink_ratio,
                   search_date, code, name, actual_rank,
                   entry_from_day_open_pct, entry_from_day_low_pct,
                   max_return_after_entry_pct, close_return_from_entry_pct, max_drawdown_after_entry_pct,
                   radar_close_return_pct, pullback_depth_from_radar_high_pct,
                   pullback_bars, pullback_volume_ratio_to_radar
            FROM radar_pullback_entry_result
            WHERE valid_flag = 1
        """)
        return list(cur.fetchall())


def summarize_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    max_returns = [to_float(r.get("max_return_after_entry_pct")) for r in rows]
    close_returns = [to_float(r.get("close_return_from_entry_pct")) for r in rows]
    drawdowns = [to_float(r.get("max_drawdown_after_entry_pct")) for r in rows]
    entry_open = [to_float(r.get("entry_from_day_open_pct")) for r in rows]
    entry_low = [to_float(r.get("entry_from_day_low_pct")) for r in rows]
    top10 = sum(1 for r in rows if 1 <= to_int(r.get("actual_rank")) <= 10)
    active_days = len({r.get("search_date") for r in rows})
    return {
        "sample_count": len(rows),
        "active_days": active_days,
        "avg_trade_per_day": len(rows) / 82.0,
        "actual_top10_rate": top10 / float(len(rows)) if rows else None,
        "avg_entry_from_open": avg(entry_open),
        "median_entry_from_open": median(entry_open),
        "avg_entry_from_low": avg(entry_low),
        "avg_max_return": avg(max_returns),
        "median_max_return": median(max_returns),
        "avg_close_return": avg(close_returns),
        "avg_drawdown": avg(drawdowns),
        "win3": rate(max_returns, 3.0, True),
        "win5": rate(max_returns, 5.0, True),
        "win10": rate(max_returns, 10.0, True),
        "loss_close3": rate(close_returns, -3.0, False),
        "loss_close5": rate(close_returns, -5.0, False),
        "overheat10_rate": rate(entry_open, 10.0, True),
        "overheat15_rate": rate(entry_open, 15.0, True),
    }


def build_param_groups(rows: List[Dict[str, Any]], min_count: int) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[float, float, int, float], List[Dict[str, Any]]] = {}
    for row in rows:
        key = (
            float(row["radar_threshold_pct"]),
            float(row["pullback_depth_pct"]),
            int(row["max_pullback_bars"]),
            float(row["volume_shrink_ratio"]),
        )
        grouped.setdefault(key, []).append(row)
    result: List[Dict[str, Any]] = []
    for key, vals in grouped.items():
        if len(vals) < min_count:
            continue
        summary = summarize_rows(vals)
        summary["radar_threshold_pct"] = key[0]
        summary["pullback_depth_pct"] = key[1]
        summary["max_pullback_bars"] = key[2]
        summary["volume_shrink_ratio"] = key[3]
        result.append(summary)
    result.sort(key=lambda r: (-(r["avg_max_return"] or -999.0), r["loss_close5"] if r["loss_close5"] is not None else 999.0))
    return result


def build_overheat_caps(rows: List[Dict[str, Any]], min_count: int) -> List[Dict[str, Any]]:
    caps_open = [6.0, 8.0, 10.0, 12.0, 15.0, 999.0]
    caps_low = [10.0, 12.0, 15.0, 18.0, 20.0, 999.0]
    result: List[Dict[str, Any]] = []
    for cap_open in caps_open:
        for cap_low in caps_low:
            vals: List[Dict[str, Any]] = []
            for row in rows:
                entry_open = to_float(row.get("entry_from_day_open_pct"))
                entry_low = to_float(row.get("entry_from_day_low_pct"))
                if entry_open is None or entry_low is None:
                    continue
                if entry_open <= cap_open and entry_low <= cap_low:
                    vals.append(row)
            if len(vals) < min_count:
                continue
            summary = summarize_rows(vals)
            summary["entry_open_cap"] = cap_open
            summary["entry_low_cap"] = cap_low
            result.append(summary)
    result.sort(key=lambda r: (-(r["avg_max_return"] or -999.0), r["loss_close5"] if r["loss_close5"] is not None else 999.0))
    return result


def build_selected_param_overheat(rows: List[Dict[str, Any]], min_count: int) -> List[Dict[str, Any]]:
    selected = [
        (2.5, 5.0, 6, 0.5),
        (2.5, 5.0, 6, 0.7),
        (3.0, 5.0, 6, 0.7),
        (2.0, 2.0, 6, 0.7),
        (2.5, 3.0, 6, 0.7),
    ]
    caps_open = [8.0, 10.0, 12.0, 15.0, 999.0]
    result: List[Dict[str, Any]] = []
    for param in selected:
        pvals = [
            row for row in rows
            if float(row["radar_threshold_pct"]) == param[0]
            and float(row["pullback_depth_pct"]) == param[1]
            and int(row["max_pullback_bars"]) == param[2]
            and float(row["volume_shrink_ratio"]) == param[3]
        ]
        for cap_open in caps_open:
            vals: List[Dict[str, Any]] = []
            for row in pvals:
                entry_open = to_float(row.get("entry_from_day_open_pct"))
                if entry_open is not None and entry_open <= cap_open:
                    vals.append(row)
            if len(vals) < min_count:
                continue
            summary = summarize_rows(vals)
            summary["radar_threshold_pct"] = param[0]
            summary["pullback_depth_pct"] = param[1]
            summary["max_pullback_bars"] = param[2]
            summary["volume_shrink_ratio"] = param[3]
            summary["entry_open_cap"] = cap_open
            result.append(summary)
    result.sort(key=lambda r: (-(r["avg_max_return"] or -999.0), r["loss_close5"] if r["loss_close5"] is not None else 999.0))
    return result


def pct_text(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return fmt(value * 100.0)


def render_table(headers: List[str], rows: List[Dict[str, Any]], columns: List[Tuple[str, str, str]], limit: int) -> str:
    out = ["<table><thead><tr>"]
    for h in headers:
        out.append("<th>" + html.escape(h) + "</th>")
    out.append("</tr></thead><tbody>")
    for row in rows[:limit]:
        out.append("<tr>")
        for _title, key, typ in columns:
            value = row.get(key)
            if typ == "rate":
                text = pct_text(value)
            elif typ == "float":
                text = fmt(value)
            elif typ == "int":
                text = str(value) if value is not None else "-"
            else:
                text = str(value) if value is not None else "-"
            out.append("<td>" + html.escape(text) + "</td>")
        out.append("</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def build_html(rows: List[Dict[str, Any]]) -> str:
    all_summary = summarize_rows(rows)
    param_groups = build_param_groups(rows, 20)
    cap_groups = build_overheat_caps(rows, 30)
    selected_groups = build_selected_param_overheat(rows, 20)

    param_cols = [
        ("Radar", "radar_threshold_pct", "float"),
        ("PB", "pullback_depth_pct", "float"),
        ("Bars", "max_pullback_bars", "int"),
        ("Vol", "volume_shrink_ratio", "float"),
        ("N", "sample_count", "int"),
        ("/Day", "avg_trade_per_day", "float"),
        ("Top10%", "actual_top10_rate", "rate"),
        ("EntryOpen", "avg_entry_from_open", "float"),
        ("EntryLow", "avg_entry_from_low", "float"),
        ("MaxRet", "avg_max_return", "float"),
        ("MedMax", "median_max_return", "float"),
        ("CloseRet", "avg_close_return", "float"),
        ("Win3%", "win3", "rate"),
        ("Win5%", "win5", "rate"),
        ("Loss-5%", "loss_close5", "rate"),
        ("OH10%", "overheat10_rate", "rate"),
    ]
    cap_cols = [
        ("OpenCap", "entry_open_cap", "float"),
        ("LowCap", "entry_low_cap", "float"),
        ("N", "sample_count", "int"),
        ("/Day", "avg_trade_per_day", "float"),
        ("Top10%", "actual_top10_rate", "rate"),
        ("EntryOpen", "avg_entry_from_open", "float"),
        ("EntryLow", "avg_entry_from_low", "float"),
        ("MaxRet", "avg_max_return", "float"),
        ("CloseRet", "avg_close_return", "float"),
        ("Win3%", "win3", "rate"),
        ("Win5%", "win5", "rate"),
        ("Loss-5%", "loss_close5", "rate"),
    ]
    selected_cols = [
        ("Radar", "radar_threshold_pct", "float"),
        ("PB", "pullback_depth_pct", "float"),
        ("Bars", "max_pullback_bars", "int"),
        ("Vol", "volume_shrink_ratio", "float"),
        ("OpenCap", "entry_open_cap", "float"),
        ("N", "sample_count", "int"),
        ("/Day", "avg_trade_per_day", "float"),
        ("Top10%", "actual_top10_rate", "rate"),
        ("EntryOpen", "avg_entry_from_open", "float"),
        ("MaxRet", "avg_max_return", "float"),
        ("CloseRet", "avg_close_return", "float"),
        ("Win3%", "win3", "rate"),
        ("Win5%", "win5", "rate"),
        ("Loss-5%", "loss_close5", "rate"),
    ]

    return f"""<!doctype html>
<html lang='ko'>
<head>
<meta charset='utf-8' />
<title>Radar Pullback Quality Report</title>
<style>
body {{ font-family: Segoe UI, Malgun Gothic, Arial, sans-serif; background:#111827; color:#e5e7eb; margin:0; padding:18px; }}
h1 {{ margin-top:0; }}
.cardwrap {{ display:grid; grid-template-columns: repeat(6, minmax(140px, 1fr)); gap:10px; margin:14px 0; }}
.card {{ background:#0f172a; border:1px solid #334155; border-radius:10px; padding:10px; }}
.k {{ color:#94a3b8; font-size:12px; }} .v {{ font-size:20px; font-weight:700; margin-top:4px; }}
section {{ margin-top:26px; }}
table {{ border-collapse:collapse; width:100%; font-size:12px; background:#0f172a; }}
th, td {{ border:1px solid #334155; padding:6px 8px; text-align:right; }}
th {{ background:#1e293b; color:#cbd5e1; position:sticky; top:0; }}
.note {{ color:#cbd5e1; line-height:1.55; }}
</style>
</head>
<body>
<h1>Radar Pullback Quality Report</h1>
<p class='note'>개별 차트가 아니라 전체 조건의 개선 여부를 보는 집계판입니다. Top N 연결 없이 Radar-Pullback 자체만 평가합니다.</p>
<div class='cardwrap'>
<div class='card'><div class='k'>Total Rows</div><div class='v'>{all_summary['sample_count']}</div></div>
<div class='card'><div class='k'>Avg Max Return</div><div class='v'>{fmt(all_summary['avg_max_return'])}%</div></div>
<div class='card'><div class='k'>Avg Close Return</div><div class='v'>{fmt(all_summary['avg_close_return'])}%</div></div>
<div class='card'><div class='k'>Win +3%</div><div class='v'>{pct_text(all_summary['win3'])}%</div></div>
<div class='card'><div class='k'>Loss Close -5%</div><div class='v'>{pct_text(all_summary['loss_close5'])}%</div></div>
<div class='card'><div class='k'>Overheat +10%</div><div class='v'>{pct_text(all_summary['overheat10_rate'])}%</div></div>
</div>
<section>
<h2>1. Parameter Groups by Avg Max Return</h2>
{render_table([c[0] for c in param_cols], param_groups, param_cols, 80)}
</section>
<section>
<h2>2. Overheat Cap Sweep</h2>
<p class='note'>entry_from_day_open_pct와 entry_from_day_low_pct 상한을 걸었을 때 성과가 개선되는지 확인합니다.</p>
{render_table([c[0] for c in cap_cols], cap_groups, cap_cols, 80)}
</section>
<section>
<h2>3. Selected Candidate Families + Entry Open Cap</h2>
<p class='note'>초기 유망 조합에 entry_from_day_open_pct 상한을 적용했을 때 성과가 좋아지는지 확인합니다.</p>
{render_table([c[0] for c in selected_cols], selected_groups, selected_cols, 100)}
</section>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--output", default="reports/radar_pullback_quality_report.html")
    args = parser.parse_args()
    load_env(args.env)
    conn = open_conn()
    try:
        rows = load_rows(conn)
        html_text = build_html(rows)
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html_text, encoding="utf-8")
        print("=== DONE build_radar_pullback_quality_report ===")
        print("rows=" + str(len(rows)))
        print("output=" + str(out.resolve()))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
