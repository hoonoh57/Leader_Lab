param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== BUILD ST Answer Reverse Analysis v7-1 ==='
Write-Host ('RepoRoot: ' + (Get-Location))

$required = @(
    'START_HERE.md',
    'todo_list.md',
    'docs/logic_registry_st_reverse_analysis.md',
    'docs/session_handoff_2026_05_13_st_answer_reverse_v7_1.md',
    'src/review/generate_st_answer_reverse_analysis_v7_1.py',
    'src/review/generate_supertrend_regime_discovery_dashboard_v2.py',
    'src/review/generate_supertrend_regime_discovery_dashboard_v5.py',
    'src/review/generate_supertrend_regime_discovery_dashboard_v6.py'
)

foreach ($rel in $required) {
    $p = Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p)) {
        throw ('Missing required file: ' + $rel)
    }
    Write-Host ('OK ' + $rel)
}

Write-Host '=== BOARD GUARD ==='
Write-Host 'Board Type: EVALUATION_BOARD'
Write-Host 'Selected Date: NONE'
Write-Host 'Universe Source: supertrend_regime_segment + existing v2.0/v2.1 causal candidate tables'
Write-Host 'Rank Basis: causal fields only; answer fields display/evaluation only'
Write-Host 'Leakage Status: guarded by selected causal columns'

Write-Host '=== PY COMPILE ==='
python -m py_compile src/review/generate_st_answer_reverse_analysis_v7_1.py
if ($LASTEXITCODE -ne 0) {
    throw 'py_compile generate_st_answer_reverse_analysis_v7_1.py failed'
}

Write-Host '=== GENERATE DASHBOARD ==='
python -m src.review.generate_st_answer_reverse_analysis_v7_1 --env .env --output 'reports/supertrend_regime_discovery_dashboard_v7_1.html' --eval-output 'reports/st_answer_reverse_eval_v7_1.csv' --limit 12000 --warmup-bars 80 --prev-display-start '12:00'
if ($LASTEXITCODE -ne 0) {
    throw 'generate_st_answer_reverse_analysis_v7_1 failed'
}

$reportPath = Join-Path $root 'reports/supertrend_regime_discovery_dashboard_v7_1.html'
$csvPath = Join-Path $root 'reports/st_answer_reverse_eval_v7_1.csv'

if (-not (Test-Path -LiteralPath $reportPath)) {
    throw 'Missing generated report: reports/supertrend_regime_discovery_dashboard_v7_1.html'
}
if (-not (Test-Path -LiteralPath $csvPath)) {
    throw 'Missing generated csv: reports/st_answer_reverse_eval_v7_1.csv'
}

$html = Get-Content -LiteralPath $reportPath -Raw -Encoding UTF8
$tokens = @(
    'v7-1 Why',
    'Answer vs Submission',
    'MISSED_GREAT',
    'FALSE_BUY',
    'HIT_GREAT',
    'TRUE_REJECT',
    'ST_EVAL_V7_1',
    'decision_time',
    'why_note'
)

Write-Host '=== VERIFY HTML TOKENS ==='
foreach ($token in $tokens) {
    if ($html.Contains($token) -eq $false) {
        throw ('Missing report token: ' + $token)
    }
    Write-Host ('OK token: ' + $token)
}

Write-Host '=== OUTPUT ==='
Write-Host ('report=' + $reportPath)
Write-Host ('csv=' + $csvPath)
Write-Host 'Open reports/supertrend_regime_discovery_dashboard_v7_1.html and inspect MISSED_GREAT / FALSE_BUY first.'

Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE build_st_answer_reverse_analysis_v7_1.ps1 ==='
