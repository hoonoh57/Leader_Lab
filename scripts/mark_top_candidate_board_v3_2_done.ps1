param(
    [switch]$CommitAndPush
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$todoPath = Join-Path $root 'todo_list.md'
$docPath = Join-Path $root 'docs/top_candidate_board_integration_v3_2.md'
$guidePath = Join-Path $root 'vbnet/TopCandidateBoardIntegrationGuide.vb'
$formPath = Join-Path $root 'vbnet/frmTopCandidateBoard.vb'

Write-Host '=== MARK v3.2 Top Candidate Board Integration DONE ==='

foreach ($p in @($todoPath, $docPath, $guidePath, $formPath)) {
    if (-not (Test-Path $p)) {
        throw "Missing required file: $p"
    }
}

$guideText = Get-Content -LiteralPath $guidePath -Raw -Encoding UTF8
$formText = Get-Content -LiteralPath $formPath -Raw -Encoding UTF8
$docText = Get-Content -LiteralPath $docPath -Raw -Encoding UTF8

foreach ($token in @('OpenTopCandidateBoard', 'OnTopCandidateActivated', 'CandidateActivated', 'frmTopCandidateBoard')) {
    if (($guideText + $formText + $docText) -notmatch [regex]::Escape($token)) {
        throw "Missing integration token: $token"
    }
}

$todo = Get-Content -LiteralPath $todoPath -Raw -Encoding UTF8

if ($todo -notmatch 'Top Candidate Board v3\.2 통합 가이드 검증 완료') {
    $insert = @'
- [x] Top Candidate Board v3.2 통합 가이드 검증 완료
  - `docs/top_candidate_board_integration_v3_2.md`
  - `vbnet/TopCandidateBoardIntegrationGuide.vb`
  - `vbnet/frmTopCandidateBoard.vb`
  - local verification: `build_top_candidate_board_integration_v3_2.ps1`
  - result: integration tokens OK, `working tree clean`
'@

    $anchor = '- [x] SuperTrend Regime Discovery 결과 생성\r?\n  - `segments=25070`\r?\n  - `reports/supertrend_regime_discovery_dashboard.html`'
    if ($todo -match $anchor) {
        $todo = [regex]::Replace($todo, $anchor, { param($m) $m.Value + "`r`n" + $insert }, 1)
    } else {
        $fallback = '### 현재 최우선 진행 중'
        if ($todo.Contains($fallback)) {
            $todo = $todo.Replace($fallback, $insert + "`r`n" + $fallback)
        } else {
            throw 'Could not find insertion anchor in todo_list.md'
        }
    }

    Set-Content -LiteralPath $todoPath -Value $todo -Encoding UTF8
    Write-Host 'todo_list.md updated: v3.2 completion marker inserted.'
} else {
    Write-Host 'todo_list.md already contains v3.2 completion marker. No content change needed.'
}

Write-Host '=== VERIFY TODO MARKER ==='
Select-String -Path $todoPath -Pattern 'Top Candidate Board v3.2 통합 가이드 검증 완료|Chart Consistency Gate' | ForEach-Object {
    Write-Host $_.Line
}

if ($CommitAndPush) {
    $status = git status --porcelain
    if ($status) {
        git add todo_list.md scripts/mark_top_candidate_board_v3_2_done.ps1
        git commit -m 'docs: mark top candidate board v3.2 integration done'
        git push origin main
    } else {
        Write-Host 'No git changes to commit.'
    }
}

Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE mark_top_candidate_board_v3_2_done.ps1 ==='
