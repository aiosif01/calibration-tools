"""ANN training and calibration reporting figures."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_training_loss(history_path: str | Path, out_path: str | Path, *, title: str = "Training loss") -> None:
    df = pd.read_csv(history_path)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(df["epoch"], df["train_loss"], label="Train")
    if "val_loss" in df.columns:
        ax.plot(df["epoch"], df["val_loss"], label="Validation")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Weighted MSE")
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def plot_validation_predictions(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    out_path: str | Path,
    *,
    title: str = "Validation predictions",
) -> None:
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(y_true.ravel(), y_pred.ravel(), alpha=0.4, s=12)
    lo = float(min(y_true.min(), y_pred.min()))
    hi = float(max(y_true.max(), y_pred.max()))
    ax.plot([lo, hi], [lo, hi], "--", color="gray")
    ax.set_xlabel("ABM target")
    ax.set_ylabel("ANN prediction")
    ax.set_title(title)
    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def plot_inverse_fit_curve(
    out_path: str | Path,
    *,
    time_h: Sequence[float],
    y_target: Sequence[float],
    y_ann: Sequence[float],
    y_abm: Sequence[float] | None = None,
    sigma: Sequence[float] | None = None,
    title: str = "Inverse calibration fit",
) -> None:
    t = np.asarray(time_h, dtype=float)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(t, y_target, "o-", label="Experiment", linewidth=2)
    ax.plot(t, y_ann, "s--", label="ANN prediction", linewidth=2)
    if y_abm is not None:
        ax.plot(t, y_abm, "d-.", label="ABM validation", linewidth=2)
    if sigma is not None:
        sig = np.asarray(sigma, dtype=float)
        ax.fill_between(t, np.asarray(y_target) - sig, np.asarray(y_target) + sig, alpha=0.15)
    ax.set_xlabel("Time [h]")
    ax.set_ylabel("Normalized viability")
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def plot_abm_validation_band(
    out_path: str | Path,
    *,
    time_h: Sequence[float],
    y_target: Sequence[float],
    replicate_curves: np.ndarray,
    title: str = "ABM validation band",
) -> None:
    t = np.asarray(time_h, dtype=float)
    mean = replicate_curves.mean(axis=0)
    std = replicate_curves.std(axis=0)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(t, y_target, "o-", label="Experiment", linewidth=2)
    ax.plot(t, mean, "s--", label="ABM mean", linewidth=2)
    ax.fill_between(t, mean - std, mean + std, alpha=0.2, label="±1 std")
    ax.set_xlabel("Time [h]")
    ax.set_ylabel("Normalized viability")
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=220)
    plt.close(fig)
