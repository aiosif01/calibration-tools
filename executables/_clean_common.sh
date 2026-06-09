#!/usr/bin/env bash
# Remove generated outputs for one cell line so calibration/test runs start fresh.
# Required env from caller: CELL_LINE
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

OUTPUTS_DIR="${ROOT_DIR}/executables/${CELL_LINE}/outputs"

if [[ ! -e "${OUTPUTS_DIR}" ]]; then
  echo "${CELL_LINE}: no outputs directory (${OUTPUTS_DIR}); nothing to clean."
  exit 0
fi

echo "Cleaning ${CELL_LINE} outputs:"
echo "  ${OUTPUTS_DIR}"
rm -rf "${OUTPUTS_DIR}"
echo "Done. Re-run calibrate_control.sh or run_*.sh to regenerate outputs."
