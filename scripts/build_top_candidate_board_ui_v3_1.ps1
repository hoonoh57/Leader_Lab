#requires -Version 5.1
$ErrorActionPreference = "Stop"

Write-Host "=== VERIFY v3.1 Top Candidate Board UI ==="

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DocPath = Join-Path $Root "docs\top_candidate_board_ui_v3_1.md"
$FormPath = Join-Path $Root "vbnet\frmTopCandidateBoard.vb"

if (-not (Test-Path $DocPath)) {
    throw "Missing doc: $DocPath"
}

if (-not (Test-Path $FormPath)) {
    throw "Missing VB form: $FormPath"
}

$formText = Get-Content -Path $FormPath -Raw -Encoding UTF8
$docText = Get-Content -Path $DocPath -Raw -Encoding UTF8

$requiredFormTokens = @(
    "Option Strict On",
    "Option Explicit On",
    "Option Infer Off",
    "Public Class frmTopCandidateBoard",
    "Public Event CandidateActivated",
    "LIVE_COMPACT",
    "TEST_ALL",
    "AUTO_BUY_ONLY",
    "WATCH_ONLY",
    "REJECT_ONLY",
    "supertrend_top_candidate_board_dedup_view_v2_9",
    "supertrend_top_candidate_board_raw_view_v2_9",
    "ui_live_compact_flag_v2_9",
    "ui_test_all_flag_v2_9",
    "ui_auto_buy_only_flag_v2_9",
    "ui_watch_only_flag_v2_9",
    "ui_reject_only_flag_v2_9",
    "AUTO_BUY_READY",
    "WATCH_HOGA_TICK",
    "REJECT"
)

foreach ($token in $requiredFormTokens) {
    if ($formText.IndexOf($token, [System.StringComparison]::Ordinal) -lt 0) {
        throw "Missing required form token: $token"
    }
}

$requiredDocTokens = @(
    "Top Candidate Board UI v3.1",
    "frmTopCandidateBoard",
    "LIVE_COMPACT",
    "TEST_ALL",
    "WATCH_HOGA_TICK",
    "CandidateActivated"
)

foreach ($token in $requiredDocTokens) {
    if ($docText.IndexOf($token, [System.StringComparison]::Ordinal) -lt 0) {
        throw "Missing required doc token: $token"
    }
}

Write-Host "doc= $DocPath"
Write-Host "form= $FormPath"
Write-Host "form_bytes= $((Get-Item $FormPath).Length)"
Write-Host "doc_bytes= $((Get-Item $DocPath).Length)"
Write-Host "modes= LIVE_COMPACT, TEST_ALL, AUTO_BUY_ONLY, WATCH_ONLY, REJECT_ONLY"
Write-Host "tables= supertrend_top_candidate_board_dedup_view_v2_9, supertrend_top_candidate_board_raw_view_v2_9"
Write-Host "=== DONE scripts/build_top_candidate_board_ui_v3_1.ps1 ==="
