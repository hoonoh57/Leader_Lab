$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$pyPath = Join-Path $root 'src/review/build_leader_reaccel_parametric_v1.py'
$psPath = Join-Path $root 'scripts/build_leader_reaccel_parametric_v1.ps1'

if (-not (Test-Path -LiteralPath $pyPath)) { throw 'Missing python file' }
if (-not (Test-Path -LiteralPath $psPath)) { throw 'Missing runner file' }

$py = Get-Content -LiteralPath $pyPath -Raw -Encoding UTF8
$ps = Get-Content -LiteralPath $psPath -Raw -Encoding UTF8

# 1) argparse add --day-close-return-min-pct
if ($py -notmatch '--day-close-return-min-pct') {
    $needle = '    parser.add_argument("--bar-return-min-pcts", default="2,2.5,3")'
    $replace = $needle + "`r`n" + '    parser.add_argument("--day-close-return-min-pct", type=float, default=0.0)'
    if ($py -notlike "*$needle*") { throw 'argparse insertion point not found' }
    $py = $py.Replace($needle, $replace)
}

# 2) compute previous trading day close after date parse
if ($py -notmatch 'prev_day_close_for_signal') {
    $needle = @'
    d = base.parse_date(candidate["trade_date"])
    if d is None:
        return None

    first_bar = first_day_bar(candles, candidate["trade_date"])
'@
    $replace = @'
    d = base.parse_date(candidate["trade_date"])
    if d is None:
        return None

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

    first_bar = first_day_bar(candles, candidate["trade_date"])
'@
    if ($py -notlike "*$needle*") { throw 'previous-day close insertion point not found' }
    $py = $py.Replace($needle, $replace)
}

# 3) add day_close_return_pct after bar_ret calculation
if ($py -notmatch 'day_close_return_pct') {
    $needle = '        bar_ret = (close / prev_close - 1.0) * 100.0'
    $replace = $needle + "`r`n" + '        day_close_return_pct = pct(close, prev_day_close_for_signal)'
    if ($py -notlike "*$needle*") { throw 'day close return insertion point not found' }
    $py = $py.Replace($needle, $replace)
}

# 4) replace candle_ok logic to use OR condition
$old = '        candle_ok = bar_ret >= float(params["bar_return_min_pct"])'
$new = @'
        day_return_ok = False
        if args.day_close_return_min_pct > 0 and day_close_return_pct is not None:
            day_return_ok = day_close_return_pct >= args.day_close_return_min_pct
        candle_ok = bar_ret >= float(params["bar_return_min_pct"]) or day_return_ok
'@.TrimEnd()
if ($py -like "*$old*") {
    $py = $py.Replace($old, $new)
}

# 5) add signal output column
$needle = '                "bar_return_pct": bar_ret,'
$replace = $needle + "`r`n" + '                "day_close_return_pct": day_close_return_pct,'
if ($py -notmatch '"day_close_return_pct": day_close_return_pct') {
    if ($py -notlike "*$needle*") { throw 'output column insertion point not found' }
    $py = $py.Replace($needle, $replace)
}

# 6) add runner parameter and forward to Python
if ($ps -notmatch '\$DayCloseReturnMinPct') {
    $needle = '    [string]$BarReturnMinPcts = ''2,2.5,3'','
    $replace = $needle + "`r`n" + '    [string]$DayCloseReturnMinPct = ''0'','
    if ($ps -notlike "*$needle*") { throw 'runner param insertion point not found' }
    $ps = $ps.Replace($needle, $replace)
}

if ($ps -notmatch '--day-close-return-min-pct=') {
    $needle = "    ('--bar-return-min-pcts=' + `$BarReturnMinPcts),"
    $replace = $needle + "`r`n" + "    ('--day-close-return-min-pct=' + `$DayCloseReturnMinPct),"
    if ($ps -notlike "*$needle*") { throw 'runner args insertion point not found' }
    $ps = $ps.Replace($needle, $replace)
}

Set-Content -LiteralPath $pyPath -Value $py -Encoding UTF8
Set-Content -LiteralPath $psPath -Value $ps -Encoding UTF8

Write-Host '=== PY COMPILE ==='
python -m py_compile src/review/build_leader_reaccel_parametric_v1.py
if ($LASTEXITCODE -ne 0) { throw 'py_compile failed' }

Write-Host 'OK patched Leader Reaccel v1.1: bar_return >= threshold OR day_close_return >= threshold'
git diff -- src/review/build_leader_reaccel_parametric_v1.py scripts/build_leader_reaccel_parametric_v1.ps1
