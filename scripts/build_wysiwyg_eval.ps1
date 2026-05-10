$ErrorActionPreference = "Stop"

Set-Location -Path (Resolve-Path "$PSScriptRoot\..")

Write-Host "=== Leader_Lab build_wysiwyg_eval ==="
Write-Host "RepoRoot: $(Get-Location)"

if (-not (Test-Path ".env")) {
    Write-Host "[WARN] .env 파일이 없습니다. 환경변수 또는 .env.example을 확인하세요."
}

python -m py_compile src/evaluation/build_wysiwyg_eval.py
if ($LASTEXITCODE -ne 0) {
    throw "py_compile build_wysiwyg_eval failed"
}

python -m src.evaluation.build_wysiwyg_eval --env .env --rebuild
if ($LASTEXITCODE -ne 0) {
    throw "build_wysiwyg_eval failed"
}

Write-Host "=== DONE scripts/build_wysiwyg_eval.ps1 ==="
