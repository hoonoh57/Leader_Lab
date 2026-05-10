$ErrorActionPreference = "Stop"

Set-Location -Path (Resolve-Path "$PSScriptRoot\..")

Write-Host "=== Leader_Lab build_5m_analysis_result ==="
Write-Host "RepoRoot: $(Get-Location)"

if (-not (Test-Path ".env")) {
    Write-Host "[WARN] .env 파일이 없습니다. 환경변수 또는 .env.example을 확인하세요."
}

python -m py_compile src/analysis/build_5m_analysis_result.py
if ($LASTEXITCODE -ne 0) {
    throw "py_compile build_5m_analysis_result failed"
}

python -m py_compile src/analysis/apply_market_closed.py
if ($LASTEXITCODE -ne 0) {
    throw "py_compile apply_market_closed failed"
}

python -m src.analysis.build_5m_analysis_result --env .env --rebuild
if ($LASTEXITCODE -ne 0) {
    throw "build_5m_analysis_result failed"
}

python -m src.analysis.apply_market_closed --env .env --calendar configs/krx_market_closed_2026.json
if ($LASTEXITCODE -ne 0) {
    throw "apply_market_closed failed"
}

Write-Host "=== DONE scripts/build_5m_analysis_result.ps1 ==="
