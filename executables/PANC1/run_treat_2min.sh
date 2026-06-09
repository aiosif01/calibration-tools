#!/usr/bin/env bash
set -euo pipefail

CELL_LINE="PANC1"
EXPOSURE_SECONDS=120
OUTPUT_LABEL="treat_2min"
SET_CAP_DURATION=1

# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/_run_test_common.sh"
