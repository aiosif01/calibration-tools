#!/usr/bin/env bash
set -euo pipefail

CELL_LINE="EGI1"
CASE_MODE="treatment"
EXPOSURE_SECONDS=300
N_TRIALS="${N_TRIALS:-300}"
REPLICATES="${REPLICATES:-3}"

# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/_optuna_common.sh"
