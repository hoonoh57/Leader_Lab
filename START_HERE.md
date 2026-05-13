# Leader_Lab START HERE

Date: 2026-05-13

This file is the default entry point for every new session.

## One-line user request for a new session

```text
Continue hoonoh57/Leader_Lab from START_HERE.md.
```

The assistant must then read the required repository documents before suggesting or editing anything.

## Required reading order

```text
1. START_HERE.md
2. docs/workflow_server_editing_v1.md
3. docs/powershell_script_rule_v1.md
4. docs/pre_edit_reading_rule_v1.md
5. docs/todo_update_rule_v1.md
6. todo_list.md
7. docs/session_handoff_2026_05_13_causal_board_guard_v1.md
8. latest task handoff document in docs/
```

## Operating rule

```text
Server creates or modifies files first.
Local only runs git pull, the versioned script, and git status.
If local verification fails, fix the server-side file or script and pull again.
```

## Board-type guard rule

Before any candidate-board, Top Candidate Board, SuperTrend board, or selected-date board work, the assistant must explicitly identify:

```text
Board Type: CAUSAL_BOARD / ANSWER_BOARD / RESEARCH_BOARD / SELECTED_DATE_BOARD
Selected Date: explicit date or NONE
Universe Source: explicit table
Rank Basis: causal fields or answer fields
Leakage Status: PASS / FAIL / NOT YET AUDITED
```

If this information is unknown, do not implement. Audit first.

## Fixed board terminology

```text
CAUSAL_BOARD
= test sheet. Uses only data available at capture/search time.

ANSWER_BOARD
= answer/validation board. May use ST result labels, st_up_max_return_pct, max_ret_in_period, actual ranks.

RESEARCH_BOARD
= mixed-date or offline research sample. Never call it live or selected-date recommendation.

SELECTED_DATE_BOARD
= board filtered to exactly one search_date/trade_date and one source condition.
```

Forbidden interpretation:

```text
LIVE_COMPACT_V3_4 = today buy-priority board
```

Correct interpretation:

```text
LIVE_COMPACT_V3_4 / v3.4 smoke UI = research/mixed-date compact board unless selected date is explicitly shown.
```

## Current next priority

```text
1. Read docs/session_handoff_2026_05_13_causal_board_guard_v1.md
2. Do not create a new score formula first.
3. Inspect existing v2.0/v2.1 causal score generation logic.
4. Locate the exact script or SQL that created:
   - supertrend_realtime_entry_candidate_v2_0
   - supertrend_realtime_entry_top_candidate_v2_1
   - execution_score_v1_9
   - score_total
   - filter_score_v1_6
   - entry_score_v2_0
   - top_rank_score_v2_1
5. After causality is confirmed, apply existing causal score logic to selected-date performance_result candidates.
6. Compare only against v3.8 ST answer board.
```

## Still important but temporarily secondary

```text
SuperTrend Chart Consistency Gate
```

Do not move to entry or exit strategy before the board-type/causal-score audit and Chart Consistency Gate are both clearly handled.
