#!/usr/bin/env bash
# Shared launcher for ANN surrogate calibration workflow.
# Required env: CELL_LINE, ANN_STEP (generate|train|calibrate|all)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-${0}}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}"
while [[ ! -d "${ROOT_DIR}/scripts" && "${ROOT_DIR}" != "/" ]]; do
  ROOT_DIR="$(dirname "${ROOT_DIR}")"
done

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
    if "${candidate}" -c "import torch" >/dev/null 2>&1; then
      echo "${candidate}"
      return
    fi
  done
  for candidate in "${candidates[@]}"; do
    [[ -n "${candidate}" && -x "${candidate}" ]] || continue
    echo "${candidate}"
    return
  done
  echo "python3"
}

PYTHON_BIN="$(resolve_python_bin)"

CELL_LINE="${CELL_LINE:?CELL_LINE required}"
ANN_STEP="${ANN_STEP:-all}"
CASE_LABEL="${CASE_LABEL:-control}"
MOCK_MODE="${MOCK_MODE:-0}"
N_SAMPLES="${N_SAMPLES:-}"
TARGETS_CSV="${TARGETS_CSV:-${ROOT_DIR}/data/calibration_targets_from_excel.csv}"
OUT_DIR="${OUT_DIR:-${ROOT_DIR}/outputs/ann/${CELL_LINE}/${CASE_LABEL}}"
WORK_ROOT="${WORK_ROOT:-${OUT_DIR}/abm_evals}"
EXTRA_ARGS="${EXTRA_ARGS:-}"

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

COMMON_ARGS=(
  --cell-line "${CELL_LINE}"
  --case-label "${CASE_LABEL}"
  --out-dir "${OUT_DIR}"
)
GENERATE_ARGS=(
  "${COMMON_ARGS[@]}"
  --work-root "${WORK_ROOT}"
  --run-command "${RUN_COMMAND}"
  --parameter-space "${ROOT_DIR}/configs/parameter_space_control.yaml"
)
CALIBRATE_ARGS=(
  "${COMMON_ARGS[@]}"
  --work-root "${WORK_ROOT}"
  --run-command "${RUN_COMMAND}"
)
if [[ -n "${TARGETS_CSV}" && -f "${TARGETS_CSV}" ]]; then
  GENERATE_ARGS+=(--targets-csv "${TARGETS_CSV}")
  CALIBRATE_ARGS+=(--targets-csv "${TARGETS_CSV}")
fi
if [[ "${MOCK_MODE}" == "1" ]]; then
  GENERATE_ARGS+=(--mock)
  CALIBRATE_ARGS+=(--mock)
fi
if [[ -n "${N_SAMPLES}" ]]; then
  GENERATE_ARGS+=(--n-samples "${N_SAMPLES}")
fi

source_biodynamo_env
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"

run_generate() {
  echo "=== ANN dataset generation (${CELL_LINE}) ==="
  # shellcheck disable=SC2086
  "${PYTHON_BIN}" "${ROOT_DIR}/scripts/generate_ann_dataset.py" "${GENERATE_ARGS[@]}" ${EXTRA_ARGS}
}

run_train() {
  echo "=== ANN surrogate training (${CELL_LINE}) ==="
  TRAIN_ARGS=("${COMMON_ARGS[@]}")
  if [[ "${MOCK_MODE}" == "1" ]]; then
    TRAIN_ARGS+=(--mock)
  fi
  # shellcheck disable=SC2086
  "${PYTHON_BIN}" "${ROOT_DIR}/scripts/train_ann_surrogate.py" "${TRAIN_ARGS[@]}" ${EXTRA_ARGS}
}

run_calibrate() {
  echo "=== ANN inverse calibration (${CELL_LINE}) ==="
  # shellcheck disable=SC2086
  "${PYTHON_BIN}" "${ROOT_DIR}/scripts/calibrate_with_ann.py" "${CALIBRATE_ARGS[@]}" ${EXTRA_ARGS}
}

case "${ANN_STEP}" in
  generate) run_generate ;;
  train) run_train ;;
  calibrate) run_calibrate ;;
  all)
    run_generate
    run_train
    run_calibrate
    ;;
  *)
    echo "Unknown ANN_STEP=${ANN_STEP}. Use generate|train|calibrate|all." >&2
    exit 1
    ;;
esac

echo ""
echo "ANN outputs (${CELL_LINE}/${CASE_LABEL}): ${OUT_DIR}"
