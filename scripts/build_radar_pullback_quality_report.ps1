$ErrorActionPreference = "Stop"

Set-Location -Path (Resolve-Path "$PSScriptRoot\..")

Write-Host "=== Leader_Lab Radar Pullback Quality Report ==="
Write-Host "RepoRoot: $(Get-Location)"

if (-not (Test-Path ".env")) {
    Write-Host "[WARN] .env 파일이 없습니다. 환경변수 또는 .env.example을 확인하세요."
}

python -m py_compile src/analysis/build_radar_pullback_quality_report.py
if ($LASTEXITCODE -ne 0) {
    throw "py_compile build_radar_pullback_quality_report failed"
}

python -m src.analysis.build_radar_pullback_quality_report --env .env --output "reports/radar_pullback_quality_report.html"
if ($LASTEXITCODE -ne 0) {
    throw "build_radar_pullback_quality_report failed"
}

$reportPath = Resolve-Path "reports/radar_pullback_quality_report.html"
Write-Host "Report: $reportPath"
Start-Process $reportPath

Write-Host "=== DONE scripts/build_radar_pullback_quality_report.ps1 ==="
