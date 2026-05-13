#requires -Version 5.1
$ErrorActionPreference = "Stop"

Write-Host "=== VERIFY v3.2 Top Candidate Board Integration ==="

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DocPath = Join-Path $Root "docs\top_candidate_board_integration_v3_2.md"
$GuidePath = Join-Path $Root "vbnet\TopCandidateBoardIntegrationGuide.vb"
$FormPath = Join-Path $Root "vbnet\frmTopCandidateBoard.vb"
$ContractDocPath = Join-Path $Root "docs\top_candidate_board_contract_v3_0.md"
$UiDocPath = Join-Path $Root "docs\top_candidate_board_ui_v3_1.md"

$requiredFiles = @($DocPath, $GuidePath, $FormPath, $ContractDocPath, $UiDocPath)
foreach ($path in $requiredFiles) {
    if (-not (Test-Path $path)) {
        throw "Missing required file: $path"
    }
}

$guideText = Get-Content -Path $GuidePath -Raw -Encoding UTF8
$docText = Get-Content -Path $DocPath -Raw -Encoding UTF8
$formText = Get-Content -Path $FormPath -Raw -Encoding UTF8

$requiredGuideTokens = @(
    "Option Strict On",
    "Option Explicit On",
    "Option Infer Off",
    "TopCandidateBoardIntegrationGuide",
    "OpenTopCandidateBoard",
    "OnTopCandidateActivated",
    "CandidateActivated",
    "frmTopCandidateBoard",
    "GetMysqlConnectionString",
    "MYSQL_CONN",
    "Show(Me)",
    "MessageBox.Show"
)

foreach ($token in $requiredGuideTokens) {
    if ($guideText.IndexOf($token, [System.StringComparison]::Ordinal) -lt 0) {
        throw "Missing required integration guide token: $token"
    }
}

$requiredDocTokens = @(
    "Top Candidate Board Integration v3.2",
    "frmTopCandidateBoard",
    "CandidateActivated",
    "OpenTopCandidateBoard",
    "OnTopCandidateActivated",
    "ChartBoard",
    "v3.3"
)

foreach ($token in $requiredDocTokens) {
    if ($docText.IndexOf($token, [System.StringComparison]::Ordinal) -lt 0) {
        throw "Missing required integration doc token: $token"
    }
}

$requiredFormTokens = @(
    "Public Class frmTopCandidateBoard",
    "Public Event CandidateActivated",
    "LIVE_COMPACT",
    "TEST_ALL",
    "WATCH_HOGA_TICK"
)

foreach ($token in $requiredFormTokens) {
    if ($formText.IndexOf($token, [System.StringComparison]::Ordinal) -lt 0) {
        throw "Missing required form token: $token"
    }
}

Write-Host "doc= $DocPath"
Write-Host "guide= $GuidePath"
Write-Host "form= $FormPath"
Write-Host "doc_bytes= $((Get-Item $DocPath).Length)"
Write-Host "guide_bytes= $((Get-Item $GuidePath).Length)"
Write-Host "form_bytes= $((Get-Item $FormPath).Length)"
Write-Host "integration_tokens= OpenTopCandidateBoard, OnTopCandidateActivated, CandidateActivated, frmTopCandidateBoard"
Write-Host "next= v3.3 MainForm actual patch or Docking ToolWindow registration"
Write-Host "=== DONE scripts/build_top_candidate_board_integration_v3_2.ps1 ==="
