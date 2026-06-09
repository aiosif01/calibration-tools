#!/usr/bin/env python3
"""3-stage Optuna calibration for ABM4bio CAP in-vitro trajectories (mechanism 12).

Stages
------
control_baseline (Stage 1):
    Fit 5 baseline growth parameters on the untreated control (0 s) per cell line:
      apoptosis_prob, growth_prob, growth_diameter_rate, division_prob, division_time_window

bar_chart (Stage 2 / direct_bar_fit):
    Fit 3 probabilities (apoptosis, growth, division) per (cell line × exposure case).
    Reproduces the professor-style bar chart for: Control, 30 s, 2 min, 4 min, 5 min.
    Optional LM-style Nelder-Mead comparator (--lm-compare) also runs for reference.

mechanistic (Stage 3 / mechanistic_cap_fit):
    Fit 14 mechanism-12 intracellular parameters across ALL exposures simultaneously.
    One Optuna study per cell line; the objective sums residuals over all exposure cases.

Exposure-unit correction
------------------------
The workbook labels ``15"`` and ``30"`` are SECONDS, not minutes.
The corrected CSV (experimental_targets_t0_normalized_corrected_units.csv) already contains
the correct ``exposure_minutes`` column (0.25 for 15 s, 0.5 for 30 s, etc.).
Pass --data-csv to use it; the Excel fallback requires the fixed parse_exposure_minutes().

Usage example
-------------
python3 scripts/calibrate_cap_optuna.py \\
  --stage bar_chart \\
  --template-input input_mechanism12_CAP_template.csv \\
  --data-csv data/experimental_targets_t0_normalized_corrected_units.csv \\
  --param-space-csv data/optuna_parameter_space_mechanism12.csv \\
  --cell-lines EGI1,HuCCT1,PANC1,MiaPaCa2 \\
  --exposures-min 0,0.5,2,4,5 \\
  --n-trials 80 --n-startup-trials 20 --replicates 3 \\
  --bar-chart-only
"""

from __future__ import annotations

import argparse
import fcntl
import json
import math
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, IO, List, Optional, Sequence, Tuple

# Set BLAS / OpenMP thread caps BEFORE numpy import to avoid fork EAGAIN.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("BLIS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import pandas as pd

try:
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)
except ImportError:
    print("ERROR: optuna is not installed.  Run: pip install optuna")
    sys.exit(1)

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    HAS_MPL = True
except ImportError:
    HAS_MPL = False

from abm_io import get_param, get_float_param, read_rows, set_param, viable_counts, write_rows
from excel_data import (
    available_cell_lines,
    build_cap_target,
    build_cap_target_from_csv,
    load_csv_targets,
    parse_workbook,
)

# ---------------------------------------------------------------------------
# Fork / EAGAIN safety helpers
# ---------------------------------------------------------------------------


