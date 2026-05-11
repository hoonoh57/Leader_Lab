param(
    [string]$SourceTable = "supertrend_start_entry_filter_detail_v1_6",
    [string]$CandleTable = "",
    [string]$FilterGrade = "A",
    [string]$FilterLabel = "ST_START_A_FAST_LEADER",
    [int]$Limit = 0,
    [int]$ExampleTopN = 30,
    [int]$SessionEndHour = 15,
    [int]$SessionEndMinute = 30,
    [int]$MaxBarsAfterStart = 420,
    [int]$PullbackLookaheadBars = 10,
    [double]$PullbackMinPct = 0.8,
    [double]$PullbackMaxBreakPct = 1.5,
    [int]$RebreakLookaheadBars = 10,
    [double]$RebreakBufferPct = 0.05
)

$ErrorActionPreference = "Stop"

Write-Host "=== BUILD v1.8 ST_START Intraday Timing ==="

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$pyFile = Join-Path $scriptDir "build_supertrend_start_entry_intraday_timing_v1_8.py"

if (-not (Test-Path $pyFile)) {
    throw "Python script not found: $pyFile"
}

$culture = [Globalization.CultureInfo]::InvariantCulture

$argsList = @(
    $pyFile,
    "--source-table", $SourceTable,
    "--filter-grade", $FilterGrade,
    "--filter-label", $FilterLabel,
    "--example-top-n", $ExampleTopN.ToString(),
    "--session-end-hour", $SessionEndHour.ToString(),
    "--session-end-minute", $SessionEndMinute.ToString(),
    "--max-bars-after-start", $MaxBarsAfterStart.ToString(),
    "--pullback-lookahead-bars", $PullbackLookaheadBars.ToString(),
    "--pullback-min-pct", $PullbackMinPct.ToString($culture),
    "--pullback-max-break-pct", $PullbackMaxBreakPct.ToString($culture),
    "--rebreak-lookahead-bars", $RebreakLookaheadBars.ToString(),
    "--rebreak-buffer-pct", $RebreakBufferPct.ToString($culture)
)

if ($CandleTable -ne "") {
    $argsList += @("--candle-table", $CandleTable)
}

if ($Limit -gt 0) {
    $argsList += @("--limit", $Limit.ToString())
}

Push-Location $repoRoot
try {
    & py -3 @argsList
    if ($LASTEXITCODE -ne 0) {
        throw "build_supertrend_start_entry_intraday_timing_v1_8 failed"
    }
}
finally {
    Pop-Location
}
