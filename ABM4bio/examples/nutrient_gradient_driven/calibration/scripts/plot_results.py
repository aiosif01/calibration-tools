"""
plot_results.py
===============
Generates calibration diagnostic plots:

  1. Experimental vs simulation time-series  (per condition, per target)
  2. Optuna convergence  (loss vs trial number)
  3. Parameter importance  (Optuna FAnova or manual)
  4. Calibrated parameter table  (printed + saved as CSV)

Usage
-----
    # Plot results for the best run of a given condition:
    python scripts/plot_results.py \
        --run results/best_runs/<run_id> \
        --config configs/calibration_config.yaml \
        --condition ISO10

    # Plot Optuna convergence and parameter importance from a study DB:
    python scripts/plot_results.py \
        --config  configs/calibration_config.yaml \
        --storage sqlite:///results/optuna_runs/study.db \
        --condition ISO10

    # Minimal: just the exp-vs-sim comparison using a simulation_metrics.csv:
    python scripts/plot_results.py \
        --sim_metrics results/best_runs/<run_id>/simulation_metrics.csv \
        --config configs/calibration_config.yaml \
        --condition ISO10
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

try:
    import matplotlib
    matplotlib.use("Agg")          # non-interactive backend for servers
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    _HAS_MPL = True
except ImportError:
    _HAS_MPL = False
    print("WARNING: matplotlib not installed – plot output disabled.")

_SCRIPTS_DIR = Path(__file__).parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from load_experimental_data import load_config, load_experimental_data

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def plot_exp_vs_sim(
    sim_df: pd.DataFrame,
    exp_df: pd.DataFrame,
    config: dict,
    condition: str,
    output_path: Optional[str | Path] = None,
) -> None:
    """
    Plot experimental vs simulation time-series for the five calibration targets.
    Experimental error bars use shell_SEM / core_SEM.
    """
    if not _HAS_MPL:
        return

    targets_meta = [
        ("shell_area_um2",  "Shell area (µm²)",           "shell_SEM"),
        ("core_area_um2",   "Core area (µm²)",            "core_SEM"),
        # SEM columns in the workbook are in area units; do not use them for A/A0.
        ("shell_A_over_A0", "Shell A/A₀",                  None),
        ("core_A_over_A0",  "Core A/A₀",                   None),
        ("viable_rim_um",   "Viable rim thickness (µm)",    None),
    ]

    exp_c = exp_df[exp_df["condition"] == condition].sort_values("time_h")
    sim_c = sim_df[sim_df["condition"] == condition].sort_values("time_h")

    fig, axes = plt.subplots(1, len(targets_meta), figsize=(20, 4))
    fig.suptitle(
        f"Exp vs Simulation — {condition}", fontsize=13, fontweight="bold"
    )

    for ax, (col, ylabel, sem_col) in zip(axes, targets_meta):
        if col not in exp_c.columns:
            ax.set_visible(False)
            continue

        # Experimental
        e_t   = exp_c["time_h"].values
        e_val = exp_c[col].values
        e_sem = exp_c[sem_col].values if (sem_col and sem_col in exp_c.columns) else None

        ax.plot(e_t, e_val, "o-", color="steelblue", linewidth=2, markersize=6,
                label="Experiment", zorder=3)
        if e_sem is not None:
            ax.fill_between(
                e_t, e_val - e_sem, e_val + e_sem,
                alpha=0.25, color="steelblue", label="Exp ± SEM"
            )

        # Simulation
        if col in sim_c.columns:
            s_t   = sim_c["time_h"].values
            s_val = sim_c[col].values
            ax.plot(s_t, s_val, "s--", color="tomato", linewidth=2, markersize=6,
                    label="Simulation", zorder=3)

        ax.set_xlabel("Time (h)")
        ax.set_ylabel(ylabel)
        ax.set_title(ylabel, fontsize=10)
        ax.legend(fontsize=8)
        ax.grid(True, linestyle="--", alpha=0.4)
        ax.set_xticks([0, 12, 24, 36, 48])

    plt.tight_layout()
    _save_or_show(fig, output_path)


def plot_optuna_convergence(
    study,
    output_path: Optional[str | Path] = None,
) -> None:
    """Plot Optuna trial values and running best."""
    if not _HAS_MPL:
        return

    trials = [t for t in study.trials
              if t.value is not None and t.state.name == "COMPLETE"]
    if not trials:
        print("No completed trials found.")
        return

    nums   = [t.number for t in trials]
    losses = [t.value  for t in trials]
    best   = [min(losses[:i+1]) for i in range(len(losses))]

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.scatter(nums, losses, s=15, alpha=0.5, color="slategrey", label="Trial loss")
    ax.plot(nums, best, color="crimson", linewidth=2, label="Best so far")
    ax.set_xlabel("Trial number")
    ax.set_ylabel("Objective (weighted RMSE)")
    ax.set_title("Optuna convergence")
    ax.legend()
    ax.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()
    _save_or_show(fig, output_path)


def plot_parameter_importance(
    study,
    output_path: Optional[str | Path] = None,
) -> None:
    """Bar chart of Optuna parameter importances (FAnova)."""
    if not _HAS_MPL:
        return

    try:
        import optuna
        importances = optuna.importance.get_param_importances(study)
    except Exception as exc:
        print(f"Could not compute importances: {exc}")
        return

    names  = list(importances.keys())
    values = [importances[k] for k in names]

    fig, ax = plt.subplots(figsize=(7, max(3, len(names) * 0.55)))
    ax.barh(names, values, color="steelblue", edgecolor="white")
    ax.set_xlabel("Relative importance")
    ax.set_title("Parameter importance (FAnova)")
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    plt.tight_layout()
    _save_or_show(fig, output_path)


def print_calibrated_params(
    study_or_params: dict | "optuna.Study",
    output_csv: Optional[str | Path] = None,
) -> pd.DataFrame:
    """Print and optionally save the best calibrated parameter table."""
    if hasattr(study_or_params, "best_trial"):
        best = study_or_params.best_trial
        params = best.params
        meta   = {"trial_number": best.number, "loss": best.value}
    else:
        params = study_or_params
        meta   = {}

    rows = []
    for k, v in params.items():
        rows.append({"parameter": k, "best_value": v})
    df = pd.DataFrame(rows)

    print("\n=== Calibrated Parameters ===")
    if meta:
        print(f"  Trial #{meta.get('trial_number','?')}  "
              f"Loss = {meta.get('loss', float('nan')):.5f}")
    print(df.to_string(index=False))

    if output_csv:
        df.to_csv(output_csv, index=False)
        print(f"\nSaved to {output_csv}")
    return df


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _save_or_show(fig, path: Optional[str | Path]) -> None:
    if path:
        fig.savefig(str(path), dpi=150, bbox_inches="tight")
        print(f"Saved: {path}")
    else:
        plt.show()
    plt.close(fig)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate calibration diagnostic plots."
    )
    parser.add_argument(
        "--config", default="configs/calibration_config.yaml",
        help="Path to calibration_config.yaml"
    )
    parser.add_argument("--condition", default="ISO10")
    parser.add_argument(
        "--run", default=None,
        help="Path to a run directory containing simulation_metrics.csv"
    )
    parser.add_argument(
        "--sim_metrics", default=None,
        help="Direct path to simulation_metrics.csv (overrides --run)"
    )
    parser.add_argument(
        "--storage", default=None,
        help="Optuna storage URL for convergence / importance plots"
    )
    parser.add_argument(
        "--output_dir", default=None,
        help="Directory to save plots (default: results/plots)"
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    config      = load_config(config_path)
    excel_path  = config_path.parent.parent / config["excel_file"]
    exp_df      = load_experimental_data(excel_path, config, args.condition)

    plots_dir = (
        Path(args.output_dir)
        if args.output_dir
        else config_path.parent.parent / config.get("plots_dir", "results/plots")
    )
    plots_dir.mkdir(parents=True, exist_ok=True)

    # --- Exp vs Sim ---
    sim_metrics_path = None
    if args.sim_metrics:
        sim_metrics_path = Path(args.sim_metrics)
    elif args.run:
        sim_metrics_path = Path(args.run) / "simulation_metrics.csv"

    if sim_metrics_path and sim_metrics_path.exists():
        sim_df = pd.read_csv(sim_metrics_path)
        out    = plots_dir / f"exp_vs_sim_{args.condition}.png"
        plot_exp_vs_sim(sim_df, exp_df, config, args.condition, output_path=out)
    else:
        print("No simulation_metrics.csv found; skipping exp vs sim plot.")

    # --- Optuna convergence + importance ---
    if args.storage:
        try:
            import optuna as _optuna
            _optuna.logging.set_verbosity(_optuna.logging.WARNING)
            study = _optuna.load_study(
                study_name=config.get("study_name", "NIH3T3_ctrl_calib"),
                storage=args.storage,
            )
            plot_optuna_convergence(
                study,
                output_path=plots_dir / f"convergence_{args.condition}.png",
            )
            plot_parameter_importance(
                study,
                output_path=plots_dir / f"param_importance_{args.condition}.png",
            )
            print_calibrated_params(
                study,
                output_csv=plots_dir / f"best_params_{args.condition}.csv",
            )
        except Exception as exc:
            print(f"Could not load Optuna study: {exc}")

    # --- Print from best_params JSON (if study not available) ---
    elif args.run:
        bp = Path(args.run).parent / f"best_params_{args.condition}.json"
        if bp.exists():
            with open(bp) as fh:
                data = json.load(fh)
            print_calibrated_params(data.get("params", {}))


if __name__ == "__main__":
    main()
