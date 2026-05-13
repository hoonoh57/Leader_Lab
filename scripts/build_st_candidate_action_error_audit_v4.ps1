param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== BUILD ST Candidate Action Error Audit v4 ==='

$required = @(
    'START_HERE.md',
    'docs/workflow_server_editing_v1.md',
    'docs/powershell_script_rule_v1.md',
    'docs/pre_edit_reading_rule_v1.md',
    'docs/todo_update_rule_v1.md',
    'docs/st_dashboard_live_overlay_research_v1.md',
    'docs/live_candidate_overlay_on_st_dashboard_v1.md',
    'todo_list.md'
)
foreach ($rel in $required) {
    $p = Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p)) { throw ('Missing required file: ' + $rel) }
    Write-Host ('OK ' + $rel)
}

$inputCsv = Join-Path $root 'reports/st_candidate_overlap_causal_v3.csv'
if (-not (Test-Path -LiteralPath $inputCsv)) {
    throw 'Missing reports/st_candidate_overlap_causal_v3.csv. Run scripts/build_st_candidate_overlap_report_v3_causal.ps1 first.'
}

$tmp = Join-Path $root '.tmp_build_st_candidate_action_error_audit_v4.py'
$code = @'
from __future__ import annotations
import csv
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional

IN_CSV = Path('reports/st_candidate_overlap_causal_v3.csv')
OUT_CSV = Path('reports/st_candidate_action_error_audit_v4.csv')
OUT_MD = Path('reports/st_candidate_action_error_audit_summary_v4.md')


def fnum(v: Any) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def avg(values: List[Optional[float]]) -> Optional[float]:
    xs = [x for x in values if x is not None]
    return None if not xs else sum(xs) / float(len(xs))


def med(values: List[Optional[float]]) -> Optional[float]:
    xs = [x for x in values if x is not None]
    return None if not xs else float(statistics.median(xs))


def fmt(v: Optional[float]) -> str:
    if v is None:
        return ''
    return ('%.4f' % v).rstrip('0').rstrip('.')


def is_good(q: str) -> bool:
    return q in ('GREAT', 'GOOD')


