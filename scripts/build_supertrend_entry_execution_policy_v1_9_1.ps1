#requires -Version 5.1
$ErrorActionPreference = "Stop"

Write-Host "=== BUILD v1.9.1 ST Entry Execution Policy Hotfix ==="

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PyFile = Join-Path $ScriptDir "build_supertrend_entry_execution_policy_v1_9_1.py"

if (-not (Test-Path $PyFile)) {
    throw "Python builder not found: $PyFile"
}

$ArgsList = @(
    $PyFile,
    "--source-table", "supertrend_start_entry_intraday_timing_detail_v1_8",
    "--filter-grade", "A",
    "--filter-label", "ST_START_A_FAST_LEADER",
    "--example-top-n", "120"
)

try {
    & py -3 @ArgsList
    if ($LASTEXITCODE -ne 0) {
        throw "build_supertrend_entry_execution_policy_v1_9_1 failed with exit code $LASTEXITCODE"
    }
}
catch {
    throw "build_supertrend_entry_execution_policy_v1_9_1 failed: $($_.Exception.Message)"
}

Write-Host "=== DONE scripts/build_supertrend_entry_execution_policy_v1_9_1.ps1 ==="
