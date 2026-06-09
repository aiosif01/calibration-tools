"""Export Optuna study results, trial history, and summary figures."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
import optuna
import pandas as pd


@dataclass
class OptunaFitResult:
    x: list[float]
    cost: float
    weighted_sse: float
    success: bool
    message: str
    n_trials: int
    r_squared: float | None
    y_fit: list[float]
    residuals: list[float]
    study_name: str
    best_trial_number: int

    def save_json(self, path: str | Path) -> None:
        import json

        Path(path).write_text(json.dumps(asdict(self), indent=2))


def export_trial_history(study: optuna.Study, out_path: str | Path) -> pd.DataFrame:
    rows: list[dict] = []
    for trial in study.trials:
        row = {
            "number": trial.number,
            "state": str(trial.state),
            "value": trial.value,
            "datetime_start": trial.datetime_start,
            "datetime_complete": trial.datetime_complete,
        }
        row.update(trial.params)
        for key, val in trial.user_attrs.items():
            if key not in ("mean_curve", "replicate_scores", "params_dict"):
                row[f"attr_{key}"] = val
        rows.append(row)
    df = pd.DataFrame(rows)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return df


def export_failed_trials(study: optuna.Study, out_path: str | Path) -> pd.DataFrame:
    rows = []
    for trial in study.trials:
        if trial.state == optuna.trial.TrialState.COMPLETE:
            continue
        rows.append({
            "number": trial.number,
            "state": str(trial.state),
            "value": trial.value,
            "params": trial.params,
            "error": trial.user_attrs.get("error"),
        })
    df = pd.DataFrame(rows)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return df


def export_best_parameters(
    study: optuna.Study,
    parameter_keys: Sequence[str],
    out_path: str | Path,
) -> pd.DataFrame:
    best = study.best_trial
    values = [float(best.params.get(key, np.nan)) for key in parameter_keys]
    df = pd.DataFrame({"parameter_name": list(parameter_keys), "fitted_value": values})
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return df


def plot_optimization_history(study: optuna.Study, out_path: str | Path, *, title: str = "") -> None:
    values = [t.value for t in study.trials if t.value is not None]
    if not values:
        return
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(range(1, len(values) + 1), values, "o-", color="#4472C4", markersize=4)
    best_so_far = np.minimum.accumulate(values)
    ax.plot(range(1, len(best_so_far) + 1), best_so_far, "--", color="#ED7D31", linewidth=2, label="Best so far")
    ax.set_xlabel("Trial")
    ax.set_ylabel("Objective")
    ax.set_title(title or "Optimization history")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def plot_best_fit_curve(
    out_path: str | Path,
    *,
    time_h: Sequence[float],
    y_target: Sequence[float],
    y_sim: Sequence[float],
    sigma: Sequence[float] | None = None,
    title: str = "",
) -> None:
    t = np.asarray(time_h, dtype=float)
    y_t = np.asarray(y_target, dtype=float)
    y_s = np.asarray(y_sim, dtype=float)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(t, y_t, "o-", color="#4472C4", linewidth=2, markersize=8, label="Experiment")
    ax.plot(t, y_s, "s--", color="#ED7D31", linewidth=2, markersize=8, label="Best ABM fit")
    if sigma is not None:
        sig = np.asarray(sigma, dtype=float)
        ax.fill_between(t, y_t - sig, y_t + sig, color="#4472C4", alpha=0.15)
    ax.set_xlabel("Time post-treatment [h]")
    ax.set_ylabel("Normalized viability")
    ax.set_title(title or "Best fit curve")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def write_summary_report(
    out_path: str | Path,
    *,
    study: optuna.Study,
    cell_line: str,
    case_label: str,
    parameter_keys: Sequence[str],
    n_replicates: int,
) -> None:
    best = study.best_trial
    lines = [
        f"# Optuna calibration summary — {cell_line} / {case_label}",
        "",
        f"- Study: `{study.study_name}`",
        f"- Trials completed: {len([t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE])}",
        f"- Best trial: {best.number}",
        f"- Best objective: {best.value:.6g}",
        f"- Replicates per trial: {n_replicates}",
        "",
        "## Best parameters",
        "",
    ]
    for key in parameter_keys:
        val = best.params.get(key)
        lines.append(f"- `{key}`: {val}")
    lines.append("")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text("\n".join(lines))
