#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

echo "[CAP safe-init] $(date '+%Y-%m-%d %H:%M:%S')"

TOTAL=$(/usr/bin/ps -u "$USER" --no-headers 2>/dev/null | /usr/bin/wc -l || echo 999)
MAKE_COUNT=$(/usr/bin/pgrep -c -u "$USER" -x make 2>/dev/null || true)
CMAKE_COUNT=$(/usr/bin/pgrep -c -u "$USER" -x cmake 2>/dev/null || true)
ABM_COUNT=$(/usr/bin/pgrep -c -u "$USER" -x ABM4bio 2>/dev/null || true)

echo "[INFO] total=$TOTAL make=${MAKE_COUNT:-0} cmake=${CMAKE_COUNT:-0} ABM4bio=${ABM_COUNT:-0}"

echo "[INFO] Removing stale CAP lock files from ${TMPDIR:-/tmp}"
rm -f "${TMPDIR:-/tmp}/abm4bio_cap_"*"_${USER}.lock" 2>/dev/null || true
rm -f "$CAP_ROOT/calibration_outputs/.cap_optuna.lock" 2>/dev/null || true

echo "[INFO] Checking runtime"
check_runtime

echo "[OK] CAP runtime looks safe. Next steps:"
echo "     ./calibration/1_run_cap_stage1.sh [trials] [seed]"
echo "     ./calibration/2_run_cap_stage2.sh [trials] [seed]"
echo "     ./calibration/3_run_cap_stage3.sh [trials] [seed]"
