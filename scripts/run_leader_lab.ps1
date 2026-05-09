$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$EnvPath = Join-Path $Root ".env"

python -m src.evaluation.baseline_topk_report --env $EnvPath --score ret_1m --actual-k 10 --score-k 10
python -m src.evaluation.baseline_topk_report --env $EnvPath --score ret_3m --actual-k 10 --score-k 10
python -m src.evaluation.baseline_topk_report --env $EnvPath --score volume --actual-k 10 --score-k 10
