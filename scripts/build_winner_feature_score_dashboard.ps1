$ErrorActionPreference = "Stop"

Set-Location -Path (Resolve-Path "$PSScriptRoot\..")

Write-Host "=== Leader_Lab Winner Feature Score Dashboard ==="
Write-Host "RepoRoot: $(Get-Location)"

if (-not (Test-Path ".env")) {
    Write-Host "[WARN] .env 파일이 없습니다. 환경변수 또는 .env.example을 확인하세요."
}

python -m py_compile src/review/generate_winner_feature_score_dashboard.py
if ($LASTEXITCODE -ne 0) {
    throw "py_compile generate_winner_feature_score_dashboard failed"
}

python -m src.review.generate_winner_feature_score_dashboard --env .env --output "reports/winner_feature_score_dashboard.html" --top-n 10
if ($LASTEXITCODE -ne 0) {
    throw "generate_winner_feature_score_dashboard failed"
}

$reportPath = Resolve-Path "reports/winner_feature_score_dashboard.html"
Write-Host "Report: $reportPath"
Start-Process $reportPath

Write-Host "=== DONE scripts/build_winner_feature_score_dashboard.ps1 ==="
