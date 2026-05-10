$ErrorActionPreference = "Stop"

Set-Location -Path (Resolve-Path "$PSScriptRoot\..")

Write-Host "=== Leader_Lab GREAT ST Early Score v1 ==="
Write-Host "RepoRoot: $(Get-Location)"

python -m py_compile src/analysis/build_great_st_early_score_v1.py
if ($LASTEXITCODE -ne 0) {
    throw "py_compile build_great_st_early_score_v1 failed"
}

python -m src.analysis.build_great_st_early_score_v1 --env .env --rebuild
if ($LASTEXITCODE -ne 0) {
    throw "build_great_st_early_score_v1 failed"
}

Write-Host "=== DONE scripts/build_great_st_early_score_v1.ps1 ==="
