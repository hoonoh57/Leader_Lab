param(
    [string]$SourceTable = "",
    [ValidateSet("v13", "v12")]
    [string]$Prefer = "v13",
    [int]$Limit = 0,
    [int]$EarlyTopN = 3,
    [double]$WeakReturnPct = 2.0,
    [double]$SuccessReturnPct = 5.0
)

$ErrorActionPreference = "Stop"

Write-Host "=== BUILD v1.5 ST_START vs EARLY3 Failure Diagnostics ==="

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$pyFile = Join-Path $scriptDir "build_supertrend_start_vs_early3_failure_v1_5.py"

if (-not (Test-Path $pyFile)) {
    throw "Python script not found: $pyFile"
}

$argsList = @(
    $pyFile,
    "--prefer", $Prefer,
    "--early-top-n", $EarlyTopN.ToString(),
    "--weak-return-pct", $WeakReturnPct.ToString([Globalization.CultureInfo]::InvariantCulture),
    "--success-return-pct", $SuccessReturnPct.ToString([Globalization.CultureInfo]::InvariantCulture)
)

if ($SourceTable.Trim().Length -gt 0) {
    $argsList += @("--source-table", $SourceTable.Trim())
}

if ($Limit -gt 0) {
    $argsList += @("--limit", $Limit.ToString())
}

Push-Location $repoRoot
try {
    & py -3 @argsList
    if ($LASTEXITCODE -ne 0) {
        throw "build_supertrend_start_vs_early3_failure_v1_5 failed"
    }
}
finally {
    Pop-Location
}
