$ErrorActionPreference = "Stop"

Set-Location -Path (Resolve-Path "$PSScriptRoot\..")

Write-Host "=== Leader_Lab build_singlebar_threshold_sweep ==="
Write-Host "RepoRoot: $(Get-Location)"

if (-not (Test-Path ".env")) {
    Write-Host "[WARN] .env 파일이 없습니다. 환경변수 또는 .env.example을 확인하세요."
}

python -m py_compile src/analysis/build_singlebar_threshold_sweep.py
if ($LASTEXITCODE -ne 0) {
    throw "py_compile build_singlebar_threshold_sweep failed"
}

python -m src.analysis.build_singlebar_threshold_sweep --env .env --rebuild --thresholds "3.0,3.5,4.0,4.5,5.0,5.5,6.0"
if ($LASTEXITCODE -ne 0) {
    throw "build_singlebar_threshold_sweep failed"
}

Write-Host "=== DONE scripts/build_singlebar_threshold_sweep.ps1 ==="
