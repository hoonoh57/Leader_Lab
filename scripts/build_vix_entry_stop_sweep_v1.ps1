param(
    [string]$StartDate = '',
    [string]$EndDate = '',
    [string]$CandidateTable = '',
    [string]$ConditionName = '',
    [string]$Thresholds = '10,11,12,13',
    [string]$Stops = '-0.5,-1,-1.5,-2,-2.5,-3,-4,-5,-6,-8',
    [string]$CandleTable = '',
    [string]$CaptureTime = '09:05',
    [string]$TargetPct = '2.0'
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== BUILD VIX Entry Stop Sweep v1 ==='
Write-Host ('RepoRoot: ' + (Get-Location))

$required = @(
    'START_HERE.md',
    'docs/vi10_entry_continuation_methodology_v1.md',
    'docs/vix_jma_st_exit_policy_spec_v1.md',
    'src/review/build_vix_entry_continuation_benchmark_v1.py',
    'src/review/build_vix_entry_stop_sweep_v1.py'
)

foreach ($rel in $required) {
    $p = Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p)) {
        throw ('Missing required file: ' + $rel)
    }
    Write-Host ('OK ' + $rel)
}

Write-Host '=== PY COMPILE ==='
python -m py_compile src/review/build_vix_entry_continuation_benchmark_v1.py src/review/build_vix_entry_stop_sweep_v1.py
if ($LASTEXITCODE -ne 0) {
    throw 'py_compile failed'
}

# IMPORTANT:
# Negative stop values such as -0.5 are parsed by argparse as option-like tokens
# if they are passed as the next argument after --stops. Therefore pass option=value.
$argsList = @(
    '-m', 'src.review.build_vix_entry_stop_sweep_v1',
    '--env=.env',
    ('--capture-time=' + $CaptureTime),
    ('--thresholds=' + $Thresholds),
    ('--stops=' + $Stops),
    ('--target-pct=' + $TargetPct),
    '--output-dir=reports'
)

if ($StartDate.Trim() -ne '') { $argsList += ('--start-date=' + $StartDate) }
if ($EndDate.Trim() -ne '') { $argsList += ('--end-date=' + $EndDate) }
if ($CandidateTable.Trim() -ne '') { $argsList += ('--candidate-table=' + $CandidateTable) }
if ($ConditionName.Trim() -ne '') { $argsList += ('--condition-name=' + $ConditionName) }
if ($CandleTable.Trim() -ne '') { $argsList += ('--candle-table=' + $CandleTable) }

Write-Host '=== RUN STOP SWEEP ==='
python @argsList
if ($LASTEXITCODE -ne 0) {
    throw 'stop sweep generation failed'
}

$files = @(
    'reports/vix_entry_stop_sweep_detail_v1.csv',
    'reports/vix_entry_stop_sweep_summary_v1.csv',
    'reports/vix_entry_stop_sweep_daily_v1.csv',
    'reports/vix_entry_stop_sweep_v1.html'
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
Write-Host 'Open reports/vix_entry_stop_sweep_v1.html'
Write-Host 'Review reports/vix_entry_stop_sweep_summary_v1.csv sorted by expected_pct_per_entry.'
Write-Host '=== GIT STATUS ==='
git status
