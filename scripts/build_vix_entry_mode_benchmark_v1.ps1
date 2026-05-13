param(
    [string]$StartDate = '',
    [string]$EndDate = '',
    [string]$CandidateTable = '',
    [string]$ConditionName = '',
    [string]$Thresholds = '10',
    [string]$Stops = '-1,-2,-3,-4,-5,-6,-8',
    [string]$CandleTable = '',
    [string]$CaptureTime = '09:05',
    [string]$TargetPct = '2.0',
    [string]$Next1GuardPct = '-2.0',
    [string]$Next3HoldMin = '2'
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== BUILD VIX Entry Mode Benchmark v1 ==='
Write-Host ('RepoRoot: ' + (Get-Location))

$required = @(
    'START_HERE.md',
    'docs/vix_entry_avoidance_filter_spec_v1.md',
    'docs/vix_entry_avoidance_filter_observation_2026_05_13.md',
    'src/review/build_vix_entry_continuation_benchmark_v1.py',
    'src/review/build_vix_entry_mode_benchmark_v1.py'
)

foreach ($rel in $required) {
    $p = Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p)) {
        throw ('Missing required file: ' + $rel)
    }
    Write-Host ('OK ' + $rel)
}

Write-Host '=== PY COMPILE ==='
python -m py_compile src/review/build_vix_entry_continuation_benchmark_v1.py src/review/build_vix_entry_mode_benchmark_v1.py
if ($LASTEXITCODE -ne 0) {
    throw 'py_compile failed'
}

$argsList = @(
    '-m', 'src.review.build_vix_entry_mode_benchmark_v1',
    '--env=.env',
    ('--capture-time=' + $CaptureTime),
    ('--thresholds=' + $Thresholds),
    ('--stops=' + $Stops),
    ('--target-pct=' + $TargetPct),
    ('--next1-guard-pct=' + $Next1GuardPct),
    ('--next3-hold-min=' + $Next3HoldMin),
    '--output-dir=reports'
)

if ($StartDate.Trim() -ne '') { $argsList += ('--start-date=' + $StartDate) }
if ($EndDate.Trim() -ne '') { $argsList += ('--end-date=' + $EndDate) }
if ($CandidateTable.Trim() -ne '') { $argsList += ('--candidate-table=' + $CandidateTable) }
if ($ConditionName.Trim() -ne '') { $argsList += ('--condition-name=' + $ConditionName) }
if ($CandleTable.Trim() -ne '') { $argsList += ('--candle-table=' + $CandleTable) }

Write-Host '=== RUN ENTRY MODE BENCHMARK ==='
python @argsList
if ($LASTEXITCODE -ne 0) {
    throw 'entry mode benchmark generation failed'
}

$files = @(
    'reports/vix_entry_mode_detail_v1.csv',
    'reports/vix_entry_mode_summary_v1.csv',
    'reports/vix_entry_mode_daily_v1.csv',
    'reports/vix_entry_mode_benchmark_v1.html'
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
Write-Host 'Open reports/vix_entry_mode_benchmark_v1.html'
Write-Host 'Review reports/vix_entry_mode_summary_v1.csv sorted by expected_pct_per_entry.'
Write-Host '=== GIT STATUS ==='
git status
