param(
    [switch]$CommitAndPush
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== UPDATE TODO AFTER Smoke Host v3.6 ==='

$required = @(
    'START_HERE.md',
    'docs/workflow_server_editing_v1.md',
    'docs/powershell_script_rule_v1.md',
    'docs/pre_edit_reading_rule_v1.md',
    'docs/todo_update_rule_v1.md',
    'scripts/build_top_candidate_board_smoke_host_v3_6.ps1',
    'vbnet/frmTopCandidateBoard.vb',
    'vbnet/TopCandidateBoardSmokeHost/Program.vb',
    'vbnet/TopCandidateBoardSmokeHost/TopCandidateBoardSmokeHost.vbproj',
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
$marker = 'Top Candidate Board Smoke Host v3.6 verified'

if ($todo.Contains($marker) -eq $false) {
    $block = @'

- [x] Top Candidate Board Smoke Host v3.6 verified
  - project: `vbnet/TopCandidateBoardSmokeHost/TopCandidateBoardSmokeHost.vbproj`
  - program: `vbnet/TopCandidateBoardSmokeHost/Program.vb`
  - script: `scripts/build_top_candidate_board_smoke_host_v3_6.ps1`
  - target framework: `.NET Framework 4.8`
  - package: `MySql.Data 8.4.0`
  - form: `frmTopCandidateBoard.vb`
  - verified result:
    - restore success
    - build success
    - warnings: `0`
    - errors: `0`
    - exe: `vbnet/TopCandidateBoardSmokeHost/bin/Debug/TopCandidateBoardSmokeHost.exe`
  - next step: run smoke host with `-Run`, refresh `LIVE_COMPACT_V3_4`, and verify DB rows and double-click `CandidateActivated` event.
'@

    $anchor = 'Top Candidate Board UI v3.4 verified'
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
    Write-Host 'todo_list.md updated with Smoke Host v3.6 completion.'
} else {
    Write-Host 'todo_list.md already contains Smoke Host v3.6 marker.'
}

Write-Host '=== VERIFY TODO MARKER ==='
Select-String -Path $todoPath -Pattern 'Top Candidate Board Smoke Host v3.6 verified|TopCandidateBoardSmokeHost.exe|LIVE_COMPACT_V3_4' | ForEach-Object { Write-Host $_.Line }

if ($CommitAndPush) {
    $status = git status --porcelain
    if ($status) {
        git add todo_list.md scripts/update_todo_after_smoke_host_v3_6.ps1 .gitignore
        git commit -m 'docs: mark top candidate board smoke host v3.6 verified'
        git push origin main
    } else {
        Write-Host 'No git changes to commit.'
    }
}

Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE update_todo_after_smoke_host_v3_6.ps1 ==='
