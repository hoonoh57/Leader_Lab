param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== BUILD AND VERIFY SuperTrend Chart Consistency Gate v1 ==='

$required = @(
    'START_HERE.md',
    'docs/workflow_server_editing_v1.md',
    'docs/powershell_script_rule_v1.md',
    'docs/pre_edit_reading_rule_v1.md',
    'docs/todo_update_rule_v1.md',
    'docs/supertrend_chart_consistency_gate.md',
    'todo_list.md',
    'scripts/build_supertrend_regime_discovery_dashboard.ps1',
    'src/review/generate_supertrend_regime_discovery_dashboard_v2.py',
    'src/review/generate_supertrend_regime_discovery_dashboard_v6.py'
)

foreach ($rel in $required) {
    $p = Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p)) {
        throw ('Missing required file: ' + $rel)
    }
    Write-Host ('OK ' + $rel)
}

Write-Host '=== RUN DASHBOARD BUILD ==='
& (Join-Path $root 'scripts/build_supertrend_regime_discovery_dashboard.ps1')
if ($LASTEXITCODE -ne 0) {
    throw 'build_supertrend_regime_discovery_dashboard.ps1 failed'
}

$reportPath = Join-Path $root 'reports/supertrend_regime_discovery_dashboard.html'
if (-not (Test-Path -LiteralPath $reportPath)) {
    throw 'Missing generated report: reports/supertrend_regime_discovery_dashboard.html'
}

$html = Get-Content -LiteralPath $reportPath -Raw -Encoding UTF8

$tokens = @(
    'ST Up',
    'ST Down',
    'Chart Consistency',
    '09:00',
    'connectgaps:false',
    'st_up',
    'st_down',
    'st_value',
    'st_dir',
    'is_warmup',
    'is_after_0900',
    'is_prev_session_display',
    'candleMeta',
    'prev session',
    'NO_PREV_SESSION_DISPLAY',
    'START_MISMATCH',
    'END_MISMATCH'
)

Write-Host '=== VERIFY GENERATED HTML TOKENS ==='
foreach ($token in $tokens) {
    if ($html.Contains($token) -eq $false) {
        throw ('Missing report token: ' + $token)
    }
    Write-Host ('OK token: ' + $token)
}

Write-Host '=== REPORT SIZE ==='
$item = Get-Item -LiteralPath $reportPath
Write-Host ('report=' + $reportPath)
Write-Host ('bytes=' + $item.Length)

Write-Host '=== NEXT MANUAL CHECK ==='
Write-Host 'Open reports/supertrend_regime_discovery_dashboard.html'
Write-Host 'Check ST Up and ST Down lines, 09:00 baseline, previous session area, and Chart Consistency card.'

Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE build_and_verify_supertrend_chart_consistency_gate_v1.ps1 ==='
