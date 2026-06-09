"""Parameter importance and parallel-coordinates plots from Optuna studies."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import optuna


def plot_parameter_importance(
    study: optuna.Study,
    out_path: str | Path,
    *,
    title: str = "Parameter importance",
) -> bool:
    try:
        importances = optuna.importance.get_param_importances(study)
    except Exception:
        return False
    if not importances:
        return False

    names = list(importances.keys())
    values = [importances[n] for n in names]
    fig, ax = plt.subplots(figsize=(max(8, 0.5 * len(names)), 5))
    y_pos = range(len(names))
    ax.barh(list(y_pos), values, color="#4472C4")
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(names)
    ax.set_xlabel("Importance")
    ax.set_title(title)
    ax.invert_yaxis()
    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=220)
    plt.close(fig)
    return True


def plot_parallel_coordinates(
    study: optuna.Study,
    out_path: str | Path,
    *,
    title: str = "Parallel coordinates",
    max_trials: int = 50,
) -> bool:
    try:
        from optuna.visualization.matplotlib import plot_parallel_coordinate
    except Exception:
        return False
    completed = [t for t in study.trials if t.value is not None]
    if len(completed) < 3:
        return False
    fig = plot_parallel_coordinate(study)
    if fig is None:
        return False
    target = fig.figure if hasattr(fig, "figure") else fig
    if hasattr(target, "suptitle"):
        target.suptitle(title)
    elif hasattr(fig, "set_title"):
        fig.set_title(title)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    save_target = target if hasattr(target, "savefig") else fig
    save_target.savefig(out_path, dpi=220)
    plt.close(target if hasattr(target, "clf") else fig)
    return True
