param(
    [switch]$CommitAndPush
)

$ErrorActionPreference = 'Stop'

function FromB64Utf8([string]$s) {
    return [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($s))
}

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$todoPath = Join-Path $root 'todo_list.md'
$docPath = Join-Path $root 'docs/top_candidate_board_integration_v3_2.md'
$guidePath = Join-Path $root 'vbnet/TopCandidateBoardIntegrationGuide.vb'
$formPath = Join-Path $root 'vbnet/frmTopCandidateBoard.vb'

Write-Host '=== MARK v3.2 Top Candidate Board Integration DONE ==='

foreach ($p in @($todoPath, $docPath, $guidePath, $formPath)) {
    if (-not (Test-Path -LiteralPath $p)) {
        throw ('Missing required file: ' + $p)
    }
}

$guideText = Get-Content -LiteralPath $guidePath -Raw -Encoding UTF8
$formText = Get-Content -LiteralPath $formPath -Raw -Encoding UTF8
$docText = Get-Content -LiteralPath $docPath -Raw -Encoding UTF8
$joined = $guideText + $formText + $docText

foreach ($token in @('OpenTopCandidateBoard', 'OnTopCandidateActivated', 'CandidateActivated', 'frmTopCandidateBoard')) {
    if ($joined -notmatch [regex]::Escape($token)) {
        throw ('Missing integration token: ' + $token)
    }
}

$todo = Get-Content -LiteralPath $todoPath -Raw -Encoding UTF8

$marker = FromB64Utf8 'VG9wIENhbmRpZGF0ZSBCb2FyZCB2My4yIO2Gte2VqSDqsIDsnbTrk5wg6rKA7KadIOyZhOujjA=='
$insert = FromB64Utf8 'LSBbeF0gVG9wIENhbmRpZGF0ZSBCb2FyZCB2My4yIO2Gte2VqSDqsIDsnbTrk5wg6rKA7KadIOyZhOujjAogIC0gYGRvY3MvdG9wX2NhbmRpZGF0ZV9ib2FyZF9pbnRlZ3JhdGlvbl92M18yLm1kYAogIC0gYHZibmV0L1RvcENhbmRpZGF0ZUJvYXJkSW50ZWdyYXRpb25HdWlkZS52YmAKICAtIGB2Ym5ldC9mcm1Ub3BDYW5kaWRhdGVCb2FyZC52YmAKICAtIGxvY2FsIHZlcmlmaWNhdGlvbjogYGJ1aWxkX3RvcF9jYW5kaWRhdGVfYm9hcmRfaW50ZWdyYXRpb25fdjNfMi5wczFgCiAgLSByZXN1bHQ6IGludGVncmF0aW9uIHRva2VucyBPSywgYHdvcmtpbmcgdHJlZSBjbGVhbmAK'
$anchor1 = FromB64Utf8 'LSBbeF0gU3VwZXJUcmVuZCBSZWdpbWUgRGlzY292ZXJ5IOqysOqzvCDsg53shLE='
$anchor2 = FromB64Utf8 'ICAtIGBzZWdtZW50cz0yNTA3MGA='
$anchor3 = FromB64Utf8 'ICAtIGByZXBvcnRzL3N1cGVydHJlbmRfcmVnaW1lX2Rpc2NvdmVyeV9kYXNoYm9hcmQuaHRtbGA='
$fallback = FromB64Utf8 'IyMjIO2YhOyerCDstZzsmrDshKAg7KeE7ZaJIOykkQ=='

if ($todo.Contains($marker) -eq $false) {
    $target = $anchor1 + "`r`n" + $anchor2 + "`r`n" + $anchor3
    $replacement = $target + "`r`n" + $insert

    if ($todo.Contains($target)) {
        $todo = $todo.Replace($target, $replacement)
    } elseif ($todo.Contains($fallback)) {
        $todo = $todo.Replace($fallback, $insert + "`r`n" + $fallback)
    } else {
        throw 'Could not find insertion anchor in todo_list.md'
    }

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($todoPath, $todo, $utf8NoBom)
    Write-Host 'todo_list.md updated: v3.2 completion marker inserted.'
} else {
    Write-Host 'todo_list.md already contains v3.2 completion marker. No content change needed.'
}

Write-Host '=== VERIFY TODO MARKER ==='
Select-String -Path $todoPath -Pattern 'Top Candidate Board v3.2|Chart Consistency Gate' | ForEach-Object {
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
