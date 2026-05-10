$ErrorActionPreference = "Stop"

Set-Location -Path (Resolve-Path "$PSScriptRoot\..")

Write-Host "=== Leader_Lab Radar Pullback Entry Evaluation ==="
Write-Host "RepoRoot: $(Get-Location)"

if (-not (Test-Path ".env")) {
    Write-Host "[WARN] .env 파일이 없습니다. 환경변수 또는 .env.example을 확인하세요."
}

python -m py_compile src/analysis/build_radar_pullback_entry_eval.py
if ($LASTEXITCODE -ne 0) {
    throw "py_compile build_radar_pullback_entry_eval failed"
}

python -m src.analysis.build_radar_pullback_entry_eval --env .env --rebuild `
    --radar-thresholds "2.0,2.5,3.0,3.5,4.0" `
    --pullback-depths "2.0,3.0,5.0" `
    --max-pullback-bars "6,9,12" `
    --volume-shrink-ratios "0.7,0.5"
if ($LASTEXITCODE -ne 0) {
    throw "build_radar_pullback_entry_eval failed"
}

Write-Host "=== DONE scripts/build_radar_pullback_entry_eval.ps1 ==="
