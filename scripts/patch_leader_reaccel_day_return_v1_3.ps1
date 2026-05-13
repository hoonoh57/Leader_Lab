$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$pyPath = Join-Path $root 'src/review/build_leader_reaccel_parametric_v1.py'
$psPath = Join-Path $root 'scripts/build_leader_reaccel_parametric_v1.ps1'

if (-not (Test-Path -LiteralPath $pyPath)) { throw 'Missing python file: src/review/build_leader_reaccel_parametric_v1.py' }
if (-not (Test-Path -LiteralPath $psPath)) { throw 'Missing runner file: scripts/build_leader_reaccel_parametric_v1.ps1' }

$py = Get-Content -LiteralPath $pyPath -Raw -Encoding UTF8
$ps = Get-Content -LiteralPath $psPath -Raw -Encoding UTF8

# 1) Add Python CLI parameter if missing.
if ($py -notmatch '--day-close-return-min-pct') {
    $pattern = '(?m)^(\s*parser\.add_argument\("--bar-return-min-pcts",\s*default="[^"]+"\)\s*)$'
    if ($py -notmatch $pattern) { throw 'Could not find --bar-return-min-pcts argparse line' }
    $py = [regex]::Replace($py, $pattern, '$1' + "`r`n" + '    parser.add_argument("--day-close-return-min-pct", type=float, default=0.0)', 1)
}

# 2) Ensure previous-day close block exists immediately after date parse.
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

# 3) HOTFIX: Ensure first_bar assignment exists before first_bar is referenced.
# The prior v1.2 patch could insert prev_day_close block but accidentally leave first_bar undefined in some local file shapes.
if ($py -match 'if\s+first_bar\s+is\s+not\s+None:' -and $py -notmatch 'first_bar\s*=\s*first_day_bar\(candles,\s*candidate\["trade_date"\]\)') {
    $pattern = '(?m)^(\s*prev_close_for_first\s*=\s*base\.previous_close_from_candles\s+if\s+False\s+else\s+None\s*)$'
    if ($py -match $pattern) {
        $py = [regex]::Replace($py, $pattern, '    first_bar = first_day_bar(candles, candidate["trade_date"])' + "`r`n" + '$1', 1)
    } else {
        $pattern2 = '(?m)^(\s*first_open_return\s*=\s*None\s*)$'
        if ($py -notmatch $pattern2) { throw 'Could not find first_bar insertion point' }
        $py = [regex]::Replace($py, $pattern2, '    first_bar = first_day_bar(candles, candidate["trade_date"])' + "`r`n" + '$1', 1)
    }
}

# 4) Remove useless prev_close_for_first assignment if present.
$py = [regex]::Replace($py, '(?m)^\s*prev_close_for_first\s*=\s*base\.previous_close_from_candles\s+if\s+False\s+else\s+None\s*\r?\n', '')

# 5) Add day close return calculation right after bar_ret if missing.
if ($py -notmatch 'day_close_return_pct\s*=\s*pct\(close,\s*prev_day_close_for_signal\)') {
    $pattern = '(?m)^(\s*bar_ret\s*=\s*\(close\s*/\s*prev_close\s*-\s*1\.0\)\s*\*\s*100\.0\s*)$'
    if ($py -notmatch $pattern) { throw 'Could not find bar_ret calculation line' }
    $py = [regex]::Replace($py, $pattern, '$1' + "`r`n" + '        day_close_return_pct = pct(close, prev_day_close_for_signal)', 1)
}

# 6) Replace candle_ok with OR day_close_return condition if not already done.
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

# 7) Add output column.
if ($py -notmatch '"day_close_return_pct"\s*:\s*day_close_return_pct') {
    $pattern = '(?m)^(\s*"bar_return_pct":\s*bar_ret,\s*)$'
    if ($py -notmatch $pattern) { throw 'Could not find output bar_return_pct line' }
    $py = [regex]::Replace($py, $pattern, '$1' + "`r`n" + '                "day_close_return_pct": day_close_return_pct,', 1)
}

# 8) Add day_close_return_pct to visible detail if possible.
if ($py -notmatch 'day_close_return_pct", "bar_amount') {
    $py = $py.Replace('"bar_return_pct", "bar_amount"', '"bar_return_pct", "day_close_return_pct", "bar_amount"')
}

# 9) Add runner parameter if missing.
if ($ps -notmatch '\$DayCloseReturnMinPct') {
    $pattern = '(?m)^(\s*\[string\]\$BarReturnMinPcts\s*=\s*''[^'']+'',\s*)$'
    if ($ps -notmatch $pattern) { throw 'Could not find runner BarReturnMinPcts parameter line' }
    $ps = [regex]::Replace($ps, $pattern, '$1' + "`r`n" + '    [string]$DayCloseReturnMinPct = ''0'',', 1)
}

# 10) Forward runner argument if missing.
if ($ps -notmatch '--day-close-return-min-pct=') {
    $pattern = '(?m)^(\s*\(''--bar-return-min-pcts=''\s*\+\s*\$BarReturnMinPcts\),\s*)$'
    if ($ps -notmatch $pattern) { throw 'Could not find runner --bar-return-min-pcts args line' }
    $ps = [regex]::Replace($ps, $pattern, '$1' + "`r`n" + "    ('--day-close-return-min-pct=' + `$DayCloseReturnMinPct),", 1)
}

Set-Content -LiteralPath $pyPath -Value $py -Encoding UTF8
Set-Content -LiteralPath $psPath -Value $ps -Encoding UTF8

Write-Host '=== SANITY CHECK ==='
Select-String -Path $pyPath -Pattern 'prev_day_close_for_signal|first_bar = first_day_bar|day_close_return_pct|day_return_ok|candle_ok =' | ForEach-Object { $_.Line }

Write-Host '=== PY COMPILE ==='
python -m py_compile src/review/build_leader_reaccel_parametric_v1.py
if ($LASTEXITCODE -ne 0) { throw 'py_compile failed' }

Write-Host 'OK patched Leader Reaccel v1.3'
Write-Host 'Condition now uses: bar_return_pct >= threshold OR day_close_return_pct >= DayCloseReturnMinPct'