def _preflight_process_check(max_total: int, allowed_active_make: int = 0, allowed_active_cmake: int = 0) -> None:
    """Abort early if make/cmake are running or if too many user processes exist.

    This mirrors the checks in ``run_cap_optuna_clean.sh`` so the Python script
    is safe even when invoked directly (not through the wrapper).
    """
    username = (
        os.environ.get("USER")
        or os.environ.get("LOGNAME")
        or subprocess.run(
            ["id", "-un"], capture_output=True, text=True, check=False, timeout=5
        ).stdout.strip()
    )

    pgrep_bin = shutil.which("pgrep")
    if pgrep_bin and username:
        checks = (
            ("make", int(allowed_active_make)),
            ("cmake", int(allowed_active_cmake)),
        )
        for tool, allowed in checks:
            result = subprocess.run(
                [pgrep_bin, "-c", "-u", username, "-x", tool],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            count_s = result.stdout.strip()
            count = int(count_s) if count_s.isdigit() else 0
            if count > allowed:
                print(
                    f"ERROR: {count} active '{tool}' process(es) detected (allowed: {allowed}).\n"
                    "       Wait for running builds/simulations to finish before calibrating.",
                    file=sys.stderr,
                )
                sys.exit(6)

    ps_bin = shutil.which("ps")
    if ps_bin and username:
        result = subprocess.run(
            [ps_bin, "-u", username, "--no-header"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        total = len(result.stdout.strip().splitlines()) if result.stdout.strip() else 0
        if total > max_total:
            print(
                f"ERROR: {total} user processes found (limit {max_total}).\n"
                "       Log out/in or kill stale processes before calibrating.",
                file=sys.stderr,
            )
            sys.exit(7)
        print(f"[preflight] {total} user processes (limit {max_total}) — OK")


def _acquire_run_lock(lock_path: Path) -> "IO[str]":
    """Acquire an exclusive non-blocking flock on *lock_path*.

    Returns the open file handle (keep in scope for the duration of the run).
    Raises ``SystemExit(5)`` if the lock is already held by another process.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle: "IO[str]" = lock_path.open("w")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        print(
            f"ERROR: another calibration run holds the lock: {lock_path}\n"
            "       Wait for it to finish, or remove the lock file if it is stale:\n"
            f"       rm -f '{lock_path}'",
            file=sys.stderr,
        )
        sys.exit(5)
    handle.write(f"pid={os.getpid()}\n")
    handle.flush()
    return handle


# ---------------------------------------------------------------------------
# Stage definitions
# ---------------------------------------------------------------------------

# Maps CLI --stage name  →  fit_stage value in parameter-space CSV
STAGE_FIT_KEY: Dict[str, str] = {
    "control_baseline": "control_baseline",
    "bar_chart": "direct_bar_fit",
    "mechanistic": "mechanistic_cap_fit",
}

STAGE_DESCRIPTIONS: Dict[str, str] = {
    "control_baseline": (
        "Stage 1: 5 growth params on untreated control (0 s) per cell line"
    ),
    "bar_chart": (
        "Stage 2: 3 probs (apoptosis/growth/division) per (cell line × case) — bar chart"
    ),
    "mechanistic": (
        "Stage 3: 14 mechanism-12 intracellular params across all exposures"
    ),
}

THREAD_VARS: Tuple[str, ...] = (
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
    "OMP_NUM_THREADS",
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CalibrationCase:
    exposure_requested_min: float
    exposure_used_min: float
    label: str
    target_times_h: np.ndarray
    target_viability_pct: np.ndarray
    target_sd_pct: np.ndarray
    end_time_h: float
    include_in_bar_chart: bool = True


# ---------------------------------------------------------------------------
# Parameter space helpers
# ---------------------------------------------------------------------------


def load_param_space(csv_path: Path, stage_key: str) -> List[Dict]:
    """Load parameter specs for *stage_key* from the parameter-space CSV.

    Columns required: parameter_id, abm_key, type, default, lower_bound,
    upper_bound, fit_stage, suggest_distribution.
    """
    df = pd.read_csv(csv_path)
    specs = df[df["fit_stage"] == stage_key].to_dict("records")
    return specs


def suggest_params(trial: "optuna.Trial", param_specs: List[Dict]) -> Dict[str, float]:
    """Suggest all parameters for one Optuna trial from the parameter-space spec."""
    params: Dict[str, float] = {}
    for spec in param_specs:
        pid = str(spec["parameter_id"])
        lo = float(spec["lower_bound"])
        hi = float(spec["upper_bound"])
        dist = str(spec.get("suggest_distribution", "linear")).lower()
        ptype = str(spec.get("type", "float")).lower()

        if ptype == "int":
            params[pid] = float(trial.suggest_int(pid, int(lo), int(hi)))
        elif dist == "log":
            params[pid] = trial.suggest_float(pid, lo, hi, log=True)
        else:
            params[pid] = trial.suggest_float(pid, lo, hi)
    return params


def build_abm_overrides(
    param_specs: List[Dict],
    param_vals: Dict[str, float],
) -> Dict[str, Tuple[str, str]]:
    """Return ``{abm_key: (type_str, str_value)}`` ready for :func:`set_param`.

    Int parameters are rounded; float parameters are formatted with 12 significant
    digits to avoid precision loss when ABM reads the CSV.
    """
    overrides: Dict[str, Tuple[str, str]] = {}
    for spec in param_specs:
        pid = str(spec["parameter_id"])
        if pid not in param_vals:
            continue
        abm_key = str(spec["abm_key"])
        ptype = str(spec.get("type", "float")).lower()
        val = param_vals[pid]
        if ptype == "int":
            overrides[abm_key] = ("int", str(int(round(val))))
        else:
            overrides[abm_key] = ("float", f"{val:.12g}")
    return overrides


def read_template_params(
    template_rows: Sequence[Sequence[str]],
    param_specs: List[Dict],
) -> Dict[str, float]:
    """Read current template values for *param_specs*, clamped to [lower, upper]."""
    result: Dict[str, float] = {}
    for spec in param_specs:
        pid = str(spec["parameter_id"])
        abm_key = str(spec["abm_key"])
        raw = get_param(list(template_rows), abm_key)
        default = float(spec["default"])
        if raw is None:
            result[pid] = default
            continue
        try:
            val = float(raw)
        except ValueError:
            val = default
        lo = float(spec["lower_bound"])
        hi = float(spec["upper_bound"])
        result[pid] = max(lo, min(hi, val))
    return result


def maybe_enqueue_template_trial(
    study: "optuna.Study",
    template_rows: Sequence[Sequence[str]],
    param_specs: List[Dict],
) -> None:
    """Enqueue template values as trial 0 (warm-start from previous best)."""
    trial = read_template_params(template_rows, param_specs)
    if len(trial) == len(param_specs):
        study.enqueue_trial(trial)


def top_trial_param_std(
    study: "optuna.Study",
    param: str,
    top_k: int,
) -> float:
    completed = [
        t
        for t in study.trials
        if t.state == optuna.trial.TrialState.COMPLETE and t.value is not None
    ]
    if not completed:
        return 0.0
    top = sorted(completed, key=lambda t: float(t.value))[: max(1, min(top_k, len(completed)))]
    vals = [float(t.params[param]) for t in top if param in t.params]
    return float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0


# ---------------------------------------------------------------------------
# BioDynaMo environment bootstrap
# ---------------------------------------------------------------------------


def apply_thread_limits(env: Dict[str, str], omp_threads: int) -> None:
    for var in THREAD_VARS:
        env[var] = str(omp_threads if var == "OMP_NUM_THREADS" else 1)


def bootstrap_bdm_env(bdm_env_script: Path, omp_threads: int) -> Dict[str, str]:
    """Source thisbdm.sh (once) and capture the resulting environment."""
    env = os.environ.copy()
    apply_thread_limits(env, omp_threads)
    if env.get("BDMSYS"):
        return env  # already set up (e.g. by the wrapper shell script)

    cmd = (
        "export BDM_THISBDM_SILENT=true; "
        f"source {shlex.quote(str(bdm_env_script.resolve()))} >/dev/null 2>&1 && "
        'python3 -c "import os,json;print(json.dumps(dict(os.environ)))"'
    )
    proc = subprocess.run(
        ["bash", "--norc", "--noprofile", "-c", cmd],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(
            f"Failed to source BioDynaMo environment from {bdm_env_script}:\n{stderr}"
        )
    env.update(json.loads(proc.stdout))
    apply_thread_limits(env, omp_threads)
    return env


# ---------------------------------------------------------------------------
# ABM run helpers
# ---------------------------------------------------------------------------


def sanitize_name(name: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in name.strip())
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe.strip("_") or "item"


def format_case_label(exposure_min: float) -> str:
    if math.isclose(exposure_min, 0.0, abs_tol=1.0e-12):
        return "Control"
    if exposure_min < 1.0:
        return f"Treat:{int(round(exposure_min * 60.0))}s"
    if math.isclose(exposure_min, round(exposure_min), abs_tol=1.0e-12):
        return f"Treat:{int(round(exposure_min))}min"
    return f"Treat:{exposure_min:g}min"


def weighted_rmse(pred: np.ndarray, target: np.ndarray, sd: np.ndarray) -> float:
    safe_sd = np.where(np.isfinite(sd) & (sd > 1.0e-9), sd, 5.0)
    residual = (pred - target) / safe_sd
    return float(np.sqrt(np.mean(np.square(residual))))


def prepare_case_input(
    template_rows: Sequence[Sequence[str]],
    *,
    output_csv: Path,
    output_directory: Path,
    simulation_title: str,
    mechanism_order: int,
    exposure_min: float,
    end_time_h: float,
    abm_overrides: Dict[str, Tuple[str, str]],
) -> None:
    """Write a per-trial input.csv from *template_rows* with all ABM overrides applied."""
    rows = [list(r) for r in template_rows]

    dt = float(get_param(rows, "time_step") or 0.01)
    n_steps = max(1, int(round(end_time_h / max(dt, 1.0e-12))))
    duration_h = max(0.0, exposure_min / 60.0)
    duration_steps = (
        max(1, int(math.ceil(duration_h / max(dt, 1.0e-12)))) if duration_h > 0.0 else 0
    )

    set_param(rows, "output_directory", str(output_directory), "string")
    set_param(rows, "simulation_title", simulation_title, "string")
    set_param(rows, "number_of_time_steps", str(n_steps), "int")
    set_param(rows, "statistics_interval", "1", "int")
    set_param(rows, "cancer_cell/mechanism_order", str(int(mechanism_order)), "int")
    set_param(rows, "necrotic_cell/mechanism_order", str(int(mechanism_order)), "int")

    if duration_h <= 0.0:
        set_param(rows, "CAP/enabled", "false", "bool")
        set_param(rows, "CAP/duration_h", "0", "float")
        set_param(rows, "CAP/duration_steps", "0", "int")
        set_param(rows, "CAP/H2O2/concentration", "0", "float")
        set_param(rows, "CAP/NO2_/concentration", "0", "float")
    else:
        set_param(rows, "CAP/enabled", "true", "bool")
        set_param(rows, "CAP/start_step", "0", "int")
        set_param(rows, "CAP/start_time_h", "0.0", "float")
        set_param(rows, "CAP/duration_h", f"{duration_h:.12g}", "float")
        set_param(rows, "CAP/duration_steps", str(duration_steps), "int")

    # Apply all trial-specific overrides (any stage: 3 probs, 5 params, 14 intracellular…)
    for abm_key, (ptype, value) in abm_overrides.items():
        set_param(rows, abm_key, value, ptype)

    write_rows(output_csv, rows)


def run_abm_and_score(
    *,
    case: CalibrationCase,
    template_rows: Sequence[Sequence[str]],
    abm_binary: Path,
    env: Dict[str, str],
    run_dir: Path,
    seed: int,
    mechanism_order: int,
    abm_overrides: Dict[str, Tuple[str, str]],
    timeout_s: int,
) -> Tuple[float, np.ndarray]:
    """Run ABM binary for one (case, parameter-set) combination.

    Returns ``(loss, predicted_viability_pct_at_target_times)``.
    On failure returns ``(1e6, NaN array)``.
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    output_dir = run_dir / "results"
    input_csv = run_dir / "input.csv"

    prepare_case_input(
        template_rows,
        output_csv=input_csv,
        output_directory=output_dir,
        simulation_title=f"CAP_{sanitize_name(case.label)}",
        mechanism_order=mechanism_order,
        exposure_min=case.exposure_used_min,
        end_time_h=case.end_time_h,
        abm_overrides=abm_overrides,
    )

    cmd = [str(abm_binary.resolve()), str(input_csv), str(int(seed))]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(run_dir),
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        (run_dir / "abm.log").write_text("TIMEOUT\n", encoding="utf-8")
        return 1.0e6, np.full_like(case.target_times_h, np.nan)

    (run_dir / "abm.log").write_text(
        (proc.stdout or "") + "\n\n--- STDERR ---\n" + (proc.stderr or ""),
        encoding="utf-8",
    )
    if proc.returncode != 0:
        return 1.0e6, np.full_like(case.target_times_h, np.nan)

    stats_path = output_dir / "stats.csv"
    if not stats_path.exists():
        return 1.0e6, np.full_like(case.target_times_h, np.nan)

    try:
        stats = pd.read_csv(stats_path)
        stats.columns = [c.strip() for c in stats.columns]
        times = stats["current_time"].to_numpy(dtype=float)
        viable = viable_counts(stats, phenotype_id=1)
    except Exception:
        return 1.0e6, np.full_like(case.target_times_h, np.nan)

    if len(times) == 0 or len(viable) == 0:
        return 1.0e6, np.full_like(case.target_times_h, np.nan)

    pred_counts = np.interp(
        case.target_times_h, times, viable, left=viable[0], right=viable[-1]
    )
    n0 = max(float(viable[0]), 1.0)
    pred_viability = 100.0 * pred_counts / n0

    score = weighted_rmse(pred_viability, case.target_viability_pct, case.target_sd_pct)
    # Penalise early termination (simulation did not reach the full time window)
    completion = min(1.0, float(times[-1]) / max(case.end_time_h, 1.0e-12))
    score += 10.0 * max(0.0, 1.0 - completion) ** 2
    if not np.isfinite(score):
        score = 1.0e6

    return float(score), pred_viability


# ---------------------------------------------------------------------------
# Case building
# ---------------------------------------------------------------------------


def parse_list_float(text: str) -> List[float]:
    return [float(t.strip()) for t in text.split(",") if t.strip()]


def _build_case_from_curve(
    exposure_requested_min: float,
    curve: pd.DataFrame,
    matched_exposure_min: float,
    include_in_bar_chart: bool = True,
) -> CalibrationCase:
    return CalibrationCase(
        exposure_requested_min=float(exposure_requested_min),
        exposure_used_min=float(matched_exposure_min),
        label=format_case_label(float(matched_exposure_min)),
        target_times_h=curve["time_h"].to_numpy(dtype=float),
        target_viability_pct=curve["target_viability_pct"].to_numpy(dtype=float),
        target_sd_pct=curve["target_sd_pct"].to_numpy(dtype=float),
        end_time_h=float(curve["time_h"].max()),
        include_in_bar_chart=include_in_bar_chart,
    )


def _bar_chart_flag(
    cell_line: str,
    matched_exposure_min: float,
    manifest_df: Optional[pd.DataFrame],
) -> bool:
    """Return True when the manifest flags this case as include_in_first_bar_chart=yes."""
    if manifest_df is None:
        return True

    # Try matching by exposure_minutes column
    if "exposure_minutes" in manifest_df.columns:
        mask = (manifest_df["cell_line"].str.lower() == cell_line.lower()) & np.isclose(
            manifest_df["exposure_minutes"].astype(float), float(matched_exposure_min)
        )
        row = manifest_df[mask]
        if not row.empty:
            return str(row["include_in_first_bar_chart"].iloc[0]).strip().lower() == "yes"

    # Fallback: match by exposure_seconds
    if "exposure_seconds" in manifest_df.columns:
        sec = matched_exposure_min * 60.0
        mask2 = (manifest_df["cell_line"].str.lower() == cell_line.lower()) & np.isclose(
            manifest_df["exposure_seconds"].astype(float), sec
        )
        row2 = manifest_df[mask2]
        if not row2.empty:
            return str(row2["include_in_first_bar_chart"].iloc[0]).strip().lower() == "yes"

    return True  # default: include if not found in manifest


def build_cases(
    df_all: pd.DataFrame,
    cell_line: str,
    exposures_min: Sequence[float],
    normalization: str,
    manifest_df: Optional[pd.DataFrame] = None,
    use_csv_targets: bool = False,
) -> List[CalibrationCase]:
    """Build :class:`CalibrationCase` list from either CSV or Excel data."""
    cases = []
    for exp in exposures_min:
        if use_csv_targets:
            curve, matched = build_cap_target_from_csv(df_all, cell_line, exp)
        else:
            curve, matched = build_cap_target(
                df_all, cell_line, exp, normalization=normalization
            )
        in_bar = _bar_chart_flag(cell_line, matched, manifest_df)
        cases.append(_build_case_from_curve(exp, curve, matched, in_bar))

    # Deduplicate by matched exposure
    dedup: Dict[float, CalibrationCase] = {}
    for c in cases:
        dedup[c.exposure_used_min] = c
    return [dedup[k] for k in sorted(dedup.keys())]


# ---------------------------------------------------------------------------
# Template write-back
# ---------------------------------------------------------------------------


def select_template_update_candidate(all_rows: List[Dict]) -> Dict:
    """Pick the row with the lowest reference_loss (or best_loss as fallback)."""
    ranked = [
        (float(r.get("reference_loss", r.get("best_loss", 1.0e6))), r)
        for r in all_rows
    ]
    ranked.sort(key=lambda x: x[0])
    return ranked[0][1]


def update_template_with_best(
    template_path: Path,
    best_row: Dict,
    mechanism_order: int,
) -> Tuple[Path, Path]:
    """Backup template and write calibrated params from *best_row* into it.

    Looks for keys prefixed ``abm:`` in *best_row* to find the ABM CSV keys to update.
    The type of each key is inferred from the existing template row.
    """
    rows = read_rows(template_path)
    set_param(rows, "cancer_cell/mechanism_order", str(int(mechanism_order)), "int")
    set_param(rows, "necrotic_cell/mechanism_order", str(int(mechanism_order)), "int")
    set_param(rows, "cancer_cell/can_apoptose", "true", "bool")

    for key, value in best_row.items():
        if not key.startswith("abm:"):
            continue
        abm_key = key[4:]
        # Determine the existing type from the template
        current_type: Optional[str] = None
        for row in rows:
            if len(row) >= 2 and row[0].strip() == abm_key:
                current_type = row[1].strip()
                break
        if current_type == "int":
            set_param(rows, abm_key, str(int(round(float(value)))), "int")
        else:
            set_param(rows, abm_key, f"{float(value):.12g}", current_type or "float")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = template_path.with_name(
        f"{template_path.stem}.bak_optuna_{stamp}{template_path.suffix}"
    )
    shutil.copy2(template_path, backup)
    write_rows(template_path, rows)
    return template_path, backup


# ---------------------------------------------------------------------------
# LM-style comparator (bar_chart stage, Nelder-Mead via scipy)
# ---------------------------------------------------------------------------


def run_lm_compare(
    cases: List[CalibrationCase],
    template_rows: Sequence[Sequence[str]],
    abm_binary: Path,
    env: Dict[str, str],
    run_dir: Path,
    mechanism_order: int,
    timeout_s: int,
    base_seed: int,
    param_specs: List[Dict],
    n_max_calls: int = 30,
) -> Optional[Dict]:
    """Run Nelder-Mead (scipy) as an LM-style comparator for the bar_chart stage.

    Uses the same ABM objective as Optuna but with scipy.optimize.minimize.
    Returns a dict of {parameter_id: best_value, ..., lm_loss: float} or None on
    import failure / optimization error.
    """
    try:
        from scipy.optimize import minimize as _minimize
    except ImportError:
        return None

    if not cases or not param_specs:
        return None

    x0 = np.array([float(s["default"]) for s in param_specs])
    bounds_list = [
        (float(s["lower_bound"]), float(s["upper_bound"])) for s in param_specs
    ]
    eval_counter = [0]

    def objective(x: np.ndarray) -> float:
        if eval_counter[0] >= n_max_calls:
            return 1.0e6
        eval_counter[0] += 1
        overrides = build_abm_overrides(
            param_specs,
            {str(spec["parameter_id"]): float(v) for spec, v in zip(param_specs, x)},
        )
        scores = []
        for ci, case in enumerate(cases):
            lm_run = run_dir / f"eval_{eval_counter[0]:04d}_c{ci}"
            score, _ = run_abm_and_score(
                case=case,
                template_rows=template_rows,
                abm_binary=abm_binary,
                env=env,
                run_dir=lm_run,
                seed=base_seed + 700000 + eval_counter[0],
                mechanism_order=mechanism_order,
                abm_overrides=overrides,
                timeout_s=timeout_s,
            )
            scores.append(score)
        return float(np.mean(scores)) if scores else 1.0e6

    try:
        result = _minimize(
            objective,
            x0,
            method="Nelder-Mead",
            bounds=bounds_list,
            options={"maxiter": n_max_calls, "xatol": 1e-4, "fatol": 1e-4, "disp": False},
        )
        out: Dict = {
            str(spec["parameter_id"]): float(v)
            for spec, v in zip(param_specs, result.x)
        }
        out["lm_loss"] = float(result.fun)
        return out
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------


def _prob_cols(df: pd.DataFrame) -> Tuple[List[str], List[str]]:
    prob = [c for c in df.columns if "probability" in c.lower() and "std" not in c.lower()][:3]
    std = [c for c in df.columns if "std" in c.lower() and "probability" in c.lower()][:3]
    return prob, std


def plot_cell_line_bar_chart(df: pd.DataFrame, cell_line: str, out_png: Path) -> None:
    if not HAS_MPL or df.empty:
        return
    prob_cols, std_cols = _prob_cols(df)
    x = np.arange(len(df))
    width = 0.25
    colors = ["#1f77b4", "#ff7f0e", "#e6b31e"]
    labels = ["Apoptosis", "Growth", "Division"]

    fig, ax = plt.subplots(figsize=(11, 5.2))
    for i, (pcol, lbl, color) in enumerate(zip(prob_cols, labels, colors)):
        yerr = df[std_cols[i]].values if i < len(std_cols) else None
        ax.bar(x + (i - 1) * width, df[pcol], width, yerr=yerr, capsize=3, label=lbl, color=color)

    ax.set_xticks(x)
    ax.set_xticklabels(df["case_label"].tolist())
    ax.set_ylabel("Probability")
    ax.set_xlabel("Exposure Case")
    ax.set_title(f"Calibrated CAP Probabilities — {cell_line} (mechanism 12)")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


def plot_all_cell_lines(df: pd.DataFrame, out_png: Path) -> None:
    if not HAS_MPL or df.empty:
        return
    cell_lines = sorted(df["cell_line"].unique())
    n = len(cell_lines)
    cols = 2
    nrows = math.ceil(n / cols)
    prob_cols, _ = _prob_cols(df)
    colors = ["#1f77b4", "#ff7f0e", "#e6b31e"]
    labels = ["Apoptosis", "Growth", "Division"]

    fig, axes = plt.subplots(nrows, cols, figsize=(14, 4.8 * nrows), squeeze=False)
    for i, cl in enumerate(cell_lines):
        r, c = divmod(i, cols)
        ax = axes[r][c]
        sdf = df[df["cell_line"] == cl].sort_values("exposure_min")
        x = np.arange(len(sdf))
        width = 0.25
        for j, (pcol, lbl, color) in enumerate(zip(prob_cols, labels, colors)):
            ax.bar(x + (j - 1) * width, sdf[pcol], width, label=lbl, color=color)
        ax.set_xticks(x)
        ax.set_xticklabels(sdf["case_label"].tolist())
        ax.set_title(cl)
        ax.set_ylabel("Probability")
        ax.grid(axis="y", alpha=0.25)

    for i in range(n, nrows * cols):
        r, c = divmod(i, cols)
        axes[r][c].axis("off")

    handles, lbls = axes[0][0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, lbls, loc="upper center", ncol=3)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.suptitle("CAP Probability Calibration (mechanism 12)", y=0.98)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Path resolution helpers
# ---------------------------------------------------------------------------


def resolve_excel_path(arg_excel: Path, cwd: Path) -> Path:
    if arg_excel.exists():
        return arg_excel.resolve()
    for candidate in [
        cwd / "Data Modeling CCA+PDAC 0 to 72h post Gorjet - WITH MEAN 4 experiments.xlsx",
        cwd.parents[1]
        / "libs"
        / "experimental_data"
        / "Data Modeling CCA+PDAC 0 to 72h post Gorjet - WITH MEAN 4 experiments.xlsx",
    ]:
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError(
        "Could not find CAP Excel workbook. Pass --excel or --data-csv explicitly."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:  # noqa: C901  (acceptable complexity for a calibration driver)
    parser = argparse.ArgumentParser(
        description="3-stage Optuna calibration for ABM4bio CAP mechanism-12",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # --- Stage and data ---
    parser.add_argument(
        "--stage",
        choices=["control_baseline", "bar_chart", "mechanistic"],
        default="bar_chart",
        help="Calibration stage",
    )
    parser.add_argument(
        "--data-csv",
        type=Path,
        default=None,
        help="Corrected experimental targets CSV (preferred; bypasses Excel parser)",
    )
    parser.add_argument(
        "--manifest-csv",
        type=Path,
        default=None,
        help="Case manifest CSV with include_in_first_bar_chart column",
    )
    parser.add_argument(
        "--bar-chart-only",
        action="store_true",
        help="Restrict cases to include_in_first_bar_chart=yes rows from manifest",
    )
    parser.add_argument(
        "--param-space-csv",
        type=Path,
        default=None,
        help="Parameter space CSV (optuna_parameter_space_mechanism12.csv)",
    )
    parser.add_argument(
        "--excel",
        type=Path,
        default=Path(
            "Data Modeling CCA+PDAC 0 to 72h post Gorjet - WITH MEAN 4 experiments.xlsx"
        ),
        help="Legacy Excel workbook (fallback when --data-csv is absent)",
    )

    # --- Model / template ---
    parser.add_argument(
        "--template-input",
        type=Path,
        default=Path("input_mechanism12_CAP_template.csv"),
    )
    parser.add_argument("--mechanism-order", type=int, default=12)

    # --- ABM binary / environment ---
    parser.add_argument("--abm-binary", type=Path, default=Path("../../build/ABM4bio"))
    parser.add_argument(
        "--bdm-env-script",
        type=Path,
        default=Path("../../libs/biodynamo-v1.05.143/bin/thisbdm.sh"),
    )

    # --- Output ---
    parser.add_argument(
        "--out-dir", type=Path, default=Path("calibration_outputs/CAP_optuna")
    )

    # --- Calibration scope ---
    parser.add_argument("--cell-lines", default="EGI1,HuCCT1,PANC1,MiaPaCa2")
    parser.add_argument("--exposures-min", default="0,0.5,2,4,5")
    parser.add_argument("--normalization", choices=["t0", "control"], default="t0")

    # --- Optuna tuning ---
    parser.add_argument("--n-trials", type=int, default=40)
    parser.add_argument("--n-startup-trials", type=int, default=10)
    parser.add_argument("--replicates", type=int, default=1)
    parser.add_argument("--report-top-k", type=int, default=10)
    parser.add_argument("--sampler-seed", type=int, default=1234)
    parser.add_argument("--base-seed", type=int, default=1234)
    parser.add_argument("--omp-threads", type=int, default=4)
    parser.add_argument("--timeout-s", type=int, default=1800)
    parser.add_argument("--storage", default="", help="Optuna RDB storage URI (optional)")

    # --- Warm-start and write-back ---
    parser.add_argument(
        "--enqueue-template",
        dest="enqueue_template",
        action="store_true",
        default=True,
        help="Enqueue template values as trial 0 (warm-start)",
    )
    parser.add_argument("--no-enqueue-template", dest="enqueue_template", action="store_false")
    parser.add_argument(
        "--update-template",
        dest="update_template",
        action="store_true",
        default=True,
        help="Write best calibrated parameters back to template CSV",
    )
    parser.add_argument("--no-update-template", dest="update_template", action="store_false")

    # --- LM comparator ---
    parser.add_argument(
        "--lm-compare",
        action="store_true",
        help="Also run Nelder-Mead comparator after Optuna (bar_chart stage only)",
    )

    # --- Safety limits ---
    parser.add_argument(
        "--max-user-processes",
        type=int,
        default=2000,
        help="Refuse to start if total user process count exceeds this value",
    )
    parser.add_argument(
        "--allowed-active-make",
        type=int,
        default=int(os.environ.get("CAP_ALLOW_ACTIVE_MAKE", "0")),
        help="Allowed active make processes during preflight (set to 2 for make-launched runs)",
    )
    parser.add_argument(
        "--allowed-active-cmake",
        type=int,
        default=int(os.environ.get("CAP_ALLOW_ACTIVE_CMAKE", "0")),
        help="Allowed active cmake processes during preflight",
    )

    args = parser.parse_args()
    stage = args.stage
    stage_key = STAGE_FIT_KEY[stage]
    print(f"[CAP Optuna] Stage: {stage}")
    print(f"             {STAGE_DESCRIPTIONS[stage]}")

    # ------------------------------------------------------------------ paths
    cwd = Path.cwd()

    def _resolve(p: Path) -> Path:
        return p if p.is_absolute() else cwd / p

    template_input = _resolve(args.template_input)
    abm_binary = _resolve(args.abm_binary)
    bdm_env_script = _resolve(args.bdm_env_script)
    out_dir = _resolve(args.out_dir)

    # ---- process-budget preflight (before any subprocess is spawned) ----
    _preflight_process_check(
        args.max_user_processes,
        allowed_active_make=args.allowed_active_make,
        allowed_active_cmake=args.allowed_active_cmake,
    )

    # ---- exclusive lock: one calibration per output directory at a time ----
    stage_lock_path = out_dir / stage / ".lock"
    _run_lock = _acquire_run_lock(stage_lock_path)  # noqa: F841  (kept open until exit)
    print(f"[lock] acquired: {stage_lock_path}")

    for label, path in [
        ("template", template_input),
        ("ABM binary", abm_binary),
        ("BDM env script", bdm_env_script),
    ]:
        if not path.exists():
            raise FileNotFoundError(f"{label} not found: {path}")

    # ------------------------------------------------------ parameter space
    param_space_csv = args.param_space_csv
    if param_space_csv is None:
        for candidate in [
            cwd / "data" / "optuna_parameter_space_mechanism12.csv",
            cwd / "optuna_parameter_space_mechanism12.csv",
        ]:
            if candidate.exists():
                param_space_csv = candidate
                break
    if param_space_csv is None or not param_space_csv.exists():
        raise FileNotFoundError(
            "Parameter space CSV not found. "
            "Pass --param-space-csv or place "
            "'data/optuna_parameter_space_mechanism12.csv' in the working directory."
        )

    param_specs = load_param_space(param_space_csv, stage_key)
    if not param_specs:
        raise ValueError(
            f"No parameters found in {param_space_csv} for fit_stage='{stage_key}'."
        )
    print(
        f"             Parameters ({len(param_specs)}): "
        + ", ".join(s["parameter_id"] for s in param_specs)
    )

    # --------------------------------------------------- experimental data
    data_csv = args.data_csv
    use_csv = data_csv is not None
    if not use_csv:
        for candidate in [
            cwd / "data" / "experimental_targets_t0_normalized_corrected_units.csv",
            cwd / "experimental_targets_t0_normalized_corrected_units.csv",
        ]:
            if candidate.exists():
                data_csv = candidate
                use_csv = True
                break

    if use_csv:
        print(f"             Data: {data_csv} (corrected CSV)")
        df_all = load_csv_targets(data_csv)
    else:
        print("             Data: Excel workbook (fallback)")
        excel_path = resolve_excel_path(args.excel, cwd)
        df_all = parse_workbook(excel_path)

    # ------------------------------------------------------- case manifest
    manifest_df: Optional[pd.DataFrame] = None
    if args.manifest_csv and args.manifest_csv.exists():
        manifest_df = pd.read_csv(args.manifest_csv)
    else:
        for candidate in [
            cwd / "data" / "experimental_case_manifest_corrected_units.csv",
            cwd / "experimental_case_manifest_corrected_units.csv",
        ]:
            if candidate.exists():
                manifest_df = pd.read_csv(candidate)
                break

    # ------------------------------------------------- cell lines / exposures
    if args.cell_lines.strip().lower() == "all":
        cell_lines = available_cell_lines(df_all)
    else:
        cell_lines = [x.strip() for x in args.cell_lines.split(",") if x.strip()]
    if not cell_lines:
        raise ValueError("No cell lines selected.")

    exposures = parse_list_float(args.exposures_min)
    if stage == "control_baseline":
        # Stage 1 trains exclusively on the untreated control
        exposures = [0.0]
        print("             Restricting to control (0 s) exposure for Stage 1.")
    if not exposures:
        raise ValueError("No exposure durations provided.")

    # --------------------------------------------------- setup output dirs
    template_rows = read_rows(template_input)
    base_env = bootstrap_bdm_env(bdm_env_script, args.omp_threads)

    stage_out = out_dir / stage
    runs_root = stage_out / "runs"
    plots_root = stage_out / "plots"
    summaries_root = stage_out / "summaries"
    for d in [runs_root, plots_root, summaries_root]:
        d.mkdir(parents=True, exist_ok=True)

    all_rows: List[Dict] = []

    def make_trial_callback(prefix: str):
        def _callback(study: "optuna.Study", trial: "optuna.trial.FrozenTrial") -> None:
            status = str(trial.state).split(".")[-1]
            value = float(trial.value) if trial.value is not None else float("nan")
            print(
                f"     [{prefix}] trial={trial.number:04d} state={status} value={value:.4f}",
                flush=True,
            )

        return _callback

    # ================================================================ main loop
    for cell_line in cell_lines:
        print(f"\n=== Cell line: {cell_line} ===")
        safe_cell = sanitize_name(cell_line)

        cases = build_cases(
            df_all,
            cell_line,
            exposures,
            args.normalization,
            manifest_df=manifest_df,
            use_csv_targets=use_csv,
        )

        if args.bar_chart_only and manifest_df is not None:
            cases = [c for c in cases if c.include_in_bar_chart]
            print(f"  Bar-chart filter: {len(cases)} case(s) retained.")

        if not cases:
            print("  No cases after filtering; skipping cell line.")
            continue

        print(
            "  Cases: "
            + ", ".join(f"{c.label} ({c.exposure_used_min:g} min)" for c in cases)
        )

        # ------------------------------------------------ STAGE 3: mechanistic
        if stage == "mechanistic":
            cell_run_root = runs_root / safe_cell
            cell_run_root.mkdir(parents=True, exist_ok=True)
            study_name = f"CAP_{safe_cell}_mechanistic"

            sampler = optuna.samplers.TPESampler(
                seed=args.sampler_seed,
                n_startup_trials=max(1, args.n_startup_trials),
            )
            pruner = optuna.pruners.MedianPruner(
                n_startup_trials=max(1, args.n_startup_trials // 2)
            )
            study = optuna.create_study(
                study_name=study_name,
                direction="minimize",
                sampler=sampler,
                pruner=pruner,
                storage=args.storage.strip() or None,
                load_if_exists=True,
            )
            if args.enqueue_template:
                maybe_enqueue_template_trial(study, template_rows, param_specs)

            def mechanistic_objective(trial: optuna.Trial) -> float:
                print(
                    f"     [mechanistic] start trial={trial.number:04d}",
                    flush=True,
                )
                params = suggest_params(trial, param_specs)
                overrides = build_abm_overrides(param_specs, params)
                case_scores = []
                for ci, c in enumerate(cases):
                    rep_scores = []
                    for rep in range(max(1, args.replicates)):
                        seed = int(args.base_seed + trial.number * 1000 + ci * 50 + rep)
                        rdir = cell_run_root / f"trial_{trial.number:04d}_c{ci}_r{rep:02d}"
                        sc, _ = run_abm_and_score(
                            case=c,
                            template_rows=template_rows,
                            abm_binary=abm_binary,
                            env=base_env,
                            run_dir=rdir,
                            seed=seed,
                            mechanism_order=args.mechanism_order,
                            abm_overrides=overrides,
                            timeout_s=args.timeout_s,
                        )
                        rep_scores.append(sc)
                        if sc >= 1.0e6:
                            break
                    case_scores.append(float(np.mean(rep_scores)) if rep_scores else 1.0e6)
                total = float(np.mean(case_scores)) if case_scores else 1.0e6
                trial.set_user_attr(
                    "case_scores",
                    json.dumps({c.label: s for c, s in zip(cases, case_scores)}),
                )
                return total

            print(f"  Optimising mechanistic ({args.n_trials} trials)…")
            study.optimize(
                mechanistic_objective,
                n_trials=max(1, args.n_trials),
                n_jobs=1,
                callbacks=[make_trial_callback(f"{cell_line}:mechanistic")],
            )

            best = study.best_trial
            best_params = best.params
            row: Dict = {
                "cell_line": cell_line,
                "case_label": "all_exposures",
                "exposure_min": -1.0,
                "best_loss": float(best.value),
                "reference_loss": float(best.value),
            }
            for spec in param_specs:
                pid = str(spec["parameter_id"])
                if pid in best_params:
                    row[pid] = best_params[pid]
                    row[f"abm:{spec['abm_key']}"] = best_params[pid]
            all_rows.append(row)
            print(f"  mechanistic best_loss={float(best.value):.4f}")

        # ------------------------------- STAGES 1 & 2: per-case (one study each)
        else:
            cell_rows: List[Dict] = []

            for case_idx, case in enumerate(cases):
                case_key = sanitize_name(case.label)
                case_run_root = runs_root / safe_cell / case_key
                case_run_root.mkdir(parents=True, exist_ok=True)
                study_name = f"CAP_{safe_cell}_{case_key}_{stage}"

                print(
                    f"\n  -> {case.label}  (exposure={case.exposure_used_min:g} min,"
                    f" bar_chart={case.include_in_bar_chart})"
                )

                sampler = optuna.samplers.TPESampler(
                    seed=args.sampler_seed + case_idx,
                    n_startup_trials=max(1, args.n_startup_trials),
                )
                pruner = optuna.pruners.MedianPruner(
                    n_startup_trials=max(1, args.n_startup_trials // 2)
                )
                study = optuna.create_study(
                    study_name=study_name,
                    direction="minimize",
                    sampler=sampler,
                    pruner=pruner,
                    storage=args.storage.strip() or None,
                    load_if_exists=True,
                )
                if args.enqueue_template:
                    maybe_enqueue_template_trial(study, template_rows, param_specs)

                # Use a factory to avoid late-binding closure bugs
                def make_objective(
                    _case: CalibrationCase,
                    _root: Path,
                    _cidx: int,
                ):
                    def _objective(trial: optuna.Trial) -> float:
                        print(
                            f"     [{_case.label}] start trial={trial.number:04d}",
                            flush=True,
                        )
                        params = suggest_params(trial, param_specs)
                        overrides = build_abm_overrides(param_specs, params)
                        scores = []
                        for rep in range(max(1, args.replicates)):
                            seed = int(
                                args.base_seed + trial.number * 1000 + _cidx * 50 + rep
                            )
                            rdir = _root / f"trial_{trial.number:04d}_r{rep:02d}"
                            sc, _ = run_abm_and_score(
                                case=_case,
                                template_rows=template_rows,
                                abm_binary=abm_binary,
                                env=base_env,
                                run_dir=rdir,
                                seed=seed,
                                mechanism_order=args.mechanism_order,
                                abm_overrides=overrides,
                                timeout_s=args.timeout_s,
                            )
                            scores.append(sc)
                            if sc >= 1.0e6:
                                break
                        loss = float(np.mean(scores)) if scores else 1.0e6
                        trial.set_user_attr("mean_score", loss)
                        return loss

                    return _objective

                study.optimize(
                    make_objective(case, case_run_root, case_idx),
                    n_trials=max(1, args.n_trials),
                    n_jobs=1,
                    callbacks=[make_trial_callback(f"{cell_line}:{case.label}")],
                )

                best = study.best_trial
                best_params = best.params
                best_overrides = build_abm_overrides(param_specs, best_params)

                # Validation run with a separate seed
                ref_dir = case_run_root / "best_reference"
                ref_score, ref_pred = run_abm_and_score(
                    case=case,
                    template_rows=template_rows,
                    abm_binary=abm_binary,
                    env=base_env,
                    run_dir=ref_dir,
                    seed=int(args.base_seed + 900000 + case_idx),
                    mechanism_order=args.mechanism_order,
                    abm_overrides=best_overrides,
                    timeout_s=args.timeout_s,
                )

                row = {
                    "cell_line": cell_line,
                    "case_label": case.label,
                    "exposure_min": case.exposure_used_min,
                    "requested_exposure_min": case.exposure_requested_min,
                    "include_in_bar_chart": case.include_in_bar_chart,
                    "best_loss": float(best.value),
                    "reference_loss": float(ref_score),
                    "best_trial": int(best.number),
                    "best_predicted_viability_pct": json.dumps(
                        {
                            f"{float(t):g}": float(v)
                            for t, v in zip(
                                case.target_times_h.tolist(), ref_pred.tolist()
                            )
                        }
                    ),
                }
                # Store best params with both parameter_id and abm: prefix
                for spec in param_specs:
                    pid = str(spec["parameter_id"])
                    if pid in best_params:
                        row[pid] = best_params[pid]
                        row[f"abm:{spec['abm_key']}"] = best_params[pid]
                        row[f"{pid}_std_top{args.report_top_k}"] = top_trial_param_std(
                            study, pid, args.report_top_k
                        )

                # Optional LM comparator (bar_chart only)
                if args.lm_compare and stage == "bar_chart":
                    lm = run_lm_compare(
                        [case],
                        template_rows,
                        abm_binary,
                        base_env,
                        case_run_root / "lm_compare",
                        args.mechanism_order,
                        args.timeout_s,
                        args.base_seed,
                        param_specs,
                        n_max_calls=20,
                    )
                    if lm:
                        for k, v in lm.items():
                            row[f"lm_{k}"] = v

                cell_rows.append(row)
                print(
                    f"     best={float(best.value):.4f} | ref={ref_score:.4f} | "
                    + " | ".join(
                        f"{spec['parameter_id']}={best_params.get(spec['parameter_id'], '?'):.4g}"
                        for spec in param_specs[:3]
                    )
                )

            # Per-cell-line summary
            cell_df = pd.DataFrame(cell_rows).sort_values("exposure_min").reset_index(drop=True)
            cell_df.to_csv(summaries_root / f"{safe_cell}_{stage}.csv", index=False)
            (summaries_root / f"{safe_cell}_{stage}.json").write_text(
                cell_df.to_json(orient="records", indent=2), encoding="utf-8"
            )
            plot_cell_line_bar_chart(
                cell_df,
                cell_line,
                plots_root / f"{safe_cell}_{stage}_probabilities.png",
            )
            all_rows.extend(cell_rows)

    # ---------------------------------------------------------------- aggregate
    all_df = pd.DataFrame(all_rows).sort_values(
        ["cell_line", "exposure_min"], na_position="last"
    ).reset_index(drop=True)
    all_csv = stage_out / f"summary_all_cell_lines_{stage}.csv"
    all_json = stage_out / f"summary_all_cell_lines_{stage}.json"
    all_df.to_csv(all_csv, index=False)
    all_json.write_text(all_df.to_json(orient="records", indent=2), encoding="utf-8")

    if stage == "bar_chart":
        plot_all_cell_lines(all_df, plots_root / "all_cell_lines_bar_chart.png")

    # ------------------------------------------------------ template write-back
    if args.update_template and all_rows:
        best_row = select_template_update_candidate(all_rows)
        updated_template, backup_template = update_template_with_best(
            template_input,
            best_row,
            mechanism_order=args.mechanism_order,
        )
        report = {
            "stage": stage,
            "updated_template": str(updated_template),
            "backup_template": str(backup_template),
            "source_cell_line": str(best_row.get("cell_line")),
            "source_case": str(best_row.get("case_label")),
            "source_best_loss": float(best_row.get("best_loss", 1.0e6)),
            "source_reference_loss": float(best_row.get("reference_loss", 1.0e6)),
        }
        (stage_out / "template_update_report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(f"\nTemplate updated : {updated_template}")
        print(f"Template backup  : {backup_template}")

    print(f"\nCalibration complete — stage: {stage}")
    print(f"  Summary CSV  : {all_csv}")
    print(f"  Summary JSON : {all_json}")
    print(f"  Plots        : {plots_root}")


if __name__ == "__main__":
    main()
