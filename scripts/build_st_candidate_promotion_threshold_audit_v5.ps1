param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== BUILD ST Candidate Promotion Threshold Audit v5 ==='

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

$inputCsv = Join-Path $root 'reports/st_candidate_action_error_audit_v4.csv'
if (-not (Test-Path -LiteralPath $inputCsv)) {
    throw 'Missing reports/st_candidate_action_error_audit_v4.csv. Run scripts/build_st_candidate_action_error_audit_v4.ps1 first.'
}

$tmp = Join-Path $root '.tmp_build_st_candidate_promotion_threshold_audit_v5.py'
$code = @'
from __future__ import annotations
import csv
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional

IN_CSV = Path('reports/st_candidate_action_error_audit_v4.csv')
OUT_GRID = Path('reports/st_candidate_promotion_threshold_grid_v5.csv')
OUT_PICK = Path('reports/st_candidate_promotion_candidates_v5.csv')
OUT_MD = Path('reports/st_candidate_promotion_threshold_summary_v5.md')


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


def avg(xs: List[Optional[float]]) -> Optional[float]:
    vals = [x for x in xs if x is not None]
    return None if not vals else sum(vals) / float(len(vals))


def med(xs: List[Optional[float]]) -> Optional[float]:
    vals = [x for x in xs if x is not None]
    return None if not vals else float(statistics.median(vals))


def fmt(v: Optional[float]) -> str:
    if v is None:
        return ''
    return ('%.4f' % v).rstrip('0').rstrip('.')


def is_good(q: str) -> bool:
    return q in ('GREAT', 'GOOD')


