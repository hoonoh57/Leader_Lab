# -*- coding: utf-8 -*-

from src.evaluation.rank_match_metrics import aggregate_results, evaluate_daily_topk


def test_evaluate_daily_top5_hit_count() -> None:
    actual = [
        ("A", 20.0),
        ("B", 18.0),
        ("C", 15.0),
        ("D", 12.0),
        ("E", 10.0),
        ("F", 5.0),
        ("G", 3.0),
    ]
    score = [
        ("C", 95.0),
        ("F", 90.0),
        ("A", 85.0),
        ("G", 80.0),
        ("E", 75.0),
    ]

    result = evaluate_daily_topk(
        search_date="2026-01-05",
        actual_items=actual,
        score_items=score,
        actual_k=5,
        score_k=5,
    )

    assert result.candidate_count == 7
    assert result.hit_count == 3
    assert abs(result.hit_rate - 0.6) < 0.000001
    assert result.top1_capture == 1
    assert result.ndcg > 0.0
    assert result.lift > 1.0


def test_aggregate_results() -> None:
    r1 = evaluate_daily_topk(
        search_date="2026-01-05",
        actual_items=[("A", 10.0), ("B", 5.0), ("C", 1.0)],
        score_items=[("A", 90.0), ("B", 80.0), ("C", 70.0)],
        actual_k=2,
        score_k=2,
    )
    r2 = evaluate_daily_topk(
        search_date="2026-01-06",
        actual_items=[("D", 10.0), ("E", 5.0), ("F", 1.0)],
        score_items=[("F", 90.0), ("E", 80.0), ("D", 70.0)],
        actual_k=2,
        score_k=2,
    )

    summary = aggregate_results([r1, r2])

    assert summary["days"] == 2.0
    assert summary["avg_candidate_count"] == 3.0
    assert summary["avg_hit_count"] >= 1.0
