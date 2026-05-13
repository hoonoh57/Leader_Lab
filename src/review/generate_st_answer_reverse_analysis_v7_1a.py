# -*- coding: utf-8 -*-
"""Compatibility wrapper for ST Answer Reverse Analysis v7-1a.

This wrapper patches three issues without changing the legacy generator filename:

1. MySQL information_schema column rows may expose COLUMN_NAME instead of
   column_name.
2. v7-1a must not call a submission a HIT just because the same date/code has a
   different high-return ST segment. HIT requires the submitted ST parameter /
   segment_no to match, and selected_entry_time must be inside that answer
   segment.
3. Being inside the ST green segment is not enough. If the signal is detected
   long after the ST rise started, it is a late confirmation, not an early
   answer. HIT requires early detection near the ST start.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.review import generate_st_answer_reverse_analysis_v7_1 as base


MAX_EARLY_ENTRY_MINUTES = 15.0


def robust_table_columns(conn: Any, table_name: str) -> List[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name AS column_name
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = %s
            ORDER BY ordinal_position
            """,
            (table_name,),
        )
        rows = cur.fetchall()

    columns: List[str] = []
    for row in rows:
        value = None
        if isinstance(row, dict):
            value = row.get("column_name")
            if value is None:
                value = row.get("COLUMN_NAME")
            if value is None and len(row) > 0:
                value = list(row.values())[0]
        else:
            try:
                value = row[0]
            except Exception:
                value = None
        if value is not None:
            columns.append(str(value))
    return columns


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).replace("T", " ")
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _same_st_param(sub: Dict[str, Any], seg: Dict[str, Any]) -> bool:
    sp = _to_int(sub.get("st_period"))
    gp = _to_int(seg.get("st_period"))
    sm = _to_float(sub.get("st_multiplier"))
    gm = _to_float(seg.get("st_multiplier"))
    if sp is None or gp is None or sm is None or gm is None:
        return False
    return sp == gp and abs(sm - gm) < 0.000001


def _same_segment_no(sub: Dict[str, Any], seg: Dict[str, Any]) -> bool:
    ss = _to_int(sub.get("segment_no"))
    gs = _to_int(seg.get("segment_no"))
    if ss is None or gs is None:
        return False
    return ss == gs


def _decision_time(sub: Dict[str, Any]) -> Optional[datetime]:
    decision = sub.get("decision_dt")
    if isinstance(decision, datetime):
        return decision
    return _dt(sub.get("decision_time"))


def _inside_segment(sub: Dict[str, Any], seg: Dict[str, Any]) -> bool:
    decision = _decision_time(sub)
    start = _dt(seg.get("st_up_start_time"))
    end = _dt(seg.get("st_up_end_time"))
    if decision is None or start is None or end is None:
        return False
    return start <= decision <= end


def _minutes_from_start(sub: Dict[str, Any], seg: Optional[Dict[str, Any]]) -> Optional[float]:
    if seg is None:
        return None
    decision = _decision_time(sub)
    start = _dt(seg.get("st_up_start_time"))
    if decision is None or start is None:
        return None
    return (decision - start).total_seconds() / 60.0


def _is_early_entry(sub: Dict[str, Any], seg: Dict[str, Any]) -> bool:
    gap = _minutes_from_start(sub, seg)
    if gap is None:
        return False
    return 0.0 <= gap <= MAX_EARLY_ENTRY_MINUTES


