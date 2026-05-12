#requires -Version 5.1
$ErrorActionPreference = "Stop"

Write-Host "=== BUILD v2.8 ST Realtime Final Board View ==="

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PyFile = Join-Path $ScriptDir "build_supertrend_realtime_final_board_view_v2_8.py"

if (-not (Test-Path $PyFile)) {
    Write-Host "Python builder not found: $PyFile"
    exit 1
}

$Env:PYTHONPATH = $ScriptDir + ";" + $Env:PYTHONPATH

$ArgsList = @(
    $PyFile,
    "--source-view", "supertrend_hoga_tick_real_confirm_view_v2_6",
    "--preview-limit", "80",
    "--example-top-n", "120"
)

& py -3 @ArgsList
if ($LASTEXITCODE -ne 0) {
    Write-Host "build_supertrend_realtime_final_board_view_v2_8 failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "=== DONE scripts/build_supertrend_realtime_final_board_view_v2_8.ps1 ==="
