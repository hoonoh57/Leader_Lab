param(
    [switch]$CommitAndPush
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== UPDATE TODO AFTER Promotion v3.4 ==='

$required = @(
    'START_HERE.md',
    'docs/workflow_server_editing_v1.md',
    'docs/powershell_script_rule_v1.md',
    'docs/pre_edit_reading_rule_v1.md',
    'docs/todo_update_rule_v1.md',
    'docs/st_dashboard_live_overlay_research_v1.md',
    'docs/live_candidate_overlay_on_st_dashboard_v1.md',
    'docs/top_candidate_board_contract_v3_0.md',
    'scripts/build_top_candidate_board_promotion_v3_4.ps1',
    'todo_list.md'
)

foreach ($rel in $required) {
    $p = Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p)) {
        throw ('Missing required file: ' + $rel)
    }
    Write-Host ('OK ' + $rel)
}

$todoPath = Join-Path $root 'todo_list.md'
$todo = Get-Content -LiteralPath $todoPath -Raw -Encoding UTF8
$marker = 'Top Candidate Board Promotion v3.4 verified'

if ($todo.Contains($marker) -eq $false) {
    $block = @'

- [x] Top Candidate Board Promotion v3.4 verified
  - script: `scripts/build_top_candidate_board_promotion_v3_4.ps1`
  - output tables:
    - `supertrend_top_candidate_board_raw_view_v3_4`
    - `supertrend_top_candidate_board_dedup_view_v3_4`
    - `supertrend_top_candidate_board_summary_v3_4`
    - `supertrend_top_candidate_board_examples_v3_4`
  - DEDUP result:
    - `AUTO_BUY_READY=1`
    - `WATCH_HOGA_TICK=6`
    - `PROMOTE_REJECT_TO_WATCH=7`
    - `REJECT=47`
  - live compact v3.4 total: `14`
  - promotion gate:
    - `tick_confirm_score >= 30`
    - `spread_risk <= 35`
    - `buy_tick_ratio >= 60`
    - `hoga_bid_pressure >= 55`
    - `hoga_ask_absorption >= 55`
  - interpretation: v3.4 keeps v2.9 intact and adds a conservative REJECT-to-WATCH promotion layer.
  - next step: add v3.4 modes to `frmTopCandidateBoard.vb` without removing v2.9 modes.
'@

    $anchor = 'Top Candidate Board v3.2 integration guide verified'
    $pos = $todo.IndexOf($anchor)
    if ($pos -ge 0) {
        $lineEnd = $todo.IndexOf("`n", $pos)
        if ($lineEnd -lt 0) { $lineEnd = $todo.Length } else { $lineEnd = $lineEnd + 1 }
        $todo = $todo.Substring(0, $lineEnd) + $block + $todo.Substring($lineEnd)
    } else {
        $todo = $todo + "`r`n" + $block
    }

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($todoPath, $todo, $utf8NoBom)
    Write-Host 'todo_list.md updated with Promotion v3.4 completion.'
} else {
    Write-Host 'todo_list.md already contains Promotion v3.4 marker.'
}

Write-Host '=== VERIFY TODO MARKER ==='
Select-String -Path $todoPath -Pattern 'Top Candidate Board Promotion v3.4 verified|PROMOTE_REJECT_TO_WATCH|live compact v3.4 total' | ForEach-Object { Write-Host $_.Line }

if ($CommitAndPush) {
    $status = git status --porcelain
    if ($status) {
        git add todo_list.md scripts/update_todo_after_promotion_v3_4.ps1
        git commit -m 'docs: mark top candidate promotion v3.4 verified'
        git push origin main
    } else {
        Write-Host 'No git changes to commit.'
    }
}

Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE update_todo_after_promotion_v3_4.ps1 ==='
