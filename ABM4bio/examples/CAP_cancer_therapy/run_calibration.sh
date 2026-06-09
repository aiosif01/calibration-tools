#!/usr/bin/env bash
set -euo pipefail

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$THIS_DIR"

# Nutrient-style CAP workflow entrypoint (no make commands).
bash ./calibration/0_safe_init.sh
bash ./calibration/1_run_cap_stage1.sh "${1:-40}" "${2:-1234}"
