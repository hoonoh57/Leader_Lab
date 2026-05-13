param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== INSPECT Live Candidate Overlay Inputs v1 ==='

$required = @(
    'START_HERE.md',
    'docs/workflow_server_editing_v1.md',
    'docs/powershell_script_rule_v1.md',
    'docs/pre_edit_reading_rule_v1.md',
    'docs/todo_update_rule_v1.md',
    'docs/st_dashboard_live_overlay_research_v1.md',
    'docs/live_candidate_overlay_on_st_dashboard_v1.md',
    'docs/top_candidate_board_contract_v3_0.md',
    'todo_list.md'
)

foreach ($rel in $required) {
    $p = Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p)) {
        throw ('Missing required file: ' + $rel)
    }
    Write-Host ('OK ' + $rel)
}

$py = Join-Path $root 'scripts/inspect_live_candidate_overlay_inputs_v1.py'
if (-not (Test-Path -LiteralPath $py)) {
    throw 'Missing scripts/inspect_live_candidate_overlay_inputs_v1.py'
}

python -m py_compile scripts/inspect_live_candidate_overlay_inputs_v1.py
if ($LASTEXITCODE -ne 0) {
    throw 'py_compile failed: scripts/inspect_live_candidate_overlay_inputs_v1.py'
}

python scripts/inspect_live_candidate_overlay_inputs_v1.py --env .env
if ($LASTEXITCODE -ne 0) {
    throw 'inspect_live_candidate_overlay_inputs_v1.py failed'
}

Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE inspect_live_candidate_overlay_inputs_v1.ps1 ==='
