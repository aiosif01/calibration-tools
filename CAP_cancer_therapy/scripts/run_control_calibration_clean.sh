#!/usr/bin/env bash
set -euo pipefail

PS_BIN="/bin/ps"
WC_BIN="/usr/bin/wc"
ID_BIN="/usr/bin/id"

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.."; pwd)"
ABM4BIO_ROOT="$(realpath "${THIS_DIR}/../..")"

PYTHON_DEFAULT="/home/aiwsif/miniconda/bin/python3"
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
set +u
if ! source "${BDM_ENV_SCRIPT}" >/dev/null; then
  set -u
  echo "ERROR: failed to source BioDynaMo environment: ${BDM_ENV_SCRIPT}" >&2
  exit 4
fi
set -u

cd "${THIS_DIR}"

exec "${PYTHON_BIN}" scripts/calibrate_control_growth.py "$@"
