#requires -Version 5.1
$ErrorActionPreference = "Stop"

Write-Host "=== BUILD v2.7 ST Realtime Hoga/Tick Snapshot Contract ==="

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PyFile = Join-Path $ScriptDir "build_supertrend_hoga_tick_realtime_snapshot_contract_v2_7.py"

if (-not (Test-Path $PyFile)) {
    Write-Host "Python builder not found: $PyFile"
    exit 1
}

$Env:PYTHONPATH = $ScriptDir + ";" + $Env:PYTHONPATH

$ArgsList = @(
    $PyFile,
    "--source-view", "supertrend_hoga_tick_real_confirm_view_v2_6",
    "--realtime-table", "supertrend_realtime_hoga_tick_snapshot",
    "--seed-test-snapshots",
    "--test-promote-top-n", "7",
    "--preview-limit", "40",
    "--example-top-n", "80"
)

& py -3 @ArgsList
if ($LASTEXITCODE -ne 0) {
    Write-Host "build_supertrend_hoga_tick_realtime_snapshot_contract_v2_7 failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "=== Re-run v2.6 to verify real_join_rows and HOGA_TICK_CONFIRMED_BUY after v2.7 snapshot seed ==="
$V26Ps1 = Join-Path $ScriptDir "build_supertrend_hoga_tick_real_connector_v2_6.ps1"
if (Test-Path $V26Ps1) {
    & $V26Ps1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "build_supertrend_hoga_tick_real_connector_v2_6 verify failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
} else {
    Write-Host "v2.6 verify script not found: $V26Ps1"
}

Write-Host "=== DONE scripts/build_supertrend_hoga_tick_realtime_snapshot_contract_v2_7.ps1 ==="
