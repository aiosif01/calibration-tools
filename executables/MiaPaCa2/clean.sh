#!/usr/bin/env bash
set -euo pipefail

CELL_LINE="MiaPaCa2"

# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/_clean_common.sh"
