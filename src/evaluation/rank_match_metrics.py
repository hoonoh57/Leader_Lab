# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from math import log2
from typing import Dict, Iterable, List, Sequence, Set, Tuple


@dataclass(frozen=True)
class DailyRankMatchResult:
    search_date: str
    candidate_count: int
    actual_top_k: int
    score_top_k: int
    hit_count: int
    hit_rate: float
    top1_capture: int
    ndcg: float
    random_hit_rate: float
    lift: float


def _top_items(items: Sequence[Tuple[str, float]], k: int, reverse: bool = True) -> List[str]:
    ordered = sorted(items, key=lambda x: (x[1], x[0]), reverse=reverse)
    return [x[0] for x in ordered[:k]]


def _dcg(relevance: Sequence[float]) -> float:
    total = 0.0
    for idx, rel in enumerate(relevance):
        total += (2.0 ** rel - 1.0) / log2(idx + 2.0)
    return total


def ndcg_at_k(score_order: Sequence[str], actual_rank_map: Dict[str, int], k: int) -> float:
    """Compute NDCG@k using inverse actual rank relevance.

    Higher relevance is assigned to better actual ranks.
    Missing items get zero relevance.
    """
    if k <= 0:
        return 0.0

    max_rank = max(actual_rank_map.values()) if actual_rank_map else 0
    if max_rank <= 0:
        return 0.0

    relevance: List[float] = []
    for item in score_order[:k]:
        rank = actual_rank_map.get(item)
        if rank is None:
            relevance.append(0.0)
        else:
            relevance.append(float(max_rank - rank + 1))

    ideal_relevance = sorted(
        [float(max_rank - rank + 1) for rank in actual_rank_map.values()],
        reverse=True,
    )[:k]

    ideal = _dcg(ideal_relevance)
    if ideal <= 0:
        return 0.0
    return _dcg(relevance) / ideal


def evaluate_daily_topk(
    search_date: str,
    actual_items: Sequence[Tuple[str, float]],
    score_items: Sequence[Tuple[str, float]],
    actual_k: int = 5,
    score_k: int = 5,
) -> DailyRankMatchResult:
    """Evaluate one day's score ranking against actual max-return ranking.

    actual_items: [(code, max_ret)]
    score_items: [(code, score)]
    """
    candidate_codes: Set[str] = {x[0] for x in actual_items}
    candidate_count = len(candidate_codes)

    if candidate_count == 0:
        return DailyRankMatchResult(search_date, 0, actual_k, score_k, 0, 0.0, 0, 0.0, 0.0, 0.0)

    actual_top = set(_top_items(actual_items, actual_k, reverse=True))
    score_top_order = _top_items(score_items, score_k, reverse=True)
    score_top = set(score_top_order)

    hit_count = len(actual_top.intersection(score_top))
    hit_rate = hit_count / float(max(1, actual_k))

    score_top1 = score_top_order[0] if score_top_order else ""
    top1_capture = 1 if score_top1 in actual_top else 0

    actual_order = _top_items(actual_items, candidate_count, reverse=True)
    actual_rank_map: Dict[str, int] = {code: idx + 1 for idx, code in enumerate(actual_order)}
    ndcg = ndcg_at_k(score_top_order, actual_rank_map, score_k)

    # Expected hit-rate by random score_top_k draw against actual_top_k.
    random_hit_rate = min(score_k, candidate_count) / float(candidate_count)
    lift = hit_rate / random_hit_rate if random_hit_rate > 0 else 0.0

    return DailyRankMatchResult(
        search_date=search_date,
        candidate_count=candidate_count,
        actual_top_k=actual_k,
        score_top_k=score_k,
        hit_count=hit_count,
        hit_rate=hit_rate,
        top1_capture=top1_capture,
        ndcg=ndcg,
        random_hit_rate=random_hit_rate,
        lift=lift,
    )


def aggregate_results(results: Iterable[DailyRankMatchResult]) -> Dict[str, float]:
    rows = list(results)
    if not rows:
        return {
            "days": 0.0,
            "avg_candidate_count": 0.0,
            "avg_hit_rate": 0.0,
            "avg_hit_count": 0.0,
            "top1_capture_rate": 0.0,
            "avg_ndcg": 0.0,
            "avg_lift": 0.0,
        }

    n = float(len(rows))
    return {
        "days": n,
        "avg_candidate_count": sum(x.candidate_count for x in rows) / n,
        "avg_hit_rate": sum(x.hit_rate for x in rows) / n,
        "avg_hit_count": sum(x.hit_count for x in rows) / n,
        "top1_capture_rate": sum(x.top1_capture for x in rows) / n,
        "avg_ndcg": sum(x.ndcg for x in rows) / n,
        "avg_lift": sum(x.lift for x in rows) / n,
    }
