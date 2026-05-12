#requires -Version 5.1
$ErrorActionPreference = "Stop"

Write-Host "=== BUILD v2.3 ST Realtime Trade Board Screen ==="

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PyFile = Join-Path $ScriptDir "build_supertrend_realtime_trade_board_screen_v2_3.py"

if (-not (Test-Path $PyFile)) {
    Write-Host "Python builder not found: $PyFile"
    exit 1
}

$ArgsList = @(
    $PyFile,
    "--source-table", "supertrend_realtime_trade_board_v2_2",
    "--wait-min-display-score", "85",
    "--hoga-compact-min-display-score", "80",
    "--hoga-compact-min-return-pct", "12",
    "--hoga-compact-min-mae-pct", "-2.5",
    "--compact-example-top-n", "80",
    "--test-hoga-example-top-n", "120"
)

& py -3 @ArgsList
if ($LASTEXITCODE -ne 0) {
    Write-Host "build_supertrend_realtime_trade_board_screen_v2_3 failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "=== DONE scripts/build_supertrend_realtime_trade_board_screen_v2_3.ps1 ==="
