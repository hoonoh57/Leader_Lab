$ErrorActionPreference = "Stop"

Set-Location -Path (Resolve-Path "$PSScriptRoot\..")

Write-Host "=== Leader_Lab build_hypothesis_validation_v1 ==="
Write-Host "RepoRoot: $(Get-Location)"

if (-not (Test-Path ".env")) {
    Write-Host "[WARN] .env 파일이 없습니다. 환경변수 또는 .env.example을 확인하세요."
}

python -m py_compile src/analysis/build_hypothesis_validation_v1.py
if ($LASTEXITCODE -ne 0) {
    throw "py_compile build_hypothesis_validation_v1 failed"
}

python -m src.analysis.build_hypothesis_validation_v1 --env .env --rebuild --threshold-pct 5.0
if ($LASTEXITCODE -ne 0) {
    throw "build_hypothesis_validation_v1 failed"
}

Write-Host "=== DONE scripts/build_hypothesis_validation_v1.ps1 ==="
