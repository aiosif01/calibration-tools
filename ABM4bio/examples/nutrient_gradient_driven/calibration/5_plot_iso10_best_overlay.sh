#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./5_plot_iso10_best_overlay.sh [seed]
# Example:
#   ./5_plot_iso10_best_overlay.sh 1234

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

SEED="${1:-1234}"

check_runtime
cd "$CALIB_ROOT"

BEST_JSON="$(iso10_best_params_path)"
if [[ ! -f "$BEST_JSON" ]]; then
  echo "ERROR: Missing $BEST_JSON"
  echo "Run calibration first (step 2 or 3)."
  exit 1
fi

RUN_ID="$(SEED="$SEED" "$PYTHON_BIN" - <<'PY'
import json
import os
p = 'results/best_runs/best_params_ISO10.json'
d = json.load(open(p))
seed = os.environ.get('SEED', '1234')
print(f"trial_{d['trial_number']:04d}_ISO10_s{seed}")
PY
)"

SIM_METRICS="results/optuna_runs/${RUN_ID}/simulation_metrics.csv"
if [[ ! -f "$SIM_METRICS" ]]; then
  echo "ERROR: Missing $SIM_METRICS"
  echo "Best run directory may have been cleaned."
  exit 1
fi

"$PYTHON_BIN" scripts/plot_results.py \
  --config configs/calibration_config.yaml \
  --condition ISO10 \
  --sim_metrics "$SIM_METRICS"

echo "[OK] Overlay plot generated at results/plots/exp_vs_sim_ISO10.png"
