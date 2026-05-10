$ErrorActionPreference = "Stop"

Set-Location -Path (Resolve-Path "$PSScriptRoot\..")

Write-Host "=== Leader_Lab SuperTrend Regime Discovery Dashboard ==="
Write-Host "RepoRoot: $(Get-Location)"

python -m py_compile src/review/generate_supertrend_regime_discovery_dashboard_v3.py
if ($LASTEXITCODE -ne 0) {
    throw "py_compile generate_supertrend_regime_discovery_dashboard_v3 failed"
}

python -m src.review.generate_supertrend_regime_discovery_dashboard_v3 --env .env --output "reports/supertrend_regime_discovery_dashboard.html" --limit 12000 --warmup-bars 80 --prev-display-start "12:00"
if ($LASTEXITCODE -ne 0) {
    throw "generate_supertrend_regime_discovery_dashboard_v3 failed"
}

$reportPath = Resolve-Path "reports/supertrend_regime_discovery_dashboard.html"
Write-Host "Report: $reportPath"
Write-Host "=== DONE scripts/build_supertrend_regime_discovery_dashboard.ps1 ==="
