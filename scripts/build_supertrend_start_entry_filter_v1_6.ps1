param(
    [string]$SourceTable = "supertrend_start_vs_early3_failure_diag_v1_5",
    [int]$Limit = 0,
    [int]$ExampleTopN = 30,
    [double]$WeakReturnPct = 1.0,
    [double]$SuccessReturnPct = 5.0,
    [double]$PostExtensionGoodPct = 3.0,
    [double]$OpenOverheatPct = 9.0,
    [double]$LowOverextendPct = 10.0,
    [double]$MinStartAmount = 1000000000.0,
    [double]$MinScoreTotal = 85.0,
    [double]$LowRiskScore = 5.0,
    [double]$MidRiskScore = 25.0,
    [double]$HighRiskScore = 50.0
)

$ErrorActionPreference = "Stop"

Write-Host "=== BUILD v1.6 ST_START Entry Filter ==="

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$pyFile = Join-Path $scriptDir "build_supertrend_start_entry_filter_v1_6.py"

if (-not (Test-Path $pyFile)) {
    throw "Python script not found: $pyFile"
}

$culture = [Globalization.CultureInfo]::InvariantCulture

$argsList = @(
    $pyFile,
    "--source-table", $SourceTable,
    "--example-top-n", $ExampleTopN.ToString(),
    "--weak-return-pct", $WeakReturnPct.ToString($culture),
    "--success-return-pct", $SuccessReturnPct.ToString($culture),
    "--post-extension-good-pct", $PostExtensionGoodPct.ToString($culture),
    "--open-overheat-pct", $OpenOverheatPct.ToString($culture),
    "--low-overextend-pct", $LowOverextendPct.ToString($culture),
    "--min-start-amount", $MinStartAmount.ToString($culture),
    "--min-score-total", $MinScoreTotal.ToString($culture),
    "--low-risk-score", $LowRiskScore.ToString($culture),
    "--mid-risk-score", $MidRiskScore.ToString($culture),
    "--high-risk-score", $HighRiskScore.ToString($culture)
)

if ($Limit -gt 0) {
    $argsList += @("--limit", $Limit.ToString())
}

Push-Location $repoRoot
try {
    & py -3 @argsList
    if ($LASTEXITCODE -ne 0) {
        throw "build_supertrend_start_entry_filter_v1_6 failed"
    }
}
finally {
    Pop-Location
}
