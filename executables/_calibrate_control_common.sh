#!/usr/bin/env bash
# Shared launcher for control proliferation calibration (mechanism 11 by default).
# Settings: config/calibration_settings.py (override via env or EXTRA_ARGS).
# Required env from caller: CELL_LINE
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

PYTHON_BIN="${PYTHON_BIN:-${ROOT_DIR}/.venv/bin/python}"
[[ -x "${PYTHON_BIN}" ]] || PYTHON_BIN="python3"

MOCK_MODE="${MOCK_MODE:-0}"
OUT_DIR="${OUT_DIR:-${ROOT_DIR}/executables/${CELL_LINE}/outputs/calibration_control}"
WORK_ROOT="${WORK_ROOT:-${OUT_DIR}/abm_evals}"
TARGETS_CSV="${TARGETS_CSV:-${ROOT_DIR}/data/calibration_targets_from_excel.csv}"
XLSX_PATH="${XLSX_PATH:-${ROOT_DIR}/data/Data Modeling CCA+PDAC 0 to 72h post Gorjet - WITH MEAN 4 experiments.xlsx}"
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

ARGS=(
  "${ROOT_DIR}/scripts/calibrate_one_case.py"
  --cell-line "${CELL_LINE}"
  --control-mode
  --use-config
  --work-root "${WORK_ROOT}"
  --out-dir "${OUT_DIR}"
  --run-command "${RUN_COMMAND}"
)

if [[ -n "${TEMPLATE_PATH:-}" ]]; then
  ARGS+=(--template "${TEMPLATE_PATH}")
fi
if [[ -n "${PARAMETER_KEYS:-}" ]]; then
  ARGS+=(--parameter-keys "${PARAMETER_KEYS}")
fi
if [[ -n "${STAGE_NFEV:-}" ]]; then
  ARGS+=(--stage-nfev "${STAGE_NFEV}")
fi
if [[ -n "${GLOBAL_NFEV:-}" ]]; then
  ARGS+=(--global-nfev "${GLOBAL_NFEV}")
fi
if [[ -n "${REPLICATES:-}" ]]; then
  ARGS+=(--replicates "${REPLICATES}")
fi

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
if [[ "${NO_EARLY_STOP:-0}" == "1" ]]; then
  ARGS+=(--no-early-stop)
fi

source_biodynamo_env

export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-1}"
export VECLIB_MAXIMUM_THREADS="${VECLIB_MAXIMUM_THREADS:-1}"
export OMP_PROC_BIND="${OMP_PROC_BIND:-true}"
export OMP_WAIT_POLICY="${OMP_WAIT_POLICY:-PASSIVE}"

echo "Control calibration (${CELL_LINE}): settings from config/calibration_settings.py"
"${PYTHON_BIN}" "${ROOT_DIR}/scripts/show_calibration_config.py" --cell-line "${CELL_LINE}" || true
echo ""

# shellcheck disable=SC2086
"${PYTHON_BIN}" "${ARGS[@]}" ${EXTRA_ARGS}

echo ""
echo "${CELL_LINE} control calibration outputs:"
echo "  Results: ${OUT_DIR}"
echo "  Fitted parameters: ${OUT_DIR}/calibrated_parameters.csv"
echo "  Fit result: ${OUT_DIR}/fit_result.json"
echo "  Live plot: ${OUT_DIR}/live_calibration_latest.png"
echo ""
echo "Edit config/calibration_settings.py to change mechanism, templates, stage_nfev, early-stop."
echo "Per-cell-line templates: templates/cell_lines/${CELL_LINE}/"
echo ""
echo "After validating the control curve, run treated cases with:"
echo "  ./executables/${CELL_LINE}/run_treat_30s.sh"
