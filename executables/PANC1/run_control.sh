#!/usr/bin/env bash
set -euo pipefail

CELL_LINE="PANC1"
EXPOSURE_SECONDS=0
OUTPUT_LABEL="control"
SET_CAP_DURATION=0

# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/_run_test_common.sh"
