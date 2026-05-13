param(
    [switch]$Run
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host '=== BUILD Top Candidate Board Smoke Host v3.6 ==='

$required = @(
    'START_HERE.md',
    'docs/workflow_server_editing_v1.md',
    'docs/powershell_script_rule_v1.md',
    'docs/pre_edit_reading_rule_v1.md',
    'docs/todo_update_rule_v1.md',
    'vbnet/frmTopCandidateBoard.vb',
    'vbnet/TopCandidateBoardSmokeHost/Program.vb',
    'vbnet/TopCandidateBoardSmokeHost/TopCandidateBoardSmokeHost.vbproj',
    'todo_list.md'
)

foreach ($rel in $required) {
    $p = Join-Path $root $rel
    if (-not (Test-Path -LiteralPath $p)) {
        throw ('Missing required file: ' + $rel)
    }
    Write-Host ('OK ' + $rel)
}

$proj = Join-Path $root 'vbnet/TopCandidateBoardSmokeHost/TopCandidateBoardSmokeHost.vbproj'
$projText = Get-Content -LiteralPath $proj -Raw -Encoding UTF8

$tokens = @(
    '<TargetFrameworkVersion>v4.8</TargetFrameworkVersion>',
    '<OptionStrict>On</OptionStrict>',
    '<OptionExplicit>On</OptionExplicit>',
    '<OptionInfer>Off</OptionInfer>',
    '<UseWindowsForms>true</UseWindowsForms>',
    'PackageReference Include="MySql.Data"',
    '..\frmTopCandidateBoard.vb'
)

Write-Host '=== VERIFY PROJECT TOKENS ==='
foreach ($token in $tokens) {
    if ($projText.Contains($token) -eq $false) {
        throw ('Missing project token: ' + $token)
    }
    Write-Host ('OK token: ' + $token)
}

function Find-MSBuild {
    $cmd = Get-Command msbuild.exe -ErrorAction SilentlyContinue
    if ($cmd -ne $null) {
        return $cmd.Source
    }

    $candidates = @(
        'C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe',
        'C:\Program Files\Microsoft Visual Studio\2022\Professional\MSBuild\Current\Bin\MSBuild.exe',
        'C:\Program Files\Microsoft Visual Studio\2022\Enterprise\MSBuild\Current\Bin\MSBuild.exe',
        'C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\MSBuild\Current\Bin\MSBuild.exe',
        'C:\Program Files (x86)\Microsoft Visual Studio\2019\Professional\MSBuild\Current\Bin\MSBuild.exe',
        'C:\Program Files (x86)\Microsoft Visual Studio\2019\Enterprise\MSBuild\Current\Bin\MSBuild.exe',
        'C:\Program Files (x86)\Microsoft Visual Studio\2017\Community\MSBuild\15.0\Bin\MSBuild.exe'
    )

    foreach ($p in $candidates) {
        if (Test-Path -LiteralPath $p) {
            return $p
        }
    }

    return ''
}

$msbuild = Find-MSBuild
if ([String]::IsNullOrWhiteSpace($msbuild)) {
    throw 'MSBuild.exe not found. Install Visual Studio Build Tools or run from Developer PowerShell.'
}
Write-Host ('msbuild=' + $msbuild)

Write-Host '=== MSBUILD RESTORE+BUILD ==='
& $msbuild $proj /t:Restore,Build /p:Configuration=Debug /p:Platform=AnyCPU /m
if ($LASTEXITCODE -ne 0) {
    throw 'MSBuild failed'
}

$exe = Join-Path $root 'vbnet/TopCandidateBoardSmokeHost/bin/Debug/TopCandidateBoardSmokeHost.exe'
if (-not (Test-Path -LiteralPath $exe)) {
    throw 'Missing smoke host exe'
}

Write-Host '=== VERIFY OUTPUT ==='
Write-Host ('exe=' + $exe)
Write-Host ('bytes=' + (Get-Item -LiteralPath $exe).Length)

if ($Run) {
    Write-Host '=== RUN SMOKE HOST ==='
    Write-Host 'The form should open. Use LIVE_COMPACT_V3_4 mode and Refresh.'
    Start-Process -FilePath $exe -WorkingDirectory (Split-Path -Parent $exe)
}

Write-Host '=== GIT STATUS ==='
git status
Write-Host '=== DONE build_top_candidate_board_smoke_host_v3_6.ps1 ==='
