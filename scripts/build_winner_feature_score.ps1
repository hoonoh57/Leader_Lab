$ErrorActionPreference = "Stop"

Set-Location -Path (Resolve-Path "$PSScriptRoot\..")

Write-Host "=== Leader_Lab Winner Feature Score v1 ==="
Write-Host "RepoRoot: $(Get-Location)"

if (-not (Test-Path ".env")) {
    Write-Host "[WARN] .env 파일이 없습니다. 환경변수 또는 .env.example을 확인하세요."
}

python -m py_compile src/analysis/build_winner_feature_score.py
if ($LASTEXITCODE -ne 0) {
    throw "py_compile build_winner_feature_score failed"
}

python -m src.analysis.build_winner_feature_score --env .env --rebuild
if ($LASTEXITCODE -ne 0) {
    throw "build_winner_feature_score failed"
}

Write-Host "=== DONE scripts/build_winner_feature_score.ps1 ==="
