from __future__ import annotations

from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROBABILITY_COLORS = {
    "Apoptosis": "#4472C4",
    "Growth": "#ED7D31",
    "Division": "#FFC000",
}
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
        ax.bar(offsets, values, width, label=name, color=color, edgecolor="black", linewidth=0.6)
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

    apoptosis = [float(fitted_values[0])]
    growth = [float(fitted_values[1])]
    division = [float(fitted_values[2])]
    apoptosis_err = [float(parameter_sigmas[0])] if parameter_sigmas else None
    growth_err = [float(parameter_sigmas[1])] if parameter_sigmas else None
    division_err = [float(parameter_sigmas[2])] if parameter_sigmas else None

    plot_probability_bars(
        out_dir / f"{prefix}_03_probability_bars.png",
        exposure_labels=[exposure_label],
        apoptosis=apoptosis,
        growth=growth,
        division=division,
        apoptosis_err=apoptosis_err,
        growth_err=growth_err,
        division_err=division_err,
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
