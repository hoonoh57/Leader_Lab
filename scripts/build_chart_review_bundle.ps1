$ErrorActionPreference = "Stop"

Set-Location -Path (Resolve-Path "$PSScriptRoot\..")

Write-Host "=== Leader_Lab Chart Review Bundle v1 ==="
Write-Host "RepoRoot: $(Get-Location)"

if (-not (Test-Path ".env")) {
    Write-Host "[WARN] .env 파일이 없습니다. 환경변수 또는 .env.example을 확인하세요."
}

python -m py_compile src/review/build_chart_review_case.py
if ($LASTEXITCODE -ne 0) {
    throw "py_compile build_chart_review_case failed"
}

python -m py_compile src/review/generate_chart_review_dashboard.py
if ($LASTEXITCODE -ne 0) {
    throw "py_compile generate_chart_review_dashboard failed"
}

python -m src.review.build_chart_review_case --env .env --rebuild --thresholds "6.0,5.5"
if ($LASTEXITCODE -ne 0) {
    throw "build_chart_review_case failed"
}

python -m src.review.generate_chart_review_dashboard --env .env --output "reports/chart_review_dashboard.html"
if ($LASTEXITCODE -ne 0) {
    throw "generate_chart_review_dashboard failed"
}

$reportPath = Resolve-Path "reports/chart_review_dashboard.html"
Write-Host "Report: $reportPath"
Start-Process $reportPath

Write-Host "=== DONE scripts/build_chart_review_bundle.ps1 ==="
