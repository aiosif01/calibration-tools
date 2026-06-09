#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

check_process_budget
cd "$CALIB_ROOT"

echo "[INFO] Cleaning previous ISO10 outputs"
rm -rf results/optuna_runs/trial_*_ISO10_s*
rm -f results/optuna_runs/trial_*_ISO10_s*_input.csv
rm -f results/optuna_runs/study_iso10_fresh.db
rm -f results/optuna_runs/study_iso10_smoketest.db
rm -f results/optuna_runs/study_iso10_smoketest2.db
rm -f results/best_runs/best_params_ISO10.json
rm -f results/best_runs/trials_summary_ISO10.csv
rm -f results/plots/exp_vs_sim_ISO10.png
rm -f results/plots/convergence_ISO10.png
rm -f results/plots/param_importance_ISO10.png
rm -f results/plots/best_params_ISO10.csv

echo "[OK] ISO10 cleanup complete"
