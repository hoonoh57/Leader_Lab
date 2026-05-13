param()

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== AUDIT v3 Score Leakage v3.8b ==='

$required = @(
    'START_HERE.md',
    'docs/workflow_server_editing_v1.md',
    'docs/powershell_script_rule_v1.md',
    'docs/pre_edit_reading_rule_v1.md',
    'docs/todo_update_rule_v1.md',
    'todo_list.md'
)
foreach ($rel in $required) {
    $p = Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p)) { throw ('Missing required file: ' + $rel) }
    Write-Host ('OK ' + $rel)
}

$tmp = Join-Path $root '.tmp_audit_v3_score_leakage_v3_8b.py'
$code = @'
from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path('.').resolve()
SEARCH_DIRS = ['scripts', 'src', 'docs', 'vbnet']

FORBIDDEN = [
    'st_up_max_return_pct',
    'st_up_max_price',
    'st_up_end_price',
    'st_up_end_return_pct',
    'st_up_end_time',
    'st_up_bars',
    'label_st_gain_3pct',
    'label_st_gain_5pct',
    'label_st_gain_10pct',
    'label_st_fail_1pct',
    'label_st_end_negative',
    'max_ret_in_period',
    'actual_rank_by_max_ret',
    'ret_1m',
    'ret_3m',
    'ret_7h',
    'max_return',
    'max_profit',
]

CURRENT_ALLOWED_HINTS = [
    'search_date',
    'search_time',
    'capture_time',
    'code',
    'name',
    'entry_time',
    'entry_price',
    'start_cum_amount',
    'start_cum_volume',
    'start_from_day_open_pct',
    'start_from_day_low_pct',
    'start_range_so_far_pct',
    'start_high_so_far_from_open_pct',
    'tick_confirm_score_v2_6',
    'tick_intensity_v2_6',
    'buy_tick_ratio_v2_6',
    'large_trade_amount_eok_v2_6',
    'hoga_bid_pressure_v2_6',
    'hoga_ask_absorption_v2_6',
    'spread_risk_v2_6',
]

RANK_ACTION_PATTERNS = [
    'ORDER BY',
    'ROW_NUMBER',
    'board_action',
    'final_rank',
    'selected_date_rank',
    'tick_confirm_score',
    'expected_return_pct',
    'PROMOTE_REJECT_TO_WATCH',
]

TARGET_NAME_PATTERNS = [
    'top_candidate',
    'selected_date',
    'supertrend_realtime',
    'candidate_board',
    'promotion',
]


def should_scan(path: Path) -> bool:
    if '.git' in path.parts:
        return False
    if path.suffix.lower() not in ['.ps1', '.py', '.md', '.vb', '.sql']:
        return False
    low = str(path).lower().replace('\\', '/')
    if not any('/' + d + '/' in '/' + low for d in SEARCH_DIRS):
        return False
    if any(p in path.name.lower() for p in TARGET_NAME_PATTERNS):
        return True
    return False


def context(lines: List[str], idx: int, radius: int = 2) -> str:
    start = max(0, idx - radius)
    end = min(len(lines), idx + radius + 1)
    out = []
    for i in range(start, end):
        out.append(str(i + 1) + ': ' + lines[i].rstrip())
    return '\n'.join(out)


def classify_line(line: str) -> str:
    up = line.upper()
    if any(p in up for p in RANK_ACTION_PATTERNS):
        return 'RANK_OR_ACTION_CONTEXT'
    return 'REFERENCE_CONTEXT'


def main() -> int:
    files = [p for p in ROOT.rglob('*') if p.is_file() and should_scan(p)]
    print('scan_file_count=' + str(len(files)))
    hits: List[Tuple[str, int, str, str, str]] = []
    allowed_hits: List[Tuple[str, int, str]] = []
    for p in sorted(files):
        try:
            text = p.read_text(encoding='utf-8-sig', errors='replace')
        except Exception:
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines):
            low = line.lower()
            for token in FORBIDDEN:
                if token.lower() in low:
                    cls = classify_line(line)
                    hits.append((str(p.relative_to(ROOT)), i + 1, token, cls, context(lines, i)))
            for token in CURRENT_ALLOWED_HINTS:
                if token.lower() in low:
                    allowed_hits.append((str(p.relative_to(ROOT)), i + 1, token))

    print('forbidden_hit_count=' + str(len(hits)))
    print('current_allowed_hint_hit_count=' + str(len(allowed_hits)))
    print('\n=== FORBIDDEN TOKEN HITS ===')
    for path, line_no, token, cls, ctx in hits[:240]:
        print('--- ' + cls + ' / token=' + token + ' / ' + path + ':' + str(line_no) + ' ---')
        print(ctx)

    rank_leaks = [h for h in hits if h[3] == 'RANK_OR_ACTION_CONTEXT']
    print('\n=== LEAKAGE VERDICT ===')
    if len(rank_leaks) > 0:
        print('VERDICT=NEEDS_MANUAL_REVIEW_OR_LEAKAGE_RISK')
        print('rank_or_action_forbidden_hits=' + str(len(rank_leaks)))
        print('Meaning: at least one future/result column appears near ranking/action logic.')
    elif len(hits) > 0:
        print('VERDICT=FORBIDDEN_ONLY_IN_REFERENCE_CONTEXT')
        print('Meaning: future/result columns appear, but not obviously near ranking/action keywords. Manual review still required.')
    else:
        print('VERDICT=NO_FORBIDDEN_TOKEN_FOUND')
        print('Meaning: static token scan found no obvious future/result data usage.')

    print('\n=== REQUIRED NEXT CHECK ===')
    print('1. If v2.9/v3.4 builders use st_up_max_return_pct/max_ret_in_period/label_st_gain_* in ORDER BY or board_action, it is a cheating/answer-sheet logic.')
    print('2. A valid test-sheet logic may use only capture/search-time available fields such as start_cum_amount, start_from_day_open_pct, tick/hoga fields available at capture time.')
    print('3. If existing v3 has leakage, rebuild selected-date test board with causal-only columns and keep v3.8 as answer/validation board.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
'@

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($tmp, $code, $utf8NoBom)

python -m py_compile $tmp
if ($LASTEXITCODE -ne 0) { throw 'py_compile failed' }
python $tmp
if ($LASTEXITCODE -ne 0) { throw 'v3 leakage audit failed' }
Remove-Item -LiteralPath $tmp -Force

Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE audit_v3_score_leakage_v3_8b.ps1 ==='
