param(
    [string]$SourceTable = "supertrend_start_entry_filter_detail_v1_6",
    [string]$IncludeGrades = "A",
    [int]$Limit = 0,
    [int]$ExampleTopN = 30,
    [double]$SuccessReturnPct = 5.0,
    [double]$WeakReturnPct = 1.0,
    [double]$MaxAllowedDelayPenaltyPct = 2.0,
    [double]$OpenOverheatPct = 9.0,
    [double]$LowOverextendPct = 10.0
)

$ErrorActionPreference = "Stop"

Write-Host "=== BUILD v1.7 ST_START Fast Leader Timing Diagnostics ==="

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$pyFile = Join-Path $scriptDir "build_supertrend_start_fast_leader_timing_v1_7.py"

if (-not (Test-Path $pyFile)) {
    throw "Python script not found: $pyFile"
}

$culture = [Globalization.CultureInfo]::InvariantCulture

$argsList = @(
    $pyFile,
    "--source-table", $SourceTable,
    "--include-grades", $IncludeGrades,
    "--example-top-n", $ExampleTopN.ToString(),
    "--success-return-pct", $SuccessReturnPct.ToString($culture),
    "--weak-return-pct", $WeakReturnPct.ToString($culture),
    "--max-allowed-delay-penalty-pct", $MaxAllowedDelayPenaltyPct.ToString($culture),
    "--open-overheat-pct", $OpenOverheatPct.ToString($culture),
    "--low-overextend-pct", $LowOverextendPct.ToString($culture)
)

if ($Limit -gt 0) {
    $argsList += @("--limit", $Limit.ToString())
}

Push-Location $repoRoot
try {
    & py -3 @argsList
    if ($LASTEXITCODE -ne 0) {
        throw "build_supertrend_start_fast_leader_timing_v1_7 failed"
    }
}
finally {
    Pop-Location
}
