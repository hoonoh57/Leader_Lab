param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== BUILD SuperTrend Dashboard v7 Overlay ==='

$required = @(
    'START_HERE.md',
    'docs/workflow_server_editing_v1.md',
    'docs/powershell_script_rule_v1.md',
    'docs/pre_edit_reading_rule_v1.md',
    'docs/todo_update_rule_v1.md',
    'docs/st_dashboard_live_overlay_research_v1.md',
    'docs/live_candidate_overlay_on_st_dashboard_v1.md',
    'src/review/generate_supertrend_regime_discovery_dashboard_v7.py'
)

foreach ($rel in $required) {
    $p = Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p)) {
        throw ('Missing required file: ' + $rel)
    }
    Write-Host ('OK ' + $rel)
}

python -m py_compile src/review/generate_supertrend_regime_discovery_dashboard_v7.py
if ($LASTEXITCODE -ne 0) {
    throw 'py_compile failed: generate_supertrend_regime_discovery_dashboard_v7.py'
}

python -m src.review.generate_supertrend_regime_discovery_dashboard_v7 --env .env --output reports/supertrend_regime_discovery_dashboard_v7_overlay.html --limit 12000 --candidate-limit 500 --warmup-bars 80 --prev-display-start 12:00
if ($LASTEXITCODE -ne 0) {
    throw 'generate_supertrend_regime_discovery_dashboard_v7 failed'
}

$report = Join-Path $root 'reports/supertrend_regime_discovery_dashboard_v7_overlay.html'
if (-not (Test-Path -LiteralPath $report)) {
    throw 'Missing v7 report'
}

$html = Get-Content -LiteralPath $report -Raw -Encoding UTF8
$tokens = @(
    'LIVE_CANDIDATES_V7',
    'Live Candidate Overlay v7',
    'AUTO_BUY_READY',
    'WATCH_HOGA_TICK',
    'REJECT',
    'actionName(action)',
    'buildCandidateTraces',
    'Plotly.addTraces',
    'ST Up',
    'ST Down',
    'Chart Consistency',
    'Good-vs-Bad'
)

Write-Host '=== VERIFY v7 REPORT TOKENS ==='
foreach ($token in $tokens) {
    if ($html.Contains($token) -eq $false) {
        throw ('Missing report token: ' + $token)
    }
    Write-Host ('OK token: ' + $token)
}

$item = Get-Item -LiteralPath $report
Write-Host ('report=' + $report)
Write-Host ('bytes=' + $item.Length)
Write-Host 'Open reports/supertrend_regime_discovery_dashboard_v7_overlay.html'

Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE build_supertrend_dashboard_v7_overlay.ps1 ==='
