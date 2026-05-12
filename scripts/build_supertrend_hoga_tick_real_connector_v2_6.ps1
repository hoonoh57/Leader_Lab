#requires -Version 5.1
$ErrorActionPreference = "Stop"

Write-Host "=== BUILD v2.6 ST Real Hoga/Tick Connector ==="

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PyFile = Join-Path $ScriptDir "build_supertrend_hoga_tick_real_connector_v2_6.py"

if (-not (Test-Path $PyFile)) {
    Write-Host "Python builder not found: $PyFile"
    exit 1
}

$Env:PYTHONPATH = $ScriptDir + ";" + $Env:PYTHONPATH

$ArgsList = @(
    $PyFile,
    "--source-table", "supertrend_hoga_tick_confirm_view_v2_5",
    "--realtime-table", "supertrend_realtime_hoga_tick_snapshot",
    "--preview-limit", "40",
    "--example-top-n", "80"
)

& py -3 @ArgsList
if ($LASTEXITCODE -ne 0) {
    Write-Host "build_supertrend_hoga_tick_real_connector_v2_6 failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "=== DONE scripts/build_supertrend_hoga_tick_real_connector_v2_6.ps1 ==="
