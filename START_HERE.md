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
8. docs/session_handoff_2026_05_13_st_answer_reverse_v7_1.md
9. docs/logic_registry_st_reverse_analysis.md
10. latest task handoff document in docs/
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
Board Type: CAUSAL_BOARD / ANSWER_BOARD / RESEARCH_BOARD / SELECTED_DATE_BOARD / EVALUATION_BOARD
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

EVALUATION_BOARD
= joined research screen. May display both causal score and answer labels, but causal ranking must be finalized before answer fields are joined.

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
1. Run v7-1 ST Answer Reverse Analysis dashboard.
2. Do not create a new score formula first.
3. Open reports/supertrend_regime_discovery_dashboard_v7_1.html.
4. Inspect MISSED_GREAT first: answer was GREAT, causal submission failed or missed it.
5. Inspect FALSE_BUY second: causal submission was BUY/WATCH, but answer was weak.
6. Record repeated why reasons before adding daily/MTF/sector features.
```

## Current local command

```powershell
cd E:\2026\Leader_Lab

git pull origin main

.\scripts\build_st_answer_reverse_analysis_v7_1.ps1

start .\reports\supertrend_regime_discovery_dashboard_v7_1.html

git status
```

## Research discipline

```text
The current goal is not to find one magic buy pattern.
A successful logic version must be preserved in the registry and compared against later versions.
The answer sheet is the high-return SuperTrend segment list.
The submission sheet is a causal hypothesis.
The dashboard is a dissection table for asking why a GREAT segment worked, why it was missed, and why false buys failed.
Do not expand to v7-2 daily/MTF/sector features until v7-1 MISSED_GREAT/FALSE_BUY rows are reviewed.
```

## Still important but temporarily secondary

```text
SuperTrend Chart Consistency Gate
```

Do not move to entry or exit strategy before the board-type/causal-score audit and Chart Consistency Gate are both clearly handled.
