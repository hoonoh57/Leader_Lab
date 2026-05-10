$ErrorActionPreference = "Stop"

Set-Location -Path (Resolve-Path "$PSScriptRoot\..")

Write-Host "=== Leader_Lab SuperTrend Regime Discovery ==="
Write-Host "RepoRoot: $(Get-Location)"

python -m py_compile src/analysis/build_supertrend_regime_discovery.py
if ($LASTEXITCODE -ne 0) {
    throw "py_compile build_supertrend_regime_discovery failed"
}

python -m src.analysis.build_supertrend_regime_discovery --env .env --rebuild --params "7:1.5,7:2.0,10:2.0,14:2.0"
if ($LASTEXITCODE -ne 0) {
    throw "build_supertrend_regime_discovery failed"
}

Write-Host "=== DONE scripts/build_supertrend_regime_discovery.ps1 ==="
