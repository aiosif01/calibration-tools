#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}"
if [[ ! -d "${ROOT_DIR}/scripts" ]]; then
  ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
fi

activate_python_env() {
  if [[ "${AUTO_SOURCE_PYTHON:-1}" != "1" ]]; then
    return
  fi
  if [[ -f "${ROOT_DIR}/.venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "${ROOT_DIR}/.venv/bin/activate"
  fi
}

# shellcheck disable=SC1091
source "${ROOT_DIR}/scripts/abm_env.sh"

activate_python_env

PYTHON_BIN="${PYTHON_BIN:-${ROOT_DIR}/.venv/bin/python}"
[[ -x "${PYTHON_BIN}" ]] || PYTHON_BIN="python3"

CELL_LINE="${CELL_LINE:-EGI1}"
# Control viability baseline uses 0 s exposure (no CAP). Set EXPOSURE_SECONDS=30 for treated test runs.
EXPOSURE_SECONDS="${EXPOSURE_SECONDS:-0}"
TARGET_MODE="${TARGET_MODE:-t0_normalized}"
TIME_POINTS="${TIME_POINTS:-0,24,48,72}"
TEMPLATE_PATH="${TEMPLATE_PATH:-${ROOT_DIR}/templates/input_control_mechanism10_template.csv}"
TARGETS_CSV="${TARGETS_CSV:-${ROOT_DIR}/data/calibration_targets_from_excel.csv}"
XLSX_PATH="${XLSX_PATH:-}"
OUT_DIR="${OUT_DIR:-${ROOT_DIR}/outputs/test_template_case}"
MOCK_MODE="${MOCK_MODE:-0}"
NORMALIZE_SIM_TO_T0="${NORMALIZE_SIM_TO_T0:-1}"
COPY_FILE="${COPY_FILE:-}"
PARAMS="${PARAMS:-}"
PARAMETER_KEYS="${PARAMETER_KEYS:-}"
# Leave at 0 for control runs so the template CAP/enabled value is kept. Set to 1 for treated cases.
SET_CAP_DURATION="${SET_CAP_DURATION:-0}"

if [[ "${MOCK_MODE}" == "1" ]]; then
  RUN_COMMAND="${RUN_COMMAND:-make}"
else
  ABM_BIN="${ABM_BIN:-$(resolve_abm_bin "${CELL_LINE}" || true)}"
  if [[ -z "${ABM_BIN}" || ! -f "${ABM_BIN}" || ! -x "${ABM_BIN}" ]]; then
    echo "Error: ABM executable not found for real simulation." >&2
    abm_paths_hint
    exit 1
  fi
  RUN_COMMAND="${RUN_COMMAND:-${ABM_BIN} input.csv}"
fi

ARGS=(
  "${ROOT_DIR}/scripts/run_test_case.py"
  --cell-line "${CELL_LINE}"
  --exposure-seconds "${EXPOSURE_SECONDS}"
  --target-mode "${TARGET_MODE}"
  --time-points "${TIME_POINTS}"
  --template "${TEMPLATE_PATH}"
  --out-dir "${OUT_DIR}"
  --run-dir "${OUT_DIR}"
  --run-command "${RUN_COMMAND}"
)

if [[ -n "${COPY_FILE}" ]]; then
  ARGS+=(--copy-file "${COPY_FILE}")
fi
if [[ -n "${PARAMS}" ]]; then
  ARGS+=(--params "${PARAMS}")
fi

if [[ -n "${TARGETS_CSV}" && -f "${TARGETS_CSV}" ]]; then
  ARGS+=(--targets-csv "${TARGETS_CSV}")
fi
if [[ -n "${XLSX_PATH}" && -f "${XLSX_PATH}" ]]; then
  ARGS+=(--xlsx "${XLSX_PATH}")
fi
if [[ -n "${PARAMETER_KEYS}" ]]; then
  ARGS+=(--parameter-keys "${PARAMETER_KEYS}")
fi
if [[ "${SET_CAP_DURATION}" == "1" ]]; then
  ARGS+=(--set-cap-duration)
fi
if [[ "${MOCK_MODE}" == "1" ]]; then
  ARGS+=(--mock)
else
  ARGS+=(--no-mock)
fi
if [[ "${NORMALIZE_SIM_TO_T0}" == "1" ]]; then
  ARGS+=(--normalize-sim-to-t0)
else
  ARGS+=(--no-normalize-sim-to-t0)
fi

source_biodynamo_env

export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-1}"
export VECLIB_MAXIMUM_THREADS="${VECLIB_MAXIMUM_THREADS:-1}"
export OMP_PROC_BIND="${OMP_PROC_BIND:-true}"
export OMP_WAIT_POLICY="${OMP_WAIT_POLICY:-PASSIVE}"

"${PYTHON_BIN}" "${ARGS[@]}"

echo ""
echo "Test run outputs:"
echo "  Run directory: ${OUT_DIR}"
echo "  Curve plot: ${OUT_DIR}/simulation_preview.png"
if [[ "${MOCK_MODE}" == "1" ]]; then
  echo "  ABM visualization: skipped (MOCK_MODE=1)"
else
  echo "  ABM visualization: ${OUT_DIR}/results_CAP_mech12/"
  echo "    Open the .pvd files in ParaView from that folder."
fi