def strict_answer_segment(sub: Dict[str, Any], segments_by_key: Dict[Tuple[str, str], List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    key = (str(sub.get("trade_date")), str(sub.get("code")))
    candidates = segments_by_key.get(key, [])
    if not candidates:
        return None

    exact: List[Dict[str, Any]] = []
    for seg in candidates:
        if _same_st_param(sub, seg) and _same_segment_no(sub, seg):
            exact.append(seg)
    if exact:
        exact.sort(key=lambda s: base.safe_float(s.get("st_up_max_return_pct")) or -999999.0, reverse=True)
        return exact[0]

    temporal: List[Dict[str, Any]] = []
    for seg in candidates:
        if _same_st_param(sub, seg) and _inside_segment(sub, seg):
            temporal.append(seg)
    if temporal:
        temporal.sort(key=lambda s: base.safe_float(s.get("st_up_max_return_pct")) or -999999.0, reverse=True)
        return temporal[0]

    return None


def eval_group_for_strict(quality: str, sub: Optional[Dict[str, Any]] = None, seg: Optional[Dict[str, Any]] = None) -> str:
    if seg is None:
        return "NO_TEMPORAL_OVERLAP"
    if sub is not None and not _inside_segment(sub, seg):
        return "TIME_MISMATCH"
    if sub is not None and not _is_early_entry(sub, seg):
        return "LATE_OVERLAP"
    if quality == "GREAT":
        return "HIT_GREAT"
    if quality == "GOOD":
        return "HIT_GOOD"
    if quality in ("BAD", "NEUTRAL"):
        return "FALSE_BUY"
    return "NO_TEMPORAL_OVERLAP"


def why_note_for_strict(group: str, sub: Dict[str, Any], seg: Optional[Dict[str, Any]]) -> str:
    gap = _minutes_from_start(sub, seg)
    gap_text = ""
    if gap is not None:
        gap_text = " entry-start %.1f분" % gap
    if group == "HIT_GREAT":
        return "초기 검출: 동일 ST 파라미터/segment_no + 진입시각이 ST 시작 후 %.0f분 이내:" % MAX_EARLY_ENTRY_MINUTES + gap_text
    if group == "HIT_GOOD":
        return "초기 검출이나 GREAT 미달. GREAT와의 구조 차이 확인:" + gap_text
    if group == "FALSE_BUY":
        return "초기 검출이나 GOOD 미달. 오탐 원인 확인:" + gap_text
    if group == "LATE_OVERLAP":
        return "ST 구간 내부지만 너무 늦은 검출. 이미 오른 뒤의 강세 확인은 정답 아님:" + gap_text
    if group == "TIME_MISMATCH":
        return "동일 ST segment_no는 찾았지만 진입시각이 ST 구간 밖임. overlap 아님:" + gap_text
    return "동일 날짜/종목의 고수익 ST 구간만으로는 HIT 판정 금지. 시간/segment overlap 없음"


def build_submission_evaluation_strict(submissions: Sequence[Dict[str, Any]], segments: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    segments_by_key: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for seg in segments:
        key = (base.stringify_date(seg.get("trade_date")), str(seg.get("code")))
        segments_by_key.setdefault(key, []).append(seg)

    eval_rows: List[Dict[str, Any]] = []
    display_segments: List[Dict[str, Any]] = []
    seen_segment_ids = set()

    for sub in submissions:
        seg = strict_answer_segment(sub, segments_by_key)
        quality = base.answer_quality(seg)
        group = eval_group_for_strict(quality, sub, seg)
        seg_id = seg.get("id") if seg else None
        if seg is not None and seg_id not in seen_segment_ids:
            display_segments.append(seg)
            seen_segment_ids.add(seg_id)

        gap = _minutes_from_start(sub, seg)
        row = {
            "submission_id": sub.get("id"),
            "segment_id": seg_id,
            "trade_date": sub.get("trade_date"),
            "code": sub.get("code"),
            "name": sub.get("name"),
            "decision_time": sub.get("decision_time"),
            "selected_entry_price": base.safe_float(sub.get("selected_entry_price")),
            "causal_action": sub.get("causal_action"),
            "causal_score": sub.get("causal_score"),
            "execution_score_v1_9": base.safe_float(sub.get("execution_score_v1_9")),
            "score_total": base.safe_float(sub.get("score_total")),
            "filter_score_v1_6": base.safe_float(sub.get("filter_score_v1_6")),
            "entry_score_v2_0": base.safe_float(sub.get("entry_score_v2_0")),
            "top_rank_score_v2_1": base.safe_float(sub.get("top_rank_score_v2_1")),
            "start_from_day_open_pct": base.safe_float(sub.get("start_from_day_open_pct")),
            "start_from_day_low_pct": base.safe_float(sub.get("start_from_day_low_pct")),
            "start_cum_amount": base.safe_float(sub.get("start_cum_amount")),
            "entry_reason_v2_0": sub.get("entry_reason_v2_0"),
            "top_rank_reason_v2_1": sub.get("top_rank_reason_v2_1"),
            "answer_quality": quality,
            "st_param": base.v2.param_key(seg.get("st_period"), seg.get("st_multiplier")) if seg else None,
            "answer_segment_no": seg.get("segment_no") if seg else None,
            "st_up_start_time": str(seg.get("st_up_start_time")) if seg else None,
            "st_up_end_time": str(seg.get("st_up_end_time")) if seg else None,
            "entry_delay_minutes": gap,
            "max_early_entry_minutes": MAX_EARLY_ENTRY_MINUTES,
            "st_up_max_return_pct": base.safe_float(seg.get("st_up_max_return_pct")) if seg else None,
            "st_up_end_return_pct": base.safe_float(seg.get("st_up_end_return_pct")) if seg else None,
            "eval_group": group,
            "why_note": why_note_for_strict(group, sub, seg),
            "leakage_status": "PASS_EARLY_SEGMENT_OVERLAP" if group in ("HIT_GREAT", "HIT_GOOD", "FALSE_BUY") else "NO_VALID_EARLY_OVERLAP",
        }
        eval_rows.append(row)

    return eval_rows, display_segments


base.table_columns = robust_table_columns
base.best_answer_segment = strict_answer_segment
base.eval_group_for = eval_group_for_strict
base.why_note_for = why_note_for_strict
base.build_submission_evaluation = build_submission_evaluation_strict


if __name__ == "__main__":
    raise SystemExit(base.main())
