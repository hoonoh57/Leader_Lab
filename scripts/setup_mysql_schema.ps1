$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$EnvPath = Join-Path $Root ".env"

if (!(Test-Path $EnvPath)) {
    Write-Host "[WARN] .env not found. Copy .env.example to .env and fill local values."
}

python -m src.tools.setup_mysql_schema --env $EnvPath
