#!/usr/bin/env bash

# Default BioDynaMo install used by this project (same as: alias thisbdm="source .../thisbdm.sh").
DEFAULT_BDMSYS="/home/aiwsif/Desktop/ABM4bio/libs/biodynamo-v1.05.143"

resolve_bdmsys() {
  if [[ -n "${BDMSYS:-}" && -d "${BDMSYS}" ]]; then
    echo "${BDMSYS}"
    return 0
  fi

  if [[ -d "${DEFAULT_BDMSYS}" ]]; then
    echo "${DEFAULT_BDMSYS}"
    return 0
  fi

  local abm_root="${ABM4BIO_ROOT:-/home/aiwsif/Desktop/ABM4bio}"
  local candidate
  for candidate in "${abm_root}"/libs/biodynamo-*; do
    if [[ -d "${candidate}" ]]; then
      echo "${candidate}"
      return 0
    fi
  done
  return 1
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
