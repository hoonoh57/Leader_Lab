param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== INSPECT SuperTrend Chart Gate v1 ==='

$required = @(
    'START_HERE.md',
    'docs/workflow_server_editing_v1.md',
    'docs/powershell_script_rule_v1.md',
    'docs/pre_edit_reading_rule_v1.md',
    'docs/todo_update_rule_v1.md',
    'docs/supertrend_chart_consistency_gate.md',
    'todo_list.md'
)

foreach ($rel in $required) {
    if (-not (Test-Path -LiteralPath (Join-Path $root $rel))) {
        throw ('Missing required file: ' + $rel)
    }
    Write-Host ('OK ' + $rel)
}

Write-Host '=== CANDIDATE FILES ==='
$patterns = @('supertrend', 'regime', 'dashboard', 'plotly', 'st_')
$files = Get-ChildItem -LiteralPath $root -Recurse -File -ErrorAction Stop |
    Where-Object {
        $full = $_.FullName
        if ($full -match '\\.git\\') { return $false }
        if ($full -match '\\reports\\') { return $false }
        if ($full -match '\\__pycache__\\') { return $false }
        $name = $_.Name.ToLowerInvariant()
        foreach ($pat in $patterns) {
            if ($name.Contains($pat)) { return $true }
        }
        return $false
    } |
    Sort-Object FullName

foreach ($f in $files) {
    $rel = $f.FullName.Substring($root.Length + 1)
    Write-Host $rel
}

Write-Host '=== CONTENT HITS ==='
$scanExt = @('.py', '.ps1', '.md', '.html', '.js', '.sql')
$scanFiles = Get-ChildItem -LiteralPath $root -Recurse -File -ErrorAction Stop |
    Where-Object {
        $full = $_.FullName
        if ($full -match '\\.git\\') { return $false }
        if ($full -match '\\reports\\') { return $false }
        if ($full -match '\\__pycache__\\') { return $false }
        return $scanExt -contains $_.Extension.ToLowerInvariant()
    }

$hitPattern = 'supertrend|SuperTrend|regime_discovery|Plotly|candlestick|segment'
$hits = Select-String -Path ($scanFiles.FullName) -Pattern $hitPattern -CaseSensitive:$false -ErrorAction SilentlyContinue |
    Select-Object -First 120

foreach ($h in $hits) {
    $rel = $h.Path.Substring($root.Length + 1)
    Write-Host ($rel + ':' + $h.LineNumber + ': ' + $h.Line.Trim())
}

Write-Host '=== REPORT FILES ==='
$reportDir = Join-Path $root 'reports'
if (Test-Path -LiteralPath $reportDir) {
    Get-ChildItem -LiteralPath $reportDir -File -ErrorAction Stop |
        Sort-Object Name |
        ForEach-Object { Write-Host ($_.FullName.Substring($root.Length + 1) + ' bytes=' + $_.Length) }
} else {
    Write-Host 'reports directory not found'
}

Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE inspect_supertrend_chart_gate_v1.ps1 ==='
