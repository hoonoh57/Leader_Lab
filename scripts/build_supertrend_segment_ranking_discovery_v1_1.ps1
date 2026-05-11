$ErrorActionPreference = "Stop"

Set-Location -Path (Resolve-Path "$PSScriptRoot\..")

Write-Host "=== Leader_Lab SuperTrend Segment Ranking Discovery v1.1 ==="
Write-Host "RepoRoot: $(Get-Location)"

python -m py_compile src/analysis/build_supertrend_segment_ranking_discovery_v1_1.py
if ($LASTEXITCODE -ne 0) {
    throw "py_compile build_supertrend_segment_ranking_discovery_v1_1 failed"
}

python -m src.analysis.build_supertrend_segment_ranking_discovery_v1_1 --env .env --rebuild
if ($LASTEXITCODE -ne 0) {
    throw "build_supertrend_segment_ranking_discovery_v1_1 failed"
}

Write-Host "=== DONE scripts/build_supertrend_segment_ranking_discovery_v1_1.ps1 ==="
