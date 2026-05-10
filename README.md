# Leader_Lab

`Leader_Lab` is a research and validation project for ranking Kiwoom HTS 1516 performance-screening candidates by their probability of becoming intraday leaders.

The primary objective is not simple average-return optimization. The objective is to determine whether a reproducible `LeaderScore` can rank daily 1516 candidates so that the score Top5/Top10 overlaps strongly with the actual `max_ret_in_period` Top5/Top10.

## Current Research Position

The current stack is fixed as follows:

```text
Experiment Registry
→ Winner Pattern Discovery
→ Winner Feature Score v1
→ Time-Aware Winner Feature Score v2
→ SuperTrend Regime Discovery
→ Chart Consistency Gate  ← current pending gate
→ Good ST Segment Similarity
→ Regime-aware entry/exit strategy
→ Macro/news/sector/LLM overlay
```

Important: do not proceed to entry/exit strategy design until the `Chart Consistency Gate` passes.

Current SuperTrend Regime Discovery output has been generated with:

```text
targets=2622
params=(7,1.5), (7,2.0), (10,2.0), (14,2.0)
warmup_bars=80
segments=25070
report=reports/supertrend_regime_discovery_dashboard.html
```

The next required implementation is to modify the dashboard so that the selected SuperTrend parameter draws actual `ST Up` and `ST Down` lines on the chart, not only DB segment shading.

See:

- [`docs/supertrend_chart_consistency_gate.md`](docs/supertrend_chart_consistency_gate.md)
- [`todo_list.md`](todo_list.md)

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
- research handoff documents
- dashboard consistency specifications

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

## Current SuperTrend Consistency Flow

After pulling the latest docs/code, run:

```powershell
cd E:\2026\Leader_Lab
git pull
.\scripts\build_supertrend_regime_discovery.ps1
.\scripts\build_supertrend_regime_discovery_dashboard.ps1
start .\reports\supertrend_regime_discovery_dashboard.html
```

The dashboard must be upgraded/verified so that:

```text
1. 09:00 이전 warmup 봉 포함 여부가 보인다.
2. 09:00 기준선이 보인다.
3. 선택 ST 파라미터 기준 ST Up / ST Down 선이 보인다.
4. DB segment shade가 ST Up line과 일치하는지 확인 가능하다.
5. 장초반 강한 상승구간이 warmup 부족 때문에 누락되지 않는지 확인 가능하다.
```

Only after this gate passes should the project move to `Good ST Segment Similarity`.

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
