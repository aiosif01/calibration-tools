#!/usr/bin/env bash
set -euo pipefail
CELL_LINE="MiaPaCa2"
ANN_STEP="generate"
N_SAMPLES="${N_SAMPLES:-1000}"
# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/_ann_common.sh"