def load_rows() -> List[Dict[str, str]]:
    with IN_CSV.open('r', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def by_action_summary(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    actions = sorted(set(r.get('board_action', '') for r in rows))
    out: List[Dict[str, Any]] = []
    for action in actions:
        part = [r for r in rows if r.get('board_action', '') == action]
        total = len(part)
        great = sum(1 for r in part if r.get('causal_quality') == 'GREAT')
        good = sum(1 for r in part if is_good(r.get('causal_quality', '')))
        inside = sum(1 for r in part if str(r.get('causal_inside_segment', '')).strip() == '1')
        near = sum(1 for r in part if str(r.get('causal_near_or_inside_segment', '')).strip() == '1')
        remain_values = [fnum(r.get('causal_remain_to_max_pct')) for r in part]
        tick_values = [fnum(r.get('tick_confirm_score')) for r in part]
        spread_values = [fnum(r.get('spread_risk')) for r in part]
        out.append({
            'action': action,
            'total': total,
            'causal_great': great,
            'causal_good_or_great': good,
            'causal_inside': inside,
            'causal_near_or_inside': near,
            'good_or_great_rate': good / total if total else None,
            'great_rate': great / total if total else None,
            'avg_remain_to_max_pct': avg(remain_values),
            'median_remain_to_max_pct': med(remain_values),
            'avg_tick_confirm_score': avg(tick_values),
            'median_tick_confirm_score': med(tick_values),
            'avg_spread_risk': avg(spread_values),
            'median_spread_risk': med(spread_values),
        })
    return out


def audit_rows(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows:
        action = r.get('board_action', '')
        q = r.get('causal_quality', '')
        remain = fnum(r.get('causal_remain_to_max_pct'))
        tick = fnum(r.get('tick_confirm_score'))
        spread = fnum(r.get('spread_risk'))
        issue = ''
        if action == 'REJECT' and is_good(q):
            issue = 'REJECT_BUT_GOOD_OR_GREAT'
        elif action == 'WATCH_HOGA_TICK' and q == 'GREAT':
            issue = 'WATCH_GREAT_PROMOTION_CANDIDATE'
        elif action == 'AUTO_BUY_READY' and q == 'GREAT':
            issue = 'AUTO_BUY_CONFIRMED_GREAT'
        elif action in ('AUTO_BUY_READY', 'WATCH_HOGA_TICK') and not is_good(q):
            issue = 'LIVE_ACTION_BUT_NOT_GOOD'
        else:
            issue = 'REFERENCE'
        out.append({
            'issue': issue,
            'candidate_no': r.get('candidate_no', ''),
            'code': r.get('code', ''),
            'name': r.get('name', ''),
            'candidate_date': r.get('candidate_date', ''),
            'board_action': action,
            'entry_time_text': r.get('entry_time_text', ''),
            'entry_price': r.get('entry_price', ''),
            'causal_quality': q,
            'causal_inside_segment': r.get('causal_inside_segment', ''),
            'causal_bars_from_st_start': r.get('causal_bars_from_st_start', ''),
            'causal_bars_to_st_end': r.get('causal_bars_to_st_end', ''),
            'causal_remain_to_max_pct': fmt(remain),
            'tick_confirm_score': fmt(tick),
            'tick_intensity': r.get('tick_intensity', ''),
            'buy_tick_ratio': r.get('buy_tick_ratio', ''),
            'hoga_bid_pressure': r.get('hoga_bid_pressure', ''),
            'hoga_ask_absorption': r.get('hoga_ask_absorption', ''),
            'spread_risk': fmt(spread),
        })
    out.sort(key=lambda x: (str(x['issue']), -float(x['causal_remain_to_max_pct'] or -999), str(x['code'])))
    return out


def write_csv(rows: List[Dict[str, Any]]) -> None:
    fields = list(rows[0].keys()) if rows else []
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> int:
    rows = load_rows()
    summary = by_action_summary(rows)
    audits = audit_rows(rows)
    write_csv(audits)

    reject_good = [r for r in audits if r['issue'] == 'REJECT_BUT_GOOD_OR_GREAT']
    watch_great = [r for r in audits if r['issue'] == 'WATCH_GREAT_PROMOTION_CANDIDATE']
    auto_great = [r for r in audits if r['issue'] == 'AUTO_BUY_CONFIRMED_GREAT']
    live_bad = [r for r in audits if r['issue'] == 'LIVE_ACTION_BUT_NOT_GOOD']

    lines: List[str] = []
    lines.append('# ST Candidate Action Error Audit Summary v4')
    lines.append('')
    lines.append('Goal: preserve the successful ST reference map and find which live action gates are too strict or too loose.')
    lines.append('')
    lines.append('total_candidates=' + str(len(rows)))
    lines.append('reject_but_good_or_great=' + str(len(reject_good)))
    lines.append('watch_great_promotion_candidates=' + str(len(watch_great)))
    lines.append('auto_buy_confirmed_great=' + str(len(auto_great)))
    lines.append('live_action_but_not_good=' + str(len(live_bad)))
    lines.append('')
    lines.append('## By action')
    for s in summary:
        lines.append(
            str(s['action']) + ': total=' + str(s['total']) +
            ', good_or_great=' + str(s['causal_good_or_great']) +
            ', great=' + str(s['causal_great']) +
            ', good_rate=' + fmt(s['good_or_great_rate']) +
            ', great_rate=' + fmt(s['great_rate']) +
            ', med_remain=' + fmt(s['median_remain_to_max_pct']) +
            ', med_tick=' + fmt(s['median_tick_confirm_score']) +
            ', med_spread=' + fmt(s['median_spread_risk'])
        )
    lines.append('')
    lines.append('## Interpretation')
    lines.append('If REJECT_BUT_GOOD_OR_GREAT is large, the current reject gate is too conservative or missing a promotion path.')
    lines.append('If WATCH_GREAT_PROMOTION_CANDIDATE is large, watch rows need a second-stage promotion rule instead of immediate rejection or passive watching.')
    lines.append('If LIVE_ACTION_BUT_NOT_GOOD is nonzero, live action gates are too loose.')
    lines.append('')
    lines.append('csv=reports/st_candidate_action_error_audit_v4.csv')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')

    print('=== DONE build_st_candidate_action_error_audit_v4 ===')
    for line in lines:
        if '=' in line or line.startswith('AUTO_') or line.startswith('WATCH_') or line.startswith('REJECT'):
            print(line)
    print('summary=' + str(OUT_MD.resolve()))
    print('csv=' + str(OUT_CSV.resolve()))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
'@

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($tmp, $code, $utf8NoBom)

python -m py_compile $tmp
if ($LASTEXITCODE -ne 0) { throw 'py_compile failed' }
python $tmp
if ($LASTEXITCODE -ne 0) { throw 'action error audit failed' }
Remove-Item -LiteralPath $tmp -Force

Write-Host '=== VERIFY OUTPUTS ==='
if (-not (Test-Path -LiteralPath (Join-Path $root 'reports/st_candidate_action_error_audit_v4.csv'))) { throw 'Missing v4 CSV output' }
if (-not (Test-Path -LiteralPath (Join-Path $root 'reports/st_candidate_action_error_audit_summary_v4.md'))) { throw 'Missing v4 summary output' }
Write-Host 'OK reports/st_candidate_action_error_audit_v4.csv'
Write-Host 'OK reports/st_candidate_action_error_audit_summary_v4.md'
Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE build_st_candidate_action_error_audit_v4.ps1 ==='
