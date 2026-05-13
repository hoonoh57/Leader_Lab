param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== INSPECT MainForm v3.5a ==='

$required = @(
    'START_HERE.md',
    'docs/workflow_server_editing_v1.md',
    'docs/powershell_script_rule_v1.md',
    'docs/pre_edit_reading_rule_v1.md',
    'docs/todo_update_rule_v1.md',
    'vbnet/frmTopCandidateBoard.vb',
    'todo_list.md'
)

foreach ($rel in $required) {
    $p = Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p)) { throw ('Missing required file: ' + $rel) }
    Write-Host ('OK ' + $rel)
}

Write-Host '=== PROJECT FILES ==='
Get-ChildItem -LiteralPath $root -Recurse -File -Include *.vbproj,*.sln -ErrorAction Stop |
    Where-Object { $_.FullName -notmatch '\\.git\\' } |
    Sort-Object FullName |
    ForEach-Object { Write-Host ($_.FullName.Substring($root.Length + 1)) }

Write-Host '=== VB FILES WITH MAINFORM NAMES ==='
Get-ChildItem -LiteralPath $root -Recurse -File -Include *Main*.vb,*Form*.vb,*Board*.vb -ErrorAction Stop |
    Where-Object { $_.FullName -notmatch '\\.git\\' } |
    Sort-Object FullName |
    ForEach-Object { Write-Host ($_.FullName.Substring($root.Length + 1)) }

Write-Host '=== CONTENT HITS ==='
$vbFiles = Get-ChildItem -LiteralPath $root -Recurse -File -Include *.vb -ErrorAction Stop | Where-Object { $_.FullName -notmatch '\\.git\\' }
Select-String -Path ($vbFiles.FullName) -Pattern 'Class MainForm|Class frmMain|Application.Run|DockPanel|ChartBoard|OpenChart|TopCandidateBoard' -CaseSensitive:$false -ErrorAction SilentlyContinue |
    Select-Object -First 120 |
    ForEach-Object { Write-Host ($_.Path.Substring($root.Length + 1) + ':' + $_.LineNumber + ': ' + $_.Line.Trim()) }

Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE inspect_mainform_v3_5a.ps1 ==='
