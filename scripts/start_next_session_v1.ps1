param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$required = @(
    'START_HERE.md',
    'docs/workflow_server_editing_v1.md',
    'docs/powershell_script_rule_v1.md',
    'docs/pre_edit_reading_rule_v1.md',
    'docs/todo_update_rule_v1.md',
    'todo_list.md'
)

Write-Host '=== START NEXT SESSION v1 ==='

foreach ($rel in $required) {
    $p = Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p)) {
        throw ('Missing required file: ' + $rel)
    }
    Write-Host ('OK ' + $rel)
}

Write-Host '=== REQUIRED READING ORDER ==='
foreach ($rel in $required) {
    Write-Host $rel
}

Write-Host '=== CURRENT PRIORITY HINT ==='
Select-String -Path (Join-Path $root 'START_HERE.md') -Pattern 'SuperTrend Chart Consistency Gate' | ForEach-Object { Write-Host $_.Line }
Select-String -Path (Join-Path $root 'todo_list.md') -Pattern 'Chart Consistency Gate|Top Candidate Board v3.2 integration guide verified' | ForEach-Object { Write-Host $_.Line }

Write-Host '=== NEXT CHAT REQUEST ==='
Write-Host 'Continue hoonoh57/Leader_Lab from START_HERE.md.'

Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE start_next_session_v1.ps1 ==='
