#!/usr/bin/env bash
set -euo pipefail

# Usage: ./calibration/1_run_cap_stage1.sh [n_trials] [seed]
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

TRIALS="${1:-40}"
SEED="${2:-1234}"
LOCK_FILE="$(cap_lock_file stage1)"

check_runtime
cd "$CAP_ROOT"

if [[ -e "$LOCK_FILE" ]]; then
  echo "ERROR: stage1 calibration active or stale lock exists: $LOCK_FILE" >&2
  exit 10
fi
trap 'rm -f "$LOCK_FILE"' EXIT
: > "$LOCK_FILE"

bash scripts/run_cap_optuna_clean.sh \
  --stage control_baseline \
  --data-csv data/experimental_targets_t0_normalized_corrected_units.csv \
  --manifest-csv data/experimental_case_manifest_corrected_units.csv \
  --param-space-csv data/optuna_parameter_space_mechanism12.csv \
  --template-input input_mechanism12_CAP_template.csv \
  --abm-binary ../../build/ABM4bio \
  --bdm-env-script ../../libs/biodynamo-v1.05.143/bin/thisbdm.sh \
  --out-dir calibration_outputs/CAP_optuna \
  --cell-lines EGI1,HuCCT1,PANC1,MiaPaCa2 \
  --exposures-min 0 \
  --n-trials "$TRIALS" \
  --n-startup-trials 10 \
  --replicates 1 \
  --sampler-seed "$SEED" \
  --base-seed "$SEED" \
  --omp-threads 4 \
  --timeout-s 1800 \
  --mechanism-order 12 \
  --enqueue-template \
  --update-template
