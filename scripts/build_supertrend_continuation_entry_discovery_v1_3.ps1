$ErrorActionPreference = "Stop"

Set-Location -Path (Resolve-Path "$PSScriptRoot\..")

Write-Host "=== Leader_Lab SuperTrend Continuation Entry Discovery v1.3 ==="
Write-Host "RepoRoot: $(Get-Location)"

python -m py_compile src/analysis/build_supertrend_continuation_entry_discovery_v1_3.py
if ($LASTEXITCODE -ne 0) {
    throw "py_compile build_supertrend_continuation_entry_discovery_v1_3 failed"
}

python -m src.analysis.build_supertrend_continuation_entry_discovery_v1_3 --env .env --rebuild
if ($LASTEXITCODE -ne 0) {
    throw "build_supertrend_continuation_entry_discovery_v1_3 failed"
}

Write-Host "=== DONE scripts/build_supertrend_continuation_entry_discovery_v1_3.ps1 ==="
