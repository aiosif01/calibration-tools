#!/usr/bin/env bash
set -euo pipefail

# Usage: ./calibration/2_run_cap_stage2.sh [n_trials] [seed]
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

TRIALS="${1:-80}"
SEED="${2:-1234}"
LOCK_FILE="$(cap_lock_file stage2)"

check_runtime
cd "$CAP_ROOT"

if [[ -e "$LOCK_FILE" ]]; then
  echo "ERROR: stage2 calibration active or stale lock exists: $LOCK_FILE" >&2
  exit 10
fi
trap 'rm -f "$LOCK_FILE"' EXIT
: > "$LOCK_FILE"

bash scripts/run_cap_optuna_clean.sh \
  --stage bar_chart \
  --data-csv data/experimental_targets_t0_normalized_corrected_units.csv \
  --manifest-csv data/experimental_case_manifest_corrected_units.csv \
  --param-space-csv data/optuna_parameter_space_mechanism12.csv \
  --template-input input_mechanism12_CAP_template.csv \
  --abm-binary ../../build/ABM4bio \
  --bdm-env-script ../../libs/biodynamo-v1.05.143/bin/thisbdm.sh \
  --out-dir calibration_outputs/CAP_optuna \
  --cell-lines EGI1,HuCCT1,PANC1,MiaPaCa2 \
  --exposures-min 0,0.5,2,4,5 \
  --n-trials "$TRIALS" \
  --n-startup-trials 20 \
  --replicates 3 \
  --sampler-seed "$SEED" \
  --base-seed "$SEED" \
  --omp-threads 4 \
  --timeout-s 1800 \
  --mechanism-order 12 \
  --bar-chart-only \
  --enqueue-template \
  --update-template
