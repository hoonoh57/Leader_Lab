$ErrorActionPreference = "Stop"

Set-Location -Path (Resolve-Path "$PSScriptRoot\..")

Write-Host "=== Leader_Lab Time-Aware Winner Feature Score v2 ==="
Write-Host "RepoRoot: $(Get-Location)"

if (-not (Test-Path ".env")) {
    Write-Host "[WARN] .env 파일이 없습니다. 환경변수 또는 .env.example을 확인하세요."
}

python -m py_compile src/analysis/build_winner_feature_score_time.py
if ($LASTEXITCODE -ne 0) {
    throw "py_compile build_winner_feature_score_time failed"
}

python -m src.analysis.build_winner_feature_score_time --env .env --rebuild --decision-times "09:20,09:30,10:00,10:30,11:00,13:00"
if ($LASTEXITCODE -ne 0) {
    throw "build_winner_feature_score_time failed"
}

Write-Host "=== DONE scripts/build_winner_feature_score_time.ps1 ==="
