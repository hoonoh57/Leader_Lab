$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$pyPath = Join-Path $root 'src/review/build_leader_reaccel_parametric_v1.py'
if (-not (Test-Path -LiteralPath $pyPath)) {
    throw 'Missing python file: src/review/build_leader_reaccel_parametric_v1.py'
}

$py = Get-Content -LiteralPath $pyPath -Raw -Encoding UTF8

# v1.4 local patch could create this malformed line:
#     breakfirst_bar = first_day_bar(...)
# Python compiles it as an assignment to variable breakfirst_bar, so first_bar remains undefined.
$py = $py.Replace('breakfirst_bar = first_day_bar(candles, candidate["trade_date"])', 'break' + "`r`n`r`n" + '    first_bar = first_day_bar(candles, candidate["trade_date"])')

# If the malformed line was not present and first_bar assignment is still missing, insert it safely.
if ($py -notmatch '^[ \t]*first_bar\s*=\s*first_day_bar\(candles,\s*candidate\["trade_date"\]\)' ) {
    $pattern = '(?m)^(\s*first_open_return\s*=\s*None\s*)$'
    if ($py -notmatch $pattern) {
        throw 'Could not find first_open_return = None insertion point'
    }
    $py = [regex]::Replace(
        $py,
        $pattern,
        '    first_bar = first_day_bar(candles, candidate["trade_date"])' + "`r`n" + '$1',
        1
    )
}

# Verify first_bar assignment appears before the first reference in this function.
$idxAssign = $py.IndexOf('first_bar = first_day_bar(candles, candidate["trade_date"])')
$idxUse = $py.IndexOf('if first_bar is not None:')
if ($idxAssign -lt 0 -or $idxUse -lt 0 -or $idxAssign -gt $idxUse) {
    throw 'first_bar assignment is still missing or after first use'
}

Set-Content -LiteralPath $pyPath -Value $py -Encoding UTF8

Write-Host '=== SANITY CHECK: first_bar block ==='
Select-String -Path $pyPath -Pattern 'breakfirst_bar|first_bar = first_day_bar|if first_bar is not None' | ForEach-Object { $_.Line }

if ((Select-String -Path $pyPath -Pattern 'breakfirst_bar' -SimpleMatch).Count -gt 0) {
    throw 'Malformed breakfirst_bar still exists'
}

Write-Host '=== PY COMPILE ==='
python -m py_compile src/review/build_leader_reaccel_parametric_v1.py
if ($LASTEXITCODE -ne 0) { throw 'py_compile failed' }

Write-Host 'OK hotfixed Leader Reaccel v1.5'
