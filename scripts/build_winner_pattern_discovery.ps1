$ErrorActionPreference = "Stop"

Set-Location -Path (Resolve-Path "$PSScriptRoot\..")

Write-Host "=== Leader_Lab Winner Pattern Discovery ==="
Write-Host "RepoRoot: $(Get-Location)"

if (-not (Test-Path ".env")) {
    Write-Host "[WARN] .env 파일이 없습니다. 환경변수 또는 .env.example을 확인하세요."
}

python -m py_compile src/analysis/build_winner_pattern_discovery.py
if ($LASTEXITCODE -ne 0) {
    throw "py_compile build_winner_pattern_discovery failed"
}

python -m src.analysis.build_winner_pattern_discovery --env .env --rebuild --output "reports/winner_pattern_discovery_report.html"
if ($LASTEXITCODE -ne 0) {
    throw "build_winner_pattern_discovery failed"
}

$reportPath = Resolve-Path "reports/winner_pattern_discovery_report.html"
Write-Host "Report: $reportPath"
Start-Process $reportPath

Write-Host "=== DONE scripts/build_winner_pattern_discovery.ps1 ==="
