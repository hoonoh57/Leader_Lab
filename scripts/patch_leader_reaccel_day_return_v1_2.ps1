$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$pyPath = Join-Path $root 'src/review/build_leader_reaccel_parametric_v1.py'
$psPath = Join-Path $root 'scripts/build_leader_reaccel_parametric_v1.ps1'

if (-not (Test-Path -LiteralPath $pyPath)) { throw 'Missing python file: src/review/build_leader_reaccel_parametric_v1.py' }
if (-not (Test-Path -LiteralPath $psPath)) { throw 'Missing runner file: scripts/build_leader_reaccel_parametric_v1.ps1' }

$py = Get-Content -LiteralPath $pyPath -Raw -Encoding UTF8
$ps = Get-Content -LiteralPath $psPath -Raw -Encoding UTF8

# 1. Add Python CLI parameter.
if ($py -notmatch '--day-close-return-min-pct') {
    $pattern = '(?m)^(\s*parser\.add_argument\("--bar-return-min-pcts",\s*default="[^"]+"\)\s*)$'
    if ($py -notmatch $pattern) { throw 'Could not find --bar-return-min-pcts argparse line' }
    $py = [regex]::Replace($py, $pattern, '$1' + "`r`n" + '    parser.add_argument("--day-close-return-min-pct", type=float, default=0.0)', 1)
}

# 2. Add previous-day close calculation immediately after date parse block inside find_signal_for_params.
if ($py -notmatch 'prev_day_close_for_signal') {
    $pattern = '(?s)(\s*d\s*=\s*base\.parse_date\(candidate\["trade_date"\]\)\s*\r?\n\s*if\s+d\s+is\s+None:\s*\r?\n\s*return\s+None\s*)'
    if ($py -notmatch $pattern) { throw 'Could not find date-parse block for previous-day close insertion' }
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

# 3. Add day close return right after bar_ret calculation.
if ($py -notmatch 'day_close_return_pct\s*=\s*pct\(close,\s*prev_day_close_for_signal\)') {
    $pattern = '(?m)^(\s*bar_ret\s*=\s*\(close\s*/\s*prev_close\s*-\s*1\.0\)\s*\*\s*100\.0\s*)$'
    if ($py -notmatch $pattern) { throw 'Could not find bar_ret calculation line' }
    $py = [regex]::Replace($py, $pattern, '$1' + "`r`n" + '        day_close_return_pct = pct(close, prev_day_close_for_signal)', 1)
}

# 4. Replace candle_ok assignment with OR(day close return >= threshold).
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

# 5. Add output column.
if ($py -notmatch '"day_close_return_pct"\s*:\s*day_close_return_pct') {
    $pattern = '(?m)^(\s*"bar_return_pct":\s*bar_ret,\s*)$'
    if ($py -notmatch $pattern) { throw 'Could not find output bar_return_pct line' }
    $py = [regex]::Replace($py, $pattern, '$1' + "`r`n" + '                "day_close_return_pct": day_close_return_pct,', 1)
}

# 6. Make summary/detail table include day_close_return_pct if present.
if ($py -notmatch '"day_close_return_pct", "bar_amount"') {
    $py = $py.Replace('"bar_return_pct", "bar_amount"', '"bar_return_pct", "day_close_return_pct", "bar_amount"')
}

# 7. Add runner parameter.
if ($ps -notmatch '\$DayCloseReturnMinPct') {
    $pattern = '(?m)^(\s*\[string\]\$BarReturnMinPcts\s*=\s*''[^'']+'',\s*)$'
    if ($ps -notmatch $pattern) { throw 'Could not find runner BarReturnMinPcts parameter line' }
    $ps = [regex]::Replace($ps, $pattern, '$1' + "`r`n" + '    [string]$DayCloseReturnMinPct = ''0'',', 1)
}

# 8. Forward runner argument.
if ($ps -notmatch '--day-close-return-min-pct=') {
    $pattern = '(?m)^(\s*\(''--bar-return-min-pcts=''\s*\+\s*\$BarReturnMinPcts\),\s*)$'
    if ($ps -notmatch $pattern) { throw 'Could not find runner --bar-return-min-pcts args line' }
    $ps = [regex]::Replace($ps, $pattern, '$1' + "`r`n" + "    ('--day-close-return-min-pct=' + `$DayCloseReturnMinPct),", 1)
}

Set-Content -LiteralPath $pyPath -Value $py -Encoding UTF8
Set-Content -LiteralPath $psPath -Value $ps -Encoding UTF8

Write-Host '=== PY COMPILE ==='
python -m py_compile src/review/build_leader_reaccel_parametric_v1.py
if ($LASTEXITCODE -ne 0) { throw 'py_compile failed' }

Write-Host 'OK patched Leader Reaccel v1.2'
Write-Host 'Condition now uses: bar_return_pct >= threshold OR day_close_return_pct >= DayCloseReturnMinPct'
Write-Host '=== GIT DIFF ==='
git diff -- src/review/build_leader_reaccel_parametric_v1.py scripts/build_leader_reaccel_parametric_v1.ps1
