$ErrorActionPreference = "Stop"

Set-Location -Path (Resolve-Path "$PSScriptRoot\..")

Write-Host "=== Leader_Lab build_exit_strategy_simulation ==="
Write-Host "RepoRoot: $(Get-Location)"

if (-not (Test-Path ".env")) {
    Write-Host "[WARN] .env 파일이 없습니다. 환경변수 또는 .env.example을 확인하세요."
}

python -m py_compile src/analysis/build_exit_strategy_simulation.py
if ($LASTEXITCODE -ne 0) {
    throw "py_compile build_exit_strategy_simulation failed"
}

python -m src.analysis.build_exit_strategy_simulation --env .env --rebuild
if ($LASTEXITCODE -ne 0) {
    throw "build_exit_strategy_simulation failed"
}

Write-Host "=== DONE scripts/build_exit_strategy_simulation.ps1 ==="
