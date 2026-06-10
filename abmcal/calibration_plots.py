from __future__ import annotations

from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np

from .calibration_params import parameter_plot_color, parameter_plot_label


def plot_fitted_parameters_bars(
    out_path: str | Path,
    *,
    exposure_label: str,
    parameter_keys: Sequence[str],
    fitted_values: Sequence[float],
    parameter_sigmas: Sequence[float] | None = None,
    title: str,
) -> None:
    """Bar chart of all fitted parameters with descriptive legend labels."""
    out_path = Path(out_path)
    keys = list(parameter_keys)
    values = np.asarray(fitted_values, dtype=float)
    labels = [parameter_plot_label(k) for k in keys]
    colors = [parameter_plot_color(k, i) for i, k in enumerate(keys)]
    errs = None
    if parameter_sigmas is not None:
        errs = np.nan_to_num(np.asarray(parameter_sigmas, dtype=float), nan=0.0)
        # Ill-conditioned Jacobians inflate sigma_a; cap display at 35% of each bar for readability.
        rel_cap = np.maximum(np.abs(values) * 0.35, 1.0e-6)
        errs = np.minimum(errs, rel_cap)

    fig, ax = plt.subplots(figsize=(max(8, 1.2 * len(keys)), 5.5))
    x = np.arange(len(keys))
    ax.bar(x, values, color=colors, edgecolor="black", linewidth=0.6)
    if errs is not None and np.any(errs > 0):
        ax.errorbar(x, values, yerr=errs, fmt="none", ecolor="black", elinewidth=1.2, capsize=4)
    ax.set_ylabel("Parameter value")
    ax.set_xlabel(f"Fitted parameters — {exposure_label}")
    ax.set_title("Calibrated parameters")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ymax = float(np.max(values)) if len(values) else 1.0
    if ymax <= 1.0:
        ax.set_ylim(0, min(1.0, max(0.05, ymax * 1.25)))
    else:
        ax.set_ylim(0, ymax * 1.15)
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def plot_n_cells_vs_time(
    out_path: str | Path,
    *,
    time_h: Sequence[float],
    n_cells: Sequence[float],
    title: str,
) -> None:
    out_path = Path(out_path)
    t = np.asarray(time_h, dtype=float)
    y = np.asarray(n_cells, dtype=float)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(t, y, "o-", color="#4472C4", linewidth=2, markersize=8, label="Simulation")
    ax.set_xlabel("Time post-treatment [h]")
    ax.set_ylabel("N_cells")
    ax.set_title("Number of cells vs time")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def plot_exp_vs_sim(
    out_path: str | Path,
    *,
    time_h: Sequence[float],
    y_target: Sequence[float],
    y_sim: Sequence[float],
    sigma_target: Sequence[float] | None = None,
    title: str,
    ylabel: str = "Normalized output",
) -> None:
    out_path = Path(out_path)
    t = np.asarray(time_h, dtype=float)
    y_target = np.asarray(y_target, dtype=float)
    y_sim = np.asarray(y_sim, dtype=float)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(t, y_sim, "o-", color="#4472C4", linewidth=2, markersize=8, label="Simulation")
    ax.plot(t, y_target, "s--", color="#ED7D31", linewidth=2, markersize=8, label="Experimental target")
    if sigma_target is not None:
        sigma = np.asarray(sigma_target, dtype=float)
        ax.fill_between(
            t,
            y_target - sigma,
            y_target + sigma,
            color="#9DC3E6",
            alpha=0.35,
            label="Target +/- 1 SD",
        )
    ax.set_xlabel("Time post-treatment [h]")
    ax.set_ylabel(ylabel)
    ax.set_title("Experimental vs simulation")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def save_calibration_result_plots(
    out_dir: str | Path,
    *,
    title: str,
    exposure_label: str,
    time_h: Sequence[float],
    y_target: Sequence[float],
    y_sim_raw: Sequence[float],
    y_sim_comparable: Sequence[float],
    sigma_target: Sequence[float] | None,
    parameter_keys: Sequence[str],
    fitted_values: Sequence[float],
    parameter_sigmas: Sequence[float] | None = None,
    prefix: str = "calibration",
) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    plot_n_cells_vs_time(
        out_dir / f"{prefix}_01_N_cells_vs_time.png",
        time_h=time_h,
        n_cells=y_sim_raw,
        title=title,
    )
    plot_exp_vs_sim(
        out_dir / f"{prefix}_02_exp_vs_sim.png",
        time_h=time_h,
        y_target=y_target,
        y_sim=y_sim_comparable,
        sigma_target=sigma_target,
        title=title,
    )

    plot_fitted_parameters_bars(
        out_dir / f"{prefix}_03_fitted_parameters.png",
        exposure_label=exposure_label,
        parameter_keys=parameter_keys,
        fitted_values=fitted_values,
        parameter_sigmas=parameter_sigmas,
        title=title,
    )
