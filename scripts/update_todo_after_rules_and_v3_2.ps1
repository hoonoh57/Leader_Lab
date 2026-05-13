param(
    [switch]$CommitAndPush
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$todoPath = Join-Path $root 'todo_list.md'
$requiredDocs = @(
    'docs/workflow_server_editing_v1.md',
    'docs/powershell_script_rule_v1.md',
    'docs/pre_edit_reading_rule_v1.md',
    'docs/todo_update_rule_v1.md'
)

Write-Host '=== UPDATE TODO AFTER RULES AND v3.2 ==='

if (-not (Test-Path -LiteralPath $todoPath)) {
    throw 'Missing todo_list.md'
}

foreach ($rel in $requiredDocs) {
    $p = Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p)) {
        throw ('Missing rule doc: ' + $rel)
    }
}

$todo = Get-Content -LiteralPath $todoPath -Raw -Encoding UTF8
$changed = $false

if ($todo.Contains('docs/workflow_server_editing_v1.md') -eq $false) {
    $ruleBlock = @'

### Mandatory repository working rules

Before any future code, script, or document modification, read and follow:

```text
docs/workflow_server_editing_v1.md
docs/powershell_script_rule_v1.md
docs/pre_edit_reading_rule_v1.md
docs/todo_update_rule_v1.md
todo_list.md
latest task handoff document in docs/
```

Server-first editing remains mandatory. GitHub/server files are created or modified first. Local work is limited to pull, run the versioned script, and status verification.

PowerShell scripts must be Windows PowerShell 5.1 safe. Use ASCII-only ps1 source by default. If Korean text must be written by ps1, write it through UTF-8 Base64 decoding, not direct Korean string literals.
'@

    $anchor = '## 2.'
    $pos = $todo.IndexOf($anchor)
    if ($pos -lt 0) {
        throw 'Could not find section anchor: ## 2.'
    }
    $todo = $todo.Substring(0, $pos) + $ruleBlock + "`r`n" + $todo.Substring($pos)
    $changed = $true
}

if ($todo.Contains('Top Candidate Board v3.2 integration guide verified') -eq $false) {
    $doneBlock = @'
- [x] Top Candidate Board v3.2 integration guide verified
  - docs/top_candidate_board_integration_v3_2.md
  - vbnet/TopCandidateBoardIntegrationGuide.vb
  - vbnet/frmTopCandidateBoard.vb
  - verification script: scripts/build_top_candidate_board_integration_v3_2.ps1
  - observed result: integration tokens OK, working tree clean
  - next step: SuperTrend Chart Consistency Gate
'@

    $sectionPos = $todo.IndexOf('## 3.')
    if ($sectionPos -lt 0) {
        throw 'Could not find section anchor: ## 3.'
    }
    $needle = 'reports/supertrend_regime_discovery_dashboard.html'
    $reportPos = $todo.IndexOf($needle, $sectionPos)
    if ($reportPos -lt 0) {
        throw 'Could not find report line after section 3.'
    }
    $lineEnd = $todo.IndexOf("`n", $reportPos)
    if ($lineEnd -lt 0) {
        $lineEnd = $todo.Length
    } else {
        $lineEnd = $lineEnd + 1
    }
    $todo = $todo.Substring(0, $lineEnd) + $doneBlock + $todo.Substring($lineEnd)
    $changed = $true
}

if ($changed) {
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($todoPath, $todo, $utf8NoBom)
    Write-Host 'todo_list.md updated.'
} else {
    Write-Host 'todo_list.md already up to date.'
}

Write-Host '=== VERIFY TODO RULE LINKS ==='
foreach ($rel in $requiredDocs) {
    Select-String -Path $todoPath -Pattern ([regex]::Escape($rel)) | ForEach-Object { Write-Host $_.Line }
}
Select-String -Path $todoPath -Pattern 'Top Candidate Board v3.2 integration guide verified|SuperTrend Chart Consistency Gate' | ForEach-Object { Write-Host $_.Line }

if ($CommitAndPush) {
    $status = git status --porcelain
    if ($status) {
        git add todo_list.md scripts/update_todo_after_rules_and_v3_2.ps1 docs/workflow_server_editing_v1.md docs/powershell_script_rule_v1.md docs/pre_edit_reading_rule_v1.md docs/todo_update_rule_v1.md
        git commit -m 'docs: record working rules and v3.2 completion in todo'
        git push origin main
    } else {
        Write-Host 'No git changes to commit.'
    }
}

Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE update_todo_after_rules_and_v3_2.ps1 ==='
