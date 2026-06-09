#!/usr/bin/env bash

# Shared ABM4bio / BioDynaMo path resolution for calibration-tools.
# This repo does not bundle ABM4bio; point at an external checkout via
# scripts/abm_paths.local.sh (copy from abm_paths.local.sh.example).

_ABM_ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "${_ABM_ENV_DIR}/abm_paths.local.sh" ]]; then
  # shellcheck disable=SC1091
  source "${_ABM_ENV_DIR}/abm_paths.local.sh"
fi

# Default external ABM4bio tree (sibling repo on Desktop).
DEFAULT_ABM4BIO_ROOT="${HOME}/Desktop/ABM4bio"

resolve_abm4bio_root() {
  if [[ -n "${ABM4BIO_ROOT:-}" && -d "${ABM4BIO_ROOT}" ]]; then
    echo "${ABM4BIO_ROOT}"
    return 0
  fi

  if [[ -d "${DEFAULT_ABM4BIO_ROOT}" ]]; then
    echo "${DEFAULT_ABM4BIO_ROOT}"
    return 0
  fi

  return 1
}

resolve_bdmsys() {
  if [[ -n "${BDMSYS:-}" && -d "${BDMSYS}" ]]; then
    echo "${BDMSYS}"
    return 0
  fi

  local abm_root=""
  abm_root="$(resolve_abm4bio_root || true)"
  if [[ -n "${abm_root}" ]]; then
    local candidate="${abm_root}/libs/biodynamo-v1.05.143"
    if [[ -d "${candidate}" ]]; then
      echo "${candidate}"
      return 0
    fi

    local bdm_glob
    for bdm_glob in "${abm_root}"/libs/biodynamo-*; do
      if [[ -d "${bdm_glob}" ]]; then
        echo "${bdm_glob}"
        return 0
      fi
    done
  fi

  return 1
}

# Resolve an ABM4bio executable (regular file, not a directory).
# Optional arg: cell line name for per-line overrides (ABM_BIN_EGI1, etc.).
resolve_abm_bin() {
  local cell_line="${1:-}"
  local candidate abm_root var_name

  if [[ -n "${ABM_BIN:-}" && -f "${ABM_BIN}" && -x "${ABM_BIN}" ]]; then
    echo "${ABM_BIN}"
    return 0
  fi

  if [[ -n "${cell_line}" ]]; then
    var_name="ABM_BIN_${cell_line}"
    candidate="${!var_name:-}"
    if [[ -n "${candidate}" && -f "${candidate}" && -x "${candidate}" ]]; then
      echo "${candidate}"
      return 0
    fi
  fi

  abm_root="$(resolve_abm4bio_root || true)"
  if [[ -n "${abm_root}" ]]; then
    if [[ -n "${cell_line}" ]]; then
      candidate="${abm_root}/build/ABM4bio_${cell_line}"
      if [[ -f "${candidate}" && -x "${candidate}" ]]; then
        echo "${candidate}"
        return 0
      fi
    fi

    candidate="${abm_root}/build/ABM4bio"
    if [[ -f "${candidate}" && -x "${candidate}" ]]; then
      echo "${candidate}"
      return 0
    fi
  fi

  return 1
}

abm_paths_hint() {
  cat >&2 <<EOF
ABM4bio executable not found.

This calibration repo expects ABM4bio as an external dependency.

1. Build ABM4bio in a separate checkout (default: ${DEFAULT_ABM4BIO_ROOT}):
     cd ${DEFAULT_ABM4BIO_ROOT}
     make fresh BUILD_JOBS=4

2. Or copy scripts/abm_paths.local.sh.example to scripts/abm_paths.local.sh
   and set ABM4BIO_ROOT / ABM_BIN for a custom fork.

3. Or pass ABM_BIN on the command line:
     ABM_BIN=/path/to/ABM4bio/build/ABM4bio ./executables/EGI1/calibrate_control.sh

4. Smoke-test without ABM4bio:
     MOCK_MODE=1 ./executables/EGI1/calibrate_control.sh
EOF
}

_source_bdm_minimal() {
  local bdm_sys="$1"
  export BDMSYS="${bdm_sys}"
  export BDM_ROOT_DIR="${BDMSYS}/third_party/root"
  export ROOTSYS="${BDMSYS}/third_party/root"
  export PATH="${BDMSYS}/bin:${ROOTSYS}/bin:${PATH}"
  export LD_LIBRARY_PATH="${BDMSYS}/lib:${ROOTSYS}/lib:${LD_LIBRARY_PATH:-}"

  if [[ -f "${ROOTSYS}/bin/thisroot.sh" ]]; then
    # shellcheck disable=SC1090
    source "${ROOTSYS}/bin/thisroot.sh"
  fi
}

source_biodynamo_env() {
  if [[ "${AUTO_SOURCE_BDM:-1}" != "1" || "${MOCK_MODE:-0}" == "1" ]]; then
    return 0
  fi

  if [[ -n "${BDM_ENV_SOURCED:-}" ]]; then
    return 0
  fi

  local bdm_sys=""
  bdm_sys="$(resolve_bdmsys || true)"
  if [[ -z "${bdm_sys}" ]]; then
    echo "Warning: BioDynaMo not found. Set BDMSYS or ABM4BIO_ROOT." >&2
    return 0
  fi

  local thisbdm="${bdm_sys}/bin/thisbdm.sh"
  if [[ -f "${thisbdm}" ]]; then
    # thisbdm.sh tests BDM_THISBDM_QUIET/SILENT without defaults; set -u in caller scripts errors if unset.
    export BDM_THISBDM_QUIET="${BDM_THISBDM_QUIET:-false}"
    export BDM_THISBDM_SILENT="${BDM_THISBDM_SILENT:-false}"
    export BDM_THISBDM_NOPROMPT=true
    export BDM_THISBDM_LOGLEVEL="${BDM_THISBDM_LOGLEVEL:-0}"
    local errexit_was_on=0
    [[ $- == *e* ]] && errexit_was_on=1
    set +e
    set +u
    # shellcheck disable=SC1090
    source "${thisbdm}"
    local source_status=$?
    set -u
    [[ "${errexit_was_on}" == "1" ]] && set -e
    if [[ "${source_status}" -eq 0 ]]; then
      export BDM_ENV_SOURCED=1
      return 0
    fi
    echo "Note: thisbdm.sh failed in this shell; falling back to minimal BioDynaMo paths." >&2
  fi

  _source_bdm_minimal "${bdm_sys}"
  export BDM_ENV_SOURCED=1
}
