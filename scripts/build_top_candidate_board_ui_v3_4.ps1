param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== VERIFY Top Candidate Board UI v3.4 ==='

$required = @(
    'START_HERE.md',
    'docs/workflow_server_editing_v1.md',
    'docs/powershell_script_rule_v1.md',
    'docs/pre_edit_reading_rule_v1.md',
    'docs/todo_update_rule_v1.md',
    'docs/top_candidate_board_contract_v3_0.md',
    'vbnet/frmTopCandidateBoard.vb',
    'todo_list.md'
)

foreach ($rel in $required) {
    $p = Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p)) {
        throw ('Missing required file: ' + $rel)
    }
    Write-Host ('OK ' + $rel)
}

$formPath = Join-Path $root 'vbnet/frmTopCandidateBoard.vb'
$form = Get-Content -LiteralPath $formPath -Raw -Encoding UTF8

$tokens = @(
    'Option Strict On',
    'Option Explicit On',
    'Option Infer Off',
    'LIVE_COMPACT',
    'LIVE_COMPACT_V3_4',
    'TEST_ALL_V3_4',
    'PROMOTED_WATCH_ONLY',
    'REJECT_ONLY_V3_4',
    'supertrend_top_candidate_board_dedup_view_v2_9',
    'supertrend_top_candidate_board_raw_view_v2_9',
    'supertrend_top_candidate_board_dedup_view_v3_4',
    'supertrend_top_candidate_board_raw_view_v3_4',
    'board_action_v3_4 AS board_action_display',
    'promotion_flag_display',
    'promotion_reason_v3_4',
    'PROMOTE_REJECT_TO_WATCH',
    'BuildSelectColumnSqlV29',
    'BuildSelectColumnSqlV34'
)

Write-Host '=== VERIFY TOKENS ==='
foreach ($token in $tokens) {
    if ($form.Contains($token) -eq $false) {
        throw ('Missing token: ' + $token)
    }
    Write-Host ('OK token: ' + $token)
}

Write-Host ('form_bytes=' + (Get-Item -LiteralPath $formPath).Length)
Write-Host 'modes= LIVE_COMPACT, LIVE_COMPACT_V3_4, TEST_ALL, TEST_ALL_V3_4, AUTO_BUY_ONLY, WATCH_ONLY, PROMOTED_WATCH_ONLY, REJECT_ONLY, REJECT_ONLY_V3_4'
Write-Host 'next= run app compile or wire MainForm/Docking ToolWindow'

Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE build_top_candidate_board_ui_v3_4.ps1 ==='
