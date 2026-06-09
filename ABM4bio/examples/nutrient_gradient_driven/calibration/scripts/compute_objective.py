"""
compute_objective.py
====================
Computes a scalar objective (loss) value by comparing simulation metrics
from simulation_metrics.csv against the experimental DataFrame.

Objective function definition
------------------------------
For each active target t and each time point τ:

    residual(t, τ) = (sim(t,τ) − exp(t,τ)) / normalizer(t, τ)

    where normalizer = max(|exp(t,τ)|, 1e-6)

Weighted RMSE across all (target, time_point) pairs:

    L = sqrt[ Σ_{t,τ} w_t * w_τ * residual²(t,τ)  /  Σ_{t,τ} w_t * w_τ ]

A penalty term is added when constraints are violated:
    necrosis_threshold >= quiescence_threshold  → large penalty
    quiescence_threshold >= proliferation_threshold → large penalty

Usage (standalone)
------------------
    python scripts/compute_objective.py \
        --sim_metrics results/optuna_runs/run_0001/simulation_metrics.csv \
        --config      configs/calibration_config.yaml \
        --condition   ISO10
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import yaml

# Ensure scripts/ is importable
_SCRIPTS_DIR = Path(__file__).parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from load_experimental_data import (
    load_config,
    load_experimental_data,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PENALTY_VALUE  = 1_000.0   # large loss for constraint violations
FALLBACK_LOSS  = PENALTY_VALUE  # returned on simulation failure


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_objective(
    sim_metrics_df: pd.DataFrame,
    exp_df: pd.DataFrame,
    config: dict,
    condition: str,
    params_dict: Optional[dict[str, Any]] = None,
) -> float:
    """
    Compute weighted RMSE objective between simulation and experimental data.

    Parameters
    ----------
    sim_metrics_df : DataFrame from simulation_metrics.csv
    exp_df         : DataFrame from load_experimental_data()
    config         : dict from calibration_config.yaml
    condition      : 'ISO10' | 'DeltaC'
    params_dict    : calibrated parameters (used for constraint penalties)

    Returns
    -------
    Scalar loss ≥ 0.  Lower is better.  Returns FALLBACK_LOSS on failure.
    """
    # ---- Constraint check -------------------------------------------------
    if params_dict:
        penalty = _check_constraints(params_dict, config)
        if penalty > 0.0:
            return PENALTY_VALUE + penalty

    # ---- Filter to condition ----------------------------------------------
    sim  = sim_metrics_df[sim_metrics_df["condition"] == condition].copy()
    exp  = exp_df[exp_df["condition"] == condition].copy()

    if sim.empty or exp.empty:
        return FALLBACK_LOSS

    # ---- Configuration ----------------------------------------------------
    targets  = config.get("calibration_targets",
                           ["shell_A_over_A0", "core_A_over_A0", "viable_rim_um"])
    t_weights = config.get("target_weights", {})
    tp_weights = config.get("time_weights", {})
    tps       = config.get("experimental_time_points_h", [0, 12, 24, 36, 48])

    # Mapping: exp column ↔ sim column (some names differ)
    col_map = {
        "shell_area_um2":  ("shell_area_um2",   "shell_area_um2"),
        "core_area_um2":   ("core_area_um2",    "core_area_um2"),
        "shell_A_over_A0": ("shell_A_over_A0",  "shell_A_over_A0"),
        "core_A_over_A0":  ("core_A_over_A0",   "core_A_over_A0"),
        "viable_rim_um":   ("viable_rim_um",     "viable_rim_um"),
    }

    residuals = []
    weights   = []
    hard_penalty_num = 0.0
    hard_penalty_den = 0.0

    use_sem_norm = bool(config.get("use_sem_normalization", True))
    sem_floor_fraction = float(config.get("sem_floor_fraction", 0.05))
    late_cfg = config.get("late_time_hard_constraints", {})
    late_enabled = bool(late_cfg.get("enabled", True))
    late_tps = set(float(x) for x in late_cfg.get("time_points_h", [24, 36, 48]))
    late_thresholds = late_cfg.get("thresholds", {})
    late_penalty_scale = float(late_cfg.get("penalty_scale", 4.0))

    sem_col_map = {
        "shell_area_um2": "shell_SEM",
        "core_area_um2": "core_SEM",
        "shell_A_over_A0": "shell_A_over_A0_SEM",
        "core_A_over_A0": "core_A_over_A0_SEM",
        "viable_rim_um": "viable_rim_sem_um",
    }

    for tp in tps:
        exp_row = exp[np.isclose(exp["time_h"], tp, atol=0.5)]
        sim_row = sim[np.isclose(sim["time_h"], tp, atol=0.5)]

        if exp_row.empty or sim_row.empty:
            continue

        exp_row = exp_row.iloc[0]
        sim_row = sim_row.iloc[0]

        # Time-point weight
        w_tp = float(tp_weights.get(tp, tp_weights.get(str(int(tp)), 1.0)))

        for target in targets:
            if target not in col_map:
                continue
            exp_col, sim_col = col_map[target]
            if exp_col not in exp_row.index or sim_col not in sim_row.index:
                continue

            exp_val = float(exp_row[exp_col])
            sim_val = float(sim_row[sim_col])

            if math.isnan(exp_val) or math.isnan(sim_val):
                continue

            # Target weight
            w_t = float(t_weights.get(target, 1.0))

            normalizer = max(abs(exp_val), 1.0e-6)
            if use_sem_norm:
                sem_col = sem_col_map.get(target)
                sem_val = float(exp_row.get(sem_col, float("nan"))) if sem_col else float("nan")
                if sem_val == sem_val and sem_val > 0:
                    sem_floor = sem_floor_fraction * max(abs(exp_val), 1.0e-6)
                    normalizer = max(sem_val, sem_floor, 1.0e-6)
            r = (sim_val - exp_val) / normalizer
            residuals.append(r)
            weights.append(w_t * w_tp)

            if late_enabled and float(tp) in late_tps:
                thr = float(late_thresholds.get(target, float("inf")))
                abs_rel = abs((sim_val - exp_val) / max(abs(exp_val), 1.0e-6))
                if abs_rel > thr:
                    hard_penalty_num += (w_t * w_tp) * ((abs_rel - thr) ** 2)
                    hard_penalty_den += (w_t * w_tp)

    if not residuals:
        return FALLBACK_LOSS

    residuals = np.array(residuals)
    weights   = np.array(weights)
    w_sum     = weights.sum()
    if w_sum <= 0:
        return FALLBACK_LOSS

    wmse  = float(np.dot(weights, residuals ** 2) / w_sum)
    wrmse = math.sqrt(wmse)
    if hard_penalty_den > 0:
        wrmse += late_penalty_scale * math.sqrt(hard_penalty_num / hard_penalty_den)
    return wrmse


def compute_objective_from_run(
    run_dir: str | Path,
    exp_df: pd.DataFrame,
    config: dict,
    condition: str,
    time_points_h: Optional[list[float]] = None,
    params_dict: Optional[dict[str, Any]] = None,
) -> float:
    """
    Convenience wrapper: load simulation_metrics.csv from run_dir and
    compute the objective.
    """
    from export_simulation_stats import compute_metrics_for_run

    run_dir = Path(run_dir)
    if time_points_h is None:
        time_points_h = config.get("experimental_time_points_h", [0, 12, 24, 36, 48])

    # --- Derive seed from metadata if available ---
    seed = 0
    meta_path = run_dir / "metadata.json"
    if meta_path.exists():
        import json
        with open(meta_path) as fh:
            meta = json.load(fh)
        seed = meta.get("seed", 0)

    try:
        sim_df = compute_metrics_for_run(
            run_dir=run_dir,
            condition=condition,
            seed=seed,
            time_points_h=time_points_h,
        )
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return FALLBACK_LOSS

    return compute_objective(
        sim_metrics_df=sim_df,
        exp_df=exp_df,
        config=config,
        condition=condition,
        params_dict=params_dict,
    )


# ---------------------------------------------------------------------------
# Constraint penalties
# ---------------------------------------------------------------------------

def _check_constraints(params_dict: dict, config: dict) -> float:
    """
    Returns 0 if all constraints satisfied, else a positive penalty.
    Constraints:
        necrosis_threshold < quiescence_threshold < proliferation_threshold
    """
    nec  = params_dict.get("necrosis_threshold")
    qui  = params_dict.get("quiescence_threshold")
    prol = params_dict.get("proliferation_threshold")

    if nec is None or qui is None or prol is None:
        return 0.0

    penalty = 0.0
    if nec >= qui:
        penalty += (nec - qui + 0.01) * 100.0
    if qui >= prol:
        penalty += (qui - prol + 0.01) * 100.0
    return penalty


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute calibration objective from simulation metrics."
    )
    parser.add_argument(
        "--sim_metrics", required=True,
        help="Path to simulation_metrics.csv"
    )
    parser.add_argument(
        "--config", default="configs/calibration_config.yaml",
        help="Path to calibration_config.yaml"
    )
    parser.add_argument("--condition", default="ISO10")
    args = parser.parse_args()

    config_path = Path(args.config)
    config      = load_config(config_path)
    excel_path  = config_path.parent.parent / config["excel_file"]
    exp_df      = load_experimental_data(excel_path, config, args.condition)

    sim_df = pd.read_csv(args.sim_metrics)
    loss   = compute_objective(sim_df, exp_df, config, args.condition)

    print(f"Objective (weighted RMSE): {loss:.6f}")


if __name__ == "__main__":
    main()
