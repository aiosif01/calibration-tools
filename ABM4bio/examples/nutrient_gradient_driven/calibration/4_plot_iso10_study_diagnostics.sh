#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./4_plot_iso10_study_diagnostics.sh [db_name]
# Example:
#   ./4_plot_iso10_study_diagnostics.sh study_iso10_fresh.db

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

DB_NAME="${1:-study_iso10_fresh.db}"
STORAGE_URL="$(iso10_storage_url "$DB_NAME")"

check_runtime
cd "$CALIB_ROOT"

"$PYTHON_BIN" scripts/plot_results.py \
  --config configs/calibration_config.yaml \
  --condition ISO10 \
  --storage "$STORAGE_URL"
