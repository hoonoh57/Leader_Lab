param(
    [string]$StartDate = '',
    [string]$EndDate = '',
    [string]$CandidateTable = '',
    [string]$ConditionName = '',
    [string]$CandleTable = '',
    [string]$CaptureTime = '09:05',
    [string]$BarReturnMinPct = '3.0',
    [string]$BarAmountMin = '1000000000',
    [string]$CumAmountMin = '5000000000',
    [string]$Last5dHighRiseMinPct = '10.0',
    [string]$P1 = '3.0',
    [string]$P2 = '6.0',
    [string]$Q = '0.3',
    [string]$Trail = '1.0'
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== BUILD RSI70 MA20 Amount Breakout v1 ==='
Write-Host ('RepoRoot: ' + (Get-Location))

$required = @(
    'START_HERE.md',
    'docs/rsi70_ma20_amount_breakout_strategy_spec_v1.md',
    'src/review/build_vix_entry_continuation_benchmark_v1.py',
    'src/review/build_vix_entry_jma_st_hold_overlay_v1.py',
    'src/review/build_vix_jma_partial_st_remainder_v1.py',
    'src/review/build_rsi70_ma20_amount_breakout_v1.py'
)

foreach ($rel in $required) {
    $p = Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p)) {
        throw ('Missing required file: ' + $rel)
    }
    Write-Host ('OK ' + $rel)
}

Write-Host '=== PY COMPILE ==='
python -m py_compile src/review/build_vix_entry_continuation_benchmark_v1.py src/review/build_vix_entry_jma_st_hold_overlay_v1.py src/review/build_vix_jma_partial_st_remainder_v1.py src/review/build_rsi70_ma20_amount_breakout_v1.py
if ($LASTEXITCODE -ne 0) {
    throw 'py_compile failed'
}

$argsList = @(
    '-m', 'src.review.build_rsi70_ma20_amount_breakout_v1',
    '--env=.env',
    ('--capture-time=' + $CaptureTime),
    ('--bar-return-min-pct=' + $BarReturnMinPct),
    ('--bar-amount-min=' + $BarAmountMin),
    ('--cum-amount-min=' + $CumAmountMin),
    ('--last5d-high-rise-min-pct=' + $Last5dHighRiseMinPct),
    ('--p1=' + $P1),
    ('--p2=' + $P2),
    ('--q=' + $Q),
    ('--trail=' + $Trail),
    '--output-dir=reports'
)

if ($StartDate.Trim() -ne '') { $argsList += ('--start-date=' + $StartDate) }
if ($EndDate.Trim() -ne '') { $argsList += ('--end-date=' + $EndDate) }
if ($CandidateTable.Trim() -ne '') { $argsList += ('--candidate-table=' + $CandidateTable) }
if ($ConditionName.Trim() -ne '') { $argsList += ('--condition-name=' + $ConditionName) }
if ($CandleTable.Trim() -ne '') { $argsList += ('--candle-table=' + $CandleTable) }

Write-Host '=== RUN RSI70 MA20 AMOUNT BREAKOUT BENCHMARK ==='
python @argsList
if ($LASTEXITCODE -ne 0) {
    throw 'RSI70 MA20 amount breakout generation failed'
}

$files = @(
    'reports/rsi70_ma20_amount_breakout_detail_v1.csv',
    'reports/rsi70_ma20_amount_breakout_summary_v1.csv',
    'reports/rsi70_ma20_amount_breakout_daily_v1.csv',
    'reports/rsi70_ma20_amount_breakout_v1.html'
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
Write-Host 'Open reports/rsi70_ma20_amount_breakout_v1.html'
Write-Host 'Review reports/rsi70_ma20_amount_breakout_summary_v1.csv and daily result.'
Write-Host '=== GIT STATUS ==='
git status
