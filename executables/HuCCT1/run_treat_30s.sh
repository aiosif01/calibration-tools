#!/usr/bin/env bash
set -euo pipefail

CELL_LINE="HuCCT1"
EXPOSURE_SECONDS=30
OUTPUT_LABEL="treat_30s"
SET_CAP_DURATION=1

# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/_run_test_common.sh"
