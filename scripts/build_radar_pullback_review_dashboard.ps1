$ErrorActionPreference = "Stop"

Set-Location -Path (Resolve-Path "$PSScriptRoot\..")

Write-Host "=== Leader_Lab Radar Pullback Review Dashboard ==="
Write-Host "RepoRoot: $(Get-Location)"

if (-not (Test-Path ".env")) {
    Write-Host "[WARN] .env 파일이 없습니다. 환경변수 또는 .env.example을 확인하세요."
}

python -m py_compile src/review/generate_radar_pullback_review_dashboard.py
if ($LASTEXITCODE -ne 0) {
    throw "py_compile generate_radar_pullback_review_dashboard failed"
}

python -m src.review.generate_radar_pullback_review_dashboard --env .env --output "reports/radar_pullback_review_dashboard.html"
if ($LASTEXITCODE -ne 0) {
    throw "generate_radar_pullback_review_dashboard failed"
}

$reportPath = Resolve-Path "reports/radar_pullback_review_dashboard.html"
Write-Host "Report: $reportPath"
Start-Process $reportPath

Write-Host "=== DONE scripts/build_radar_pullback_review_dashboard.ps1 ==="
