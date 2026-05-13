param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== INSPECT MainForm v3.5b ==='

$required = @(
    'START_HERE.md',
    'docs/workflow_server_editing_v1.md',
    'docs/powershell_script_rule_v1.md',
    'docs/pre_edit_reading_rule_v1.md',
    'docs/todo_update_rule_v1.md',
    'vbnet/frmTopCandidateBoard.vb',
    'vbnet/TopCandidateBoardIntegrationGuide.vb',
    'todo_list.md'
)

foreach ($rel in $required) {
    $p = Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p)) { throw ('Missing required file: ' + $rel) }
    Write-Host ('OK ' + $rel)
}

Write-Host '=== EXACT SOLUTION AND PROJECT FILES ==='
$projectFiles = Get-ChildItem -LiteralPath $root -Recurse -File -ErrorAction Stop |
    Where-Object {
        $_.FullName -notmatch '\\.git\\' -and
        ($_.Extension.Equals('.sln', [System.StringComparison]::OrdinalIgnoreCase) -or $_.Extension.Equals('.vbproj', [System.StringComparison]::OrdinalIgnoreCase))
    } |
    Sort-Object FullName

if ($projectFiles.Count -eq 0) {
    Write-Host 'NO_SOLUTION_OR_VBPROJ_FOUND'
} else {
    foreach ($f in $projectFiles) { Write-Host ($f.FullName.Substring($root.Length + 1)) }
}

Write-Host '=== EXACT MAINFORM CANDIDATES ==='
$vbFiles = Get-ChildItem -LiteralPath $root -Recurse -File -Filter *.vb -ErrorAction Stop |
    Where-Object { $_.FullName -notmatch '\\.git\\' } |
    Sort-Object FullName

$hits = Select-String -Path ($vbFiles.FullName) -Pattern 'Public Class MainForm|Public Class frmMain|Class MainForm|Class frmMain|Application.Run|DockPanel|ChartBoard|OpenChart' -CaseSensitive:$false -ErrorAction SilentlyContinue
if ($hits.Count -eq 0) {
    Write-Host 'NO_MAINFORM_OR_APP_SHELL_FOUND'
} else {
    foreach ($h in ($hits | Select-Object -First 120)) {
        Write-Host ($h.Path.Substring($root.Length + 1) + ':' + $h.LineNumber + ': ' + $h.Line.Trim())
    }
}

Write-Host '=== TOP CANDIDATE BOARD STATUS ==='
$formPath = Join-Path $root 'vbnet/frmTopCandidateBoard.vb'
$form = Get-Content -LiteralPath $formPath -Raw -Encoding UTF8
foreach ($token in @('Public Class frmTopCandidateBoard','LIVE_COMPACT_V3_4','PROMOTED_WATCH_ONLY','CandidateActivated')) {
    if ($form.Contains($token)) { Write-Host ('OK token ' + $token) } else { throw ('Missing token ' + $token) }
}

Write-Host '=== DECISION ==='
if ($projectFiles.Count -eq 0 -and $hits.Count -eq 0) {
    Write-Host 'NEXT=CREATE_STANDALONE_SMOKE_HOST'
} else {
    Write-Host 'NEXT=PATCH_EXISTING_MAINFORM_OR_PROJECT'
}

Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE inspect_mainform_v3_5b.ps1 ==='