def load_rows() -> List[Dict[str, str]]:
    with IN_CSV.open('r', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def passes(row: Dict[str, str], tick_min: float, spread_max: float, buy_min: float, bid_min: float, ask_min: float) -> bool:
    tick = fnum(row.get('tick_confirm_score'))
    spread = fnum(row.get('spread_risk'))
    buy = fnum(row.get('buy_tick_ratio'))
    bid = fnum(row.get('hoga_bid_pressure'))
    ask = fnum(row.get('hoga_ask_absorption'))
    if tick is None or spread is None or buy is None or bid is None or ask is None:
        return False
    return tick >= tick_min and spread <= spread_max and buy >= buy_min and bid >= bid_min and ask >= ask_min


def grid_search(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    tick_set = [30, 40, 50, 60, 70]
    spread_set = [10, 15, 20, 25, 30, 35, 40]
    buy_set = [60, 65, 70, 75]
    bid_set = [55, 60, 65, 70]
    ask_set = [55, 60, 65, 70]
    result: List[Dict[str, Any]] = []
    for tick_min in tick_set:
        for spread_max in spread_set:
            for buy_min in buy_set:
                for bid_min in bid_set:
                    for ask_min in ask_set:
                        selected = [r for r in rows if passes(r, tick_min, spread_max, buy_min, bid_min, ask_min)]
                        n = len(selected)
                        if n == 0:
                            continue
                        good = sum(1 for r in selected if is_good(r.get('causal_quality', '')))
                        great = sum(1 for r in selected if r.get('causal_quality') == 'GREAT')
                        reject_good = sum(1 for r in selected if r.get('board_action') == 'REJECT' and is_good(r.get('causal_quality', '')))
                        reject_great = sum(1 for r in selected if r.get('board_action') == 'REJECT' and r.get('causal_quality') == 'GREAT')
                        live_bad = sum(1 for r in selected if r.get('board_action') in ('AUTO_BUY_READY','WATCH_HOGA_TICK') and not is_good(r.get('causal_quality','')))
                        remain = [fnum(r.get('causal_remain_to_max_pct')) for r in selected]
                        result.append({
                            'tick_min': tick_min,
                            'spread_max': spread_max,
                            'buy_min': buy_min,
                            'bid_min': bid_min,
                            'ask_min': ask_min,
                            'selected_count': n,
                            'good_or_great_count': good,
                            'great_count': great,
                            'good_or_great_rate': good / n,
                            'great_rate': great / n,
                            'reject_good_or_great_count': reject_good,
                            'reject_great_count': reject_great,
                            'live_bad_count': live_bad,
                            'median_remain_to_max_pct': med(remain),
                            'avg_remain_to_max_pct': avg(remain),
                        })
    result.sort(key=lambda r: (float(r['good_or_great_rate']), int(r['great_count']), int(r['selected_count']), float(r.get('median_remain_to_max_pct') or -999)), reverse=True)
    return result


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else []
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def pick_promotions(rows: List[Dict[str, str]], rule: Dict[str, Any]) -> List[Dict[str, Any]]:
    picked: List[Dict[str, Any]] = []
    for r in rows:
        if not passes(r, float(rule['tick_min']), float(rule['spread_max']), float(rule['buy_min']), float(rule['bid_min']), float(rule['ask_min'])):
            continue
        issue = 'PROMOTE_REJECT_TO_WATCH' if r.get('board_action') == 'REJECT' else 'KEEP_OR_SECOND_STAGE'
        picked.append({
            'promotion_issue': issue,
            'candidate_no': r.get('candidate_no'),
            'code': r.get('code'),
            'name': r.get('name'),
            'board_action': r.get('board_action'),
            'entry_time_text': r.get('entry_time_text'),
            'entry_price': r.get('entry_price'),
            'causal_quality': r.get('causal_quality'),
            'causal_remain_to_max_pct': r.get('causal_remain_to_max_pct'),
            'tick_confirm_score': r.get('tick_confirm_score'),
            'buy_tick_ratio': r.get('buy_tick_ratio'),
            'hoga_bid_pressure': r.get('hoga_bid_pressure'),
            'hoga_ask_absorption': r.get('hoga_ask_absorption'),
            'spread_risk': r.get('spread_risk'),
        })
    return picked


def main() -> int:
    rows = load_rows()
    grid = grid_search(rows)
    write_csv(OUT_GRID, grid)
    conservative = [r for r in grid if int(r['selected_count']) >= 5 and float(r['good_or_great_rate']) >= 0.9 and int(r['live_bad_count']) == 0]
    chosen = conservative[0] if conservative else (grid[0] if grid else {})
    picks = pick_promotions(rows, chosen) if chosen else []
    write_csv(OUT_PICK, picks)

    lines: List[str] = []
    lines.append('# ST Candidate Promotion Threshold Summary v5')
    lines.append('')
    lines.append('Purpose: find broad promotion gates without using future labels as rule inputs.')
    lines.append('Inputs used for gate search: tick_confirm_score, spread_risk, buy_tick_ratio, hoga_bid_pressure, hoga_ask_absorption.')
    lines.append('Future labels are used only for evaluation.')
    lines.append('')
    lines.append('total_candidates=' + str(len(rows)))
    lines.append('grid_rows=' + str(len(grid)))
    if chosen:
        for k in ['tick_min','spread_max','buy_min','bid_min','ask_min','selected_count','good_or_great_count','great_count','good_or_great_rate','great_rate','reject_good_or_great_count','reject_great_count','live_bad_count','median_remain_to_max_pct']:
            lines.append('chosen_' + k + '=' + fmt(fnum(chosen.get(k))) if isinstance(chosen.get(k), float) else 'chosen_' + k + '=' + str(chosen.get(k)))
    lines.append('promotion_candidate_rows=' + str(len(picks)))
    lines.append('')
    lines.append('csv_grid=reports/st_candidate_promotion_threshold_grid_v5.csv')
    lines.append('csv_candidates=reports/st_candidate_promotion_candidates_v5.csv')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')

    print('=== DONE build_st_candidate_promotion_threshold_audit_v5 ===')
    for line in lines:
        if '=' in line:
            print(line)
    print('summary=' + str(OUT_MD.resolve()))
    print('grid=' + str(OUT_GRID.resolve()))
    print('candidates=' + str(OUT_PICK.resolve()))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
'@

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($tmp, $code, $utf8NoBom)

python -m py_compile $tmp
if ($LASTEXITCODE -ne 0) { throw 'py_compile failed' }
python $tmp
if ($LASTEXITCODE -ne 0) { throw 'promotion threshold audit failed' }
Remove-Item -LiteralPath $tmp -Force

Write-Host '=== VERIFY OUTPUTS ==='
if (-not (Test-Path -LiteralPath (Join-Path $root 'reports/st_candidate_promotion_threshold_grid_v5.csv'))) { throw 'Missing v5 grid CSV output' }
if (-not (Test-Path -LiteralPath (Join-Path $root 'reports/st_candidate_promotion_candidates_v5.csv'))) { throw 'Missing v5 candidates CSV output' }
if (-not (Test-Path -LiteralPath (Join-Path $root 'reports/st_candidate_promotion_threshold_summary_v5.md'))) { throw 'Missing v5 summary output' }
Write-Host 'OK reports/st_candidate_promotion_threshold_grid_v5.csv'
Write-Host 'OK reports/st_candidate_promotion_candidates_v5.csv'
Write-Host 'OK reports/st_candidate_promotion_threshold_summary_v5.md'
Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE build_st_candidate_promotion_threshold_audit_v5.ps1 ==='
