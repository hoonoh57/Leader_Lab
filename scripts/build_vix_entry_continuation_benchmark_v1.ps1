param(
    [string]$StartDate = '',
    [string]$EndDate = '',
    [string]$CandidateTable = '',
    [string]$ConditionName = '',
    [string]$Thresholds = '10,11,12,13',
    [string]$CandleTable = '',
    [string]$CaptureTime = '09:05'
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== BUILD VIX Entry Continuation Benchmark v1 ==='
Write-Host ('RepoRoot: ' + (Get-Location))

$required = @(
    'START_HERE.md',
    'docs/vi10_entry_continuation_methodology_v1.md',
    'src/review/build_vix_entry_continuation_benchmark_v1.py'
)

foreach ($rel in $required) {
    $p = Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p)) {
        throw ('Missing required file: ' + $rel)
    }
    Write-Host ('OK ' + $rel)
}

Write-Host '=== PY COMPILE ==='
python -m py_compile src/review/build_vix_entry_continuation_benchmark_v1.py
if ($LASTEXITCODE -ne 0) {
    throw 'py_compile failed'
}

$argsList = @(
    '-m', 'src.review.build_vix_entry_continuation_benchmark_v1',
    '--env', '.env',
    '--capture-time', $CaptureTime,
    '--thresholds', $Thresholds,
    '--output-dir', 'reports'
)

if ($StartDate.Trim() -ne '') { $argsList += @('--start-date', $StartDate) }
if ($EndDate.Trim() -ne '') { $argsList += @('--end-date', $EndDate) }
if ($CandidateTable.Trim() -ne '') { $argsList += @('--candidate-table', $CandidateTable) }
if ($ConditionName.Trim() -ne '') { $argsList += @('--condition-name', $ConditionName) }
if ($CandleTable.Trim() -ne '') { $argsList += @('--candle-table', $CandleTable) }

Write-Host '=== RUN BENCHMARK ==='
python @argsList
if ($LASTEXITCODE -ne 0) {
    throw 'benchmark generation failed'
}

$files = @(
    'reports/vix_entry_continuation_benchmark_v1.csv',
    'reports/vix_entry_threshold_comparison_v1.csv',
    'reports/vix_entry_daily_summary_v1.csv',
    'reports/vix_entry_continuation_benchmark_v1.html'
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
Write-Host 'Open reports/vix_entry_continuation_benchmark_v1.html'
Write-Host 'Review threshold comparison: X=10/11/12/13 plus2_success_rate, reject_rate, avg_mae.'
Write-Host '=== GIT STATUS ==='
git status
