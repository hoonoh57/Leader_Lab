#requires -Version 5.1
$ErrorActionPreference = "Stop"

Write-Host "=== BUILD v2.2 ST Realtime Trade Board ==="

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PyFile = Join-Path $ScriptDir "build_supertrend_realtime_trade_board_v2_2.py"

if (-not (Test-Path $PyFile)) {
    Write-Host "Python builder not found: $PyFile"
    exit 1
}

$ArgsList = @(
    $PyFile,
    "--source-table", "supertrend_realtime_entry_top_candidate_v2_1",
    "--example-top-n", "120",
    "--include-confirm", "1",
    "--min-display-score", "0"
)

& py -3 @ArgsList
if ($LASTEXITCODE -ne 0) {
    Write-Host "build_supertrend_realtime_trade_board_v2_2 failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "=== DONE scripts/build_supertrend_realtime_trade_board_v2_2.ps1 ==="
