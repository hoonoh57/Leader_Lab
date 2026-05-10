$ErrorActionPreference = "Stop"

Set-Location -Path (Resolve-Path "$PSScriptRoot\..")

Write-Host "=== Leader_Lab Time-Aware Winner Feature Score Dashboard ==="
Write-Host "RepoRoot: $(Get-Location)"

python -m py_compile src/review/generate_winner_feature_score_time_dashboard.py
if ($LASTEXITCODE -ne 0) {
    throw "py_compile generate_winner_feature_score_time_dashboard failed"
}

python -m src.review.generate_winner_feature_score_time_dashboard --env .env --output "reports/winner_feature_score_time_dashboard.html" --top-n 10
if ($LASTEXITCODE -ne 0) {
    throw "generate_winner_feature_score_time_dashboard failed"
}

$reportPath = Resolve-Path "reports/winner_feature_score_time_dashboard.html"
Write-Host "Report: $reportPath"
Write-Host "=== DONE scripts/build_winner_feature_score_time_dashboard.ps1 ==="
