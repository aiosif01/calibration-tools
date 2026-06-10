#!/usr/bin/env bash
set -euo pipefail
CELL_LINE="PANC1"
ANN_STEP="train"
# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/_ann_common.sh"
