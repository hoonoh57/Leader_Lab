$ErrorActionPreference = "Stop"

Set-Location -Path (Resolve-Path "$PSScriptRoot\..")

Write-Host "=== Leader_Lab GREAT ST Early Signature Discovery ==="
Write-Host "RepoRoot: $(Get-Location)"

python -m py_compile src/analysis/build_great_st_early_signature.py
if ($LASTEXITCODE -ne 0) {
    throw "py_compile build_great_st_early_signature failed"
}

python -m src.analysis.build_great_st_early_signature --env .env --rebuild
if ($LASTEXITCODE -ne 0) {
    throw "build_great_st_early_signature failed"
}

Write-Host "=== DONE scripts/build_great_st_early_signature.ps1 ==="
