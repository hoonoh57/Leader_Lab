param(
    [switch]$CommitAndPush
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== UPDATE TODO AFTER UI v3.4 ==='

$required = @(
    'START_HERE.md',
    'docs/workflow_server_editing_v1.md',
    'docs/powershell_script_rule_v1.md',
    'docs/pre_edit_reading_rule_v1.md',
    'docs/todo_update_rule_v1.md',
    'scripts/build_top_candidate_board_ui_v3_4.ps1',
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

$todoPath = Join-Path $root 'todo_list.md'
$todo = Get-Content -LiteralPath $todoPath -Raw -Encoding UTF8
$marker = 'Top Candidate Board UI v3.4 verified'

if ($todo.Contains($marker) -eq $false) {
    $block = @'

- [x] Top Candidate Board UI v3.4 verified
  - file: `vbnet/frmTopCandidateBoard.vb`
  - script: `scripts/build_top_candidate_board_ui_v3_4.ps1`
  - added modes:
    - `LIVE_COMPACT_V3_4`
    - `TEST_ALL_V3_4`
    - `PROMOTED_WATCH_ONLY`
    - `REJECT_ONLY_V3_4`
  - preserved v2.9 modes:
    - `LIVE_COMPACT`
    - `TEST_ALL`
    - `AUTO_BUY_ONLY`
    - `WATCH_ONLY`
    - `REJECT_ONLY`
  - default mode: `LIVE_COMPACT_V3_4`
  - interpretation: UI can compare v2.9 compact board and v3.4 promoted compact board.
  - next step: compile/run app or wire MainForm/Docking ToolWindow.
'@

    $anchor = 'Top Candidate Board Promotion v3.4 verified'
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
    Write-Host 'todo_list.md updated with UI v3.4 completion.'
} else {
    Write-Host 'todo_list.md already contains UI v3.4 marker.'
}

Write-Host '=== VERIFY TODO MARKER ==='
Select-String -Path $todoPath -Pattern 'Top Candidate Board UI v3.4 verified|LIVE_COMPACT_V3_4|PROMOTED_WATCH_ONLY' | ForEach-Object { Write-Host $_.Line }

if ($CommitAndPush) {
    $status = git status --porcelain
    if ($status) {
        git add todo_list.md scripts/update_todo_after_ui_v3_4.ps1 .gitignore
        git commit -m 'docs: mark top candidate board UI v3.4 verified'
        git push origin main
    } else {
        Write-Host 'No git changes to commit.'
    }
}

Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE update_todo_after_ui_v3_4.ps1 ==='
