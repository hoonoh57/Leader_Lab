param(
    [switch]$CommitAndPush
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== UPDATE TODO AFTER Causal Board Guard v1 ==='

$required = @(
    'START_HERE.md',
    'docs/workflow_server_editing_v1.md',
    'docs/powershell_script_rule_v1.md',
    'docs/pre_edit_reading_rule_v1.md',
    'docs/todo_update_rule_v1.md',
    'docs/session_handoff_2026_05_13_causal_board_guard_v1.md',
    'scripts/audit_existing_v3_test_logic_v3_8c.ps1',
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
$marker = 'Causal Board Guard v1 handoff completed'

if ($todo.Contains($marker) -eq $false) {
    $block = @'

---

## Current Guardrail: Causal Board / Answer Board Separation

- [x] Causal Board Guard v1 handoff completed
  - document: `docs/session_handoff_2026_05_13_causal_board_guard_v1.md`
  - START document updated: `START_HERE.md`
  - pre-edit rule updated: `docs/pre_edit_reading_rule_v1.md`
  - reason: prevent confusing mixed-date research boards with selected-date or live buy-priority boards.

### Mandatory next-session first task

- [ ] Read `START_HERE.md`
- [ ] Read `docs/session_handoff_2026_05_13_causal_board_guard_v1.md`
- [ ] Run or review `scripts/audit_existing_v3_test_logic_v3_8c.ps1`
- [ ] Locate the exact builder or SQL that created existing v2.0/v2.1 causal score fields:
  - `supertrend_realtime_entry_candidate_v2_0`
  - `supertrend_realtime_entry_top_candidate_v2_1`
  - `execution_score_v1_9`
  - `score_total`
  - `filter_score_v1_6`
  - `entry_score_v2_0`
  - `top_rank_score_v2_1`
- [ ] Do not create a new score formula until the existing causal score logic is located and audited.

### Board-type declaration required before implementation

Every future board/ranking/scoring response must declare:

```text
Board Type: CAUSAL_BOARD / ANSWER_BOARD / RESEARCH_BOARD / SELECTED_DATE_BOARD
Selected Date: explicit date or NONE
Universe Source: explicit table
Rank Basis: causal fields or answer fields
Leakage Status: PASS / FAIL / NOT YET AUDITED
```

### Fixed interpretation

```text
v3.8 selected-date board = ANSWER_BOARD / validation board.
v3.4 LIVE_COMPACT smoke UI = RESEARCH_BOARD unless an explicit selected date is shown.
v2.0/v2.1 candidate tables = likely causal score source; must locate builder before reuse.
```
'@

    $anchor = '### 현재 최우선 진행 중'
    $pos = $todo.IndexOf($anchor)
    if ($pos -ge 0) {
        $todo = $todo.Substring(0, $pos) + $block + "`r`n" + $todo.Substring($pos)
    } else {
        $todo = $todo + "`r`n" + $block
    }

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($todoPath, $todo, $utf8NoBom)
    Write-Host 'todo_list.md updated with Causal Board Guard v1 block.'
} else {
    Write-Host 'todo_list.md already contains Causal Board Guard v1 marker.'
}

Write-Host '=== VERIFY TODO MARKER ==='
Select-String -Path $todoPath -Pattern 'Causal Board Guard v1 handoff completed|Board Type: CAUSAL_BOARD|top_rank_score_v2_1|Do not create a new score formula' | ForEach-Object { Write-Host $_.Line }

if ($CommitAndPush) {
    $status = git status --porcelain
    if ($status) {
        git add todo_list.md scripts/update_todo_after_causal_board_guard_v1.ps1
        git commit -m 'docs: mark causal board guard handoff in todo'
        git push origin main
    } else {
        Write-Host 'No git changes to commit.'
    }
}

Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE update_todo_after_causal_board_guard_v1.ps1 ==='
