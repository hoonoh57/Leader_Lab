$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$pyPath = Join-Path $root 'src/review/build_leader_reaccel_parametric_v1.py'
if (-not (Test-Path -LiteralPath $pyPath)) {
    throw 'Missing python file: src/review/build_leader_reaccel_parametric_v1.py'
}

$py = Get-Content -LiteralPath $pyPath -Raw -Encoding UTF8

# Direct minimal hotfix:
# If the code references first_bar but the assignment is missing, insert it immediately before first_open_return = None.
if ($py -notmatch 'first_bar\s*=\s*first_day_bar\(candles,\s*candidate\["trade_date"\]\)') {
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

# Ensure day-close-return option exists. This keeps the intended v1.2/v1.3 behavior.
if ($py -notmatch '--day-close-return-min-pct') {
    $pattern = '(?m)^(\s*parser\.add_argument\("--bar-return-min-pcts",\s*default="[^"]+"\)\s*)$'
    if ($py -notmatch $pattern) { throw 'Could not find --bar-return-min-pcts argparse line' }
    $py = [regex]::Replace($py, $pattern, '$1' + "`r`n" + '    parser.add_argument("--day-close-return-min-pct", type=float, default=0.0)', 1)
}

if ($py -notmatch 'prev_day_close_for_signal\s*:') {
    $pattern = '(?s)(\s*d\s*=\s*base\.parse_date\(candidate\["trade_date"\]\)\s*\r?\n\s*if\s+d\s+is\s+None:\s*\r?\n\s*return\s+None\s*)'
    if ($py -notmatch $pattern) { throw 'Could not find date parse block' }
    $insert = @'

    prev_day_close_for_signal: Optional[float] = None
    for prev_row in candles:
        prev_ts = candle_dt(prev_row)
        if prev_ts is None:
            continue
        if prev_ts.date() < d:
            prev_close_value = get_num(prev_row, "close")
            if prev_close_value is not None and prev_close_value > 0:
                prev_day_close_for_signal = prev_close_value
        elif prev_ts.date() == d:
            break
'@
    $py = [regex]::Replace($py, $pattern, '$1' + $insert, 1)
}

if ($py -notmatch 'day_close_return_pct\s*=\s*pct\(close,\s*prev_day_close_for_signal\)') {
    $pattern = '(?m)^(\s*bar_ret\s*=\s*\(close\s*/\s*prev_close\s*-\s*1\.0\)\s*\*\s*100\.0\s*)$'
    if ($py -notmatch $pattern) { throw 'Could not find bar_ret calculation line' }
    $py = [regex]::Replace($py, $pattern, '$1' + "`r`n" + '        day_close_return_pct = pct(close, prev_day_close_for_signal)', 1)
}

if ($py -notmatch 'day_return_ok\s*=\s*False') {
    $pattern = '(?m)^\s*candle_ok\s*=\s*bar_ret\s*>=\s*float\(params\["bar_return_min_pct"\]\)\s*$'
    if ($py -notmatch $pattern) { throw 'Could not find candle_ok assignment line' }
    $replacement = @'
        day_return_ok = False
        if args.day_close_return_min_pct > 0 and day_close_return_pct is not None:
            day_return_ok = day_close_return_pct >= args.day_close_return_min_pct
        candle_ok = bar_ret >= float(params["bar_return_min_pct"]) or day_return_ok
'@.TrimEnd()
    $py = [regex]::Replace($py, $pattern, $replacement, 1)
}

if ($py -notmatch '"day_close_return_pct"\s*:\s*day_close_return_pct') {
    $pattern = '(?m)^(\s*"bar_return_pct":\s*bar_ret,\s*)$'
    if ($py -notmatch $pattern) { throw 'Could not find output bar_return_pct line' }
    $py = [regex]::Replace($py, $pattern, '$1' + "`r`n" + '                "day_close_return_pct": day_close_return_pct,', 1)
}

Set-Content -LiteralPath $pyPath -Value $py -Encoding UTF8

Write-Host '=== SANITY CHECK: first_bar / day return ==='
Select-String -Path $pyPath -Pattern 'first_bar = first_day_bar|if first_bar is not None|prev_day_close_for_signal|day_close_return_pct|day_return_ok|candle_ok =' | ForEach-Object { $_.Line }

Write-Host '=== PY COMPILE ==='
python -m py_compile src/review/build_leader_reaccel_parametric_v1.py
if ($LASTEXITCODE -ne 0) { throw 'py_compile failed' }

Write-Host 'OK hotfixed Leader Reaccel v1.4'
