#!/usr/bin/env bash
# Shared launcher for per-cell-line test runs.
# Required env from caller: CELL_LINE, EXPOSURE_SECONDS, OUTPUT_LABEL, SET_CAP_DURATION
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
OUT_DIR="${OUT_DIR:-${ROOT_DIR}/executables/${CELL_LINE}/outputs/${OUTPUT_LABEL}}"
NORMALIZE_SIM_TO_T0="${NORMALIZE_SIM_TO_T0:-1}"
COPY_FILE="${COPY_FILE:-}"
PARAMS="${PARAMS:-}"
PARAMETER_KEYS="${PARAMETER_KEYS:-}"

if [[ "${MOCK_MODE}" == "1" ]]; then
  RUN_COMMAND="${RUN_COMMAND:-make}"
else
  ABM_BIN="${ABM_BIN:-$(resolve_abm_bin || true)}"
  if [[ -z "${ABM_BIN}" || ! -x "${ABM_BIN}" ]]; then
    echo "Error: ABM executable not found for ${CELL_LINE}." >&2
    echo "Set ABM_BIN or place the binary at /home/aiwsif/Desktop/ABM4bio/build/ABM4bio" >&2
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
echo "${CELL_LINE} ${OUTPUT_LABEL} test outputs:"
echo "  Run directory: ${OUT_DIR}"
echo "  Curve plot: ${OUT_DIR}/simulation_preview.png"
if [[ "${MOCK_MODE}" == "1" ]]; then
  echo "  ABM visualization: skipped (MOCK_MODE=1)"
else
  echo "  ABM visualization: ${OUT_DIR}/results_CAP_mech12/"
  echo "    Open the .pvd files in ParaView from that folder."
fi
