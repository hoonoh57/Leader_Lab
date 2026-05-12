#requires -Version 5.1
$ErrorActionPreference = "Stop"

Write-Host "=== BUILD v2.4 ST Top Candidate Board UI ==="

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PyFile = Join-Path $ScriptDir "build_supertrend_top_candidate_board_ui_v2_4.py"

if (-not (Test-Path $PyFile)) {
    Write-Host "Python builder not found: $PyFile"
    exit 1
}

$ArgsList = @(
    $PyFile,
    "--source-table", "supertrend_realtime_trade_board_screen_v2_3",
    "--preview-limit", "40"
)

& py -3 @ArgsList
if ($LASTEXITCODE -ne 0) {
    Write-Host "build_supertrend_top_candidate_board_ui_v2_4 failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "=== DONE scripts/build_supertrend_top_candidate_board_ui_v2_4.ps1 ==="
