#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import build_supertrend_entry_execution_policy_v1_9 as base
from typing import Any


def build_summary(conn: Any) -> None:
    sql = """
INSERT INTO {summary_table} (
    st_period, st_multiplier, filter_grade_v1_6, filter_label_v1_6, recommended_entry_policy_v1_9, execution_label_v1_9,
    row_count, avg_execution_score_v1_9, avg_selected_return_pct, avg_selected_mae_pct, avg_selected_lost_move_pct,
    avg_next_bar_return_pct, avg_next_bar_mae_pct, avg_pullback_return_pct, avg_pullback_mae_pct,
    avg_overheat_score_v1_9, avg_liquidity_score_v1_9, avg_start_from_day_open_pct, avg_start_from_day_low_pct, avg_start_cum_amount
)
SELECT
    st_period,
    st_multiplier,
    filter_grade_v1_6,
    filter_label_v1_6,
    recommended_entry_policy_v1_9,
    execution_label_v1_9,
    COUNT(*) AS row_count,
    AVG(execution_score_v1_9) AS avg_execution_score_v1_9,
    AVG(selected_estimated_return_pct) AS avg_selected_return_pct,
    AVG(selected_max_adverse_excursion_pct) AS avg_selected_mae_pct,
    AVG(selected_estimated_lost_move_pct) AS avg_selected_lost_move_pct,
    AVG(next_bar_return_pct) AS avg_next_bar_return_pct,
    AVG(next_bar_mae_pct) AS avg_next_bar_mae_pct,
    AVG(pullback_return_pct) AS avg_pullback_return_pct,
    AVG(pullback_mae_pct) AS avg_pullback_mae_pct,
    AVG(overheat_score_v1_9) AS avg_overheat_score_v1_9,
    AVG(liquidity_score_v1_9) AS avg_liquidity_score_v1_9,
    AVG(start_from_day_open_pct) AS avg_start_from_day_open_pct,
    AVG(start_from_day_low_pct) AS avg_start_from_day_low_pct,
    AVG(start_cum_amount) AS avg_start_cum_amount
FROM {detail_table}
GROUP BY st_period, st_multiplier, filter_grade_v1_6, filter_label_v1_6, recommended_entry_policy_v1_9, execution_label_v1_9
ORDER BY AVG(execution_score_v1_9) DESC, AVG(selected_estimated_return_pct) DESC
""".format(
        summary_table=base.qident(base.SUMMARY_TABLE),
        detail_table=base.qident(base.DETAIL_TABLE),
    )
    base.execute(conn, sql)


def main() -> None:
    base.build_summary = build_summary
    base.main()


if __name__ == "__main__":
    main()
