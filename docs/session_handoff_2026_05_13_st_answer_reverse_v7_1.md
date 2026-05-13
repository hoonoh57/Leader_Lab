# Session Handoff: ST Answer Reverse Analysis v7-1

Date: 2026-05-13
Repository: hoonoh57/Leader_Lab

## Board guard

```text
Board Type: EVALUATION_BOARD
Selected Date: NONE for the full ST dashboard; individual rows retain trade_date/search_time.
Universe Source: supertrend_regime_segment as answer sheet, existing v2.0/v2.1 causal candidate tables as submission sheet if available.
Rank Basis: causal fields only for submission rank; answer fields are display/evaluation only.
Leakage Status: guarded, but local run must verify available causal source columns.
```

## Why this task exists

The project already has a strong answer sheet: high-return SuperTrend up segments. The immediate task is not to invent a new magic buy formula. The task is to put the existing causal submission score next to the answer sheet and ask:

```text
Why did this ST segment become GREAT?
Did the current causal score capture that reason at decision time?
If not, what feature is missing?
```

## v7-1 scope

Add a minimal reverse-analysis overlay to the existing SuperTrend dashboard:

```text
1. eval_group column: HIT_GREAT / MISSED_GREAT / FALSE_BUY / TRUE_REJECT
2. why_note column: short hypothesis prompt for human review
3. decision_time marker on chart when a causal submission row matches
4. score/rank/action display beside answer fields
5. CSV output for review
```

## v7-1 non-scope

```text
No new score formula.
No ML.
No broad daily/MTF/sector feature build yet.
No file explosion.
```

## Required local command

```powershell
cd E:\2026\Leader_Lab

git pull origin main

.\scripts\build_st_answer_reverse_analysis_v7_1.ps1

start .\reports\supertrend_regime_discovery_dashboard_v7_1.html

git status
```

## Review order after opening dashboard

```text
1. Sort/filter mentally by MISSED_GREAT.
2. Inspect GREAT rows whose causal score/action failed to catch them.
3. Inspect FALSE_BUY rows whose causal score was high but answer result was weak.
4. Write repeated reasons into why_note ideas before adding any new feature.
```
