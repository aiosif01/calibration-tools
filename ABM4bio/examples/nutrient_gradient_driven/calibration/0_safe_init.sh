#!/usr/bin/env bash
# ==============================================================================
# 0_safe_init.sh — Safe pre-flight cleanup and initialization
# ==============================================================================
#
# Run this ONCE before any calibration to guarantee a clean, safe state.
# Designed to survive sandbox restrictions (read-only /tmp, seccomp, etc.)
#
# What it does:
#   1. Report current process budget
#   2. Kill any runaway ABM4bio / make / cmake processes owned by this user
#   3. Remove all stale calibration lock files (both /tmp and $TMPDIR)
#   4. Remove leftover Optuna lock artifacts from aborted runs
#   5. Validate BioDynaMo runtime is sourced
#   6. Set safe OMP / process environment defaults
#   7. Print a green-light summary
#
# Usage:
#   source ./0_safe_init.sh          ← also exports env vars to current shell
#   bash   ./0_safe_init.sh          ← standalone check only
#
# Exit codes:
#   0  clean state — safe to proceed
#   1  BioDynaMo not sourced
#   2  ABM4bio binary not found
#   3  active build processes remain after kill attempt
# ==============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# ── colour helpers ─────────────────────────────────────────────────────────────
_RED='\033[0;31m'; _GRN='\033[0;32m'; _YLW='\033[1;33m'; _RST='\033[0m'
ok()   { echo -e "${_GRN}[OK]${_RST}    $*"; }
warn() { echo -e "${_YLW}[WARN]${_RST}  $*"; }
err()  { echo -e "${_RED}[ERR]${_RST}   $*" >&2; }
info() { echo -e "        $*"; }

echo ""
echo "════════════════════════════════════════════════════════"
echo "  ABM4bio calibration safe-init  ($(date '+%Y-%m-%d %H:%M:%S'))"
echo "════════════════════════════════════════════════════════"
echo ""

# ── 1. Process budget snapshot ─────────────────────────────────────────────────
echo "── 1. Process budget ──────────────────────────────────"
TOTAL_PROCS=$(/usr/bin/ps -u "$USER" --no-headers 2>/dev/null | /usr/bin/wc -l || echo 999)
MAKE_COUNT=$(/usr/bin/pgrep  -c -u "$USER" -x make   2>/dev/null || echo 0)
CMAKE_COUNT=$(/usr/bin/pgrep -c -u "$USER" -x cmake  2>/dev/null || echo 0)
SH_COUNT=$(/usr/bin/pgrep   -c -u "$USER" -x sh     2>/dev/null || echo 0)
ABM_COUNT=$(/usr/bin/pgrep  -c -u "$USER" -x ABM4bio 2>/dev/null || echo 0)
PYTHON_COUNT=$(/usr/bin/pgrep -c -u "$USER" -f "optimize_optuna" 2>/dev/null || echo 0)

info "Total user processes : $TOTAL_PROCS"
info "make                 : $MAKE_COUNT"
info "cmake                : $CMAKE_COUNT"
info "sh                   : $SH_COUNT"
info "ABM4bio              : $ABM_COUNT"
info "optimize_optuna.py   : $PYTHON_COUNT"
echo ""

# ── 2. Kill runaway processes ──────────────────────────────────────────────────
echo "── 2. Terminate stale processes ───────────────────────"
_killed=0

