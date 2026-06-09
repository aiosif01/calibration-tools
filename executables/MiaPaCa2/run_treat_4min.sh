#!/usr/bin/env bash
set -euo pipefail

CELL_LINE="MiaPaCa2"
EXPOSURE_SECONDS=240
OUTPUT_LABEL="treat_4min"
SET_CAP_DURATION=1

# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/_run_test_common.sh"
