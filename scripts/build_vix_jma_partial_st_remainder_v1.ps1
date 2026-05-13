param(
    [string]$StartDate = '',
    [string]$EndDate = '',
    [string]$CandidateTable = '',
    [string]$ConditionName = '',
    [string]$Thresholds = '10',
    [string]$JmaPeriods = '7',
    [string]$JmaPhase = '50',
    [string]$JmaPower = '2',
    [string]$StPeriods = '14',
    [string]$StMultipliers = '3',
    [string]$P1Values = '3',
    [string]$P2Values = '4,5,6,8',
    [string]$QValues = '0.3,0.5,0.7',
    [string]$TrailValues = '1,1.5,2,3',
    [string]$CandleTable = '',
    [string]$CaptureTime = '09:05'
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== BUILD VIX JMA Partial ST Remainder v1 ==='
Write-Host ('RepoRoot: ' + (Get-Location))

$required = @(
    'START_HERE.md',
    'docs/vix_jma_partial_st_remainder_spec_v1.md',
    'docs/vix_entry_jma_st_hold_overlay_observation_2026_05_13.md',
    'src/review/build_vix_entry_continuation_benchmark_v1.py',
    'src/review/build_vix_entry_jma_st_hold_overlay_v1.py',
    'src/review/build_vix_jma_partial_st_remainder_v1.py'
)

foreach ($rel in $required) {
    $p = Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p)) {
        throw ('Missing required file: ' + $rel)
    }
    Write-Host ('OK ' + $rel)
}

Write-Host '=== PY COMPILE ==='
python -m py_compile src/review/build_vix_entry_continuation_benchmark_v1.py src/review/build_vix_entry_jma_st_hold_overlay_v1.py src/review/build_vix_jma_partial_st_remainder_v1.py
if ($LASTEXITCODE -ne 0) {
    throw 'py_compile failed'
}

$argsList = @(
    '-m', 'src.review.build_vix_jma_partial_st_remainder_v1',
    '--env=.env',
    ('--capture-time=' + $CaptureTime),
    ('--thresholds=' + $Thresholds),
    ('--jma-periods=' + $JmaPeriods),
    ('--jma-phase=' + $JmaPhase),
    ('--jma-power=' + $JmaPower),
    ('--st-periods=' + $StPeriods),
    ('--st-multipliers=' + $StMultipliers),
    ('--p1-values=' + $P1Values),
    ('--p2-values=' + $P2Values),
    ('--q-values=' + $QValues),
    ('--trail-values=' + $TrailValues),
    '--output-dir=reports'
)

if ($StartDate.Trim() -ne '') { $argsList += ('--start-date=' + $StartDate) }
if ($EndDate.Trim() -ne '') { $argsList += ('--end-date=' + $EndDate) }
if ($CandidateTable.Trim() -ne '') { $argsList += ('--candidate-table=' + $CandidateTable) }
if ($ConditionName.Trim() -ne '') { $argsList += ('--condition-name=' + $ConditionName) }
if ($CandleTable.Trim() -ne '') { $argsList += ('--candle-table=' + $CandleTable) }

Write-Host '=== RUN PARTIAL ST REMAINDER BENCHMARK ==='
python @argsList
if ($LASTEXITCODE -ne 0) {
    throw 'partial ST remainder generation failed'
}

$files = @(
    'reports/vix_jma_partial_st_remainder_detail_v1.csv',
    'reports/vix_jma_partial_st_remainder_summary_v1.csv',
    'reports/vix_jma_partial_st_remainder_daily_v1.csv',
    'reports/vix_jma_partial_st_remainder_v1.html'
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
Write-Host 'Open reports/vix_jma_partial_st_remainder_v1.html'
Write-Host 'Review reports/vix_jma_partial_st_remainder_summary_v1.csv sorted by avg_realized_pnl_pct.'
Write-Host '=== GIT STATUS ==='
git status
