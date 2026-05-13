param(
    [string]$StartDate = '',
    [string]$EndDate = '',
    [string]$CandidateTable = '',
    [string]$ConditionName = '',
    [string]$Thresholds = '10',
    [string]$CandleTable = '',
    [string]$CaptureTime = '09:05',
    [string]$TargetPct = '2.0',
    [string]$CollapseMaePct = '-6.0',
    [string]$RejectMaePct = '-2.0'
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== BUILD VIX Entry Avoidance Filter v1 ==='
Write-Host ('RepoRoot: ' + (Get-Location))

$required = @(
    'START_HERE.md',
    'docs/vix_entry_avoidance_filter_spec_v1.md',
    'src/review/build_vix_entry_continuation_benchmark_v1.py',
    'src/review/build_vix_entry_avoidance_filter_v1.py'
)

foreach ($rel in $required) {
    $p = Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p)) {
        throw ('Missing required file: ' + $rel)
    }
    Write-Host ('OK ' + $rel)
}

Write-Host '=== PY COMPILE ==='
python -m py_compile src/review/build_vix_entry_continuation_benchmark_v1.py src/review/build_vix_entry_avoidance_filter_v1.py
if ($LASTEXITCODE -ne 0) {
    throw 'py_compile failed'
}

$argsList = @(
    '-m', 'src.review.build_vix_entry_avoidance_filter_v1',
    '--env=.env',
    ('--capture-time=' + $CaptureTime),
    ('--thresholds=' + $Thresholds),
    ('--target-pct=' + $TargetPct),
    ('--collapse-mae-pct=' + $CollapseMaePct),
    ('--reject-mae-pct=' + $RejectMaePct),
    '--output-dir=reports'
)

if ($StartDate.Trim() -ne '') { $argsList += ('--start-date=' + $StartDate) }
if ($EndDate.Trim() -ne '') { $argsList += ('--end-date=' + $EndDate) }
if ($CandidateTable.Trim() -ne '') { $argsList += ('--candidate-table=' + $CandidateTable) }
if ($ConditionName.Trim() -ne '') { $argsList += ('--condition-name=' + $ConditionName) }
if ($CandleTable.Trim() -ne '') { $argsList += ('--candle-table=' + $CandleTable) }

Write-Host '=== RUN AVOIDANCE FILTER BENCHMARK ==='
python @argsList
if ($LASTEXITCODE -ne 0) {
    throw 'avoidance filter generation failed'
}

$files = @(
    'reports/vix_entry_avoidance_detail_v1.csv',
    'reports/vix_entry_avoidance_feature_summary_v1.csv',
    'reports/vix_entry_avoidance_rule_lift_v1.csv',
    'reports/vix_entry_avoidance_benchmark_v1.html'
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
Write-Host 'Open reports/vix_entry_avoidance_benchmark_v1.html'
Write-Host 'Review reports/vix_entry_avoidance_rule_lift_v1.csv and feature_summary.'
Write-Host '=== GIT STATUS ==='
git status
