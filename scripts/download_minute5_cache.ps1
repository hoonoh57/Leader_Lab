$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$EnvPath = Join-Path $Root ".env"

python -m src.cache.download_minute5_from_server32 --env $EnvPath --limit 0 --min-count 200 --interval-sec 0.2
python -m src.cache.verify_minute5_cache --env $EnvPath
