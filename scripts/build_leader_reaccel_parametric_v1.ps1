param(
    [string]$TradeDate = '',
    [string]$StartDate = '',
    [string]$EndDate = '',
    [string]$CandidateTable = '',
    [string]$ConditionName = '',
    [string]$CandleTable = '',
    [string]$CaptureTime = '09:05',

    [string]$TrendPeriods = '20',
    [string]$RsiPeriods = '14',
    [string]$RsiReclaimLevels = '70',
    [string]$RsiCooldownLevels = '70',
    [string]$RsiCooldownLookbacks = '24',
    [string]$BarReturnMinPcts = '2,2.5,3',
    [string]$ParticipationType = 'amount',
    [string]$BarAmountMin = '1000000000',
    [string]$CumAmountMin = '5000000000',
    [string]$HighRiseMinPcts = '10',

    [string]$P1 = '3.0',
    [string]$P2 = '6.0',
    [string]$Q = '0.3',
    [string]$Trail = '1.0',
    [string]$TopN = '3,5,6',
    [switch]$UseCandleQuality,
    [string]$ExcludeFirstOpenReturnGte = '0'
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== BUILD Leader Reaccel Parametric v1 ==='
Write-Host ('RepoRoot: ' + (Get-Location))

$required = @(
    'START_HERE.md',
    'docs/leader_reaccel_parameterized_research_plan_v1.md',
    'docs/leader_reacceleration_rsi_ma20_amount_basebar_strategy_v1.md',
    'docs/leader_reaccel_market_theme_confidence_overlay_v1.md',
    'docs/leader_reaccel_vix_warning_overlay_v1.md',
    'src/review/build_vix_entry_continuation_benchmark_v1.py',
    'src/review/build_rsi70_ma20_amount_breakout_v1.py',
    'src/review/build_vix_entry_jma_st_hold_overlay_v1.py',
    'src/review/build_vix_jma_partial_st_remainder_v1.py',
    'src/review/build_leader_reaccel_parametric_v1.py'
)

foreach ($rel in $required) {
    $p = Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p)) {
        throw ('Missing required file: ' + $rel)
    }
    Write-Host ('OK ' + $rel)
}

Write-Host '=== PY COMPILE ==='
python -m py_compile `
    src/review/build_vix_entry_continuation_benchmark_v1.py `
    src/review/build_vix_entry_jma_st_hold_overlay_v1.py `
    src/review/build_vix_jma_partial_st_remainder_v1.py `
    src/review/build_rsi70_ma20_amount_breakout_v1.py `
    src/review/build_leader_reaccel_parametric_v1.py
if ($LASTEXITCODE -ne 0) {
    throw 'py_compile failed'
}

$argsList = @(
    '-m', 'src.review.build_leader_reaccel_parametric_v1',
    '--env=.env',
    ('--capture-time=' + $CaptureTime),
    ('--trend-periods=' + $TrendPeriods),
    ('--rsi-periods=' + $RsiPeriods),
    ('--rsi-reclaim-levels=' + $RsiReclaimLevels),
    ('--rsi-cooldown-levels=' + $RsiCooldownLevels),
    ('--rsi-cooldown-lookbacks=' + $RsiCooldownLookbacks),
    ('--bar-return-min-pcts=' + $BarReturnMinPcts),
    ('--participation-type=' + $ParticipationType),
    ('--bar-amount-min=' + $BarAmountMin),
    ('--cum-amount-min=' + $CumAmountMin),
    ('--high-rise-min-pcts=' + $HighRiseMinPcts),
    ('--p1=' + $P1),
    ('--p2=' + $P2),
    ('--q=' + $Q),
    ('--trail=' + $Trail),
    ('--topn=' + $TopN),
    ('--exclude-first-open-return-gte=' + $ExcludeFirstOpenReturnGte),
    '--output-dir=reports'
)

if ($UseCandleQuality) { $argsList += '--use-candle-quality' }
if ($TradeDate.Trim() -ne '') { $argsList += ('--trade-date=' + $TradeDate) }
if ($StartDate.Trim() -ne '') { $argsList += ('--start-date=' + $StartDate) }
if ($EndDate.Trim() -ne '') { $argsList += ('--end-date=' + $EndDate) }
if ($CandidateTable.Trim() -ne '') { $argsList += ('--candidate-table=' + $CandidateTable) }
if ($ConditionName.Trim() -ne '') { $argsList += ('--condition-name=' + $ConditionName) }
if ($CandleTable.Trim() -ne '') { $argsList += ('--candle-table=' + $CandleTable) }

Write-Host '=== RUN LEADER REACCEL PARAMETRIC BACKTEST ==='
python @argsList
if ($LASTEXITCODE -ne 0) {
    throw 'Leader Reaccel parametric backtest failed'
}

$files = @(
    'reports/leader_reaccel_parametric_detail_v1.csv',
    'reports/leader_reaccel_parametric_summary_v1.csv',
    'reports/leader_reaccel_parametric_daily_v1.csv',
    'reports/leader_reaccel_parametric_topn_v1.csv',
    'reports/leader_reaccel_parametric_v1.html'
)

Write-Host '=== VERIFY OUTPUTS ==='
foreach ($rel in $files) {
    $p = Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p)) {
        throw ('Missing output: ' + $rel)
    }
    Write-Host ('OK ' + $rel)
}

Write-Host '=== OUTPUT ==='
Write-Host 'Open reports/leader_reaccel_parametric_v1.html'
Write-Host 'Review summary, daily, and topn CSV files.'
Write-Host '=== GIT STATUS ==='
git status
