from __future__ import annotations

from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .calibration_params import parameter_plot_color, parameter_plot_label

PROBABILITY_COLORS = {
    "Apoptosis": "#4472C4",
    "Growth": "#ED7D31",
    "Division": "#FFC000",
}


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
PREFERRED_EXPOSURE_ORDER = ["Control", "Treat:30s", "Treat:2min", "Treat:4min", "Treat:5min"]


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


def plot_probability_bars(
    out_path: str | Path,
    *,
    exposure_labels: Sequence[str],
    apoptosis: Sequence[float],
    growth: Sequence[float],
    division: Sequence[float],
    apoptosis_err: Sequence[float] | None = None,
    growth_err: Sequence[float] | None = None,
    division_err: Sequence[float] | None = None,
    title: str,
    y_max: float | None = None,
) -> None:
    out_path = Path(out_path)
    labels = list(exposure_labels)
    x = np.arange(len(labels))
    width = 0.25
    metrics = [
        ("Apoptosis", np.asarray(apoptosis, dtype=float), apoptosis_err),
        ("Growth", np.asarray(growth, dtype=float), growth_err),
        ("Division", np.asarray(division, dtype=float), division_err),
    ]

    fig, ax = plt.subplots(figsize=(10, 5.5))
    for j, (name, values, errs) in enumerate(metrics):
        offsets = x + (j - 1) * width
        color = PROBABILITY_COLORS[name]
        legend_label = {
            "Apoptosis": "Apoptosis probability",
            "Growth": "Growth probability",
            "Division": "Division probability",
        }.get(name, name)
        ax.bar(offsets, values, width, label=legend_label, color=color, edgecolor="black", linewidth=0.6)
        if errs is not None:
            yerr = np.asarray(errs, dtype=float)
            yerr = np.nan_to_num(yerr, nan=0.0, posinf=0.0, neginf=0.0)
            ax.errorbar(
                offsets,
                values,
                yerr=yerr,
                fmt="none",
                ecolor="black",
                elinewidth=1.2,
                capsize=4,
                capthick=1.2,
            )

    ax.set_ylabel("Probability")
    ax.set_xlabel("Experiment Case")
    ax.set_title("Calibrated probabilities")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    if y_max is not None:
        ax.set_ylim(0, y_max)
    else:
        ymax = max(
            float(np.max(apoptosis)),
            float(np.max(growth)),
            float(np.max(division)),
            0.05,
        )
        ax.set_ylim(0, min(1.0, ymax * 1.25))
    ax.legend()
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=220)
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

    # Legacy 3-probability bar chart when exactly apoptosis / growth / division probs.
    if (
        len(parameter_keys) == 3
        and all("probability" in k for k in parameter_keys)
        and len(fitted_values) == 3
    ):
        plot_probability_bars(
            out_dir / f"{prefix}_03_probability_bars.png",
            exposure_labels=[exposure_label],
            apoptosis=[float(fitted_values[0])],
            growth=[float(fitted_values[1])],
            division=[float(fitted_values[2])],
            apoptosis_err=[float(parameter_sigmas[0])] if parameter_sigmas else None,
            growth_err=[float(parameter_sigmas[1])] if parameter_sigmas else None,
            division_err=[float(parameter_sigmas[2])] if parameter_sigmas else None,
            title=title,
        )
    else:
        plot_fitted_parameters_bars(
            out_dir / f"{prefix}_03_fitted_parameters.png",
            exposure_label=exposure_label,
            parameter_keys=parameter_keys,
            fitted_values=fitted_values,
            parameter_sigmas=parameter_sigmas,
            title=title,
        )


def make_summary_bar_plots(summary_df: pd.DataFrame, out_dir: str | Path, *, title_prefix: str = "") -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics = [
        ("apoptosis_probability", "apoptosis_sigma", "apoptosis"),
        ("growth_probability", "growth_sigma", "growth"),
        ("division_probability", "division_sigma", "division"),
    ]

    for cell_line, sub in summary_df.groupby("cell_line"):
        sub = sub.copy()
        order = [x for x in PREFERRED_EXPOSURE_ORDER if x in set(sub["exposure_label"])]
        order += [x for x in sub["exposure_label"].tolist() if x not in order]
        sub["_order"] = sub["exposure_label"].apply(lambda x: order.index(x) if x in order else 999)
        sub = sub.sort_values("_order")

        plot_probability_bars(
            out_dir / f"{cell_line}_probability_bar_chart.png",
            exposure_labels=sub["exposure_label"].tolist(),
            apoptosis=sub["apoptosis_probability"].to_numpy(dtype=float),
            growth=sub["growth_probability"].to_numpy(dtype=float),
            division=sub["division_probability"].to_numpy(dtype=float),
            apoptosis_err=sub["apoptosis_sigma"].replace([np.inf, -np.inf], np.nan).fillna(0).to_numpy(dtype=float),
            growth_err=sub["growth_sigma"].replace([np.inf, -np.inf], np.nan).fillna(0).to_numpy(dtype=float),
            division_err=sub["division_sigma"].replace([np.inf, -np.inf], np.nan).fillna(0).to_numpy(dtype=float),
            title=f"{title_prefix}{cell_line}: calibrated probabilities".strip(),
        )
