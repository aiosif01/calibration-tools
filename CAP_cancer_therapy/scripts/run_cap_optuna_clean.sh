#!/usr/bin/env bash
# EAGAIN-safe wrapper for CAP Optuna calibration.
set -euo pipefail

PS_BIN="/bin/ps"
WC_BIN="/usr/bin/wc"
ID_BIN="/usr/bin/id"
PGREP_BIN="$(command -v pgrep 2>/dev/null || echo '')"

safe_count() {
  local out
  out="$("$@" 2>/dev/null || true)"
  out="$(printf '%s' "$out" | tr -d '[:space:]')"
  if [[ "$out" =~ ^[0-9]+$ ]]; then
    printf '%s' "$out"
  else
    printf '0'
  fi
}

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.."; pwd)"
ABM4BIO_ROOT="$(realpath "${THIS_DIR}/../..")"

PYTHON_DEFAULT="python3"
PYTHON_BIN="${PYTHON_BIN:-${PYTHON_DEFAULT}}"
BDM_ENV_SCRIPT="${BDM_ENV_SCRIPT:-${ABM4BIO_ROOT}/libs/biodynamo-v1.05.143/bin/thisbdm.sh}"

if [[ ! -f "${BDM_ENV_SCRIPT}" ]]; then
  echo "ERROR: BioDynaMo env script not found: ${BDM_ENV_SCRIPT}" >&2
  exit 2
fi

export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1
export OMP_NUM_THREADS=1

export BDM_THISBDM_SILENT=true
if ! command -v pyenv >/dev/null 2>&1; then
  pyenv() {
    case "${1:-}" in
      rehash|shell)
        return 0
        ;;
      *)
        return 0
        ;;
    esac
  }
fi
set +u
if ! source "${BDM_ENV_SCRIPT}" >/dev/null; then
  set -u
  echo "ERROR: failed to source BioDynaMo environment: ${BDM_ENV_SCRIPT}" >&2
  exit 4
fi
set -u

cd "${THIS_DIR}"

CAP_LOCK_DIR="${THIS_DIR}/calibration_outputs"
mkdir -p "${CAP_LOCK_DIR}"
CAP_LOCK_FILE="${CAP_LOCK_DIR}/.cap_optuna.lock"
exec 9>"${CAP_LOCK_FILE}"
if ! flock -n 9; then
  echo "ERROR: another CAP Optuna calibration is already in progress." >&2
  exit 5
fi

exec "${PYTHON_BIN}" scripts/calibrate_cap_optuna.py "$@"
