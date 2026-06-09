#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./2_run_iso10_fresh_calibration.sh [n_trials] [seed] [db_name]
# Example:
#   ./2_run_iso10_fresh_calibration.sh 200 1234 study_iso10_fresh.db

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

TRIALS="${1:-200}"
SEED="${2:-1234}"
DB_NAME="${3:-study_iso10_fresh.db}"
STORAGE_URL="$(iso10_storage_url "$DB_NAME")"
LOCK_FILE="${TMPDIR:-/tmp}/abm4bio_iso10_calibration_${USER}.lock"

check_runtime
cd "$CALIB_ROOT"

if [[ -e "$LOCK_FILE" ]]; then
  echo "ERROR: calibration already active or stale lock exists: $LOCK_FILE" >&2
  exit 10
fi
trap 'rm -f "$LOCK_FILE"' EXIT
touch "$LOCK_FILE"

"$PYTHON_BIN" scripts/optimize_optuna.py \
  --config configs/calibration_config.yaml \
  --bounds configs/parameter_bounds.yaml \
  --condition ISO10 \
  --seed "$SEED" \
  --n_trials "$TRIALS" \
  --storage "$STORAGE_URL"
