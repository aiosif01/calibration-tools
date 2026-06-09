#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CALIB_ROOT="$SCRIPT_DIR"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
PYTHON_BIN=""
MAX_USER_PROCESSES="${MAX_USER_PROCESSES:-2000}"

check_process_budget() {
  local total make_count cmake_count sh_count abm_count
  total=$(/usr/bin/ps -u "$USER" --no-headers | /usr/bin/wc -l)
  make_count=$(/usr/bin/pgrep -c -u "$USER" -x make    || true)
  cmake_count=$(/usr/bin/pgrep -c -u "$USER" -x cmake   || true)
  sh_count=$(/usr/bin/pgrep   -c -u "$USER" -x sh      || true)
  abm_count=$(/usr/bin/pgrep  -c -u "$USER" -x ABM4bio || true)

  echo "[INFO] User processes: $total  (make=$make_count  cmake=$cmake_count  sh=$sh_count  ABM4bio=$abm_count)"

  if [[ "$total" -gt "$MAX_USER_PROCESSES" ]]; then
    echo "ERROR: too many user processes ($total > $MAX_USER_PROCESSES). Run ./0_safe_init.sh first." >&2
    exit 20
  fi
  if [[ "$make_count" -gt 0 || "$cmake_count" -gt 0 ]]; then
    echo "ERROR: active build processes detected. Run ./0_safe_init.sh first." >&2
    exit 21
  fi
  if [[ "${abm_count:-0}" -gt 8 ]]; then
    echo "ERROR: too many ABM4bio processes ($abm_count). Run ./0_safe_init.sh first." >&2
    exit 22
  fi
}

check_runtime() {
  # Prefer explicit project venv python to avoid interpreter drift after `thisbdm`.
  if [[ -n "${VIRTUAL_ENV:-}" && -x "$VIRTUAL_ENV/bin/python" ]]; then
    PYTHON_BIN="$VIRTUAL_ENV/bin/python"
  elif [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
    PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  else
    echo "ERROR: no python interpreter found."
    echo "Activate the ABM4bio venv first (source $REPO_ROOT/.venv/bin/activate)."
    exit 1
  fi

  export PYTHON_BIN
  echo "[INFO] Using python: $PYTHON_BIN"

  if [[ -z "${ROOTSYS:-}" ]]; then
    echo "ERROR: ROOT/BioDynaMo runtime is not sourced in this shell."
    echo "Run this first, then re-run the script:"
    echo "  source $REPO_ROOT/libs/biodynamo-v1.05.143/bin/thisbdm.sh"
    exit 1
  fi

  check_process_budget
}

iso10_storage_url() {
  local db_name="${1:-study_iso10_fresh.db}"
  echo "sqlite:///results/optuna_runs/${db_name}"
}

iso10_best_params_path() {
  echo "results/best_runs/best_params_ISO10.json"
}
