$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$EnvPath = Join-Path $Root ".env"

python -m src.migration.migrate_1516_sqlite_to_mysql --env $EnvPath
python -m src.migration.verify_performance_result --env $EnvPath
