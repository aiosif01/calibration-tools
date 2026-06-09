#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CAP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

MAX_USER_PROCESSES="${MAX_USER_PROCESSES:-2000}"
PYTHON_BIN=""

check_process_budget() {
  local total make_count cmake_count sh_count abm_count
  total=$(/usr/bin/ps -u "$USER" --no-headers 2>/dev/null | /usr/bin/wc -l || echo 999)
  make_count=$(/usr/bin/pgrep -c -u "$USER" -x make 2>/dev/null || true)
  cmake_count=$(/usr/bin/pgrep -c -u "$USER" -x cmake 2>/dev/null || true)
  sh_count=$(/usr/bin/pgrep -c -u "$USER" -x sh 2>/dev/null || true)
  abm_count=$(/usr/bin/pgrep -c -u "$USER" -x ABM4bio 2>/dev/null || true)

  make_count="${make_count:-0}"; cmake_count="${cmake_count:-0}"; sh_count="${sh_count:-0}"; abm_count="${abm_count:-0}"

  echo "[INFO] Process budget: total=$total make=$make_count cmake=$cmake_count sh=$sh_count ABM4bio=$abm_count"

  if [[ "$total" -gt "$MAX_USER_PROCESSES" ]]; then
    echo "ERROR: too many user processes ($total > $MAX_USER_PROCESSES)." >&2
    exit 20
  fi
  if [[ "$make_count" -gt 0 || "$cmake_count" -gt 0 ]]; then
    echo "ERROR: active make/cmake process detected; refuse to start calibration." >&2
    exit 21
  fi
}

pick_python() {
  if [[ -n "${PYTHON_BIN:-}" ]] && command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v "$PYTHON_BIN")"
  elif [[ -n "${VIRTUAL_ENV:-}" && -x "$VIRTUAL_ENV/bin/python3" ]]; then
    PYTHON_BIN="$VIRTUAL_ENV/bin/python3"
  elif [[ -x "$REPO_ROOT/.venv/bin/python3" ]]; then
    PYTHON_BIN="$REPO_ROOT/.venv/bin/python3"
  elif [[ -x "/home/aiwsif/miniconda/bin/python3" ]]; then
    PYTHON_BIN="/home/aiwsif/miniconda/bin/python3"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    echo "ERROR: no python3 interpreter found." >&2
    exit 1
  fi

  export PYTHON_BIN
  echo "[INFO] Using python: $PYTHON_BIN"

  "$PYTHON_BIN" -c "import optuna,pandas,numpy" >/dev/null 2>&1 || {
    echo "ERROR: python env '$PYTHON_BIN' is missing optuna/pandas/numpy." >&2
    echo "       Install in .venv or activate the env that has these packages." >&2
    exit 2
  }
}

check_runtime() {
  pick_python
  check_process_budget

  export BDM_ENV_SCRIPT="${BDM_ENV_SCRIPT:-$REPO_ROOT/libs/biodynamo-v1.05.143/bin/thisbdm.sh}"
  if [[ ! -f "$BDM_ENV_SCRIPT" ]]; then
    echo "ERROR: BioDynaMo env script not found: $BDM_ENV_SCRIPT" >&2
    exit 3
  fi

  if [[ ! -x "$REPO_ROOT/build/ABM4bio" ]]; then
    echo "ERROR: ABM4bio executable missing: $REPO_ROOT/build/ABM4bio" >&2
    exit 4
  fi

  export CAP_ALLOW_ACTIVE_MAKE="${CAP_ALLOW_ACTIVE_MAKE:-0}"
  export CAP_ALLOW_ACTIVE_CMAKE="${CAP_ALLOW_ACTIVE_CMAKE:-0}"
}

cap_lock_file() {
  local stage="$1"
  echo "${TMPDIR:-/tmp}/abm4bio_cap_${stage}_${USER}.lock"
}
