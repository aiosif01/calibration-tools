#!/usr/bin/env bash
# Remove Optuna outputs for one cell line (results + study DB).
# Required env from caller: CELL_LINE
# Optional: EXPOSURE_SECONDS (treatment); if unset, cleans control + all treat_* dirs.
set -euo pipefail

if [[ -z "${CELL_LINE:-}" ]]; then
  echo "Error: CELL_LINE is not set." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}"
while [[ ! -d "${ROOT_DIR}/scripts" && "${ROOT_DIR}" != "/" ]]; do
  ROOT_DIR="$(dirname "${ROOT_DIR}")"
done
if [[ ! -d "${ROOT_DIR}/scripts" ]]; then
  echo "Error: could not locate project root from ${SCRIPT_DIR}" >&2
  exit 1
fi

OPTUNA_ROOT="${ROOT_DIR}/outputs/optuna/${CELL_LINE}"
STUDIES_DIR="${ROOT_DIR}/outputs/optuna/studies"

clean_paths=()

if [[ -n "${EXPOSURE_SECONDS:-}" ]]; then
  clean_paths+=("${OPTUNA_ROOT}/treat_${EXPOSURE_SECONDS}s")
  clean_paths+=("${STUDIES_DIR}/${CELL_LINE}_treat_${EXPOSURE_SECONDS}s.db")
else
  clean_paths+=("${OPTUNA_ROOT}/control")
  clean_paths+=("${STUDIES_DIR}/${CELL_LINE}_control.db")
  shopt -s nullglob
  for treat_dir in "${OPTUNA_ROOT}"/treat_*s; do
    clean_paths+=("${treat_dir}")
    label="$(basename "${treat_dir}")"
  done
  for db in "${STUDIES_DIR}/${CELL_LINE}_treat_"*.db; do
    clean_paths+=("${db}")
  done
  shopt -u nullglob
fi

if [[ ${#clean_paths[@]} -eq 0 ]]; then
  echo "${CELL_LINE}: nothing to clean."
  exit 0
fi

echo "Cleaning ${CELL_LINE} Optuna outputs:"
for path in "${clean_paths[@]}"; do
  if [[ -e "${path}" ]]; then
    echo "  ${path}"
    rm -rf "${path}"
  fi
done
echo "Done. Re-run optuna_control.sh or optuna_treat_*.sh to regenerate."
