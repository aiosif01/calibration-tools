#!/usr/bin/env bash
# EAGAIN-safe wrapper for CAP Optuna calibration.
# Enforces:
#   - exclusive lock to block concurrent calibration runs
#   - process-budget preflight (total, make, cmake)
#   - BLAS / OpenMP thread caps before numpy import
#   - pyenv no-op shim when pyenv is absent
set -euo pipefail

PS_BIN="/bin/ps"
WC_BIN="/usr/bin/wc"
ID_BIN="/usr/bin/id"
PGREP_BIN="$(command -v pgrep 2>/dev/null || echo '')"

safe_count() {
  # pgrep -c prints 0 and exits with code 1 for no matches.
  # Avoid fallback patterns that can yield malformed values like '0\n0'.
  local out
  out="$($@ 2>/dev/null || true)"
  out="$(printf '%s' "$out" | tr -d '[:space:]')"
  if [[ "$out" =~ ^[0-9]+$ ]]; then
    printf '%s' "$out"
  else
    printf '0'
  fi
}

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ABM4BIO_ROOT="$(realpath "${THIS_DIR}/../..")"

PYTHON_DEFAULT="python3"
PYTHON_BIN="${PYTHON_BIN:-${PYTHON_DEFAULT}}"
BDM_ENV_SCRIPT="${BDM_ENV_SCRIPT:-${ABM4BIO_ROOT}/libs/biodynamo-v1.05.143/bin/thisbdm.sh}"

if [[ ! -f "${BDM_ENV_SCRIPT}" ]]; then
  echo "ERROR: BioDynaMo env script not found: ${BDM_ENV_SCRIPT}" >&2
  exit 2
fi

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "ERROR: Python binary not found in PATH: ${PYTHON_BIN}" >&2
  exit 2
fi

run_user="${USER:-$(${ID_BIN} -un)}"
max_process_count="${MAX_PROCESS_COUNT:-2000}"
# Allow a small number of active `make` processes when calibration is launched
# from a Makefile target (parent + child make). Keep default strict for direct runs.
allowed_active_make="${CAP_ALLOW_ACTIVE_MAKE:-0}"
allowed_active_cmake="${CAP_ALLOW_ACTIVE_CMAKE:-0}"
proc_count="$(${PS_BIN} -u "${run_user}" --no-header 2>/dev/null | ${WC_BIN} -l | tr -d ' ')"
lwp_count="$(${PS_BIN} -eLf -u "${run_user}" 2>/dev/null | ${WC_BIN} -l | tr -d ' ')"
if [[ -n "${proc_count}" ]] && [[ "${proc_count}" -gt "${max_process_count}" ]]; then
  echo "ERROR: process count is too high (${proc_count})." >&2
  echo "       user=${run_user}  max=${max_process_count}  lwp_count=${lwp_count}" >&2
  echo "Log out/in to clear stale processes before launching calibration." >&2
  exit 3
fi

# Refuse to start if make/cmake process counts exceed configured thresholds.
# cmake remains strict-zero by default. make can be relaxed via CAP_ALLOW_ACTIVE_MAKE
# to support invocation through make targets without false positives.
if [[ -n "${PGREP_BIN}" ]]; then
  make_cnt="$(safe_count "${PGREP_BIN}" -c -u "${run_user}" -x make)"
  if [[ "${make_cnt}" -gt "${allowed_active_make}" ]]; then
    echo "ERROR: ${make_cnt} active 'make' process(es) found (allowed: ${allowed_active_make})." >&2
    echo "       Wait for running builds/simulations to finish before calibrating." >&2
    exit 3
  fi

  cmake_cnt="$(safe_count "${PGREP_BIN}" -c -u "${run_user}" -x cmake)"
  if [[ "${cmake_cnt}" -gt "${allowed_active_cmake}" ]]; then
    echo "ERROR: ${cmake_cnt} active 'cmake' process(es) found (allowed: ${allowed_active_cmake})." >&2
    echo "       Wait for running builds/simulations to finish before calibrating." >&2
    exit 3
  fi
fi

export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export BLIS_NUM_THREADS=1
export OMP_NUM_THREADS=1

export BDM_THISBDM_SILENT=true
# BioDynaMo env script may call pyenv shell/rehash; provide a no-op shim when pyenv is absent.
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
# shellcheck disable=SC1090
set +u
if ! source "${BDM_ENV_SCRIPT}" >/dev/null; then
  set -u
  echo "ERROR: failed to source BioDynaMo environment: ${BDM_ENV_SCRIPT}" >&2
  exit 4
fi
set -u

cd "${THIS_DIR}"

# Acquire an exclusive lock so only one calibration run can execute at a time.
# fd 9 is inherited by the Python process after exec, keeping the lock alive.
CAP_LOCK_DIR="${THIS_DIR}/calibration_outputs"
mkdir -p "${CAP_LOCK_DIR}"
CAP_LOCK_FILE="${CAP_LOCK_DIR}/.cap_optuna.lock"
exec 9>"${CAP_LOCK_FILE}"
if ! flock -n 9; then
  echo "ERROR: another CAP Optuna calibration is already in progress." >&2
  echo "       Lock file: ${CAP_LOCK_FILE}" >&2
  echo "       If the previous run crashed, remove the lock with: rm -f '${CAP_LOCK_FILE}'" >&2
  exit 5
fi

exec "${PYTHON_BIN}" scripts/calibrate_cap_optuna.py "$@"
