#!/usr/bin/env bash
# Shared launcher for Optuna calibration.
# Required env from caller: CELL_LINE, CASE_MODE (control|treatment)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}"
while [[ ! -d "${ROOT_DIR}/scripts" && "${ROOT_DIR}" != "/" ]]; do
  ROOT_DIR="$(dirname "${ROOT_DIR}")"
done
if [[ ! -d "${ROOT_DIR}/scripts" ]]; then
  echo "Error: could not locate calibration-tools root from ${SCRIPT_DIR}" >&2
  exit 1
fi

# shellcheck disable=SC1091
source "${ROOT_DIR}/scripts/abm_env.sh"

activate_python_env() {
  if [[ "${AUTO_SOURCE_PYTHON:-1}" != "1" ]]; then
    return
  fi
  if [[ -f "${ROOT_DIR}/.venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "${ROOT_DIR}/.venv/bin/activate"
  fi
}

activate_python_env

resolve_python_bin() {
  if [[ -n "${PYTHON_BIN:-}" && -x "${PYTHON_BIN}" ]]; then
    echo "${PYTHON_BIN}"
    return
  fi
  local candidates=(
    "${ROOT_DIR}/.venv/bin/python"
    "$(command -v python3 2>/dev/null || true)"
    "$(command -v python 2>/dev/null || true)"
  )
  local candidate
  for candidate in "${candidates[@]}"; do
    [[ -n "${candidate}" && -x "${candidate}" ]] || continue
    if "${candidate}" -c "import optuna" >/dev/null 2>&1; then
      echo "${candidate}"
      return
    fi
  done
  # Fall back to first available interpreter (will surface a clear import error).
  for candidate in "${candidates[@]}"; do
    [[ -n "${candidate}" && -x "${candidate}" ]] || continue
    echo "${candidate}"
    return
  done
  echo "python3"
}

PYTHON_BIN="$(resolve_python_bin)"

MOCK_MODE="${MOCK_MODE:-0}"
CASE_MODE="${CASE_MODE:-control}"
N_TRIALS="${N_TRIALS:-}"
REPLICATES="${REPLICATES:-}"
TARGETS_CSV="${TARGETS_CSV:-${ROOT_DIR}/data/calibration_targets_from_excel.csv}"
XLSX_PATH="${XLSX_PATH:-${ROOT_DIR}/data/Data Modeling CCA+PDAC 0 to 72h post Gorjet - WITH MEAN 4 experiments.xlsx}"
EXTRA_ARGS="${EXTRA_ARGS:-}"

if [[ "${CASE_MODE}" == "control" ]]; then
  OUT_DIR="${OUT_DIR:-${ROOT_DIR}/outputs/optuna/${CELL_LINE}/control}"
  WORK_ROOT="${WORK_ROOT:-${OUT_DIR}/abm_evals}"
  STORAGE="${STORAGE:-sqlite:///${ROOT_DIR}/outputs/optuna/studies/${CELL_LINE}_control.db}"
  SCRIPT="${ROOT_DIR}/scripts/run_optuna_control.py"
  CASE_ARGS=(--cell-line "${CELL_LINE}")
else
  EXPOSURE_SECONDS="${EXPOSURE_SECONDS:?EXPOSURE_SECONDS required for treatment mode}"
  OUT_DIR="${OUT_DIR:-${ROOT_DIR}/outputs/optuna/${CELL_LINE}/treat_${EXPOSURE_SECONDS}s}"
  WORK_ROOT="${WORK_ROOT:-${OUT_DIR}/abm_evals}"
  STORAGE="${STORAGE:-sqlite:///${ROOT_DIR}/outputs/optuna/studies/${CELL_LINE}_treat_${EXPOSURE_SECONDS}s.db}"
  SCRIPT="${ROOT_DIR}/scripts/run_optuna_treatment.py"
  CASE_ARGS=(--cell-line "${CELL_LINE}" --exposure-seconds "${EXPOSURE_SECONDS}")
fi

if [[ "${MOCK_MODE}" == "1" ]]; then
  RUN_COMMAND="${RUN_COMMAND:-make}"
else
  ABM_BIN="${ABM_BIN:-$(resolve_abm_bin "${CELL_LINE}" || true)}"
  if [[ -z "${ABM_BIN}" || ! -f "${ABM_BIN}" || ! -x "${ABM_BIN}" ]]; then
    echo "Error: ABM executable not found for ${CELL_LINE}." >&2
    abm_paths_hint
    exit 1
  fi
  RUN_COMMAND="${RUN_COMMAND:-${ABM_BIN} input.csv}"
fi

ARGS=(
  "${SCRIPT}"
  "${CASE_ARGS[@]}"
  --use-config
  --work-root "${WORK_ROOT}"
  --out-dir "${OUT_DIR}"
  --run-command "${RUN_COMMAND}"
  --storage "${STORAGE}"
  --parameter-space "${ROOT_DIR}/configs/parameter_space_${CASE_MODE}.yaml"
  --objective-config "${ROOT_DIR}/configs/objective_${CASE_MODE}.yaml"
)

if [[ -n "${N_TRIALS}" ]]; then
  ARGS+=(--n-trials "${N_TRIALS}")
fi
if [[ -n "${REPLICATES}" ]]; then
  ARGS+=(--replicates "${REPLICATES}")
fi
if [[ -n "${TARGETS_CSV}" && -f "${TARGETS_CSV}" ]]; then
  ARGS+=(--targets-csv "${TARGETS_CSV}")
elif [[ -n "${XLSX_PATH}" && -f "${XLSX_PATH}" ]]; then
  ARGS+=(--xlsx "${XLSX_PATH}")
fi
if [[ "${MOCK_MODE}" == "1" ]]; then
  ARGS+=(--mock --replicates 1 --n-trials "${N_TRIALS:-20}")
fi
if [[ "${LIVE:-0}" == "1" ]]; then
  ARGS+=(--live)
fi

source_biodynamo_env

export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-1}"
export VECLIB_MAXIMUM_THREADS="${VECLIB_MAXIMUM_THREADS:-1}"
export OMP_PROC_BIND="${OMP_PROC_BIND:-true}"
export OMP_WAIT_POLICY="${OMP_WAIT_POLICY:-PASSIVE}"

echo "Optuna ${CASE_MODE} calibration (${CELL_LINE}): configs/runtime_local.yaml + configs/parameter_space_${CASE_MODE}.yaml"
"${PYTHON_BIN}" "${ROOT_DIR}/scripts/show_calibration_config.py" --cell-line "${CELL_LINE}" || true
echo ""

# shellcheck disable=SC2086
"${PYTHON_BIN}" "${ARGS[@]}" ${EXTRA_ARGS}

echo ""
echo "${CELL_LINE} Optuna ${CASE_MODE} outputs:"
echo "  Results: ${OUT_DIR}"
echo "  Study DB: ${STORAGE}"
echo "  Best parameters: ${OUT_DIR}/calibrated_parameters.csv"
echo "  Figures: ${OUT_DIR}/figures/"
