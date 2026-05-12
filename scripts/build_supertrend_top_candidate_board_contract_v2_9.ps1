#requires -Version 5.1
$ErrorActionPreference = "Stop"

Write-Host "=== BUILD v2.9 ST Top Candidate Board Contract ==="

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PyFile = Join-Path $ScriptDir "build_supertrend_top_candidate_board_contract_v2_9.py"

if (-not (Test-Path $PyFile)) {
    Write-Host "Python builder not found: $PyFile"
    exit 1
}

$Env:PYTHONPATH = $ScriptDir + ";" + $Env:PYTHONPATH

$ArgsList = @(
    $PyFile,
    "--source-table", "supertrend_realtime_final_board_view_v2_8",
    "--preview-limit", "80",
    "--example-top-n", "120"
)

& py -3 @ArgsList
if ($LASTEXITCODE -ne 0) {
    Write-Host "build_supertrend_top_candidate_board_contract_v2_9 failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "=== DONE scripts/build_supertrend_top_candidate_board_contract_v2_9.ps1 ==="
