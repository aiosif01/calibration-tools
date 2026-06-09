#!/usr/bin/env bash
# Shared launcher for control proliferation calibration (no CAP).
# Required env from caller: CELL_LINE
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}"
while [[ ! -d "${ROOT_DIR}/scripts" && "${ROOT_DIR}" != "/" ]]; do
  ROOT_DIR="$(dirname "${ROOT_DIR}")"
done
if [[ ! -d "${ROOT_DIR}/scripts" ]]; then
  echo "Error: could not locate LM-python project root from ${SCRIPT_DIR}" >&2
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

resolve_abm_bin() {
  local candidates=(
    "${ABM_BIN:-}"
    "${ROOT_DIR}/ABM4bio_${CELL_LINE}"
    "${ROOT_DIR}/ABM4bio"
    "${ROOT_DIR}/build/ABM4bio"
    "/home/aiwsif/Desktop/ABM4bio/build/ABM4bio"
  )
  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -n "${candidate}" && -x "${candidate}" ]]; then
      echo "${candidate}"
      return 0
    fi
  done
  echo ""
  return 1
}

activate_python_env

PYTHON_BIN="${PYTHON_BIN:-${ROOT_DIR}/.venv/bin/python}"
[[ -x "${PYTHON_BIN}" ]] || PYTHON_BIN="python3"

MOCK_MODE="${MOCK_MODE:-0}"
TARGET_MODE="${TARGET_MODE:-t0_normalized}"
TIME_POINTS="${TIME_POINTS:-0,24,48,72}"
TEMPLATE_PATH="${TEMPLATE_PATH:-${ROOT_DIR}/templates/input_mechanism12_CAP_template.csv}"
TARGETS_CSV="${TARGETS_CSV:-${ROOT_DIR}/data/calibration_targets_from_excel.csv}"
XLSX_PATH="${XLSX_PATH:-${ROOT_DIR}/data/Data Modeling CCA+PDAC 0 to 72h post Gorjet - WITH MEAN 4 experiments.xlsx}"
OUT_DIR="${OUT_DIR:-${ROOT_DIR}/executables/${CELL_LINE}/outputs/calibration_control}"
WORK_ROOT="${WORK_ROOT:-${OUT_DIR}/abm_evals}"

# Staged control calibration budgets: global search + 24h + 24+48h + full curve
GLOBAL_NFEV="${GLOBAL_NFEV:-40}"
STAGE_NFEV="${STAGE_NFEV:-40,50,60}"
MAX_NFEV="${MAX_NFEV:-150}"
REPLICATES="${REPLICATES:-2}"
ABM_BASE_SEED="${ABM_BASE_SEED:-1234}"
ABM_SEED_STEP="${ABM_SEED_STEP:-17}"
DIFF_STEP="${DIFF_STEP:-0.03}"
XTOL="${XTOL:-1e-6}"
FTOL="${FTOL:-1e-6}"
GTOL="${GTOL:-1e-6}"
PARAMETER_KEYS="${PARAMETER_KEYS:-cancer_cell/can_divide/probability,cancer_cell/can_apoptose/probability,cancer_cell/can_grow/diameter_rate,cancer_cell/can_grow/probability,cancer_cell/can_divide/time_window}"
EXTRA_ARGS="${EXTRA_ARGS:-}"

if [[ "${MOCK_MODE}" == "1" ]]; then
  RUN_COMMAND="${RUN_COMMAND:-make}"
else
  ABM_BIN="${ABM_BIN:-$(resolve_abm_bin || true)}"
  if [[ -z "${ABM_BIN}" || ! -x "${ABM_BIN}" ]]; then
    echo "Error: ABM executable not found for ${CELL_LINE}." >&2
    exit 1
  fi
  RUN_COMMAND="${RUN_COMMAND:-${ABM_BIN} input.csv}"
fi

ARGS=(
  "${ROOT_DIR}/scripts/calibrate_one_case.py"
  --cell-line "${CELL_LINE}"
  --exposure-seconds 0
  --target-mode "${TARGET_MODE}"
  --time-points "${TIME_POINTS}"
  --template "${TEMPLATE_PATH}"
  --work-root "${WORK_ROOT}"
  --out-dir "${OUT_DIR}"
  --run-command "${RUN_COMMAND}"
  --parameter-keys "${PARAMETER_KEYS}"
  --control-mode
  --staged
  --log-space
  --global-nfev "${GLOBAL_NFEV}"
  --stage-nfev "${STAGE_NFEV}"
  --max-nfev "${MAX_NFEV}"
  --replicates "${REPLICATES}"
  --abm-base-seed "${ABM_BASE_SEED}"
  --abm-seed-step "${ABM_SEED_STEP}"
  --diff-step "${DIFF_STEP}"
  --xtol "${XTOL}"
  --ftol "${FTOL}"
  --gtol "${GTOL}"
  --method trf
)

if [[ -n "${TARGETS_CSV}" && -f "${TARGETS_CSV}" ]]; then
  ARGS+=(--targets-csv "${TARGETS_CSV}")
elif [[ -n "${XLSX_PATH}" && -f "${XLSX_PATH}" ]]; then
  ARGS+=(--xlsx "${XLSX_PATH}")
fi
if [[ "${MOCK_MODE}" == "1" ]]; then
  ARGS+=(--mock --replicates 1)
fi
if [[ "${LIVE:-1}" == "1" ]]; then
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

# shellcheck disable=SC2086
"${PYTHON_BIN}" "${ARGS[@]}" ${EXTRA_ARGS}

echo ""
echo "${CELL_LINE} control calibration outputs:"
echo "  Results: ${OUT_DIR}"
echo "  Fitted parameters: ${OUT_DIR}/calibrated_parameters.csv"
echo "  Fit result: ${OUT_DIR}/fit_result.json"
echo "  Live plot: ${OUT_DIR}/live_calibration_latest.png"
echo ""
echo "Workflow: global search (${GLOBAL_NFEV} evals) -> staged local fits (${STAGE_NFEV})"
echo "  Metric: viable cells, log-space residuals, ${REPLICATES} replicate(s)/eval"
echo ""
echo "After validating the control curve, run treated cases with:"
echo "  ./executables/${CELL_LINE}/run_treat_30s.sh"
