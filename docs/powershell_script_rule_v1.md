# PowerShell Script Rule v1

Date: 2026-05-13

PowerShell scripts in this repository must run on Windows PowerShell 5.1.

## Required

```text
Use ASCII-only ps1 source by default.
Use English console output.
Use ErrorActionPreference Stop.
Check required files before writing outputs.
Print a VERIFY block.
End with git status or exact next commands.
```

## Korean text in ps1

Do not place Korean text directly inside ps1 string literals or here-strings.

If Korean text must be written by a ps1 script, store it as UTF-8 Base64 and decode it at runtime.

## Helper

```powershell
function FromB64Utf8([string]$s) {
    return [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($s))
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($path, $content, $utf8NoBom)
```
