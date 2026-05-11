#requires -Version 5.1
$ErrorActionPreference = "Stop"

Write-Host "=== BUILD v2.0 ST Realtime Entry Candidate ==="

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PyFile = Join-Path $ScriptDir "build_supertrend_realtime_entry_candidate_v2_0.py"

if (-not (Test-Path $PyFile)) {
    throw "Python builder not found: $PyFile"
}

$ArgsList = @(
    $PyFile,
    "--source-table", "supertrend_entry_execution_policy_detail_v1_9",
    "--only-filter-grade", "A",
    "--only-filter-label", "ST_START_A_FAST_LEADER",
    "--example-top-n", "120",
    "--auto-min-execution-score", "90",
    "--auto-min-entry-score", "88",
    "--auto-min-return-pct", "10",
    "--auto-min-mae-pct", "-1.5",
    "--auto-min-amount", "3000000000",
    "--auto-max-open-pct", "4.8",
    "--auto-max-low-pct", "7.5"
)

try {
    & py -3 @ArgsList
    if ($LASTEXITCODE -ne 0) {
        throw "build_supertrend_realtime_entry_candidate_v2_0 failed with exit code $LASTEXITCODE"
    }
}
catch {
    throw "build_supertrend_realtime_entry_candidate_v2_0 failed: $($_.Exception.Message)"
}

Write-Host "=== DONE scripts/build_supertrend_realtime_entry_candidate_v2_0.ps1 ==="
