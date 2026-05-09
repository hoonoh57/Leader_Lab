# Leader_Lab

`Leader_Lab` is a research and validation project for ranking Kiwoom HTS 1516 performance-screening candidates by their probability of becoming intraday leaders.

The primary objective is not simple average-return optimization. The objective is to determine whether a reproducible `LeaderScore` can rank daily 1516 candidates so that the score Top5/Top10 overlaps strongly with the actual `max_ret_in_period` Top5/Top10.

## Core Target

For each search date/time:

- Load 1516 captured candidates.
- Attach stock metadata, daily candle features, and 5-minute candle features.
- Calculate `LeaderScore`.
- Compare `LeaderScore` rank against actual `max_ret_in_period` rank.
- Evaluate TopK hit rate, NDCG, lift, and label_10 concentration.

## Local Data Sources

Actual data remains local and is not committed to GitHub.

Expected local sources:

- SQLite: `kiwoom_1516.sqlite3`
- MySQL: `stock_info.daily_candles`
- MySQL: `stock_information.stock_base_info`
- MySQL target cache: `stock_info.performance_result`
- MySQL target cache: `stock_info.minute5_candles`
- server32 REST API: 5-minute candle download source

## Repository Role

This repository stores only:

- code
- SQL DDL
- configuration templates
- small sample data
- tests
- report templates
- finalized score YAML versions

It does not store:

- `.env`
- MySQL passwords
- account/order/fill logs
- real large DB files
- complete daily or minute candle caches

## Basic Local Flow

```powershell
cd E:\2026\Leader_Lab
git pull
copy .env.example .env
# edit .env
.\scripts\setup_mysql_schema.ps1
.\scripts\migrate_1516_to_mysql.ps1
.\scripts\download_minute5_cache.ps1
.\scripts\run_leader_lab.ps1
```

## Development Phases

See [`todo_list.md`](todo_list.md).

## Success Criteria

Initial success:

- Score Top10 contains at least 5 of actual max-ret Top10 on average.
- Score Top5 contains at least 2.5 of actual max-ret Top5 on average.
- Score Top5 label_10 rate is materially above the baseline.

Strong success:

- Score Top10 contains at least 7 of actual max-ret Top10 on average.
- Score Top5 contains at least 3 of actual max-ret Top5 on average.
- Test-period performance remains stable after train/validation/test split.

Final output:

- `configs/PermanentLeaderScore_v1.yaml`
- `reports/final_score_v1_report.md`
