"""Shared objective functions for comparing ABM4bio output to experimental targets."""
from __future__ import annotations

from typing import Sequence

import numpy as np


def prepare_sigma(sigma: Sequence[float] | float, y_data: np.ndarray) -> np.ndarray:
    if np.isscalar(sigma):
        return np.ones_like(y_data, dtype=float) * float(sigma)
    sigma_arr = np.asarray(sigma, dtype=float)
    return np.where(np.isfinite(sigma_arr) & (sigma_arr > 0), sigma_arr, 0.45)


def normalize_simulation(y_sim: np.ndarray, *, normalize_sim_to_t0: bool) -> np.ndarray:
    y_sim = np.asarray(y_sim, dtype=float)
    if not normalize_sim_to_t0:
        return y_sim
    if y_sim[0] == 0:
        raise ZeroDivisionError("Simulation t0 output is zero; cannot normalize to t0.")
    return y_sim / y_sim[0]


def weighted_curve_error(
    y_sim: np.ndarray,
    y_data: np.ndarray,
    sigma: np.ndarray,
    *,
    log_space: bool = False,
    exclude_t0: bool = True,
    time_weights: Sequence[float] | None = None,
) -> float:
    y_data = np.asarray(y_data, dtype=float)
    y_sim = np.asarray(y_sim, dtype=float)
    sigma_arr = prepare_sigma(sigma, y_data)
    weights = np.asarray(time_weights, dtype=float) if time_weights is not None else None

    if log_space:
        eps = 1.0
        if exclude_t0 and len(y_data) > 1:
            y_d = np.maximum(y_data[1:], eps)
            y_s = np.maximum(y_sim[1:], eps)
            sig = sigma_arr[1:]
            log_sigma = np.log1p(sig / y_d)
            log_sigma = np.where(log_sigma > 1.0e-9, log_sigma, 1.0)
            residuals = (np.log(y_s) - np.log(y_d)) / log_sigma
        else:
            y_d = np.maximum(y_data, eps)
            y_s = np.maximum(y_sim, eps)
            log_sigma = np.log1p(sigma_arr / y_d)
            log_sigma = np.where(log_sigma > 1.0e-9, log_sigma, 1.0)
            residuals = (np.log(y_s) - np.log(y_d)) / log_sigma
    elif exclude_t0 and len(y_data) > 1:
        residuals = (y_data[1:] - y_sim[1:]) / sigma_arr[1:]
    else:
        residuals = (y_data - y_sim) / sigma_arr

    if weights is not None:
        residuals = residuals * weights
    return float(np.sum(residuals ** 2))


def biological_penalty(y_data: np.ndarray, y_sim: np.ndarray) -> float:
    y_data = np.asarray(y_data, dtype=float)
    y_sim = np.asarray(y_sim, dtype=float)
    penalty = 0.0
    if len(y_sim) >= 2 and y_sim[1] < 0.6 * max(y_data[1], 1.0):
        penalty += 3.0 * (0.6 * y_data[1] - y_sim[1]) ** 2
    if len(y_sim) >= 3 and y_sim[2] < 0.65 * max(y_data[2], 1.0):
        penalty += 10.0 * (0.65 * y_data[2] - y_sim[2]) ** 2
    if len(y_sim) >= 3 and y_sim[-1] < 0.75 * max(y_data[-1], 1.0):
        penalty += 12.0 * (0.75 * y_data[-1] - y_sim[-1]) ** 2
    if len(y_sim) >= 2 and y_sim[-1] <= 0.05:
        penalty += 15.0 ** 2
    return float(penalty)


def compute_scalar_objective(
    y_data: np.ndarray,
    y_sim: np.ndarray,
    sigma: Sequence[float] | float,
    *,
    log_space: bool = False,
    include_penalty: bool = True,
) -> float:
    score = weighted_curve_error(y_sim, y_data, prepare_sigma(sigma, np.asarray(y_data)), log_space=log_space)
    if include_penalty:
        score += biological_penalty(y_data, y_sim)
    return score