_kill_if_any() {
  local label="$1"; shift
  local pids
  pids=$(/usr/bin/pgrep -u "$USER" "$@" 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    warn "Killing $label PIDs: $(echo "$pids" | tr '\n' ' ')"
    # SIGTERM first, then SIGKILL after 3s
    echo "$pids" | xargs -r kill -TERM 2>/dev/null || true
    sleep 3
    echo "$pids" | xargs -r kill -KILL 2>/dev/null || true
    _killed=$(( _killed + $(echo "$pids" | wc -w) ))
  fi
}

# Kill runaway ABM4bio simulation processes
_kill_if_any "ABM4bio"       -x ABM4bio
# Kill any dangling optimize_optuna.py invocations (but NOT the current shell's python)
_kill_if_any "optimize_optuna" -f "optimize_optuna"
# Kill make/cmake build processes (safe — we never want these running during calibration)
_kill_if_any "make"          -x make
_kill_if_any "cmake"         -x cmake

if [[ $_killed -eq 0 ]]; then
  ok "No runaway processes found."
else
  warn "Killed $_killed process(es). Waiting 2s for cleanup..."
  sleep 2
fi
echo ""

# ── 3. Remove stale lock files ────────────────────────────────────────────────
echo "── 3. Remove stale lock files ─────────────────────────"
LOCK_PATTERN="abm4bio_iso10_calibration_${USER}.lock"

# Try all known lock locations
for LOCK_DIR in \
    "${TMPDIR:-}" \
    "/tmp" \
    "${XDG_RUNTIME_DIR:-}" \
    "$HOME/.local/tmp"
do
  [[ -z "$LOCK_DIR" ]] && continue
  LOCK_PATH="$LOCK_DIR/$LOCK_PATTERN"
  if [[ -e "$LOCK_PATH" ]]; then
    if rm -f "$LOCK_PATH" 2>/dev/null; then
      ok "Removed lock: $LOCK_PATH"
    else
      warn "Could not remove $LOCK_PATH (read-only fs) — trying to overwrite"
      # Overwrite with zero-length to mark stale, then try unlink via python
      python3 -c "import os; os.unlink('$LOCK_PATH')" 2>/dev/null && \
        ok "Removed via python: $LOCK_PATH" || \
        warn "Lock at $LOCK_PATH is on read-only fs — will be ignored by script (already fixed)"
    fi
  fi
done

# Also clean Optuna journal/WAL artifacts from aborted sqlite runs
find "$SCRIPT_DIR/results/optuna_runs" \
     -maxdepth 1 \
     \( -name "*.db-wal" -o -name "*.db-shm" -o -name "*.db-journal" \) \
     -delete 2>/dev/null && ok "Cleared any stale Optuna SQLite WAL/journal files" || true
echo ""

# ── 4. Re-verify process budget is safe ───────────────────────────────────────
echo "── 4. Post-cleanup process check ──────────────────────"
TOTAL_PROCS2=$(/usr/bin/ps -u "$USER" --no-headers 2>/dev/null | /usr/bin/wc -l || echo 999)
MAKE_COUNT2=$(/usr/bin/pgrep  -c -u "$USER" -x make   2>/dev/null || echo 0)
CMAKE_COUNT2=$(/usr/bin/pgrep -c -u "$USER" -x cmake  2>/dev/null || echo 0)
ABM_COUNT2=$(/usr/bin/pgrep  -c -u "$USER" -x ABM4bio 2>/dev/null || echo 0)

info "Total user processes : $TOTAL_PROCS2"
info "make                 : $MAKE_COUNT2"
info "cmake                : $CMAKE_COUNT2"
info "ABM4bio              : $ABM_COUNT2"

if [[ "$MAKE_COUNT2" -gt 0 || "$CMAKE_COUNT2" -gt 0 ]]; then
  err "Active build processes remain. Refusing to declare safe state."
  exit 3
fi
if [[ "$TOTAL_PROCS2" -gt 2000 ]]; then
  warn "Total process count ($TOTAL_PROCS2) is high — proceed with caution."
fi
echo ""

# ── 5. Validate BioDynaMo runtime ─────────────────────────────────────────────
echo "── 5. BioDynaMo runtime check ─────────────────────────"
if [[ -z "${ROOTSYS:-}" ]]; then
  err "BioDynaMo is NOT sourced (ROOTSYS is unset)."
  info "Run:  source $REPO_ROOT/libs/biodynamo-v1.05.143/bin/thisbdm.sh"
  info "Then re-run this script."
  exit 1
fi
ok "BioDynaMo sourced  (ROOTSYS=$ROOTSYS)"

ABM_BIN="$REPO_ROOT/build/ABM4bio"
if [[ ! -x "$ABM_BIN" ]]; then
  err "ABM4bio binary not found or not executable: $ABM_BIN"
  exit 2
fi
ok "ABM4bio binary     ($ABM_BIN)"
echo ""

# ── 6. Export safe environment defaults ───────────────────────────────────────
echo "── 6. Set safe environment defaults ───────────────────"
# Conservative OpenMP — override with OMP_NUM_THREADS=N before running if needed
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"
export OMP_PROC_BIND="${OMP_PROC_BIND:-false}"
# Hard cap on user process budget checked by common.sh
export MAX_USER_PROCESSES="${MAX_USER_PROCESSES:-2000}"
# Optuna must use n_jobs=1 — prevent parallel trial spawning
export OPTUNA_N_JOBS="${OPTUNA_N_JOBS:-1}"

info "OMP_NUM_THREADS      = $OMP_NUM_THREADS"
info "OMP_PROC_BIND        = $OMP_PROC_BIND"
info "MAX_USER_PROCESSES   = $MAX_USER_PROCESSES"
info "OPTUNA_N_JOBS        = $OPTUNA_N_JOBS"
echo ""

# ── 7. Green-light summary ────────────────────────────────────────────────────
echo "────────────────────────────────────────────────────────"
ok "Safe-init complete. System is ready for calibration."
echo ""
echo "  Next steps:"
echo "    ./1_clean_iso10_outputs.sh"
echo "    ./2_run_iso10_fresh_calibration.sh [n_trials] [seed] [db_name]"
echo ""
